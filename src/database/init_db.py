import sqlite3
import os

# Define o caminho para o diretório instance e o arquivo do banco de dados
instance_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "instance")
db_path = os.path.join(instance_path, "chat_interface.db")

# Garante que o diretório instance exista
os.makedirs(instance_path, exist_ok=True)

# Conecta ao banco de dados (será criado se não existir)
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Cria a tabela de usuários (se não existir)
cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    stripe_customer_id TEXT NULL,
    subscription_status TEXT DEFAULT 'inactive'
);
""")

# Cria a tabela de histórico de chat (se não existir)
# Adiciona colunas para suportar roles e function calling
cursor.execute("""
CREATE TABLE IF NOT EXISTS chat_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL, -- 'user', 'assistant', 'system', 'tool'
    user_message TEXT NULL, -- Mensagem original do usuário (se role='user')
    ai_response TEXT NULL, -- Resposta final do assistente (se role='assistant' e sem tool call)
    model_used TEXT NULL,
    context_used BOOLEAN DEFAULT 0,
    uploaded_file_path TEXT NULL,
    tool_call_id TEXT NULL, -- ID da chamada de ferramenta (se role='tool' ou role='assistant' com tool_calls)
    tool_call_info TEXT NULL, -- JSON string das tool_calls (se role='assistant') ou nome da função (se role='tool')
    tool_response_content TEXT NULL, -- Conteúdo da resposta da ferramenta (se role='tool')
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users (id)
);
""")

# Verifica e adiciona colunas ausentes (migração simples)
def add_column_if_not_exists(table, column, col_type):
    cursor.execute(f"PRAGMA table_info({table})")
    columns = [col[1] for col in cursor.fetchall()]
    if column not in columns:
        try:
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")
            print(f"Coluna '{column}' adicionada à tabela '{table}'.")
        except sqlite3.OperationalError as e:
            print(f"Erro ao adicionar coluna '{column}' à tabela '{table}': {e}")

add_column_if_not_exists("chat_history", "role", "TEXT NOT NULL DEFAULT 'user'")
add_column_if_not_exists("chat_history", "tool_call_id", "TEXT NULL")
add_column_if_not_exists("chat_history", "tool_call_info", "TEXT NULL")
add_column_if_not_exists("chat_history", "tool_response_content", "TEXT NULL")

# Salva as alterações e fecha a conexão
conn.commit()
conn.close()

print(f"Banco de dados '{db_path}' inicializado/atualizado com sucesso.")

