from flask import Blueprint, request, jsonify
from src.services.saldo_service import SaldoService
from src.models.nota_fiscal import SaldoMaterial, db
import logging

logger = logging.getLogger(__name__)

saldos_bp = Blueprint('saldos', __name__)

@saldos_bp.route('/consultar', methods=['GET'])
def consultar_saldos():
    """Consulta saldos de materiais"""
    try:
        cliente_cnpj = request.args.get('cliente_cnpj')
        cliente_nome = request.args.get('cliente_nome')
        codigo_produto = request.args.get('codigo_produto')
        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 20, type=int), 100)
        
        # Monta a query base
        query = SaldoMaterial.query
        
        # Aplica filtros
        if cliente_cnpj:
            cliente_cnpj = ''.join(filter(str.isdigit, cliente_cnpj))
            query = query.filter(SaldoMaterial.cliente_cnpj == cliente_cnpj)
        
        if cliente_nome:
            query = query.filter(
                SaldoMaterial.cliente_nome.ilike(f'%{cliente_nome}%')
            )
        
        if codigo_produto:
            query = query.filter(
                db.or_(
                    SaldoMaterial.codigo_produto.ilike(f'%{codigo_produto}%'),
                    SaldoMaterial.descricao_produto.ilike(f'%{codigo_produto}%')
                )
            )
        
        # Ordena por cliente, produto e data
        query = query.order_by(
            SaldoMaterial.cliente_nome,
            SaldoMaterial.codigo_produto,
            SaldoMaterial.created_at.desc()
        )
        
        # Paginação
        saldos = query.paginate(
            page=page, per_page=per_page, error_out=False
        )
        
        # Calcula totais
        saldos_data = []
        for saldo in saldos.items:
            saldo_dict = saldo.to_dict()
            saldos_data.append(saldo_dict)
        
        return jsonify({
            'success': True,
            'data': saldos_data,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': saldos.total,
                'pages': saldos.pages,
                'has_next': saldos.has_next,
                'has_prev': saldos.has_prev
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Erro ao consultar saldos: {str(e)}")
        return jsonify({'error': 'Erro interno do servidor'}), 500

@saldos_bp.route('/cliente/<cliente_cnpj>', methods=['GET'])
def consultar_saldos_cliente(cliente_cnpj):
    """Consulta saldos de um cliente específico"""
    try:
        # Remove caracteres especiais do CNPJ
        cliente_cnpj = ''.join(filter(str.isdigit, cliente_cnpj))
        
        if len(cliente_cnpj) not in [11, 14]:  # CPF ou CNPJ
            return jsonify({'error': 'CNPJ/CPF inválido'}), 400
        
        saldos = SaldoService.consultar_saldos_cliente(cliente_cnpj=cliente_cnpj)
        
        # Agrupa por produto para facilitar visualização
        produtos = {}
        for saldo in saldos:
            key = f"{saldo['codigo_produto']}_{saldo['numero_lote']}"
            if key not in produtos:
                produtos[key] = {
                    'codigo_produto': saldo['codigo_produto'],
                    'descricao_produto': saldo['descricao_produto'],
                    'numero_lote': saldo['numero_lote'],
                    'nfs_saida': [],
                    'total_enviado': 0,
                    'total_retornado': 0,
                    'total_utilizado': 0,
                    'total_faturado': 0,
                    'saldo_total': 0
                }
            
            produtos[key]['nfs_saida'].append({
                'nf_numero': saldo['nf_saida_numero'],
                'nf_serie': saldo['nf_saida_serie'],
                'nf_chave': saldo['nf_saida_chave'],
                'quantidade_enviada': saldo['quantidade_enviada'],
                'quantidade_retornada': saldo['quantidade_retornada'],
                'quantidade_utilizada': saldo['quantidade_utilizada'],
                'quantidade_faturada': saldo['quantidade_faturada'],
                'saldo_disponivel': saldo['saldo_disponivel']
            })
            
            produtos[key]['total_enviado'] += saldo['quantidade_enviada']
            produtos[key]['total_retornado'] += saldo['quantidade_retornada']
            produtos[key]['total_utilizado'] += saldo['quantidade_utilizada']
            produtos[key]['total_faturado'] += saldo['quantidade_faturada']
            produtos[key]['saldo_total'] += saldo['saldo_disponivel']
        
        # Informações do cliente
        cliente_info = None
        if saldos:
            cliente_info = {
                'cnpj': saldos[0]['cliente_cnpj'],
                'nome': saldos[0]['cliente_nome']
            }
        
        return jsonify({
            'success': True,
            'data': {
                'cliente': cliente_info,
                'produtos': list(produtos.values()),
                'resumo': {
                    'total_produtos': len(produtos),
                    'total_nfs': len(saldos),
                    'produtos_com_saldo': len([p for p in produtos.values() if p['saldo_total'] > 0])
                }
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Erro ao consultar saldos do cliente: {str(e)}")
        return jsonify({'error': 'Erro interno do servidor'}), 500

@saldos_bp.route('/produto/<codigo_produto>', methods=['GET'])
def consultar_saldos_produto(codigo_produto):
    """Consulta saldos de um produto específico"""
    try:
        saldos = SaldoService.consultar_saldos_produto(codigo_produto)
        
        # Agrupa por cliente
        clientes = {}
        for saldo in saldos:
            cnpj = saldo['cliente_cnpj']
            if cnpj not in clientes:
                clientes[cnpj] = {
                    'cliente_cnpj': cnpj,
                    'cliente_nome': saldo['cliente_nome'],
                    'lotes': [],
                    'total_enviado': 0,
                    'total_retornado': 0,
                    'total_utilizado': 0,
                    'saldo_total': 0
                }
            
            clientes[cnpj]['lotes'].append({
                'numero_lote': saldo['numero_lote'],
                'nf_saida_numero': saldo['nf_saida_numero'],
                'nf_saida_serie': saldo['nf_saida_serie'],
                'quantidade_enviada': saldo['quantidade_enviada'],
                'quantidade_retornada': saldo['quantidade_retornada'],
                'quantidade_utilizada': saldo['quantidade_utilizada'],
                'saldo_disponivel': saldo['saldo_disponivel']
            })
            
            clientes[cnpj]['total_enviado'] += saldo['quantidade_enviada']
            clientes[cnpj]['total_retornado'] += saldo['quantidade_retornada']
            clientes[cnpj]['total_utilizado'] += saldo['quantidade_utilizada']
            clientes[cnpj]['saldo_total'] += saldo['saldo_disponivel']
        
        # Informações do produto
        produto_info = None
        if saldos:
            produto_info = {
                'codigo': saldos[0]['codigo_produto'],
                'descricao': saldos[0]['descricao_produto']
            }
        
        return jsonify({
            'success': True,
            'data': {
                'produto': produto_info,
                'clientes': list(clientes.values()),
                'resumo': {
                    'total_clientes': len(clientes),
                    'total_lotes': len(saldos),
                    'clientes_com_saldo': len([c for c in clientes.values() if c['saldo_total'] > 0])
                }
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Erro ao consultar saldos do produto: {str(e)}")
        return jsonify({'error': 'Erro interno do servidor'}), 500

@saldos_bp.route('/resumo', methods=['GET'])
def obter_resumo_saldos():
    """Obtém resumo geral dos saldos"""
    try:
        resumo = SaldoService.obter_resumo_saldos()
        
        # Saldos críticos (produtos com pouco estoque)
        saldos_criticos = SaldoMaterial.query.filter(
            db.and_(
                SaldoMaterial.quantidade_enviada > 
                (SaldoMaterial.quantidade_retornada + SaldoMaterial.quantidade_utilizada),
                (SaldoMaterial.quantidade_enviada - 
                 SaldoMaterial.quantidade_retornada - 
                 SaldoMaterial.quantidade_utilizada) <= 5  # Menos de 5 unidades
            )
        ).limit(10).all()
        
        resumo['saldos_criticos'] = [
            {
                'cliente_nome': saldo.cliente_nome,
                'codigo_produto': saldo.codigo_produto,
                'descricao_produto': saldo.descricao_produto,
                'numero_lote': saldo.numero_lote,
                'saldo_disponivel': saldo.saldo_disponivel
            }
            for saldo in saldos_criticos
        ]
        
        return jsonify({
            'success': True,
            'data': resumo
        }), 200
        
    except Exception as e:
        logger.error(f"Erro ao obter resumo: {str(e)}")
        return jsonify({'error': 'Erro interno do servidor'}), 500

@saldos_bp.route('/buscar-clientes', methods=['GET'])
def buscar_clientes():
    """Busca clientes para autocomplete"""
    try:
        termo = request.args.get('q', '').strip()
        
        if len(termo) < 2:
            return jsonify({
                'success': True,
                'data': []
            }), 200
        
        # Busca por nome ou CNPJ
        if termo.isdigit():
            # Busca por CNPJ
            clientes = db.session.query(
                SaldoMaterial.cliente_cnpj,
                SaldoMaterial.cliente_nome
            ).filter(
                SaldoMaterial.cliente_cnpj.like(f'%{termo}%')
            ).distinct().limit(10).all()
        else:
            # Busca por nome
            clientes = db.session.query(
                SaldoMaterial.cliente_cnpj,
                SaldoMaterial.cliente_nome
            ).filter(
                SaldoMaterial.cliente_nome.ilike(f'%{termo}%')
            ).distinct().limit(10).all()
        
        resultado = [
            {
                'cnpj': cnpj,
                'nome': nome,
                'label': f"{nome} ({cnpj})"
            }
            for cnpj, nome in clientes
        ]
        
        return jsonify({
            'success': True,
            'data': resultado
        }), 200
        
    except Exception as e:
        logger.error(f"Erro na busca de clientes: {str(e)}")
        return jsonify({'error': 'Erro interno do servidor'}), 500

@saldos_bp.route('/buscar-produtos', methods=['GET'])
def buscar_produtos():
    """Busca produtos para autocomplete"""
    try:
        termo = request.args.get('q', '').strip()
        
        if len(termo) < 2:
            return jsonify({
                'success': True,
                'data': []
            }), 200
        
        # Busca por código ou descrição
        produtos = db.session.query(
            SaldoMaterial.codigo_produto,
            SaldoMaterial.descricao_produto
        ).filter(
            db.or_(
                SaldoMaterial.codigo_produto.ilike(f'%{termo}%'),
                SaldoMaterial.descricao_produto.ilike(f'%{termo}%')
            )
        ).distinct().limit(10).all()
        
        resultado = [
            {
                'codigo': codigo,
                'descricao': descricao,
                'label': f"{codigo} - {descricao}"
            }
            for codigo, descricao in produtos
        ]
        
        return jsonify({
            'success': True,
            'data': resultado
        }), 200
        
    except Exception as e:
        logger.error(f"Erro na busca de produtos: {str(e)}")
        return jsonify({'error': 'Erro interno do servidor'}), 500

