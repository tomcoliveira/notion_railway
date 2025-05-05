import sqlite3
import os

# Define o caminho para o banco de dados
DATABASE_DIR = os.path.join(os.path.dirname(__file__), '..', 'database')
DATABASE_PATH = os.path.join(DATABASE_DIR, 'chat_interface.db')

# Cria o diretório do banco de dados se não existir
os.makedirs(DATABASE_DIR, exist_ok=True)

# Conecta ao banco de dados (cria o arquivo se não existir)
conn = sqlite3.connect(DATABASE_PATH)
cursor = conn.cursor()

# Cria a tabela de usuários
cursor.execute('''
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    stripe_customer_id TEXT, -- Para futura integração com Stripe
    subscription_status TEXT DEFAULT 'inactive' -- Para futura integração com Stripe
);
''')

# Cria a tabela de histórico de chat
cursor.execute('''
CREATE TABLE IF NOT EXISTS chat_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    session_id TEXT NOT NULL, -- Para agrupar mensagens de uma conversa
    user_message TEXT,
    ai_response TEXT,
    model_used TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    context_used BOOLEAN DEFAULT FALSE,
    uploaded_file_path TEXT, -- Para associar arquivos enviados
    FOREIGN KEY (user_id) REFERENCES users (id)
);
''')

# Cria a tabela de sessões (opcional, mas útil para nomear sessões no futuro)
cursor.execute('''
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY, -- Usar UUID ou similar
    user_id INTEGER NOT NULL,
    session_name TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users (id)
);
''')


print(f"Banco de dados inicializado em {DATABASE_PATH}")

# Salva as alterações e fecha a conexão
conn.commit()
conn.close()

