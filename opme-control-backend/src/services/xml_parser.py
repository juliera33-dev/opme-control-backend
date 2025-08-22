import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import re

class XMLParser:
    """Classe para processar XMLs de Notas Fiscais"""
    
    # Mapeamento de CFOPs para tipos de operação
    CFOP_MAPPING = {
        '5917': 'saida',      # Saída para consignação (dentro do estado)
        '6917': 'saida',      # Saída para consignação (fora do estado)
        '1918': 'retorno',    # Retorno de consignação (dentro do estado)
        '2918': 'retorno',    # Retorno de consignação (fora do estado)
        '1919': 'simbolico',  # Retorno simbólico - material utilizado (dentro do estado)
        '2919': 'simbolico',  # Retorno simbólico - material utilizado (fora do estado)
        '5114': 'faturamento', # Faturamento do material utilizado (dentro do estado)
        '6114': 'faturamento'  # Faturamento do material utilizado (fora do estado)
    }
    
    @staticmethod
    def parse_xml(xml_content: str) -> Dict:
        """
        Processa o XML da nota fiscal e extrai as informações relevantes
        
        Args:
            xml_content: Conteúdo do XML da nota fiscal
            
        Returns:
            Dict com os dados extraídos da nota fiscal
        """
        try:
            # Remove namespaces para facilitar o parsing
            xml_content = XMLParser._remove_namespaces(xml_content)
            root = ET.fromstring(xml_content)
            
            # Extrai dados da nota fiscal
            nf_data = XMLParser._extract_nf_data(root)
            
            # Extrai dados do destinatário/remetente
            dest_data = XMLParser._extract_destinatario_data(root)
            
            # Extrai itens da nota fiscal
            itens = XMLParser._extract_itens_data(root)
            
            # Determina o tipo de operação baseado no CFOP
            cfop = XMLParser._extract_cfop(root)
            tipo_operacao = XMLParser.CFOP_MAPPING.get(cfop, 'outros')
            
            return {
                'numero': nf_data.get('numero'),
                'serie': nf_data.get('serie'),
                'chave_acesso': nf_data.get('chave_acesso'),
                'data_emissao': nf_data.get('data_emissao'),
                'cfop': cfop,
                'tipo_operacao': tipo_operacao,
                'destinatario_cnpj': dest_data.get('cnpj'),
                'destinatario_nome': dest_data.get('nome'),
                'itens': itens,
                'xml_content': xml_content
            }
            
        except Exception as e:
            raise ValueError(f"Erro ao processar XML: {str(e)}")
    
    @staticmethod
    def _remove_namespaces(xml_content: str) -> str:
        """Remove namespaces do XML para facilitar o parsing"""
        # Remove declarações de namespace
        xml_content = re.sub(r'\s*xmlns[^=]*="[^"]*"', '', xml_content)
        # Remove prefixos de namespace das tags
        xml_content = re.sub(r'</?[a-zA-Z0-9_]*:', '<', xml_content)
        xml_content = re.sub(r'<([a-zA-Z0-9_]+)\s', r'<\1 ', xml_content)
        return xml_content
    
    @staticmethod
    def _extract_nf_data(root: ET.Element) -> Dict:
        """Extrai dados básicos da nota fiscal"""
        ide = root.find('.//ide')
        if ide is None:
            raise ValueError("Tag 'ide' não encontrada no XML")
        
        # Extrai chave de acesso
        inf_nfe = root.find('.//infNFe')
        chave_acesso = inf_nfe.get('Id', '').replace('NFe', '') if inf_nfe is not None else ''
        
        # Extrai data de emissão
        data_emissao_str = ide.findtext('dhEmi') or ide.findtext('dEmi')
        data_emissao = None
        if data_emissao_str:
            try:
                # Tenta diferentes formatos de data
                if 'T' in data_emissao_str:
                    data_emissao = datetime.fromisoformat(data_emissao_str.replace('Z', '+00:00'))
                else:
                    data_emissao = datetime.strptime(data_emissao_str, '%Y-%m-%d')
            except ValueError:
                pass
        
        return {
            'numero': ide.findtext('nNF'),
            'serie': ide.findtext('serie'),
            'chave_acesso': chave_acesso,
            'data_emissao': data_emissao
        }
    
    @staticmethod
    def _extract_destinatario_data(root: ET.Element) -> Dict:
        """Extrai dados do destinatário"""
        dest = root.find('.//dest')
        if dest is None:
            # Se não há destinatário, pode ser uma nota de entrada, então pega o emitente
            dest = root.find('.//emit')
        
        if dest is None:
            return {'cnpj': '', 'nome': ''}
        
        cnpj = dest.findtext('CNPJ') or dest.findtext('CPF') or ''
        nome = dest.findtext('xNome') or dest.findtext('xFant') or ''
        
        # Remove caracteres especiais do CNPJ/CPF
        cnpj = re.sub(r'[^\d]', '', cnpj)
        
        return {
            'cnpj': cnpj,
            'nome': nome
        }
    
    @staticmethod
    def _extract_cfop(root: ET.Element) -> str:
        """Extrai o CFOP da nota fiscal (pega o primeiro item)"""
        det = root.find('.//det')
        if det is not None:
            imposto = det.find('.//imposto')
            if imposto is not None:
                # Procura CFOP em diferentes locais possíveis
                cfop = (imposto.findtext('.//CFOP') or 
                       det.findtext('.//CFOP') or 
                       det.findtext('.//prod/CFOP'))
                return cfop or ''
        return ''
    
    @staticmethod
    def _extract_itens_data(root: ET.Element) -> List[Dict]:
        """Extrai dados dos itens da nota fiscal"""
        itens = []
        
        for det in root.findall('.//det'):
            prod = det.find('prod')
            if prod is None:
                continue
            
            # Dados básicos do produto
            codigo = prod.findtext('cProd') or ''
            descricao = prod.findtext('xProd') or ''
            quantidade = float(prod.findtext('qCom') or 0)
            valor_unitario = float(prod.findtext('vUnCom') or 0)
            valor_total = float(prod.findtext('vProd') or 0)
            
            # Extrai dados do lote
            lote_data = XMLParser._extract_lote_data(det)
            
            item = {
                'codigo_produto': codigo,
                'descricao_produto': descricao,
                'quantidade': quantidade,
                'valor_unitario': valor_unitario,
                'valor_total': valor_total,
                'numero_lote': lote_data.get('numero_lote'),
                'data_fabricacao': lote_data.get('data_fabricacao'),
                'data_validade': lote_data.get('data_validade')
            }
            
            itens.append(item)
        
        return itens
    
    @staticmethod
    def _extract_lote_data(det_element: ET.Element) -> Dict:
        """Extrai dados do lote do item"""
        lote_data = {
            'numero_lote': None,
            'data_fabricacao': None,
            'data_validade': None
        }
        
        # Procura por dados de rastreabilidade
        rastro = det_element.find('.//rastro')
        if rastro is not None:
            lote_data['numero_lote'] = rastro.findtext('nLote')
            
            # Datas de fabricação e validade
            data_fab = rastro.findtext('dFab')
            data_val = rastro.findtext('dVal')
            
            if data_fab:
                try:
                    lote_data['data_fabricacao'] = datetime.strptime(data_fab, '%Y-%m-%d').date()
                except ValueError:
                    pass
            
            if data_val:
                try:
                    lote_data['data_validade'] = datetime.strptime(data_val, '%Y-%m-%d').date()
                except ValueError:
                    pass
        
        # Se não encontrou na tag rastro, procura em outras possíveis localizações
        if not lote_data['numero_lote']:
            # Procura na tag med (medicamentos)
            med = det_element.find('.//med')
            if med is not None:
                lote_data['numero_lote'] = med.findtext('nLote')
                
                data_fab = med.findtext('dFab')
                data_val = med.findtext('dVal')
                
                if data_fab:
                    try:
                        lote_data['data_fabricacao'] = datetime.strptime(data_fab, '%Y-%m-%d').date()
                    except ValueError:
                        pass
                
                if data_val:
                    try:
                        lote_data['data_validade'] = datetime.strptime(data_val, '%Y-%m-%d').date()
                    except ValueError:
                        pass
            
            # Procura em infAdProd (informações adicionais) - FALLBACK PRINCIPAL
            if not lote_data['numero_lote']:
                inf_ad_prod = det_element.findtext('.//infAdProd') or ''
                # Procura padrões mais abrangentes como "LOTE: 123456", "Lote: 123456", "L: 123456"
                lote_patterns = [
                    r'lote[:\s]+([^\s,;\.]+)',  # LOTE: 123456
                    r'l[:\s]+([^\s,;\.]+)',     # L: 123456
                    r'lot[:\s]+([^\s,;\.]+)',   # LOT: 123456
                    r'batch[:\s]+([^\s,;\.]+)', # BATCH: 123456
                    r'nr[:\s]*lote[:\s]+([^\s,;\.]+)', # NR LOTE: 123456
                    r'numero[:\s]*lote[:\s]+([^\s,;\.]+)' # NUMERO LOTE: 123456
                ]
                
                for pattern in lote_patterns:
                    lote_match = re.search(pattern, inf_ad_prod, re.IGNORECASE)
                    if lote_match:
                        lote_data['numero_lote'] = lote_match.group(1).strip()
                        break
        
        return lote_data
    
    @staticmethod
    def validate_xml_structure(xml_content: str) -> Tuple[bool, str]:
        """
        Valida se o XML tem a estrutura esperada de uma NFe
        
        Returns:
            Tuple[bool, str]: (is_valid, error_message)
        """
        try:
            xml_content = XMLParser._remove_namespaces(xml_content)
            root = ET.fromstring(xml_content)
            
            # Verifica se é uma NFe
            if root.find('.//infNFe') is None:
                return False, "XML não é uma Nota Fiscal Eletrônica válida"
            
            # Verifica se tem dados básicos
            ide = root.find('.//ide')
            if ide is None:
                return False, "Tag 'ide' não encontrada no XML"
            
            if not ide.findtext('nNF'):
                return False, "Número da nota fiscal não encontrado"
            
            if not ide.findtext('serie'):
                return False, "Série da nota fiscal não encontrada"
            
            # Verifica se tem pelo menos um item
            if not root.findall('.//det'):
                return False, "Nenhum item encontrado na nota fiscal"
            
            return True, ""
            
        except ET.ParseError as e:
            return False, f"Erro ao fazer parse do XML: {str(e)}"
        except Exception as e:
            return False, f"Erro na validação: {str(e)}"

