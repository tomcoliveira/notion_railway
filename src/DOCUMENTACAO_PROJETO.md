# Documentação Completa: Interface de Chat Multi-Modelo (v2 - Pós-Melhorias)

## 1. Visão Geral e Objetivos

Este documento detalha o projeto de desenvolvimento de uma interface web para interação com múltiplos modelos de Inteligência Artificial (IA), **agora com integração real e capacidades avançadas**. O objetivo principal é criar uma plataforma centralizada onde um usuário possa:

*   Autenticar-se de forma segura (login/registro).
*   Iniciar e gerenciar diferentes sessões de chat.
*   Selecionar o modelo de IA desejado (ex: GPT-4o) para cada interação.
*   Enviar mensagens de texto e receber respostas **reais** da IA selecionada.
*   **Utilizar a capacidade da IA de executar ações externas**, como fazer requisições HTTP para outras APIs (ex: ClickUp), através de *function calling*.
*   Anexar arquivos (upload) cujo conteúdo (texto) pode ser incluído no contexto enviado à IA.
*   Ter o histórico de todas as conversas (incluindo mensagens, respostas, modelo usado, arquivos anexados, chamadas de função e resultados) armazenado persistentemente por sessão e associado à sua conta.
*   Ter a estrutura preparada para futuras integrações de pagamento (via Stripe) para acesso a funcionalidades premium ou modelos específicos.

A aplicação foi desenvolvida com foco em uma interface minimalista e funcional, priorizando a clareza e a facilidade de uso, **com melhorias recentes na experiência do usuário (UI/UX)**.

## 2. Arquitetura e Tecnologias

O projeto utiliza a seguinte stack tecnológica:

*   **Backend:** Python com o microframework **Flask**.
*   **Frontend:** **HTML5**, **CSS3** e **JavaScript (Vanilla)**.
    *   **Jinja2:** Motor de templates.
*   **Banco de Dados:** **SQLite**.
*   **Servidor WSGI (Produção):** **Gunicorn**.
*   **Integração IA:** Biblioteca **`openai`** para interagir com modelos GPT.
*   **Requisições HTTP (Function Calling):** Biblioteca **`requests`** para executar chamadas HTTP solicitadas pela IA.
*   **Testes Automatizados:** **`pytest`**, **`pytest-flask`**, **`pytest-mock`**.
*   **Gerenciamento de Dependências:** **pip** e `requirements.txt`.
*   **Ambiente Virtual:** **venv**.
*   **Pagamentos:** Preparado para integração com **Stripe**.

**Fluxo Geral (Atualizado):**

1.  Usuário acessa a interface web.
2.  Interface interage com o backend Flask via API.
3.  Backend Flask processa requisições:
    *   Gerencia autenticação e sessões.
    *   Interage com SQLite para dados.
    *   Lida com uploads.
    *   **Chama a API da OpenAI (ex: GPT-4o)**, enviando a mensagem do usuário, o histórico da conversa (contexto), o conteúdo do arquivo (se houver) e a definição das ferramentas disponíveis (ex: `fazer_requisicao_http`).
    *   **Se a IA solicitar uma ferramenta (function call):**
        *   Backend detecta a solicitação.
        *   Executa a função correspondente (ex: faz a requisição HTTP usando `requests`).
        *   Envia o resultado da função de volta para a API da OpenAI.
        *   Recebe a resposta final da IA (baseada no resultado da função).
    *   **Se a IA responder diretamente:**
        *   Backend recebe a resposta.
    *   Salva a interação completa (mensagem, resposta, tool calls, etc.) no histórico do DB.
    *   (Placeholder) Interage com Stripe.
4.  Backend retorna a resposta final da IA para o frontend.
5.  Frontend atualiza a interface.

## 3. Funcionalidades Detalhadas (Atualizado)

*   **Autenticação:** (Sem alterações significativas)
*   **Interface de Chat (`/chat`):**
    *   Exibe histórico da sessão.
    *   Campo de envio de mensagem.
    *   Dropdown para selecionar modelo (agora usado para chamada real à API).
    *   Botão/área para upload.
    *   **Melhorias UI/UX:** Indicador de carregamento enquanto a IA processa; exibição de mensagens de erro mais clara; formatação de código nas respostas da IA.
*   **Histórico de Conversas (`/api/chat/history`):**
    *   Busca e retorna histórico completo, incluindo informações sobre chamadas de ferramentas.
*   **Envio de Mensagem (`/api/chat/send`):**
    *   Recebe mensagem, modelo, sessão, arquivo.
    *   **Integração Real com IA:** Chama a API da OpenAI com o modelo selecionado.
    *   **Gerenciamento de Contexto:** Envia as últimas `MAX_HISTORY_MESSAGES` da sessão atual para a IA.
    *   **Processamento de Arquivos:** Lê os primeiros 2000 caracteres de arquivos de texto enviados e os inclui no prompt do usuário.
    *   **Function Calling:**
        *   Envia a definição da ferramenta `fazer_requisicao_http` para a IA.
        *   Se a IA solicitar a ferramenta, o backend extrai os argumentos (URL, método, headers, payload), executa a requisição HTTP usando a biblioteca `requests` (adicionando automaticamente o token do ClickUp para URLs da API do ClickUp, se configurado).
        *   Envia o resultado da requisição de volta para a IA.
        *   Recebe e retorna a resposta final da IA.
    *   Salva a interação completa (incluindo `tool_call_info`, `tool_call_id`, `tool_response_content`) no banco de dados.
    *   Retorna a resposta final da IA e metadados.
