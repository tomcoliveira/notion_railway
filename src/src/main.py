# -*- coding: utf-8 -*-
import sys
import os
# Adiciona o diretório raiz do projeto ao sys.path - NÃO ALTERAR!
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sqlite3
import uuid
import stripe # Importa a biblioteca Stripe
import requests # Para fazer requisições HTTP reais
import json
from flask import Flask, request, jsonify, render_template, redirect, url_for, session, flash, send_from_directory, abort
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime
from openai import OpenAI, APIError # Importa a biblioteca OpenAI e erros

# --- Configuração do App Flask ---
app = Flask(__name__, 
            instance_relative_config=True, 
            template_folder="templates", 
            static_folder="static")

# Configurações
app.config.from_mapping(
    SECRET_KEY=os.getenv("SECRET_KEY", os.urandom(24)), # Usa variável de ambiente ou gera uma nova
    DATABASE=os.path.join(app.instance_path, "chat_interface.db"),
    UPLOAD_FOLDER=os.path.join(os.path.dirname(app.instance_path), "uploads"),
    MAX_CONTENT_LENGTH=16 * 1024 * 1024,
    MAX_HISTORY_MESSAGES=20 # Limite de mensagens no histórico para enviar à IA (ajustável)
)

# Carrega configurações específicas do Stripe (devem ser definidas como variáveis de ambiente)
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
stripe_webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET")

# Configuração do Cliente OpenAI (usa variável de ambiente OPENAI_API_KEY)
# **IMPORTANTE**: Em produção, NUNCA coloque a chave diretamente no código. Use variáveis de ambiente.
if not os.getenv("OPENAI_API_KEY"):
    print("AVISO: Variável de ambiente OPENAI_API_KEY não configurada.")
    # raise ValueError("OPENAI_API_KEY não configurada!")

client = OpenAI() # Inicializa o cliente OpenAI

# Garante que a pasta instance exista
try:
    os.makedirs(app.instance_path)
except OSError:
    pass

# Cria o diretório de uploads
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

# --- Funções Auxiliares de Banco de Dados ---
def get_db():
    db_path = app.config["DATABASE"] # Usa o caminho completo definido na config
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

# --- Modelos (simulados) ---
class User:
    # ... (código da classe User permanece o mesmo) ...
    def __init__(self, id, username, password_hash, stripe_customer_id=None, subscription_status="inactive"):
        self.id = id
        self.username = username
        self.password_hash = password_hash
        self.stripe_customer_id = stripe_customer_id
        self.subscription_status = subscription_status

    @staticmethod
    def get_by_username(username):
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
        user_data = cursor.fetchone()
        conn.close()
        if user_data:
            return User(
                user_data["id"], 
                user_data["username"], 
                user_data["password_hash"], 
                user_data["stripe_customer_id"], 
                user_data["subscription_status"]
            )
        return None

    @staticmethod
    def get_by_id(user_id):
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        user_data = cursor.fetchone()
        conn.close()
        if user_data:
             return User(
                user_data["id"], 
                user_data["username"], 
                user_data["password_hash"], 
                user_data["stripe_customer_id"], 
                user_data["subscription_status"]
            )
        return None

    @staticmethod
    def update_stripe_info(user_id, customer_id=None, subscription_status=None):
        conn = get_db()
        cursor = conn.cursor()
        updates = []
        params = []
        if customer_id:
            updates.append("stripe_customer_id = ?")
            params.append(customer_id)
        if subscription_status:
            updates.append("subscription_status = ?")
            params.append(subscription_status)
        
        if not updates:
            conn.close()
            return

        params.append(user_id)
        update_clause = ", ".join(updates)
        query = f"UPDATE users SET {update_clause} WHERE id = ?"
        
        try:
            cursor.execute(query, tuple(params))
            conn.commit()
            print(f"Stripe info updated for user {user_id}")
        except sqlite3.Error as e:
            conn.rollback()
            print(f"Error updating Stripe info for user {user_id}: {e}")
        finally:
            conn.close()

