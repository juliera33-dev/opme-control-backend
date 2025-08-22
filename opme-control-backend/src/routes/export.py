from flask import Blueprint, request, jsonify, send_file
from datetime import datetime
import pandas as pd
import io
import os
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from src.services.saldo_service import SaldoService

export_bp = Blueprint('export', __name__)

@export_bp.route('/saldos/excel', methods=['GET'])
def export_saldos_excel():
    """Exporta saldos para Excel"""
    try:
        # Pega os mesmos parâmetros da consulta de saldos
        filtros = {
            'cliente_cnpj': request.args.get('cliente_cnpj', ''),
            'cliente_nome': request.args.get('cliente_nome', ''),
            'codigo_produto': request.args.get('codigo_produto', ''),
            'data_inicio': request.args.get('data_inicio'),
            'data_fim': request.args.get('data_fim'),
            'cfop': request.args.get('cfop', '')
        }
        
        # Remove filtros vazios
        filtros = {k: v for k, v in filtros.items() if v}
        
        # Busca todos os saldos (sem paginação para export)
        saldos = SaldoService.consultar_saldos(filtros, page=1, per_page=10000)
        
        if not saldos['data']:
            return jsonify({'error': 'Nenhum saldo encontrado para exportar'}), 404
        
        # Converte para DataFrame
        df_data = []
        for saldo in saldos['data']:
            df_data.append({
                'Cliente': saldo['cliente_nome'],
                'CNPJ/CPF': _format_cnpj(saldo['cliente_cnpj']),
                'Código Produto': saldo['codigo_produto'],
                'Descrição Produto': saldo['descricao_produto'],
                'Número Lote': saldo['numero_lote'],
                'Quantidade Enviada': saldo['quantidade_enviada'],
                'Quantidade Retornada': saldo['quantidade_retornada'],
                'Quantidade Utilizada': saldo['quantidade_utilizada'],
                'Saldo Disponível': saldo['saldo_disponivel'],
                'Status': _get_status_label(saldo['saldo_disponivel'])
            })
        
        df = pd.DataFrame(df_data)
        
        # Cria arquivo Excel em memória
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Saldos OPME', index=False)
            
            # Formata a planilha
            worksheet = writer.sheets['Saldos OPME']
            
            # Ajusta largura das colunas
            for column in worksheet.columns:
                max_length = 0
                column_letter = column[0].column_letter
                for cell in column:
                    try:
                        if len(str(cell.value)) > max_length:
                            max_length = len(str(cell.value))
                    except:
                        pass
                adjusted_width = min(max_length + 2, 50)
                worksheet.column_dimensions[column_letter].width = adjusted_width
        
        output.seek(0)
        
        # Nome do arquivo com timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'saldos_opme_{timestamp}.xlsx'
        
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=filename
        )
        
    except Exception as e:
        return jsonify({'error': f'Erro ao exportar Excel: {str(e)}'}), 500

