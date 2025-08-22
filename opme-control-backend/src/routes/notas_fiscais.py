from flask import Blueprint, request, jsonify
from werkzeug.utils import secure_filename
import os
import tempfile
from src.services.saldo_service import SaldoService
from src.services.maino_api import MainoAPIService
from src.models.nota_fiscal import NotaFiscal, db
import logging

logger = logging.getLogger(__name__)

notas_fiscais_bp = Blueprint('notas_fiscais', __name__)

@notas_fiscais_bp.route('/upload-xml', methods=['POST'])
def upload_xml():
    """Upload manual de XML de nota fiscal"""
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'Nenhum arquivo enviado'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'Nenhum arquivo selecionado'}), 400
        
        if not file.filename.lower().endswith('.xml'):
            return jsonify({'error': 'Apenas arquivos XML são aceitos'}), 400
        
        # Lê o conteúdo do arquivo
        xml_content = file.read().decode('utf-8')
        
        # Processa a nota fiscal
        resultado = SaldoService.processar_nota_fiscal(xml_content)
        
        if resultado['success']:
            return jsonify({
                'success': True,
                'message': resultado['message'],
                'data': {
                    'nota_fiscal_id': resultado['nota_fiscal_id'],
                    'tipo_operacao': resultado['tipo_operacao'],
                    'itens_processados': resultado['itens_processados']
                }
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': resultado['error']
            }), 400
            
    except Exception as e:
        logger.error(f"Erro no upload de XML: {str(e)}")
        return jsonify({'error': 'Erro interno do servidor'}), 500

@notas_fiscais_bp.route('/sync-maino', methods=['POST'])
def sync_maino():
    """Sincroniza notas fiscais da API do Mainô"""
    try:
        data = request.get_json() or {}
        data_inicio = data.get('data_inicio')
        data_fim = data.get('data_fim')
        
        # Valida formato das datas (DD/MM/YYYY)
        if data_inicio and not _validar_formato_data(data_inicio):
            return jsonify({'error': 'Formato de data_inicio inválido. Use DD/MM/YYYY'}), 400
        
        if data_fim and not _validar_formato_data(data_fim):
            return jsonify({'error': 'Formato de data_fim inválido. Use DD/MM/YYYY'}), 400
        
        # Inicializa serviço da API
        maino_service = MainoAPIService()
        
        # Testa conexão
        if not maino_service.test_connection():
            return jsonify({'error': 'Falha na conexão com a API do Mainô'}), 500
        
        # Sincroniza notas fiscais
        notas = maino_service.sync_notas_fiscais(data_inicio, data_fim)
        
        # Processa cada nota fiscal
        resultados = []
        sucessos = 0
        erros = 0
        
        for nota in notas:
            xml_content = nota.get('xml_content')
            if xml_content:
                resultado = SaldoService.processar_nota_fiscal(xml_content)
                if resultado['success']:
                    sucessos += 1
                else:
                    erros += 1
                resultados.append({
                    'chave_acesso': nota.get('chave_acesso'),
                    'numero': nota.get('numero'),
                    'resultado': resultado
                })
        
        return jsonify({
            'success': True,
            'message': f'Sincronização concluída: {sucessos} sucessos, {erros} erros',
            'resumo': {
                'total_notas': len(notas),
                'sucessos': sucessos,
                'erros': erros
            },
            'detalhes': resultados
        }), 200
        
    except Exception as e:
        logger.error(f"Erro na sincronização: {str(e)}")
        return jsonify({'error': 'Erro interno do servidor'}), 500