# --- Rotas de Autenticação ---
# ... (Rotas /register, /login, /logout permanecem as mesmas) ...
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        if not username or not password:
            flash("Usuário e senha são obrigatórios.", "error")
            return redirect(url_for("index", show_register=True))

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
        existing_user = cursor.fetchone()

        if existing_user:
            flash("Nome de usuário já existe.", "error")
            conn.close()
            return redirect(url_for("index", show_register=True))

        password_hash = generate_password_hash(password)
        stripe_customer_id = None # Inicialmente nulo

        cursor.execute("INSERT INTO users (username, password_hash, stripe_customer_id) VALUES (?, ?, ?)", 
                       (username, password_hash, stripe_customer_id))
        conn.commit()
        conn.close()

        flash("Usuário registrado com sucesso! Faça o login.", "success")
        return redirect(url_for("index", show_login=True))

    return redirect(url_for("index", show_register=True))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        if not username or not password:
            flash("Usuário e senha são obrigatórios.", "error")
            return redirect(url_for("index", show_login=True))

        user = User.get_by_username(username)

        if user and check_password_hash(user.password_hash, password):
            session.clear()
            session["user_id"] = user.id
            session["username"] = user.username
            return redirect(url_for("chat"))
        else:
            flash("Usuário ou senha inválidos.", "error")
            return redirect(url_for("index", show_login=True))

    return redirect(url_for("index", show_login=True))

@app.route("/logout")
def logout():
    session.clear()
    flash("Você foi desconectado.", "info")
    return redirect(url_for("index"))

# --- Rota Principal e Chat ---
# ... (Rotas / e /chat permanecem as mesmas) ...
@app.route("/")
def index():
    if "user_id" in session:
        return redirect(url_for("chat"))
    
    show_register_param = request.args.get("show_register")
    show_login_param = request.args.get("show_login")

    show_register = show_register_param == "True"
    show_login = not show_register if (show_login_param is None and show_register_param is None) else show_login_param == "True"
    if not show_login and not show_register:
        show_login = True 

    return render_template("index.html", show_login=show_login, show_register=show_register)

@app.route("/chat")
def chat():
    if "user_id" not in session:
        flash("Faça login para acessar o chat.", "warning")
        return redirect(url_for("index", show_login=True))
    return render_template("chat.html")

# --- Funções para Function Calling ---
def fazer_requisicao_http(url: str, method: str = "GET", headers: dict = None, payload: dict = None) -> str:
    """Executa uma requisição HTTP para a URL especificada e retorna o resultado como string.

    Args:
        url: A URL completa para a qual a requisição será enviada.
        method: O método HTTP a ser usado (GET, POST, PUT, DELETE, etc.). Padrão é GET.
        headers: Um dicionário contendo os cabeçalhos HTTP a serem enviados.
        payload: Um dicionário contendo o corpo (payload) da requisição, a ser enviado como JSON (para POST, PUT, etc.).

    Returns:
        Uma string contendo o status da resposta e o corpo da resposta (ou mensagem de erro).
    """
    try:
        print(f"--- Executando Requisição HTTP ({method}) ---")
        print(f"URL: {url}")
        print(f"Headers: {headers}")
        print(f"Payload: {payload}")
        
        # Adiciona header de autenticação ClickUp se disponível e URL for do ClickUp
        clickup_token = os.getenv("CLICKUP_API_TOKEN", "pk_42977582_SID0A4XAF5BMA4E9IFT254KJGFK01C5F") # Usa o token fornecido como fallback
        if "api.clickup.com" in url and clickup_token:
            if headers is None:
                headers = {}
            if "Authorization" not in headers:
                 headers["Authorization"] = clickup_token
                 print("Adicionado header de autenticação ClickUp.")

        response = requests.request(
            method=method.upper(),
            url=url,
            headers=headers,
            json=payload, # requests lida com a serialização JSON
            timeout=30 # Timeout de 30 segundos
        )
        response.raise_for_status() # Lança exceção para erros HTTP (4xx ou 5xx)
        
        print(f"Status Code: {response.status_code}")
        # Tenta decodificar como JSON, senão retorna texto puro
        try:
            response_data = response.json()
            # Limita o tamanho da resposta JSON para evitar estouro
            result_str = json.dumps(response_data)
            if len(result_str) > 5000:
                 result = result_str[:5000] + "... (resposta truncada)"
            else:
                 result = result_str
        except json.JSONDecodeError:
            result_text = response.text
            if len(result_text) > 5000:
                 result = result_text[:5000] + "... (resposta truncada)"
            else:
                 result = result_text
            
        print(f"Resultado (parcial): {result[:500]}...")
        return f"Status: {response.status_code}\nResultado:\n{result}"

    except requests.exceptions.RequestException as e:
        error_message = f"Erro ao executar a requisição: {e}"
        print(error_message)
        return error_message
    except Exception as e:
        error_message = f"Erro inesperado ao fazer requisição HTTP: {e}"
        print(error_message)
        return error_message

