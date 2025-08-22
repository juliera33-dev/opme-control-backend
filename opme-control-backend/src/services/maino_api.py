import requests
import os
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

class MainoAPIService:
    """Serviço para integração com a API do Mainô"""
    
    def __init__(self):
        self.base_url = os.getenv('MAINO_API_BASE_URL', 'https://api.maino.com.br')
        self.application_uid = os.getenv('MAINO_APPLICATION_UID')
        self.email = os.getenv('MAINO_EMAIL')
        self.password = os.getenv('MAINO_PASSWORD')
        self.api_key = os.getenv('MAINO_API_KEY')
        self.access_token = None
        self.token_expires_at = None
    
    def authenticate(self) -> bool:
        """
        Autentica na API do Mainô usando OAuth2
        
        Returns:
            bool: True se autenticação foi bem-sucedida
        """
        if not self.application_uid or not self.email or not self.password:
            logger.error("Credenciais do Mainô não configuradas")
            return False
        
        try:
            url = f"{self.base_url}/api/v2/authentication"
            payload = {
                "application_uid": self.application_uid,
                "email": self.email,
                "password": self.password
            }
            
            response = requests.post(url, json=payload, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            
            # A resposta vem com CNPJ como chave
            for cnpj, user_data in data.items():
                if 'access_token' in user_data:
                    self.access_token = user_data['access_token']
                    # Define expiração do token para 1 hora (padrão)
                    self.token_expires_at = datetime.now() + timedelta(hours=1)
                    logger.info("Autenticação no Mainô realizada com sucesso")
                    return True
            
            logger.error("Token de acesso não encontrado na resposta")
            return False
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Erro na autenticação do Mainô: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Erro inesperado na autenticação: {str(e)}")
            return False
    
    def _get_headers(self) -> Dict[str, str]:
        """Retorna headers para requisições autenticadas"""
        if self.api_key:
            return {
                'X-Api-Key': self.api_key,
                'Content-Type': 'application/json'
            }
        elif self.access_token:
            return {
                'Authorization': f'Bearer {self.access_token}',
                'Content-Type': 'application/json'
            }
        else:
            return {'Content-Type': 'application/json'}
    
    def _ensure_authenticated(self) -> bool:
        """Garante que há um token válido"""
        if self.api_key:
            return True
        
        if (self.access_token and self.token_expires_at and 
            datetime.now() < self.token_expires_at):
            return True
        
        return self.authenticate()
    
    def get_notas_fiscais_emitidas(self, data_inicio: str = None, data_fim: str = None, 
                                 page: int = 1, per_page: int = 100) -> Optional[Dict]:
        """
        Busca notas fiscais emitidas via API do Mainô
        
        Args:
            data_inicio: Data início no formato DD/MM/YYYY
            data_fim: Data fim no formato DD/MM/YYYY
            page: Página para paginação
            per_page: Itens por página
            
        Returns:
            Dict com dados das notas fiscais ou None em caso de erro
        """
        if not self._ensure_authenticated():
            logger.error("Falha na autenticação")
            return None
        
        try:
            # Usa endpoint v2 conforme especificado pelo usuário
            url = f"{self.base_url}/api/v2/notas_fiscais_emitidas"
            
            params = {
                'page': page,
                'per_page': per_page
            }
            
            if data_inicio:
                params['data_inicio'] = data_inicio
            if data_fim:
                params['data_fim'] = data_fim
            
            response = requests.get(url, headers=self._get_headers(), 
                                  params=params, timeout=30)
            response.raise_for_status()
            
            return response.json()
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Erro ao buscar notas fiscais: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Erro inesperado: {str(e)}")
            return None
    
    def get_xml_nfe(self, chave_acesso: str) -> Optional[str]:
        """
        Busca o XML de uma NFe específica
        
        Args:
            chave_acesso: Chave de acesso da NFe
            
        Returns:
            String com o conteúdo XML ou None em caso de erro
        """
        if not self._ensure_authenticated():
            logger.error("Falha na autenticação")
            return None
        
        try:
            # Usa endpoint v2 conforme especificado pelo usuário
            url = f"{self.base_url}/api/v2/nfes_emitidas"
            
            params = {
                'chave_acesso': chave_acesso
            }
            
            response = requests.get(url, headers=self._get_headers(), 
                                  params=params, timeout=30)
            response.raise_for_status()
            
            # Assume que a resposta contém o XML diretamente ou em um campo específico
            data = response.json()
            
            # Adaptar conforme a estrutura real da resposta da API
            if isinstance(data, dict) and 'xml' in data:
                return data['xml']
            elif isinstance(data, str):
                return data
            else:
                logger.error("Formato de resposta XML não reconhecido")
                return None
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Erro ao buscar XML da NFe {chave_acesso}: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Erro inesperado: {str(e)}")
            return None
    
    def sync_notas_fiscais(self, data_inicio: str = None, data_fim: str = None) -> List[Dict]:
        """
        Sincroniza notas fiscais do Mainô
        
        Args:
            data_inicio: Data início no formato DD/MM/YYYY
            data_fim: Data fim no formato DD/MM/YYYY
            
        Returns:
            Lista de notas fiscais processadas
        """
        notas_processadas = []
        page = 1
        
        while True:
            logger.info(f"Buscando página {page} de notas fiscais")
            
            data = self.get_notas_fiscais_emitidas(
                data_inicio=data_inicio,
                data_fim=data_fim,
                page=page
            )
            
            if not data or not data.get('data'):
                break
            
            notas = data.get('data', [])
            if not notas:
                break
            
            for nota in notas:
                # Processa cada nota fiscal
                chave_acesso = nota.get('chave_acesso')
                if chave_acesso:
                    xml_content = self.get_xml_nfe(chave_acesso)
                    if xml_content:
                        nota['xml_content'] = xml_content
                
                notas_processadas.append(nota)
            
            # Verifica se há mais páginas
            pagination = data.get('pagination', {})
            if page >= pagination.get('total_pages', 1):
                break
            
            page += 1
        
        logger.info(f"Sincronização concluída: {len(notas_processadas)} notas processadas")
        return notas_processadas
    
    def test_connection(self) -> bool:
        """
        Testa a conexão com a API do Mainô
        
        Returns:
            bool: True se conexão está funcionando
        """
        try:
            if self.api_key:
                # Testa com API Key
                url = f"{self.base_url}/api/v2/empresas"
                response = requests.get(url, headers=self._get_headers(), timeout=10)
                return response.status_code == 200
            else:
                # Testa autenticação OAuth2
                return self.authenticate()
                
        except Exception as e:
            logger.error(f"Erro no teste de conexão: {str(e)}")
            return False

