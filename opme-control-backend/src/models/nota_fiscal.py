from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from src.models.user import db

class NotaFiscal(db.Model):
    __tablename__ = 'notas_fiscais'
    
    id = db.Column(db.Integer, primary_key=True)
    numero = db.Column(db.String(20), nullable=False)
    serie = db.Column(db.String(10), nullable=False)
    chave_acesso = db.Column(db.String(44), unique=True, nullable=False)
    data_emissao = db.Column(db.DateTime, nullable=False)
    cfop = db.Column(db.String(4), nullable=False)
    tipo_operacao = db.Column(db.String(20), nullable=False)  # saida, retorno, simbolico, faturamento
    
    # Dados do destinatário/remetente
    destinatario_cnpj = db.Column(db.String(14), nullable=False)
    destinatario_nome = db.Column(db.String(255), nullable=False)
    
    # Metadados
    xml_content = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relacionamento com itens
    itens = db.relationship('ItemNotaFiscal', backref='nota_fiscal', lazy=True, cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<NotaFiscal {self.numero}/{self.serie}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'numero': self.numero,
            'serie': self.serie,
            'chave_acesso': self.chave_acesso,
            'data_emissao': self.data_emissao.isoformat() if self.data_emissao else None,
            'cfop': self.cfop,
            'tipo_operacao': self.tipo_operacao,
            'destinatario_cnpj': self.destinatario_cnpj,
            'destinatario_nome': self.destinatario_nome,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'itens': [item.to_dict() for item in self.itens]
        }

class ItemNotaFiscal(db.Model):
    __tablename__ = 'itens_nota_fiscal'
    
    id = db.Column(db.Integer, primary_key=True)
    nota_fiscal_id = db.Column(db.Integer, db.ForeignKey('notas_fiscais.id'), nullable=False)
    
    # Dados do produto
    codigo_produto = db.Column(db.String(50), nullable=False)
    descricao_produto = db.Column(db.String(500), nullable=False)
    quantidade = db.Column(db.Numeric(15, 4), nullable=False)
    valor_unitario = db.Column(db.Numeric(15, 4))
    valor_total = db.Column(db.Numeric(15, 2))
    
    # Dados do lote
    numero_lote = db.Column(db.String(50))
    data_fabricacao = db.Column(db.Date)
    data_validade = db.Column(db.Date)
    
    # Metadados
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<ItemNotaFiscal {self.codigo_produto} - Lote: {self.numero_lote}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'nota_fiscal_id': self.nota_fiscal_id,
            'codigo_produto': self.codigo_produto,
            'descricao_produto': self.descricao_produto,
            'quantidade': float(self.quantidade) if self.quantidade else 0,
            'valor_unitario': float(self.valor_unitario) if self.valor_unitario else 0,
            'valor_total': float(self.valor_total) if self.valor_total else 0,
            'numero_lote': self.numero_lote,
            'data_fabricacao': self.data_fabricacao.isoformat() if self.data_fabricacao else None,
            'data_validade': self.data_validade.isoformat() if self.data_validade else None,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

class SaldoMaterial(db.Model):
    __tablename__ = 'saldos_materiais'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Chaves de identificação
    cliente_cnpj = db.Column(db.String(14), nullable=False)
    cliente_nome = db.Column(db.String(255), nullable=False)
    codigo_produto = db.Column(db.String(50), nullable=False)
    descricao_produto = db.Column(db.String(500), nullable=False)
    numero_lote = db.Column(db.String(50), nullable=False)
    
    # Referência da NF de saída original
    nf_saida_numero = db.Column(db.String(20), nullable=False)
    nf_saida_serie = db.Column(db.String(10), nullable=False)
    nf_saida_chave = db.Column(db.String(44), nullable=False)
    
    # Quantidades
    quantidade_enviada = db.Column(db.Numeric(15, 4), nullable=False, default=0)
    quantidade_retornada = db.Column(db.Numeric(15, 4), nullable=False, default=0)
    quantidade_utilizada = db.Column(db.Numeric(15, 4), nullable=False, default=0)
    quantidade_faturada = db.Column(db.Numeric(15, 4), nullable=False, default=0)
    
    # Metadados
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Índices únicos para evitar duplicatas
    __table_args__ = (
        db.UniqueConstraint('cliente_cnpj', 'codigo_produto', 'numero_lote', 'nf_saida_chave', 
                          name='_cliente_produto_lote_nf_uc'),
    )
    
    @property
    def saldo_disponivel(self):
        """Calcula o saldo disponível (enviado - retornado - utilizado)"""
        return float(self.quantidade_enviada) - float(self.quantidade_retornada) - float(self.quantidade_utilizada)
    
    def __repr__(self):
        return f'<SaldoMaterial {self.cliente_cnpj} - {self.codigo_produto} - Lote: {self.numero_lote}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'cliente_cnpj': self.cliente_cnpj,
            'cliente_nome': self.cliente_nome,
            'codigo_produto': self.codigo_produto,
            'descricao_produto': self.descricao_produto,
            'numero_lote': self.numero_lote,
            'nf_saida_numero': self.nf_saida_numero,
            'nf_saida_serie': self.nf_saida_serie,
            'nf_saida_chave': self.nf_saida_chave,
            'quantidade_enviada': float(self.quantidade_enviada),
            'quantidade_retornada': float(self.quantidade_retornada),
            'quantidade_utilizada': float(self.quantidade_utilizada),
            'quantidade_faturada': float(self.quantidade_faturada),
            'saldo_disponivel': self.saldo_disponivel,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

