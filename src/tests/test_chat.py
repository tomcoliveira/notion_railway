# -*- coding: utf-8 -*-
import pytest
import json
import os
from unittest.mock import patch, MagicMock
from flask import session, url_for

# Importa get_db diretamente
from src.main import get_db, available_functions # Importa available_functions

# Testes da API do Chat e Integração com IA (mocked)

# Mock da resposta da API OpenAI para uma mensagem simples
mock_openai_simple_response = MagicMock()
mock_openai_simple_response.choices = [MagicMock()]
mock_openai_simple_response.choices[0].message = MagicMock()
mock_openai_simple_response.choices[0].message.content = "Esta é uma resposta simples da IA."
mock_openai_simple_response.choices[0].message.tool_calls = None

# --- Mock da resposta da API OpenAI solicitando uma chamada de função (MAIS PRECISO) ---
# Cria um mock para o objeto 'function' interno
mock_function_obj = MagicMock()
mock_function_obj.name = "fazer_requisicao_http"
mock_function_obj.arguments = json.dumps({"url": "https://exemplo.com/api", "method": "GET"})

# Cria um mock para o objeto 'tool_call' que contém o 'function'
mock_tool_call_obj = MagicMock()
mock_tool_call_obj.id = "call_123"
mock_tool_call_obj.type = "function"
mock_tool_call_obj.function = mock_function_obj

# Cria um mock para a mensagem que contém a lista de 'tool_calls'
mock_message_with_tool_call = MagicMock()
mock_message_with_tool_call.content = None
mock_message_with_tool_call.tool_calls = [mock_tool_call_obj]

# Cria um mock para a escolha que contém a mensagem
mock_choice_with_tool_call = MagicMock()
mock_choice_with_tool_call.message = mock_message_with_tool_call

# Cria o mock final da resposta da API OpenAI
mock_openai_tool_call_request = MagicMock()
mock_openai_tool_call_request.choices = [mock_choice_with_tool_call]

# Adiciona um método model_dump() ao mock do tool_call para simular o objeto Pydantic
# O model_dump deve retornar um dict serializável
mock_tool_call_obj.model_dump.return_value = {
    "id": mock_tool_call_obj.id,
    "type": mock_tool_call_obj.type,
    "function": {
        "name": mock_tool_call_obj.function.name,
        "arguments": mock_tool_call_obj.function.arguments
    }
}
# ----------------------------------------------------------------------------------

# Mock da resposta da API OpenAI após receber o resultado da função
mock_openai_final_response_after_tool = MagicMock()
mock_openai_final_response_after_tool.choices = [MagicMock()]
mock_openai_final_response_after_tool.choices[0].message = MagicMock()
mock_openai_final_response_after_tool.choices[0].message.content = "A requisição para https://exemplo.com/api foi bem-sucedida."
mock_openai_final_response_after_tool.choices[0].message.tool_calls = None

# Mock da resposta da função fazer_requisicao_http
mock_http_response_success = "Status: 200\nResultado:\n{\"success\": true}"

@pytest.mark.usefixtures("auth_client") # Usa o cliente já autenticado
def test_send_simple_message(auth_client, mocker):
    """Testa o envio de uma mensagem simples e a resposta da IA (mocked)."""
    # Mocka a chamada client.chat.completions.create
    mocker.patch("src.main.client.chat.completions.create", return_value=mock_openai_simple_response)

    response = auth_client.post("/api/chat/send", json={
        "message": "Olá IA!",
        "model": "gpt-4o",
        "session_id": None # Inicia nova sessão
    })

    assert response.status_code == 200
    data = response.get_json()
    assert data["ai_response"] == "Esta é uma resposta simples da IA."
    assert data["model_used"] == "gpt-4o"
    assert "session_id" in data
    assert data["user_message"] == "Olá IA!"

    # Verifica se a mensagem foi salva no DB (user e assistant)
    with auth_client.application.app_context():
        conn = get_db() # Usa a função importada
        cursor = conn.cursor()
        cursor.execute("SELECT role, user_message, ai_response FROM chat_history WHERE session_id = ? ORDER BY timestamp ASC", (data["session_id"],))
        history = cursor.fetchall()
        conn.close()
        assert len(history) == 2
        assert history[0]["role"] == "user"
        assert history[0]["user_message"] == "Olá IA!"
        assert history[1]["role"] == "assistant"
        assert history[1]["ai_response"] == "Esta é uma resposta simples da IA."