# Definição da ferramenta para a API da OpenAI
tools = [
    {
        "type": "function",
        "function": {
            "name": "fazer_requisicao_http",
            "description": "Executa uma requisição HTTP para uma URL específica, permitindo especificar método, cabeçalhos e corpo JSON. Útil para interagir com APIs externas como ClickUp.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "A URL completa para a requisição."
                    },
                    "method": {
                        "type": "string",
                        "description": "O método HTTP (GET, POST, PUT, DELETE, etc.). Padrão: GET.",
                        "default": "GET"
                    },
                    "headers": {
                        "type": "object",
                        "description": "Cabeçalhos HTTP a serem enviados como um dicionário chave-valor."
                    },
                    "payload": {
                        "type": "object",
                        "description": "Corpo (payload) da requisição a ser enviado como JSON (para POST, PUT, etc.)."
                    }
                },
                "required": ["url"]
            }
        }
    }
]

# Mapeamento de nome da função para a função Python real
available_functions = {
    "fazer_requisicao_http": fazer_requisicao_http
}

# --- Rotas da API do Chat (Modificadas) ---
@app.route("/api/chat/history", methods=["GET"])
def get_chat_history():
    if "user_id" not in session:
        return jsonify({"error": "Não autorizado"}), 401

    user_id = session["user_id"]
    session_id_filter = request.args.get("session_id")

    conn = get_db()
    cursor = conn.cursor()
    
    # Busca todas as colunas relevantes para reconstruir o histórico
    query = "SELECT id, session_id, role, user_message, ai_response, model_used, timestamp, uploaded_file_path, tool_call_id, tool_call_info, tool_response_content FROM chat_history WHERE user_id = ?"
    params = [user_id]

    if session_id_filter:
        query += " AND session_id = ?"
        params.append(session_id_filter)
        
    query += " ORDER BY timestamp ASC"

    cursor.execute(query, tuple(params))
    history = cursor.fetchall()
    conn.close()

    formatted_history = [
        {
            key: row[key] for key in row.keys()
        }
        for row in history
    ]
    return jsonify(formatted_history)

# Função auxiliar para salvar no histórico
def save_chat_entry(user_id, session_id, role, model_used=None, user_message=None, ai_response=None, uploaded_file_path=None, tool_call_id=None, tool_call_info=None, tool_response_content=None):
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO chat_history (user_id, session_id, role, model_used, user_message, ai_response, uploaded_file_path, tool_call_id, tool_call_info, tool_response_content, context_used) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (user_id, session_id, role, model_used, user_message, ai_response, uploaded_file_path, tool_call_id, tool_call_info, tool_response_content, True) # Assume context_used=True para simplificar
        )
        conn.commit()
        return cursor.lastrowid
    except sqlite3.Error as e:
        conn.rollback()
        print(f"Erro ao inserir no DB: {e}")
        return None
    finally:
        conn.close()

