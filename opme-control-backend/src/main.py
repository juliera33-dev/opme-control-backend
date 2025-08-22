import os
import sys
# DON'T CHANGE THIS !!!
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from flask import Flask, send_from_directory
from flask_cors import CORS
from src.models.user import db
from src.models.nota_fiscal import NotaFiscal, ItemNotaFiscal, SaldoMaterial
from src.routes.user import user_bp
from src.routes.notas_fiscais import notas_fiscais_bp
from src.routes.saldos import saldos_bp
from src.routes.export import export_bp
import logging

# Configuração de logging
logging.basicConfig(level=logging.INFO)

app = Flask(__name__, static_folder=os.path.join(os.path.dirname(__file__), 'static'))
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'asdf#FGSgvasgf$5$WGT')

# Configuração CORS para permitir acesso do frontend
CORS(app, origins="*")

# Registra blueprints
app.register_blueprint(user_bp, url_prefix='/api')
app.register_blueprint(notas_fiscais_bp, url_prefix='/api/notas-fiscais')
app.register_blueprint(saldos_bp, url_prefix='/api/saldos')
app.register_blueprint(export_bp, url_prefix='/api/export')

# Configuração do banco de dados
database_url = os.getenv('DATABASE_URL')
if database_url:
    # Para PostgreSQL no Railway
    if database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
else:
    # SQLite local para desenvolvimento
    app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{os.path.join(os.path.dirname(__file__), 'database', 'app.db')}"

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

db.init_app(app)

with app.app_context():
    db.create_all()

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve(path):
    static_folder_path = app.static_folder
    if static_folder_path is None:
            return "Static folder not configured", 404

    if path != "" and os.path.exists(os.path.join(static_folder_path, path)):
        return send_from_directory(static_folder_path, path)
    else:
        index_path = os.path.join(static_folder_path, 'index.html')
        if os.path.exists(index_path):
            return send_from_directory(static_folder_path, 'index.html')
        else:
            return "index.html not found", 404

@app.route('/api/health', methods=['GET'])
def health_check():
    """Endpoint para verificação de saúde da aplicação"""
    return {'status': 'ok', 'message': 'OPME Control API is running'}, 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
