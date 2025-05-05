# -*- coding: utf-8 -*-
import pytest
import os
import tempfile
import sys

# Adiciona o diretório raiz do projeto ao sys.path para encontrar o módulo src
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, project_root)

# Define uma chave de API de teste ANTES de importar o app
os.environ["OPENAI_API_KEY"] = "dummy_key_for_testing"

# Agora importa o app de src.main
from src.main import app as flask_app
from src.main import get_db # Importa get_db

@pytest.fixture
def app(monkeypatch):
    """Create and configure a new app instance for each test."""
    # Cria um arquivo de banco de dados temporário
    db_fd, db_path = tempfile.mkstemp()
    # Cria uma pasta instance temporária
    instance_path = tempfile.mkdtemp()

    # Configura o app para usar o DB temporário e a pasta instance
    flask_app.config.update({
        "TESTING": True,
        "DATABASE": db_path,
        "SECRET_KEY": "test_secret_key", # Chave fixa para testes
        "WTF_CSRF_ENABLED": False, # Desabilita CSRF para testes de formulário mais fáceis
        "UPLOAD_FOLDER": os.path.join(instance_path, "uploads"),
        "INSTANCE_PATH": instance_path # Define o instance_path explicitamente
    })

    # Garante que a pasta de uploads exista dentro da instance temporária
    os.makedirs(flask_app.config["UPLOAD_FOLDER"], exist_ok=True)

    # Cria as tabelas do banco de dados
    try:
        with flask_app.app_context():
            conn = get_db()
            cursor = conn.cursor()
            # Replicando lógica simplificada de init_db.py
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                stripe_customer_id TEXT NULL,
                subscription_status TEXT DEFAULT 'inactive'
            );
            """)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS chat_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL, 
                user_message TEXT NULL, 
                ai_response TEXT NULL, 
                model_used TEXT NULL,
                context_used BOOLEAN DEFAULT 0,
                uploaded_file_path TEXT NULL,
                tool_call_id TEXT NULL, 
                tool_call_info TEXT NULL, 
                tool_response_content TEXT NULL, 
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            );
            """)
            conn.commit()
            conn.close()
    except Exception as e:
        print(f"Erro ao inicializar DB no teste: {e}")

    yield flask_app

    # Limpeza após o teste
    os.close(db_fd)
    os.unlink(db_path)
    import shutil
    shutil.rmtree(instance_path)

@pytest.fixture
def client(app):
    """A test client for the app."""
    return app.test_client()

@pytest.fixture
def runner(app):
    """A test runner for the app's Click commands."""
    return app.test_cli_runner()

# Fixture para simular login
@pytest.fixture
def auth_client(client):
    """Um cliente de teste já autenticado."""
    # Registra um usuário de teste
    client.post("/register", data={"username": "testuser", "password": "password"}, follow_redirects=True)
    # Faz login com o usuário de teste
    client.post("/login", data={"username": "testuser", "password": "password"}, follow_redirects=True)
    return client

