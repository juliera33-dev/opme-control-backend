# AkosMed - Sistema de Controle de Materiais OPME

Sistema para controle de saldos de materiais OPME (Órteses, Próteses e Materiais Especiais) através do processamento de Notas Fiscais XML e integração com a API do Mainô.

## 🚀 Funcionalidades

- **Processamento de XMLs**: Análise automática de Notas Fiscais com extração de dados de produtos e lotes
- **Controle de Saldos**: Cálculo automático de saldos por cliente, produto e lote
- **Integração Mainô**: Sincronização com a API do Mainô para busca de NFs
- **Exportação**: Relatórios em Excel e PDF
- **Filtros Avançados**: Busca por período, CFOP, cliente e produto
- **Interface Responsiva**: Frontend React moderno e intuitivo

## 🛠️ Tecnologias

### Backend
- **Flask** - Framework web Python
- **SQLAlchemy** - ORM para banco de dados
- **PostgreSQL** - Banco de dados principal
- **Pandas** - Processamento de dados
- **ReportLab** - Geração de PDFs
- **lxml** - Processamento de XMLs

### Frontend
- **React 19** - Framework frontend
- **Vite** - Build tool
- **Tailwind CSS** - Framework CSS
- **shadcn/ui** - Componentes UI

## 📋 Pré-requisitos

- Python 3.11+
- Node.js 20+
- PostgreSQL (para produção)

## 🔧 Configuração

### Variáveis de Ambiente

Crie um arquivo `.env` na raiz do projeto backend:

```env
# Banco de dados
DATABASE_URL=postgresql://usuario:senha@host:porta/database

# API Mainô
MAINO_API_BASE_URL=https://api.maino.com.br
MAINO_EMAIL=seu_email@empresa.com
MAINO_PASSWORD=sua_senha
MAINO_APPLICATION_UID=seu_application_uid

# Flask
SECRET_KEY=sua_chave_secreta_aqui
FLASK_ENV=production
```

### Instalação Local

1. **Backend**:
```bash
cd opme-control-backend
python -m venv venv
source venv/bin/activate  # Linux/Mac
# ou
venv\Scripts\activate  # Windows
pip install -r requirements.txt
python src/main.py
```

2. **Frontend**:
```bash
cd opme-control-frontend
npm install
npm run dev
```

## 🚀 Deploy no Railway

### Backend

1. Conecte o repositório ao Railway
2. Configure as variáveis de ambiente no painel do Railway
3. O deploy será automático

### Frontend

1. Build do projeto:
```bash
npm run build
```

2. Deploy da pasta `dist` em um serviço de hospedagem estática

## 📊 Estrutura do Banco

### Tabelas Principais

- **nota_fiscal**: Dados das notas fiscais
- **item_nota_fiscal**: Itens das notas fiscais
- **saldo_material**: Controle de saldos por material/lote

### CFOPs Suportados

- **5917/6917**: Saída para consignação
- **1918/2918**: Retorno de consignação
- **1919/2919**: Retorno simbólico (materiais utilizados)
- **5114/6114**: Faturamento do utilizado

## 🔍 Endpoints da API

### Notas Fiscais
- `POST /api/notas-fiscais/upload-xml` - Upload de XML
- `POST /api/notas-fiscais/sync-maino` - Sincronização com Mainô
- `GET /api/notas-fiscais` - Listar notas fiscais

### Saldos
- `GET /api/saldos/consultar` - Consultar saldos
- `GET /api/saldos/cliente/{cnpj}` - Saldos por cliente
- `GET /api/saldos/buscar-clientes` - Autocomplete de clientes

### Exportação
- `GET /api/export/saldos/excel` - Exportar para Excel
- `GET /api/export/saldos/pdf` - Exportar para PDF

## 📝 Logs e Monitoramento

O sistema gera logs estruturados para:
- Processamento de XMLs
- Integração com API Mainô
- Cálculos de saldos
- Erros e exceções

## 🔒 Segurança

- Validação de XMLs antes do processamento
- Sanitização de dados de entrada
- Controle de divergências de saldos
- Logs de auditoria

## 📞 Suporte

Para dúvidas ou problemas, consulte a documentação ou entre em contato com a equipe de desenvolvimento.

---

**AkosMed** - Sistema de Controle de Materiais OPME