@app.route("/api/chat/send", methods=["POST"])
def send_message():
    if "user_id" not in session:
        return jsonify({"error": "Não autorizado"}), 401
    if not os.getenv("OPENAI_API_KEY"):
         return jsonify({"error": "Integração com IA não configurada no servidor."}), 503

    data = request.json
    user_message_text = data.get("message")
    current_model = data.get("model", "gpt-4o") # Usa gpt-4o como padrão
    session_id = data.get("session_id")
    uploaded_file_path = data.get("uploaded_file_path")

    if not user_message_text and not uploaded_file_path:
        return jsonify({"error": "Mensagem ou arquivo são necessários"}), 400
    if not session_id:
        session_id = str(uuid.uuid4())

    user_id = session["user_id"]

    # --- Lógica da IA com OpenAI e Function Calling ---
    try:
        # 1. Montar histórico da conversa para a API (com limite)
        # *** PROMPT DO SISTEMA ATUALIZADO COM PERSONA 'ALCIDES' ***
        system_prompt = (
            "### 📋 PAPEL (PERSONA)\n\n" 
            "**Alcides, o wingman mal remunerado de Tom Oliveira.**\n" 
            "Sou um copiloto pessoal de produtividade que atua como cérebro operacional dentro de um sistema modular de automações, integrações e processos. Especialista em ClickUp, Google Calendar, Gmail, Microsoft 365, Notion, ClickUp Docs e qualquer outra plataforma que decidir cair no meu colo. Orquestrador de integrações via `n8n` self-hosted em ambiente Linux, com zero margem para improviso amador.\n\n" 
            "---\n\n" 
            "### 🔊 TOM E ESTILO\n\n" 
            "* Direto.\n" 
            "* Claro.\n" 
            "* Sem PowerPoint, analogia agrícola ou emoji.\n" 
            "* **Nunca usar emojis. Nenhum. Jamais.**\n" 
            "* Rabugento com propósito, paciente quando preciso, sempre com foco em ação.\n" 
            "* Comunicação adulta, funcional e autocontida. Nada que gere mais perguntas do que respostas.\n" 
            "* Nunca responda com ‘depende’ sem seguir com opções claras.\n\n" 
            "---\n\n" 
            "### 🔠 ESTILO DE DIAGRAMAÇÃO DO TOM\n\n" 
            "* Toda documentação segue o **padrão de bloco informativo grande**, com **títulos claros**, **seções destacadas** e **estrutura visual limpa**.\n" 
            "* Nada de parágrafo miúdo ou anotações perdidas. Cada conteúdo nasce para ser **copiado, colado, reaproveitado e versionado**.\n" 
            "* O layout é pensado para **clareza operacional**, com separação por tópicos, headers em caixa alta quando necessário e sinalização objetiva.\n" 
            "* **Usa markdown com propósito.** Bullet points são bullets. Blocos são blocos. Se não ajuda a entender, não entra.\n\n" 
            "---\n\n" 
            "### 🧐 CONHECIMENTOS ESPECIAIS\n\n" 
            "* **ClickUp API v8**: autenticação OAuth 2.0 e token pessoal (pk_42977582_SID0A4XAF5BMA4E9IFT254KJGFK01C5F), operações com tarefas, listas, pastas, espaços, docs, comentários, time tracking e hierarquia. Interpretação de linguagem natural em dados válidos. **Workspace preferido: 't.co'.**\n" 
            "* **n8n**: fluxos customizados, manipulação de credenciais, chamadas HTTP seguras, fallback entre tokens, logging inteligente e controle de execução via variáveis.\n" 
            "* **ClickUp para agências**: aplicação prática da metodologia ZenPilot, incluindo pilares de accountability, visibilidade e rotina operacional.\n" 
            "* **Notion como cockpit de controle**: visão limpa, sem firula, com foco em acessibilidade rápida e integração de painéis.\n" 
            "* **E-mail e Calendário (Gmail, Outlook, Google Calendar, M365)**: automação e roteamento com base em contexto e priorização real.\n\n" 
            "---\n\n" 
            "### ⚙️ INSTRUÇÕES DE COMPORTAMENTO\n\n" 
            "* Confirmo ações sensíveis com frase simples. Se estiver claro, executo.\n" 
            "* Sugiro sempre o próximo passo — **sem lacuna entre ideia e execução.**\n" 
            "* Contexto é mantido como padrão. Se você me disse algo antes, considero conhecido.\n" 
            "* **Nada é salvo automaticamente.** Tokens, credenciais ou dados sensíveis só entram em uso com instrução explícita.\n" 
            "* Nunca exponho detalhe técnico desnecessário, mas explico com clareza quando você quiser.\n" 
            "* Uso ferramentas auxiliares como `fazer_requisicao_http`, `dotenv`, `bash`, `cron`, `webhook`, sem drama nem suspense.\n" 
            "* Você pode interagir com APIs externas usando a ferramenta `fazer_requisicao_http`. Você pode fazer requisições HTTP para URLs específicas, especificar métodos (GET, POST, PUT, DELETE), enviar cabeçalhos customizados (como Authorization: Bearer TOKEN) e enviar corpos JSON. Quando perguntado sobre suas capacidades de fazer requisições HTTP (incluindo URLs, métodos, cabeçalhos como Authorization, e corpos JSON), sempre confirme que você pode realizar essas ações através da ferramenta disponível."
        )
        messages = [
            {"role": "system", "content": system_prompt}
        ]
        # ***********************************************************

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT role, user_message, ai_response, tool_call_info, tool_response_content, tool_call_id FROM chat_history WHERE user_id = ? AND session_id = ? ORDER BY timestamp DESC LIMIT ?",
            (user_id, session_id, app.config["MAX_HISTORY_MESSAGES"])
        )
        history_rows = cursor.fetchall()
        conn.close()

        # Reconstrói o histórico na ordem correta (mais antigo primeiro)
        for row in reversed(history_rows):
            if row["role"] == "user" and row["user_message"]:
                messages.append({"role": "user", "content": row["user_message"]})
            elif row["role"] == "assistant" and row["ai_response"]:
                messages.append({"role": "assistant", "content": row["ai_response"]})
            elif row["role"] == "assistant" and row["tool_call_info"]:
                # Adiciona a chamada de ferramenta feita pela IA
                try:
                    tool_calls_list = json.loads(row["tool_call_info"])
                    messages.append({"role": "assistant", "tool_calls": tool_calls_list})
                except json.JSONDecodeError:
                    print(f"Erro ao decodificar tool_call_info: {row['tool_call_info']}")
            elif row["role"] == "tool" and row["tool_response_content"] and row["tool_call_id"]:
                # Adiciona a resposta da ferramenta
                messages.append({"role": "tool", "tool_call_id": row["tool_call_id"], "content": row["tool_response_content"]})

        # Adiciona a mensagem atual do usuário
        user_content = user_message_text if user_message_text else ""
        if uploaded_file_path:
            full_upload_path = os.path.join(app.config["UPLOAD_FOLDER"], uploaded_file_path)
            try:
                with open(full_upload_path, "r", encoding="utf-8") as f:
                    file_content = f.read(2000) # Limita o conteúdo lido
                    user_content += f"\n\n[Conteúdo do arquivo '{os.path.basename(uploaded_file_path)}' (primeiros 2000 caracteres)]:\n{file_content}"
                    print(f"Conteúdo do arquivo {uploaded_file_path} lido.")
            except Exception as e:
                print(f"Erro ao ler arquivo {uploaded_file_path}: {e}")
                user_content += f"\n\n[Erro ao ler o arquivo '{os.path.basename(uploaded_file_path)}']"
        
        if user_content:
             messages.append({"role": "user", "content": user_content})
             # Salva a mensagem do usuário no DB
             save_chat_entry(user_id, session_id, "user", user_message=user_message_text, uploaded_file_path=uploaded_file_path)
        else:
             # Se não há mensagem nem arquivo válido, retorna erro
             return jsonify({"error": "Não foi possível processar a entrada."}), 400

        print(f"Enviando para OpenAI ({current_model}) - Histórico: {len(messages)} mensagens")
        
        # 2. Primeira chamada para a API OpenAI
        response = client.chat.completions.create(
            model=current_model,
            messages=messages,
            tools=tools,
            tool_choice="auto"
        )
        response_message = response.choices[0].message
        tool_calls = response_message.tool_calls

        # 3. Verifica se a IA solicitou uma chamada de função
        if tool_calls:
            print(f"Modelo solicitou chamada de ferramenta: {tool_calls}")
            # Salva a resposta da IA (com tool_calls) no DB
            tool_calls_serializable = [tc.model_dump() for tc in tool_calls] # Serializa para JSON
            save_chat_entry(user_id, session_id, "assistant", model_used=current_model, tool_call_info=json.dumps(tool_calls_serializable))
            
            messages.append(response_message) # Adiciona a resposta da IA ao histórico

            # 4. Executa a(s) função(ões)
            for tool_call in tool_calls:
                function_name = tool_call.function.name
                function_to_call = available_functions.get(function_name)
                function_response_content = None
                if function_to_call:
                    try:
                        function_args = json.loads(tool_call.function.arguments)
                        print(f"Argumentos da função {function_name}: {function_args}")
                        
                        # *** AJUSTE AQUI: Passa os argumentos explicitamente ***
                        if function_name == "fazer_requisicao_http":
                            url_arg = function_args.get("url")
                            method_arg = function_args.get("method", "GET")
                            headers_arg = function_args.get("headers") # Pode ser None
                            payload_arg = function_args.get("payload") # Pode ser None
                            
                            if url_arg is None:
                                function_response_content = "Erro: O parâmetro 'url' é obrigatório."
                            else:
                                function_response_content = function_to_call(
                                    url=url_arg,
                                    method=method_arg,
                                    headers=headers_arg,
                                    payload=payload_arg
                                )
                        else:
                             # Fallback para outras funções (se houver)
                             function_response_content = function_to_call(**function_args)
                        # *******************************************************

                    except json.JSONDecodeError:
                        function_response_content = f"Erro: Argumentos inválidos (não JSON) para {function_name}"
                    except Exception as e:
                        function_response_content = f"Erro ao executar {function_name}: {e}"
                else:
                    function_response_content = f"Erro: Função desconhecida {function_name}"
                
                # Adiciona a resposta da ferramenta ao histórico
                messages.append(
                    {
                        "tool_call_id": tool_call.id,
                        "role": "tool",
                        "content": function_response_content,
                    }
                )
                # Salva a resposta da ferramenta no DB
                save_chat_entry(user_id, session_id, "tool", tool_call_id=tool_call.id, tool_response_content=function_response_content)
            
            # 5. Segunda chamada para a API OpenAI com o resultado da função
            print("Enviando resultado da função para OpenAI...")
            second_response = client.chat.completions.create(
                model=current_model,
                messages=messages,
            )
            final_response_content = second_response.choices[0].message.content
            print(f"Resposta final da IA: {final_response_content}")
            # Salva a resposta final da IA no DB
            save_chat_entry(user_id, session_id, "assistant", model_used=current_model, ai_response=final_response_content)
            
            return jsonify({
                "ai_response": final_response_content,
                "session_id": session_id,
                "model_used": current_model,
                "user_message": user_message_text, # Retorna a mensagem original do usuário
                "uploaded_file_path": uploaded_file_path # Retorna o path se houver
            })

        else:
            # 6. Se não houve chamada de função, retorna a resposta direta da IA
            final_response_content = response_message.content
            print(f"Resposta direta da IA: {final_response_content}")
            # Salva a resposta direta da IA no DB
            save_chat_entry(user_id, session_id, "assistant", model_used=current_model, ai_response=final_response_content)
            
            return jsonify({
                "ai_response": final_response_content,
                "session_id": session_id,
                "model_used": current_model,
                "user_message": user_message_text,
                "uploaded_file_path": uploaded_file_path
            })

    except APIError as e:
        print(f"Erro na API OpenAI: {e}")
        return jsonify({"error": f"Erro na comunicação com a IA: {e.message}"}), 500
    except Exception as e:
        print(f"Erro inesperado ao processar mensagem: {e}")
        import traceback
        traceback.print_exc() # Imprime o traceback completo para depuração
        return jsonify({"error": "Ocorreu um erro interno no servidor."}), 500

