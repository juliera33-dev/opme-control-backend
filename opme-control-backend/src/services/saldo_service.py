from typing import Dict, List, Optional
from sqlalchemy import and_, or_
from src.models.nota_fiscal import NotaFiscal, ItemNotaFiscal, SaldoMaterial, db
from src.services.xml_parser import XMLParser
import logging

logger = logging.getLogger(__name__)

class SaldoService:
    """Serviço para controle de saldos de materiais OPME"""
    
    @staticmethod
    def processar_nota_fiscal(xml_content: str) -> Dict:
        """
        Processa uma nota fiscal e atualiza os saldos
        
        Args:
            xml_content: Conteúdo XML da nota fiscal
            
        Returns:
            Dict com resultado do processamento
        """
        try:
            # Valida o XML
            is_valid, error_msg = XMLParser.validate_xml_structure(xml_content)
            if not is_valid:
                return {'success': False, 'error': error_msg}
            
            # Faz o parse do XML
            nf_data = XMLParser.parse_xml(xml_content)
            
            # Verifica se a nota já foi processada
            existing_nf = NotaFiscal.query.filter_by(
                chave_acesso=nf_data['chave_acesso']
            ).first()
            
            if existing_nf:
                return {
                    'success': False, 
                    'error': f"Nota fiscal {nf_data['numero']}/{nf_data['serie']} já foi processada"
                }
            
            # Cria a nota fiscal no banco
            nota_fiscal = NotaFiscal(
                numero=nf_data['numero'],
                serie=nf_data['serie'],
                chave_acesso=nf_data['chave_acesso'],
                data_emissao=nf_data['data_emissao'],
                cfop=nf_data['cfop'],
                tipo_operacao=nf_data['tipo_operacao'],
                destinatario_cnpj=nf_data['destinatario_cnpj'],
                destinatario_nome=nf_data['destinatario_nome'],
                xml_content=xml_content
            )
            
            db.session.add(nota_fiscal)
            db.session.flush()  # Para obter o ID
            
            # Processa os itens
            itens_processados = 0
            for item_data in nf_data['itens']:
                # Cria o item da nota fiscal
                item = ItemNotaFiscal(
                    nota_fiscal_id=nota_fiscal.id,
                    codigo_produto=item_data['codigo_produto'],
                    descricao_produto=item_data['descricao_produto'],
                    quantidade=item_data['quantidade'],
                    valor_unitario=item_data['valor_unitario'],
                    valor_total=item_data['valor_total'],
                    numero_lote=item_data['numero_lote'],
                    data_fabricacao=item_data['data_fabricacao'],
                    data_validade=item_data['data_validade']
                )
                
                db.session.add(item)
                
                # Atualiza saldos se o item tem lote
                if item_data['numero_lote']:
                    SaldoService._atualizar_saldo(
                        nota_fiscal=nota_fiscal,
                        item_data=item_data
                    )
                    itens_processados += 1
            
            db.session.commit()
            
            return {
                'success': True,
                'message': f"Nota fiscal {nf_data['numero']}/{nf_data['serie']} processada com sucesso",
                'nota_fiscal_id': nota_fiscal.id,
                'tipo_operacao': nf_data['tipo_operacao'],
                'itens_processados': itens_processados
            }
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Erro ao processar nota fiscal: {str(e)}")
            return {'success': False, 'error': f"Erro interno: {str(e)}"}
    
    @staticmethod
    def _atualizar_saldo(nota_fiscal: NotaFiscal, item_data: Dict):
        """Atualiza o saldo de um material específico"""
        
        if nota_fiscal.tipo_operacao == 'saida':
            # Saída para consignação - cria novo saldo
            SaldoService._processar_saida_consignacao(nota_fiscal, item_data)
            
        elif nota_fiscal.tipo_operacao == 'retorno':
            # Retorno de consignação - atualiza quantidade retornada
            SaldoService._processar_retorno_consignacao(nota_fiscal, item_data)
            
        elif nota_fiscal.tipo_operacao == 'simbolico':
            # Retorno simbólico - marca como utilizado
            SaldoService._processar_retorno_simbolico(nota_fiscal, item_data)
            
        elif nota_fiscal.tipo_operacao == 'faturamento':
            # Faturamento - marca como faturado
            SaldoService._processar_faturamento(nota_fiscal, item_data)
    
    @staticmethod
    def _processar_saida_consignacao(nota_fiscal: NotaFiscal, item_data: Dict):
        """Processa saída para consignação"""
        
        # Verifica se já existe saldo para este item
        saldo = SaldoMaterial.query.filter_by(
            cliente_cnpj=nota_fiscal.destinatario_cnpj,
            codigo_produto=item_data['codigo_produto'],
            numero_lote=item_data['numero_lote'],
            nf_saida_chave=nota_fiscal.chave_acesso
        ).first()
        
        if saldo:
            # Atualiza quantidade enviada
            saldo.quantidade_enviada += item_data['quantidade']
        else:
            # Cria novo saldo
            saldo = SaldoMaterial(
                cliente_cnpj=nota_fiscal.destinatario_cnpj,
                cliente_nome=nota_fiscal.destinatario_nome,
                codigo_produto=item_data['codigo_produto'],
                descricao_produto=item_data['descricao_produto'],
                numero_lote=item_data['numero_lote'],
                nf_saida_numero=nota_fiscal.numero,
                nf_saida_serie=nota_fiscal.serie,
                nf_saida_chave=nota_fiscal.chave_acesso,
                quantidade_enviada=item_data['quantidade']
            )
            db.session.add(saldo)
    
    @staticmethod
    def _processar_retorno_consignacao(nota_fiscal: NotaFiscal, item_data: Dict):
        """Processa retorno de consignação"""
        
        # Busca o saldo correspondente
        saldo = SaldoService._buscar_saldo_para_retorno(
            nota_fiscal.destinatario_cnpj,
            item_data['codigo_produto'],
            item_data['numero_lote']
        )
        
        if saldo:
            saldo.quantidade_retornada += item_data['quantidade']
        else:
            logger.warning(
                f"Saldo não encontrado para retorno: "
                f"Cliente {nota_fiscal.destinatario_cnpj}, "
                f"Produto {item_data['codigo_produto']}, "
                f"Lote {item_data['numero_lote']}"
            )
    
    @staticmethod
    def _processar_retorno_simbolico(nota_fiscal: NotaFiscal, item_data: Dict):
        """Processa retorno simbólico (material utilizado)"""
        
        # Busca o saldo correspondente
        saldo = SaldoService._buscar_saldo_para_retorno(
            nota_fiscal.destinatario_cnpj,
            item_data['codigo_produto'],
            item_data['numero_lote']
        )
        
        if saldo:
            saldo.quantidade_utilizada += item_data['quantidade']
        else:
            logger.warning(
                f"Saldo não encontrado para retorno simbólico: "
                f"Cliente {nota_fiscal.destinatario_cnpj}, "
                f"Produto {item_data['codigo_produto']}, "
                f"Lote {item_data['numero_lote']}"
            )
    
    @staticmethod
    def _processar_faturamento(nota_fiscal: NotaFiscal, item_data: Dict):
        """Processa faturamento do material utilizado"""
        
        # Busca o saldo correspondente
        saldo = SaldoService._buscar_saldo_para_retorno(
            nota_fiscal.destinatario_cnpj,
            item_data['codigo_produto'],
            item_data['numero_lote']
        )
        
        if saldo:
            saldo.quantidade_faturada += item_data['quantidade']
        else:
            logger.warning(
                f"Saldo não encontrado para faturamento: "
                f"Cliente {nota_fiscal.destinatario_cnpj}, "
                f"Produto {item_data['codigo_produto']}, "
                f"Lote {item_data['numero_lote']}"
            )
    
    @staticmethod
    def _buscar_saldo_para_retorno(cliente_cnpj: str, codigo_produto: str, 
                                 numero_lote: str) -> Optional[SaldoMaterial]:
        """
        Busca saldo para operações de retorno/utilização
        Prioriza saldos com quantidade disponível
        """
        return SaldoMaterial.query.filter(
            and_(
                SaldoMaterial.cliente_cnpj == cliente_cnpj,
                SaldoMaterial.codigo_produto == codigo_produto,
                SaldoMaterial.numero_lote == numero_lote,
                # Só considera saldos com quantidade disponível
                SaldoMaterial.quantidade_enviada > 
                (SaldoMaterial.quantidade_retornada + SaldoMaterial.quantidade_utilizada)
            )
        ).order_by(SaldoMaterial.created_at.asc()).first()
    
    @staticmethod
    def consultar_saldos_cliente(cliente_cnpj: str = None, cliente_nome: str = None) -> List[Dict]:
        """
        Consulta saldos de um cliente específico
        
        Args:
            cliente_cnpj: CNPJ do cliente
            cliente_nome: Nome do cliente (busca parcial)
            
        Returns:
            Lista de saldos do cliente
        """
        query = SaldoMaterial.query
        
        if cliente_cnpj:
            # Remove caracteres especiais do CNPJ
            cliente_cnpj = ''.join(filter(str.isdigit, cliente_cnpj))
            query = query.filter(SaldoMaterial.cliente_cnpj == cliente_cnpj)
        
        if cliente_nome:
            query = query.filter(
                SaldoMaterial.cliente_nome.ilike(f'%{cliente_nome}%')
            )
        
        # Ordena por cliente, produto e data
        saldos = query.order_by(
            SaldoMaterial.cliente_nome,
            SaldoMaterial.codigo_produto,
            SaldoMaterial.created_at.desc()
        ).all()
        
        return [saldo.to_dict() for saldo in saldos]
    
    @staticmethod
    def consultar_saldos_produto(codigo_produto: str) -> List[Dict]:
        """Consulta saldos de um produto específico"""
        saldos = SaldoMaterial.query.filter(
            SaldoMaterial.codigo_produto.ilike(f'%{codigo_produto}%')
        ).order_by(
            SaldoMaterial.cliente_nome,
            SaldoMaterial.created_at.desc()
        ).all()
        
        return [saldo.to_dict() for saldo in saldos]
    
    @staticmethod
    def obter_resumo_saldos() -> Dict:
        """Obtém resumo geral dos saldos"""
        
        # Total de clientes com saldo
        total_clientes = db.session.query(SaldoMaterial.cliente_cnpj).distinct().count()
        
        # Total de produtos em consignação
        total_produtos = db.session.query(SaldoMaterial.codigo_produto).distinct().count()
        
        # Saldos com pendências (quantidade disponível > 0)
        saldos_pendentes = SaldoMaterial.query.filter(
            SaldoMaterial.quantidade_enviada > 
            (SaldoMaterial.quantidade_retornada + SaldoMaterial.quantidade_utilizada)
        ).count()
        
        # Total de notas fiscais processadas
        total_nfs = NotaFiscal.query.count()
        
        return {
            'total_clientes': total_clientes,
            'total_produtos': total_produtos,
            'saldos_pendentes': saldos_pendentes,
            'total_nfs_processadas': total_nfs
        }
    
    @staticmethod
    def validar_operacao(nota_fiscal: NotaFiscal, item_data: Dict) -> Dict:
        """
        Valida se uma operação pode ser realizada
        
        Returns:
            Dict com resultado da validação
        """
        if nota_fiscal.tipo_operacao in ['retorno', 'simbolico', 'faturamento']:
            # Para operações de retorno, verifica se há saldo disponível
            saldo = SaldoService._buscar_saldo_para_retorno(
                nota_fiscal.destinatario_cnpj,
                item_data['codigo_produto'],
                item_data['numero_lote']
            )
            
            if not saldo:
                return {
                    'valid': False,
                    'error': f"Não há saldo disponível para o produto {item_data['codigo_produto']} "
                           f"lote {item_data['numero_lote']} do cliente {nota_fiscal.destinatario_cnpj}"
                }
            
            quantidade_disponivel = saldo.saldo_disponivel
            if quantidade_disponivel < item_data['quantidade']:
                return {
                    'valid': False,
                    'error': f"Quantidade insuficiente. Disponível: {quantidade_disponivel}, "
                           f"Solicitado: {item_data['quantidade']}"
                }
        
        return {'valid': True}