@pytest.mark.usefixtures("auth_client")
def test_send_message_with_function_call(auth_client, mocker):
    """Testa o fluxo completo com a IA solicitando e executando uma função (mocked)."""
    # Mocka as chamadas da API OpenAI
    openai_mock = mocker.patch("src.main.client.chat.completions.create")
    openai_mock.side_effect = [
        mock_openai_tool_call_request, # 1ª chamada: IA pede função
        mock_openai_final_response_after_tool # 2ª chamada: IA responde após função
    ]
    # Mocka a função DENTRO do dicionário available_functions
    mock_http_func = MagicMock(return_value=mock_http_response_success)
    mocker.patch.dict(available_functions, {"fazer_requisicao_http": mock_http_func})

    response = auth_client.post("/api/chat/send", json={
        "message": "Faça um GET em https://exemplo.com/api",
        "model": "gpt-4o",
        "session_id": None # Nova sessão
    })

    assert response.status_code == 200
    data = response.get_json()
    assert data["ai_response"] == "A requisição para https://exemplo.com/api foi bem-sucedida."
    assert data["model_used"] == "gpt-4o"
    session_id = data["session_id"]

    # Verifica se a função HTTP MOCK foi chamada com os argumentos corretos
    mock_http_func.assert_called_once_with(url="https://exemplo.com/api", method="GET", headers=None, payload=None)

    # Verifica se a API OpenAI foi chamada duas vezes
    assert openai_mock.call_count == 2

    # Verifica o histórico no DB (user, assistant[tool_call], tool, assistant[final])
    with auth_client.application.app_context():
        conn = get_db() # Usa a função importada
        cursor = conn.cursor()
        cursor.execute("SELECT role, user_message, ai_response, tool_call_info, tool_response_content FROM chat_history WHERE session_id = ? ORDER BY timestamp ASC", (session_id,))
        history = cursor.fetchall()
        conn.close()
        
        assert len(history) == 4
        assert history[0]["role"] == "user"
        assert history[0]["user_message"] == "Faça um GET em https://exemplo.com/api"
        assert history[1]["role"] == "assistant" # Resposta da IA pedindo tool call
        assert history[1]["ai_response"] is None # Conteúdo pode ser nulo
        assert history[1]["tool_call_info"] is not None # Deve ter info da tool call
        # Verifica se o tool_call_info salvo é um JSON serializado do dict
        saved_tool_call_info = json.loads(history[1]["tool_call_info"])
        assert isinstance(saved_tool_call_info, list)
        # Compara com o dict retornado pelo model_dump do mock
        assert saved_tool_call_info[0]["id"] == mock_tool_call_obj.model_dump()["id"]
        assert saved_tool_call_info[0]["function"]["name"] == mock_tool_call_obj.model_dump()["function"]["name"]
        
        assert history[2]["role"] == "tool" # Resposta da ferramenta
        assert history[2]["tool_response_content"] == mock_http_response_success
        assert history[3]["role"] == "assistant" # Resposta final da IA
        assert history[3]["ai_response"] == "A requisição para https://exemplo.com/api foi bem-sucedida."