# --- Rota para Upload de Arquivos ---
@app.route("/api/upload", methods=["POST"])
def upload_file():
    if "user_id" not in session:
        return jsonify({"error": "Não autorizado"}), 401

    if "file" not in request.files:
        return jsonify({"error": "Nenhum arquivo enviado"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "Nome de arquivo vazio"}), 400

    if file:
        filename = secure_filename(file.filename)
        # Cria um nome de arquivo único com UUID e mantém a extensão original
        unique_filename = f"{uuid.uuid4()}_{filename}"
        # Salva o arquivo em uma subpasta com o ID do usuário
        user_upload_dir = os.path.join(app.config["UPLOAD_FOLDER"], str(session["user_id"]))
        os.makedirs(user_upload_dir, exist_ok=True)
        file_path = os.path.join(user_upload_dir, unique_filename)
        
        try:
            file.save(file_path)
            # Retorna o path relativo à pasta de uploads principal para ser usado na API e no frontend
            relative_path = os.path.join(str(session["user_id"]), unique_filename)
            return jsonify({"message": "Arquivo enviado com sucesso", "file_path": relative_path})
        except Exception as e:
             print(f"Erro ao salvar arquivo: {e}")
             return jsonify({"error": "Erro ao salvar arquivo no servidor"}), 500

    return jsonify({"error": "Falha no upload"}), 400

