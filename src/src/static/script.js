document.addEventListener("DOMContentLoaded", () => {
    const chatHistory = document.getElementById("chat-history");
    const messageInput = document.getElementById("message-input");
    const sendButton = document.getElementById("send-button");
    const modelSelect = document.getElementById("model-select");
    const attachButton = document.getElementById("attach-button");
    const fileInput = document.getElementById("file-input");
    const filePreview = document.getElementById("file-preview");
    const loadingIndicator = document.getElementById("loading-indicator");

    let currentSessionId = null; // Será definido na primeira mensagem ou ao carregar histórico
    let attachedFile = null;
    let attachedFilePath = null; // Caminho retornado pelo backend após upload

    // --- Funções Auxiliares ---
    function showLoading(isLoading) {
        loadingIndicator.style.display = isLoading ? "flex" : "none";
        sendButton.disabled = isLoading;
        messageInput.disabled = isLoading;
        attachButton.disabled = isLoading;
    }

    function displayMessage(role, content, model = null, timestamp = null, filePath = null) {
        const messageDiv = document.createElement("div");
        messageDiv.classList.add("message", role);

        let messageHTML = "";
        if (role === "user" || role === "ai") {
            // Usa uma biblioteca de Markdown (como Marked.js ou Showdown.js) se quiser formatação rica
            // Por simplicidade, vamos apenas substituir novas linhas por <br> e detectar blocos de código simples
            const formattedContent = content
                .replace(/</g, "&lt;").replace(/>/g, "&gt;") // Escapa HTML básico
                .replace(/\n/g, "<br>")
                .replace(/```([\s\S]*?)```/g, (match, code) => `<pre><code>${code.trim()}</code></pre>`) // Blocos de código
                .replace(/`([^`]+)`/g, `<code>$1</code>`); // Código inline
            messageHTML = formattedContent;
        } else {
            messageHTML = content; // Para system/error messages
        }
        
        // Adiciona link para arquivo se houver
        if (filePath) {
             const fileName = filePath.split("/").pop().split("_").slice(1).join("_"); // Extrai nome original
             messageHTML += `<br><small><i>Arquivo anexado: <a href="/uploads/${filePath}" target="_blank">${fileName}</a></i></small>`;
        }

        messageDiv.innerHTML = messageHTML;

        if (timestamp) {
            const timeSpan = document.createElement("span");
            timeSpan.classList.add("timestamp");
            timeSpan.textContent = new Date(timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
            messageDiv.appendChild(timeSpan);
        }
        if (role === "ai" && model) {
            const modelSpan = document.createElement("span");
            modelSpan.classList.add("model-info");
            modelSpan.textContent = `(${model})`;
            messageDiv.appendChild(modelSpan);
        }

        chatHistory.appendChild(messageDiv);
        scrollToBottom();
    }

    function scrollToBottom() {
        chatHistory.scrollTop = chatHistory.scrollHeight;
    }

    function adjustTextareaHeight() {
        messageInput.style.height = "auto"; // Reseta a altura
        messageInput.style.height = (messageInput.scrollHeight) + "px"; // Ajusta à altura do conteúdo
    }

    function updateFilePreview() {
        if (attachedFile) {
            filePreview.innerHTML = `
                <span>${attachedFile.name}</span>
                <button class="remove-file-button" title="Remover arquivo">×</button>
            `;
            filePreview.querySelector(".remove-file-button").addEventListener("click", removeAttachment);
        } else {
            filePreview.innerHTML = "";
            attachedFilePath = null; // Limpa o caminho quando o arquivo é removido
        }
    }

    function removeAttachment() {
        attachedFile = null;
        fileInput.value = ""; // Limpa o input file
        updateFilePreview();
    }

    // --- Carregar Histórico ---
    async function loadHistory() {
        showLoading(true);
        try {
            const response = await fetch("/api/chat/history"); // Carrega todo o histórico por enquanto
            if (!response.ok) {
                throw new Error(`Erro ao carregar histórico: ${response.statusText}`);
            }
            const history = await response.json();
            chatHistory.innerHTML = ""; // Limpa mensagens de carregamento
            if (history.length > 0) {
                currentSessionId = history[history.length - 1].session_id; // Pega o ID da última sessão
                history.forEach(msg => {
                    // Adapta para a nova estrutura do DB
                    if (msg.role === "user") {
                        displayMessage("user", msg.user_message, null, msg.timestamp, msg.uploaded_file_path);
                    } else if (msg.role === "assistant") {
                        displayMessage("ai", msg.ai_response, msg.model_used, msg.timestamp);
                    } // Ignora roles system/tool na exibição por enquanto
                });
                displayMessage("system-message", "Histórico carregado.");
            } else {
                displayMessage("system-message", "Nenhuma conversa anterior encontrada. Comece uma nova!");
                currentSessionId = null; // Garante que uma nova sessão será criada
            }
        } catch (error) {
            console.error("Erro ao carregar histórico:", error);
            displayMessage("error-message", `Falha ao carregar histórico: ${error.message}`);
        } finally {
            showLoading(false);
            scrollToBottom();
        }
    }

    // --- Enviar Mensagem ---
    async function sendMessage() {
        const messageText = messageInput.value.trim();
        const selectedModel = modelSelect.value;

        if (!messageText && !attachedFile) {
            return; // Não envia mensagem vazia sem anexo
        }

        showLoading(true);
        let messageToSend = messageText;
        let filePathToSend = attachedFilePath; // Usa o path do arquivo já upado, se houver

        // 1. Faz upload do arquivo ANTES de enviar a mensagem, se houver um novo
        if (attachedFile && !attachedFilePath) {
            const formData = new FormData();
            formData.append("file", attachedFile);
            try {
                const uploadResponse = await fetch("/api/upload", {
                    method: "POST",
                    body: formData
                });
                const uploadResult = await uploadResponse.json();
                if (!uploadResponse.ok) {
                    throw new Error(uploadResult.error || "Falha no upload do arquivo");
                }
                filePathToSend = uploadResult.file_path; // Guarda o caminho retornado
                console.log("Arquivo enviado:", filePathToSend);
            } catch (error) {
                console.error("Erro no upload:", error);
                displayMessage("error-message", `Erro ao enviar arquivo: ${error.message}`);
                removeAttachment();
                showLoading(false);
                return;
            }
        }

        // Exibe a mensagem do usuário imediatamente
        displayMessage("user", messageText, null, new Date().toISOString(), filePathToSend);
        messageInput.value = "";
        adjustTextareaHeight();
        removeAttachment(); // Limpa anexo após envio

        // 2. Envia a mensagem (e o caminho do arquivo, se houver) para a IA
        try {
            const response = await fetch("/api/chat/send", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                },
                body: JSON.stringify({
                    message: messageText,
                    model: selectedModel,
                    session_id: currentSessionId,
                    uploaded_file_path: filePathToSend
                }),
            });

            const result = await response.json();

            if (!response.ok) {
                throw new Error(result.error || `Erro ${response.status}: ${response.statusText}`);
            }

            // Atualiza o session ID se for a primeira mensagem da sessão
            if (!currentSessionId) {
                currentSessionId = result.session_id;
            }

            // Exibe a resposta da IA
            displayMessage("ai", result.ai_response, result.model_used, result.timestamp);

        } catch (error) {
            console.error("Erro ao enviar/receber mensagem:", error);
            displayMessage("error-message", `Erro: ${error.message}`);
        } finally {
            showLoading(false);
        }
    }

    // --- Event Listeners ---
    sendButton.addEventListener("click", sendMessage);
    messageInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault(); // Impede nova linha no textarea
            sendMessage();
        }
    });

    messageInput.addEventListener("input", adjustTextareaHeight);

    attachButton.addEventListener("click", () => {
        fileInput.click(); // Abre o seletor de arquivos
    });

    fileInput.addEventListener("change", (e) => {
        if (e.target.files.length > 0) {
            attachedFile = e.target.files[0];
            attachedFilePath = null; // Reseta o path, pois é um novo arquivo
            updateFilePreview();
        } else {
            removeAttachment();
        }
    });

    modelSelect.addEventListener("change", async () => {
        const selectedModel = modelSelect.value;
        console.log("Modelo selecionado:", selectedModel);
        // Opcional: Informar o backend sobre a mudança de modelo (se necessário)
        // try {
        //     await fetch("/api/chat/model", {
        //         method: "POST",
        //         headers: { "Content-Type": "application/json" },
        //         body: JSON.stringify({ model: selectedModel })
        //     });
        // } catch (error) {
        //     console.error("Erro ao atualizar modelo no backend:", error);
        // }
    });

    // --- Inicialização ---
    adjustTextareaHeight(); // Ajusta altura inicial
    loadHistory(); // Carrega o histórico ao iniciar
});