@notas_fiscais_bp.route('/listar', methods=['GET'])
def listar_notas_fiscais():
    """Lista notas fiscais processadas"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 20, type=int), 100)
        tipo_operacao = request.args.get('tipo_operacao')
        cliente_cnpj = request.args.get('cliente_cnpj')
        
        query = NotaFiscal.query
        
        # Filtros
        if tipo_operacao:
            query = query.filter(NotaFiscal.tipo_operacao == tipo_operacao)
        
        if cliente_cnpj:
            cliente_cnpj = ''.join(filter(str.isdigit, cliente_cnpj))
            query = query.filter(NotaFiscal.destinatario_cnpj == cliente_cnpj)
        
        # Paginação
        notas = query.order_by(NotaFiscal.data_emissao.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )
        
        return jsonify({
            'success': True,
            'data': [nota.to_dict() for nota in notas.items],
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': notas.total,
                'pages': notas.pages,
                'has_next': notas.has_next,
                'has_prev': notas.has_prev
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Erro ao listar notas fiscais: {str(e)}")
        return jsonify({'error': 'Erro interno do servidor'}), 500

@notas_fiscais_bp.route('/<int:nota_id>', methods=['GET'])
def obter_nota_fiscal(nota_id):
    """Obtém detalhes de uma nota fiscal específica"""
    try:
        nota = NotaFiscal.query.get_or_404(nota_id)
        return jsonify({
            'success': True,
            'data': nota.to_dict()
        }), 200
        
    except Exception as e:
        logger.error(f"Erro ao obter nota fiscal: {str(e)}")
        return jsonify({'error': 'Erro interno do servidor'}), 500

@notas_fiscais_bp.route('/<int:nota_id>/xml', methods=['GET'])
def obter_xml_nota_fiscal(nota_id):
    """Obtém o XML original de uma nota fiscal"""
    try:
        nota = NotaFiscal.query.get_or_404(nota_id)
        
        if not nota.xml_content:
            return jsonify({'error': 'XML não disponível para esta nota fiscal'}), 404
        
        return jsonify({
            'success': True,
            'data': {
                'chave_acesso': nota.chave_acesso,
                'numero': nota.numero,
                'serie': nota.serie,
                'xml_content': nota.xml_content
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Erro ao obter XML: {str(e)}")
        return jsonify({'error': 'Erro interno do servidor'}), 500

@notas_fiscais_bp.route('/test-maino', methods=['GET'])
def test_maino_connection():
    """Testa conexão com a API do Mainô"""
    try:
        maino_service = MainoAPIService()
        
        if maino_service.test_connection():
            return jsonify({
                'success': True,
                'message': 'Conexão com API do Mainô estabelecida com sucesso'
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': 'Falha na conexão com a API do Mainô'
            }), 500
            
    except Exception as e:
        logger.error(f"Erro no teste de conexão: {str(e)}")
        return jsonify({'error': 'Erro interno do servidor'}), 500

@notas_fiscais_bp.route('/estatisticas', methods=['GET'])
def obter_estatisticas():
    """Obtém estatísticas das notas fiscais processadas"""
    try:
        # Estatísticas por tipo de operação
        stats_operacao = db.session.query(
            NotaFiscal.tipo_operacao,
            db.func.count(NotaFiscal.id).label('total')
        ).group_by(NotaFiscal.tipo_operacao).all()
        
        # Total de notas por mês (últimos 12 meses)
        stats_mensal = db.session.query(
            db.func.strftime('%Y-%m', NotaFiscal.data_emissao).label('mes'),
            db.func.count(NotaFiscal.id).label('total')
        ).filter(
            NotaFiscal.data_emissao >= db.func.date('now', '-12 months')
        ).group_by('mes').order_by('mes').all()
        
        # Clientes com mais movimentação
        stats_clientes = db.session.query(
            NotaFiscal.destinatario_nome,
            NotaFiscal.destinatario_cnpj,
            db.func.count(NotaFiscal.id).label('total_nfs')
        ).group_by(
            NotaFiscal.destinatario_cnpj,
            NotaFiscal.destinatario_nome
        ).order_by(db.desc('total_nfs')).limit(10).all()
        
        return jsonify({
            'success': True,
            'data': {
                'por_operacao': [
                    {'tipo': op, 'total': total} 
                    for op, total in stats_operacao
                ],
                'por_mes': [
                    {'mes': mes, 'total': total} 
                    for mes, total in stats_mensal
                ],
                'top_clientes': [
                    {
                        'nome': nome,
                        'cnpj': cnpj,
                        'total_nfs': total
                    }
                    for nome, cnpj, total in stats_clientes
                ]
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Erro ao obter estatísticas: {str(e)}")
        return jsonify({'error': 'Erro interno do servidor'}), 500

def _validar_formato_data(data_str: str) -> bool:
    """Valida se a data está no formato DD/MM/YYYY"""
    try:
        from datetime import datetime
        datetime.strptime(data_str, '%d/%m/%Y')
        return True
    except ValueError:
        return False

