# Interface de Chat Multi-Modelo com Flask

Este projeto implementa uma interface web de chat que permite interagir com diferentes modelos de IA (simulados), com funcionalidades de registro/login de usuários, histórico de conversas persistente, upload de arquivos e preparação para integração com pagamentos via Stripe.

## Funcionalidades

*   **Autenticação de Usuários:** Sistema de registro e login seguro.
*   **Interface de Chat:** Permite enviar mensagens e receber respostas (simuladas) de um modelo de IA selecionado.
*   **Seleção de Modelo:** Dropdown para escolher o modelo de IA a ser utilizado (atualmente simulado).
*   **Histórico de Conversas:** As conversas são salvas por sessão e associadas ao usuário logado.
*   **Upload de Arquivos:** Permite anexar arquivos às mensagens de chat.
*   **Memória Persistente:** O histórico é armazenado em um banco de dados SQLite.
*   **Preparação para Stripe:** Estrutura básica para lidar com assinaturas e webhooks do Stripe (requer configuração adicional).

## Estrutura do Projeto

```
/chat_interface_flask
|-- venv/                   # Ambiente virtual Python
|-- src/
|   |-- __init__.py
|   |-- main.py             # Arquivo principal da aplicação Flask
|   |-- static/
|   |   `-- style.css       # Estilos CSS
|   |   `-- script.js       # Lógica JavaScript do frontend
|   `-- templates/
|       |-- index.html      # Página de login/registro
|       `-- chat.html       # Página principal do chat
|-- instance/
|   `-- chat_interface.db   # Banco de dados SQLite (criado após init_db)
|-- uploads/                # Diretório para arquivos enviados pelos usuários (criado dinamicamente)
|-- database/
|   `-- init_db.py          # Script para inicializar o banco de dados
|-- requirements.txt        # Dependências Python
`-- README.md               # Este arquivo
```

## Configuração e Instalação Local

1.  **Clone ou Baixe o Repositório:**
    Obtenha os arquivos do projeto.

2.  **Crie e Ative um Ambiente Virtual:**
    ```bash
    cd chat_interface_flask
    python3.11 -m venv venv
    source venv/bin/activate  # Linux/macOS
    # venv\Scripts\activate  # Windows
    ```

3.  **Instale as Dependências:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Configure as Variáveis de Ambiente:**
    Crie um arquivo `.env` na raiz do projeto (`chat_interface_flask/`) ou exporte as variáveis no seu terminal. A `SECRET_KEY` é essencial para a segurança das sessões Flask.
    ```
    # .env (Exemplo)
    FLASK_APP=src/main.py
    FLASK_DEBUG=1 # 1 para desenvolvimento, 0 para produção
    SECRET_KEY=\"uma_chave_secreta_muito_forte_e_aleatoria\" # Gere uma chave segura!
    
    # --- Configurações Stripe (Obrigatórias para funcionalidade Stripe) ---
    # Substitua pelos seus valores reais (modo teste ou produção)
    STRIPE_SECRET_KEY=\"sk_test_...\"
    STRIPE_WEBHOOK_SECRET=\"whsec_...\"
    STRIPE_PRICE_ID=\"price_...\" # ID do preço da assinatura no Stripe
    ```
    *   **`SECRET_KEY`:** Use `python -c 'import os; print(os.urandom(24))'` para gerar uma chave segura.
    *   **Stripe Keys:** Obtenha suas chaves (Secret Key, Webhook Secret) no painel do Stripe. Crie um produto e um preço no Stripe para obter o `STRIPE_PRICE_ID`.

5.  **Inicialize o Banco de Dados:**
    Execute o script para criar as tabelas no banco de dados SQLite.
    ```bash
    python database/init_db.py
    ```
    Isso criará o arquivo `instance/chat_interface.db`.

6.  **Execute a Aplicação (Desenvolvimento):**
    ```bash
    flask run --host=0.0.0.0 --port=5001
    # Ou diretamente:
    # python src/main.py
    ```
    A aplicação estará acessível em `http://127.0.0.1:5001`.

7.  **Execute a Aplicação (Produção Local com Gunicorn):**
    Gunicorn é um servidor WSGI recomendado para produção.
    ```bash
    gunicorn --bind 0.0.0.0:5001 src.main:app
    ```

## Deploy no Railway

O Railway é uma plataforma que facilita o deploy de aplicações. Siga estes passos:

1.  **Crie uma Conta no Railway:** Acesse [railway.app](https://railway.app) e crie sua conta (pode usar o GitHub).
2.  **Crie um Novo Projeto:** No dashboard, clique em "New Project".
3.  **Escolha o Repositório:** Selecione "Deploy from GitHub repo" e escolha o repositório onde está o código do projeto.
4.  **Configuração Automática (ou Manual):**
    *   O Railway geralmente detecta que é um projeto Python/Flask e sugere configurações.
    *   **Build Command (se necessário):** Pode deixar em branco ou garantir que as dependências sejam instaladas (ex: `pip install -r requirements.txt`).
    *   **Start Command:** Defina o comando para iniciar a aplicação com Gunicorn:
        ```
        gunicorn src.main:app --bind 0.0.0.0:$PORT
        ```
        (O Railway injeta a variável `$PORT` automaticamente).
5.  **Configure as Variáveis de Ambiente:**
    *   Vá até a aba "Variables" do seu serviço no Railway.
    *   Adicione **todas** as variáveis de ambiente necessárias (`SECRET_KEY`, `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `STRIPE_PRICE_ID`). **Não use o modo DEBUG em produção (`FLASK_DEBUG=0` ou não defina).**
6.  **Deploy:** O Railway iniciará o build e o deploy automaticamente. Após a conclusão, ele fornecerá uma URL pública para acessar sua aplicação.
7.  **Configurar Webhook Stripe:** No painel do Stripe, vá para "Developers" -> "Webhooks". Adicione um endpoint apontando para a URL pública fornecida pelo Railway, seguida de `/api/stripe/webhook` (ex: `https://seu-app.up.railway.app/api/stripe/webhook`). Selecione os eventos que você deseja receber (pelo menos `checkout.session.completed`, `customer.subscription.created`, `customer.subscription.updated`, `customer.subscription.deleted`). Use o `STRIPE_WEBHOOK_SECRET` configurado nas variáveis de ambiente.

## Notas Importantes

*   **Acesso Externo:** O acesso ao link temporário fornecido durante o desenvolvimento (`*.manus.computer`) pode ser instável devido a limitações de proxy/firewall do ambiente de desenvolvimento. O teste local (`http://127.0.0.1:5001`) ou o deploy no Railway são as formas mais confiáveis de validar a aplicação.
*   **Simulação de IA:** A lógica de interação com os modelos de IA (`/api/chat/send`) está atualmente simulada. Você precisará substituir o placeholder pela integração real com as APIs desejadas (OpenAI, Claude, etc.), usando as chaves de API apropriadas.
*   **Segurança:** Certifique-se de usar uma `SECRET_KEY` forte e manter suas chaves Stripe seguras, preferencialmente via variáveis de ambiente.
*   **Banco de Dados:** SQLite é usado para simplicidade. Para produção com maior volume, considere migrar para PostgreSQL ou outro banco de dados mais robusto (o Railway oferece PostgreSQL como serviço).