@export_bp.route('/saldos/pdf', methods=['GET'])
def export_saldos_pdf():
    """Exporta saldos para PDF"""
    try:
        # Pega os mesmos parâmetros da consulta de saldos
        filtros = {
            'cliente_cnpj': request.args.get('cliente_cnpj', ''),
            'cliente_nome': request.args.get('cliente_nome', ''),
            'codigo_produto': request.args.get('codigo_produto', ''),
            'data_inicio': request.args.get('data_inicio'),
            'data_fim': request.args.get('data_fim'),
            'cfop': request.args.get('cfop', '')
        }
        
        # Remove filtros vazios
        filtros = {k: v for k, v in filtros.items() if v}
        
        # Busca todos os saldos (sem paginação para export)
        saldos = SaldoService.consultar_saldos(filtros, page=1, per_page=10000)
        
        if not saldos['data']:
            return jsonify({'error': 'Nenhum saldo encontrado para exportar'}), 404
        
        # Cria PDF em memória
        output = io.BytesIO()
        doc = SimpleDocTemplate(output, pagesize=A4)
        
        # Estilos
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=16,
            spaceAfter=30,
            alignment=1  # Center
        )
        
        # Elementos do PDF
        elements = []
        
        # Título
        title = Paragraph("Relatório de Saldos OPME", title_style)
        elements.append(title)
        
        # Data de geração
        data_geracao = Paragraph(
            f"Gerado em: {datetime.now().strftime('%d/%m/%Y às %H:%M')}",
            styles['Normal']
        )
        elements.append(data_geracao)
        elements.append(Spacer(1, 20))
        
        # Filtros aplicados
        if any(filtros.values()):
            filtros_text = "Filtros aplicados: "
            filtros_list = []
            if filtros.get('cliente_nome'):
                filtros_list.append(f"Cliente: {filtros['cliente_nome']}")
            if filtros.get('cliente_cnpj'):
                filtros_list.append(f"CNPJ: {filtros['cliente_cnpj']}")
            if filtros.get('codigo_produto'):
                filtros_list.append(f"Produto: {filtros['codigo_produto']}")
            if filtros.get('data_inicio') and filtros.get('data_fim'):
                filtros_list.append(f"Período: {filtros['data_inicio']} a {filtros['data_fim']}")
            if filtros.get('cfop'):
                filtros_list.append(f"CFOP: {filtros['cfop']}")
            
            filtros_text += "; ".join(filtros_list)
            filtros_para = Paragraph(filtros_text, styles['Normal'])
            elements.append(filtros_para)
            elements.append(Spacer(1, 20))
        
        # Tabela de dados
        table_data = [
            ['Cliente', 'CNPJ/CPF', 'Produto', 'Lote', 'Enviado', 'Retornado', 'Utilizado', 'Saldo']
        ]
        
        for saldo in saldos['data']:
            table_data.append([
                _truncate_text(saldo['cliente_nome'], 25),
                _format_cnpj(saldo['cliente_cnpj']),
                _truncate_text(saldo['codigo_produto'], 15),
                _truncate_text(saldo['numero_lote'], 12),
                str(saldo['quantidade_enviada']),
                str(saldo['quantidade_retornada']),
                str(saldo['quantidade_utilizada']),
                str(saldo['saldo_disponivel'])
            ])
        
        # Cria tabela
        table = Table(table_data)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        
        elements.append(table)
        
        # Resumo
        elements.append(Spacer(1, 30))
        total_registros = len(saldos['data'])
        saldos_positivos = len([s for s in saldos['data'] if s['saldo_disponivel'] > 0])
        saldos_zerados = len([s for s in saldos['data'] if s['saldo_disponivel'] == 0])
        saldos_negativos = len([s for s in saldos['data'] if s['saldo_disponivel'] < 0])
        
        resumo_text = f"""
        <b>Resumo:</b><br/>
        Total de registros: {total_registros}<br/>
        Saldos positivos: {saldos_positivos}<br/>
        Saldos zerados: {saldos_zerados}<br/>
        Saldos negativos: {saldos_negativos}
        """
        
        resumo = Paragraph(resumo_text, styles['Normal'])
        elements.append(resumo)
        
        # Gera PDF
        doc.build(elements)
        output.seek(0)
        
        # Nome do arquivo com timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'saldos_opme_{timestamp}.pdf'
        
        return send_file(
            output,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=filename
        )
        
    except Exception as e:
        return jsonify({'error': f'Erro ao exportar PDF: {str(e)}'}), 500

def _format_cnpj(cnpj):
    """Formata CNPJ/CPF"""
    if not cnpj:
        return ''
    
    cnpj = str(cnpj).zfill(14) if len(str(cnpj)) > 11 else str(cnpj).zfill(11)
    
    if len(cnpj) == 14:
        return f"{cnpj[:2]}.{cnpj[2:5]}.{cnpj[5:8]}/{cnpj[8:12]}-{cnpj[12:]}"
    elif len(cnpj) == 11:
        return f"{cnpj[:3]}.{cnpj[3:6]}.{cnpj[6:9]}-{cnpj[9:]}"
    
    return cnpj

def _get_status_label(saldo):
    """Retorna label do status do saldo"""
    if saldo > 0:
        return 'Disponível'
    elif saldo == 0:
        return 'Zerado'
    else:
        return 'Negativo'

def _truncate_text(text, max_length):
    """Trunca texto para caber na tabela"""
    if not text:
        return ''
    return text[:max_length] + '...' if len(text) > max_length else text