@pytest.mark.usefixtures("auth_client")
def test_get_chat_history(auth_client, mocker):
    """Testa a recuperação do histórico de chat."""
    # Mocka a API para enviar algumas mensagens
    openai_mock = mocker.patch("src.main.client.chat.completions.create", return_value=mock_openai_simple_response)

    # Envia duas mensagens
    resp1 = auth_client.post("/api/chat/send", json={"message": "Msg 1", "model": "gpt-4o", "session_id": None})
    session_id = resp1.get_json()["session_id"]
    auth_client.post("/api/chat/send", json={"message": "Msg 2", "model": "gpt-4o", "session_id": session_id})

    # Pede o histórico da sessão
    response = auth_client.get(f"/api/chat/history?session_id={session_id}")
    assert response.status_code == 200
    history_data = response.get_json()

    # Deve haver 4 entradas (user1, ai1, user2, ai2)
    assert len(history_data) == 4 
    assert history_data[0]["role"] == "user"
    assert history_data[0]["user_message"] == "Msg 1"
    assert history_data[1]["role"] == "assistant"
    assert history_data[2]["role"] == "user"
    assert history_data[2]["user_message"] == "Msg 2"
    assert history_data[3]["role"] == "assistant"

@pytest.mark.usefixtures("auth_client")
def test_upload_file(auth_client, app):
    """Testa o upload de um arquivo."""
    # Cria um arquivo temporário para upload
    file_content = "Este é o conteúdo do arquivo de teste.".encode("utf-8")
    file_name = "test_upload.txt"
    
    # Usa BytesIO para simular um arquivo em memória
    from io import BytesIO
    data = {
        "file": (BytesIO(file_content), file_name)
    }

    # Garante o contexto do cliente para acessar a sessão
    with auth_client:
        response = auth_client.post("/api/upload", data=data, content_type="multipart/form-data")

        assert response.status_code == 200
        result = response.get_json()
        assert result["message"] == "Arquivo enviado com sucesso"
        assert "file_path" in result
        file_path = result["file_path"]
        assert file_name in file_path # Verifica se o nome original está no path retornado

        # Verifica se o arquivo foi salvo no local correto (dentro da pasta de uploads do usuário)
        user_id = session.get("user_id")
        assert user_id is not None # Garante que o user_id foi obtido da sessão
        expected_dir = os.path.join(app.config["UPLOAD_FOLDER"], str(user_id))
        # O nome do arquivo salvo contém um UUID, então verificamos se ele existe no diretório
        saved_files = os.listdir(expected_dir)
        assert any(file_name in saved_file for saved_file in saved_files)
        
        # Testa acessar o arquivo via /uploads/<path>
        access_response = auth_client.get(f"/uploads/{file_path}")
        assert access_response.status_code == 200
        assert access_response.data == file_content

@pytest.mark.usefixtures("auth_client")
def test_send_message_with_upload(auth_client, mocker, app):
    """Testa enviar uma mensagem com um arquivo anexado."""
    # 1. Faz o upload do arquivo primeiro (dentro do contexto)
    uploaded_file_path = None
    with auth_client:
        file_content = "Conteúdo relevante do arquivo.".encode("utf-8")
        file_name = "anexo.txt"
        from io import BytesIO
        upload_resp = auth_client.post("/api/upload", data={"file": (BytesIO(file_content), file_name)}, content_type="multipart/form-data")
        assert upload_resp.status_code == 200
        uploaded_file_path = upload_resp.get_json()["file_path"]
        assert uploaded_file_path is not None

    # 2. Mocka a API OpenAI
    mocker.patch("src.main.client.chat.completions.create", return_value=mock_openai_simple_response)

    # 3. Envia a mensagem referenciando o arquivo upado (dentro do contexto)
    with auth_client:
        response = auth_client.post("/api/chat/send", json={
            "message": "Analise este arquivo.",
            "model": "gpt-4o",
            "session_id": None,
            "uploaded_file_path": uploaded_file_path
        })

        assert response.status_code == 200
        data = response.get_json()
        assert data["ai_response"] == "Esta é uma resposta simples da IA."
        assert data["uploaded_file_path"] == uploaded_file_path

        # Verifica se a mensagem do usuário foi salva com o path do arquivo
        with auth_client.application.app_context():
            conn = get_db() # Usa a função importada
            cursor = conn.cursor()
            cursor.execute("SELECT uploaded_file_path FROM chat_history WHERE session_id = ? AND role = ?", (data["session_id"], "user"))
            user_entry = cursor.fetchone()
            conn.close()
            assert user_entry["uploaded_file_path"] == uploaded_file_path