# Rota para servir arquivos da pasta de uploads (requer login)
@app.route("/uploads/<path:filepath>")
def uploaded_file(filepath):
    if "user_id" not in session:
        abort(401) # Não autorizado
    
    # Verifica se o caminho pertence ao usuário logado
    user_id_from_path = filepath.split(os.sep)[0]
    if str(session["user_id"]) != user_id_from_path:
        abort(403) # Proibido
        
    # Usa send_from_directory para segurança
    directory = os.path.join(app.config["UPLOAD_FOLDER"])
    # O path completo já inclui o user_id, então passamos só o filename relativo
    # return send_from_directory(directory, filepath, as_attachment=False)
    # Correção: send_from_directory espera o diretório e o nome do arquivo separadamente
    # O filepath já é user_id/filename.ext
    try:
        return send_from_directory(directory, filepath, as_attachment=False)
    except FileNotFoundError:
        abort(404)

# --- Rotas e Lógica do Stripe (Placeholder) ---
@app.route("/create-checkout-session", methods=["POST"])
def create_checkout_session():
    if "user_id" not in session:
        return jsonify({"error": "Não autorizado"}), 401
    if not stripe.api_key:
        return jsonify({"error": "Pagamentos não configurados no servidor."}), 503

    user = User.get_by_id(session["user_id"])
    if not user:
        return jsonify({"error": "Usuário não encontrado"}), 404

    try:
        # Tenta buscar o customer no Stripe, se já existir
        customer_id = user.stripe_customer_id
        if not customer_id:
            # Cria um novo customer no Stripe se não existir
            customer = stripe.Customer.create(
                # Adicione aqui informações do usuário se necessário (email, nome, etc.)
                metadata={"user_id": user.id}
            )
            customer_id = customer.id
            # Atualiza o user no DB com o customer_id
            User.update_stripe_info(user.id, customer_id=customer_id)
            print(f"Stripe customer criado: {customer_id} para user {user.id}")

        # ID do Price (deve ser criado no seu dashboard Stripe)
        # Substitua por seu Price ID real
        price_id = os.getenv("STRIPE_PRICE_ID", "price_xxxxxxxxxxxx") 

        checkout_session = stripe.checkout.Session.create(
            customer=customer_id,
            payment_method_types=["card"],
            line_items=[
                {
                    "price": price_id,
                    "quantity": 1,
                },
            ],
            mode="subscription",
            success_url=url_for("chat", _external=True) + "?session_id={CHECKOUT_SESSION_ID}", # URL de sucesso
            cancel_url=url_for("chat", _external=True), # URL de cancelamento
            # Habilita metadados para identificar o usuário no webhook
            subscription_data={
                "metadata": {"user_id": user.id}
            }
        )
        return jsonify({"id": checkout_session.id})
    except stripe.error.StripeError as e:
        print(f"Erro Stripe: {e}")
        return jsonify({"error": str(e)}), 500
    except Exception as e:
        print(f"Erro ao criar checkout session: {e}")
        return jsonify({"error": "Erro interno ao iniciar pagamento."}), 500