*   **Upload de Arquivos (`/api/upload`):** (Sem alterações significativas na funcionalidade principal, mas agora o conteúdo é usado)
*   **Servir Arquivos (`/uploads/<path:filepath>`):** (Sem alterações significativas)
*   **Integração Stripe (Preparação):** (Sem alterações significativas)
*   **Testes Automatizados:**
    *   Foram implementados testes unitários e de integração usando `pytest` para as funcionalidades de autenticação e chat (incluindo o fluxo de function calling com mocks).
    *   Os testes garantem maior robustez e facilitam a manutenção do código.

## 4. Estrutura do Código (Atualizado)

```
/chat_interface_flask
|-- venv/                   # Ambiente virtual
|-- src/                    # Código fonte principal
|   |-- __init__.py
|   |-- main.py             # Núcleo da aplicação Flask
|   |-- static/             # Arquivos estáticos (CSS, JS)
|   |   |-- style.css
|   |   `-- script.js
|   `-- templates/          # Templates HTML (Jinja2)
|       |-- index.html
|       `-- chat.html
|-- instance/               # Dados da instância (DB)
|   `-- chat_interface.db
|-- uploads/                # Arquivos enviados pelos usuários
|-- database/               # Scripts de banco de dados
|   `-- init_db.py
|-- tests/                  # Testes automatizados
|   |-- __init__.py
|   |-- conftest.py         # Configurações e fixtures do Pytest
|   |-- test_auth.py        # Testes para autenticação
|   `-- test_chat.py        # Testes para a API de chat e function calling
|-- requirements.txt        # Dependências Python
|-- README.md               # Instruções de instalação e uso
`-- DOCUMENTACAO_PROJETO.md # Este arquivo
```

*   **`tests/`:** Novo diretório contendo os testes automatizados.

## 5. Banco de Dados (SQLite) (Atualizado)

O banco de dados `instance/chat_interface.db` contém:

1.  **`users`** (Sem alterações na estrutura)
2.  **`chat_history` (Campos Adicionados):**
    *   `id` (INTEGER, PRIMARY KEY AUTOINCREMENT)
    *   `user_id` (INTEGER, NOT NULL, FOREIGN KEY(users))
    *   `session_id` (TEXT, NOT NULL)
    *   `role` (TEXT, NOT NULL): Papel da mensagem ('user', 'assistant', 'tool').
    *   `user_message` (TEXT): Mensagem original do usuário (se role='user').
    *   `ai_response` (TEXT): Resposta final em texto da IA (se role='assistant' e sem tool call final).
    *   `model_used` (TEXT): Modelo de IA usado.
    *   `context_used` (BOOLEAN, DEFAULT 1): Indicador se o contexto foi usado.
    *   `uploaded_file_path` (TEXT, NULL): Caminho do arquivo anexado.
    *   `timestamp` (TIMESTAMP, DEFAULT CURRENT_TIMESTAMP)
    *   **`tool_call_id` (TEXT, NULL):** ID da chamada de ferramenta específica (se role='tool' ou 'assistant' com tool call).
    *   **`tool_call_info` (TEXT, NULL):** JSON contendo a(s) chamada(s) de ferramenta solicitada(s) pela IA (se role='assistant').
    *   **`tool_response_content` (TEXT, NULL):** Conteúdo da resposta retornada pela execução da ferramenta (se role='tool').

## 6. Rotas Principais (API e Páginas) (Atualizado)

*   **Páginas Web:** (Sem alterações significativas nas rotas)
*   **API (Backend):**
    *   `/api/chat/history` (GET): Retorna histórico (JSON), incluindo dados de tool calls.
    *   `/api/chat/send` (POST): **Agora lida com chamadas reais à OpenAI, contexto, processamento básico de arquivos e fluxo completo de function calling para `fazer_requisicao_http`.**
    *   `/api/chat/model` (POST): (Funcionalidade inalterada, mas o modelo selecionado é efetivamente usado).
    *   `/api/upload` (POST): (Funcionalidade inalterada).
    *   `/api/stripe/webhook` (POST): (Funcionalidade inalterada).
    *   `/api/stripe/create-checkout-session` (POST): (Funcionalidade inalterada - Placeholder).

## 7. Pontos Futuros e Placeholders (Refinado)

Com as melhorias recentes, a aplicação está mais funcional. Os próximos passos e áreas para desenvolvimento futuro incluem:

1.  **Incorporar Conhecimentos Especiais e Personas:** Ajustar o prompt do sistema em `src/main.py` para definir personas específicas e incluir conhecimentos relevantes (ex: detalhes adicionais da API do ClickUp, regras de negócio), conforme solicitado pelo usuário.
2.  **Processamento Avançado de Arquivos:** Implementar lógica para lidar com diferentes tipos de arquivos (PDFs, imagens, etc.) e extrair seu conteúdo de forma mais robusta. Integrar com APIs de IA que suportem análise de múltiplos formatos.
3.  **Memória de Longo Prazo (RAG):** Para um contexto 
