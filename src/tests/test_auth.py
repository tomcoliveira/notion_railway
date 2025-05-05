# -*- coding: utf-8 -*-
import pytest
from flask import session, url_for

# Testes de Autenticação
def test_register(client, app):
    # Testa GET na página de registro (que é a index com parâmetro)
    assert client.get("/register").status_code == 302 # Redireciona para index
    assert client.get(url_for("index", show_register=True)).status_code == 200

    # Testa POST para registrar novo usuário
    response = client.post("/register", data={"username": "newuser", "password": "newpassword"}, follow_redirects=True)
    assert response.status_code == 200
    assert b"Usu\xc3\xa1rio registrado com sucesso! Fa\xc3\xa7a o login." in response.data
    assert b"Login" in response.data # Deve mostrar o formulário de login após registro

    # Testa registrar usuário existente
    response = client.post("/register", data={"username": "newuser", "password": "anotherpassword"}, follow_redirects=True)
    assert response.status_code == 200
    assert b"Nome de usu\xc3\xa1rio j\xc3\xa1 existe." in response.data

def test_login_logout(client, app):
    # Registra um usuário primeiro (usando o auth_client faria isso, mas vamos fazer manualmente aqui para isolar)
    client.post("/register", data={"username": "loginuser", "password": "loginpass"}, follow_redirects=True)

    # Testa GET na página de login (index com parâmetro)
    assert client.get("/login").status_code == 302 # Redireciona para index
    assert client.get(url_for("index", show_login=True)).status_code == 200

    # Testa login com credenciais corretas
    response = client.post("/login", data={"username": "loginuser", "password": "loginpass"}, follow_redirects=True)
    assert response.status_code == 200
    # Verifica se foi redirecionado para /chat (ou se o conteúdo da página de chat está presente)
    # Como /chat renderiza um template, podemos verificar por um elemento específico dele
    assert b"<title>Chat IA</title>" in response.data 
    # Verifica se a sessão foi criada
    with client: # Entra no contexto do cliente para acessar a sessão
        client.get("/") # Precisa fazer uma requisição para a sessão ser carregada
        assert session.get("user_id") is not None
        assert session.get("username") == "loginuser"

    # Testa logout
    response = client.get("/logout", follow_redirects=True)
    assert response.status_code == 200
    assert b"Voc\xc3\xaa foi desconectado." in response.data
    assert b"Login" in response.data # Deve voltar para a página de login
    # Verifica se a sessão foi limpa
    with client:
        client.get("/")
        assert "user_id" not in session

def test_login_invalid_credentials(client, app):
    # Testa login com usuário inexistente
    response = client.post("/login", data={"username": "nouser", "password": "nopass"}, follow_redirects=True)
    assert response.status_code == 200
    assert b"Usu\xc3\xa1rio ou senha inv\xc3\xa1lidos." in response.data
    assert b"Login" in response.data

    # Registra um usuário para testar senha incorreta
    client.post("/register", data={"username": "testpass", "password": "correctpass"}, follow_redirects=True)
    # Testa login com senha incorreta
    response = client.post("/login", data={"username": "testpass", "password": "wrongpass"}, follow_redirects=True)
    assert response.status_code == 200
    assert b"Usu\xc3\xa1rio ou senha inv\xc3\xa1lidos." in response.data
    assert b"Login" in response.data