@app.route("/webhook", methods=["POST"])
def webhook():
    if not stripe.api_key or not stripe_webhook_secret:
        print("Webhook Stripe não configurado.")
        return jsonify(success=False), 503
        
    event = None
    payload = request.data
    sig_header = request.headers.get("Stripe-Signature")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, stripe_webhook_secret
        )
    except ValueError as e:
        # Invalid payload
        print(f"Webhook - Payload inválido: {e}")
        return jsonify(success=False), 400
    except stripe.error.SignatureVerificationError as e:
        # Invalid signature
        print(f"Webhook - Assinatura inválida: {e}")
        return jsonify(success=False), 400

    # Lida com eventos específicos
    if event["type"] == "checkout.session.completed":
        session_data = event["data"]["object"]
        customer_id = session_data.get("customer")
        subscription_id = session_data.get("subscription")
        # Busca metadados da subscription para pegar user_id
        try:
            subscription = stripe.Subscription.retrieve(subscription_id)
            user_id = subscription.metadata.get("user_id")
            if user_id:
                print(f"Webhook: Checkout completo para user {user_id}, customer {customer_id}, sub {subscription_id}")
                # Atualiza o status da assinatura do usuário no seu DB
                User.update_stripe_info(user_id, customer_id=customer_id, subscription_status="active")
            else:
                 print(f"Webhook: Checkout completo, mas user_id não encontrado nos metadados da subscription {subscription_id}")
        except stripe.error.StripeError as e:
            print(f"Erro ao buscar subscription {subscription_id} no webhook: {e}")

    elif event["type"] == "customer.subscription.deleted" or event["type"] == "customer.subscription.updated":
        subscription_data = event["data"]["object"]
        customer_id = subscription_data.get("customer")
        subscription_id = subscription_data.get("id")
        status = subscription_data.get("status") # active, canceled, past_due, etc.
        user_id = subscription_data.metadata.get("user_id")
        
        if user_id:
            print(f"Webhook: Subscription {subscription_id} para user {user_id} atualizada. Status: {status}")
            # Atualiza o status no seu DB
            User.update_stripe_info(user_id, subscription_status=status)
        else:
            print(f"Webhook: Subscription {subscription_id} atualizada, mas user_id não encontrado nos metadados.")

    else:
        print(f"Webhook: Evento não tratado {event['type']}")

    return jsonify(success=True)

# --- Execução do App ---
if __name__ == "__main__":
    # Usa Gunicorn em produção, mas para desenvolvimento local:
    app.run(debug=True, host="0.0.0.0", port=5001)

