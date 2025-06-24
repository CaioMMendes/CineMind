import base64
import hmac
import json
import os
import re
import time
import uuid
from datetime import datetime

import boto3
import requests
from functions import (format_context, generate_chat_prompt,
                       read_csv_from_uploaded_file,
                       read_pdf_from_uploaded_file,
                       read_txt_from_uploaded_file)

import streamlit as st

#todo mudar essa linha
PROFILE_NAME = os.environ.get("AWS_PROFILE", "")

INFERENCE_PROFILE_ARN = "arn:aws:bedrock:us-east-1:851614451056:inference-profile/us.anthropic.claude-sonnet-4-20250514-v1:0"
# INFERENCE_PROFILE_ARN = "arn:aws:bedrock:us-east-1:851614451056:inference-profile/us.anthropic.claude-3-5-sonnet-20241022-v2:0"



#alterar
st.set_page_config(
   page_title="CineMind",
   page_icon="logo-CineMind.png",
   layout="wide",
   initial_sidebar_state="expanded"
)

logo_path = "logo-CineMind.png"

def preprocess_user_message(message):
    """
    Função simples de pré-processamento da mensagem do usuário
    """
    return message

def get_boto3_client(service_name, region_name='us-east-1', profile_name=''):
    """
    Retorna um cliente do serviço AWS especificado.
    
    Tenta usar o perfil especificado para desenvolvimento local primeiro.
    Se falhar, assume que está em uma instância EC2 e usa as credenciais do IAM role.
    """
    try:
        session = boto3.Session(profile_name=profile_name, region_name=region_name)
        client = session.client(service_name)
        if service_name == 'sts':
            caller_identity = client.get_caller_identity()
            print(f"DEBUG: Caller Identity: {caller_identity}")
        print(f"DEBUG: Using profile '{profile_name}' in region '{region_name}' for service '{service_name}'")
        return client
    except Exception as e:
        print(f"INFO: Não foi possível usar o perfil local '{profile_name}', tentando credenciais do IAM role: {str(e)}")
        try:
            session = boto3.Session(region_name=region_name)
            client = session.client(service_name)
            caller_identity = client.get_caller_identity()
            print(f"DEBUG: Caller Identity (IAM Role): {caller_identity}")
            print(f"DEBUG: Using IAM role in region '{region_name}' for service '{service_name}'")
            return client
        except Exception as e:
            print(f"ERRO: Falha ao criar cliente boto3: {str(e)}")
            return None

def query_bedrock(message, session_id="", model_params=None, context="", conversation_history=None):
    """
    Envia uma mensagem para o Amazon Bedrock com parâmetros de modelo específicos.
    """
    #todo alterar os parametros do modelo
    if model_params is None:
        model_params = {
            "temperature": 0.6,
            "top_p": 0.8,
            "top_k": 50,
            "max_tokens": 800,
            "response_format": {"type": "text"}
        }

    
    bedrock_runtime = get_boto3_client('bedrock-runtime')
    
    if not bedrock_runtime:
        return {
            "answer": "Não foi possível conectar ao serviço Bedrock. Verifique suas credenciais.",
            "sessionId": session_id or str(uuid.uuid4())
        }
    
    try:
        prompt = generate_chat_prompt(message, conversation_history=conversation_history, context=context)
        
        body = json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": model_params["max_tokens"],
            "temperature": model_params["temperature"],
            "top_p": model_params["top_p"],
            "top_k": model_params["top_k"],
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": prompt
                        }
                    ]
                }
            ]
        })
        
        response = bedrock_runtime.invoke_model(
        modelId=INFERENCE_PROFILE_ARN,
        body=body,
        contentType="application/json",
        accept="application/json"
    )
        
        response_body = json.loads(response['body'].read())
        answer = response_body['content'][0]['text']
        
        if not session_id:
            session_id = str(uuid.uuid4())
        
        return {
            "answer": answer,
            "sessionId": session_id
        }
        
    except Exception as e:
        print(f"ERRO: Falha na requisição ao Bedrock: {str(e)}")
        return {
            "answer": "Ocorreu um erro ao processar sua solicitação. Por favor, tente novamente.",
            "sessionId": session_id or str(uuid.uuid4())
        }

def check_password():
    """Returns `True` if the user had the correct password."""

    def password_entered():
        """Checks whether a password entered by the user is correct."""
        print(f"DEBUG LOGIN: Tentativa de login - Usuário: '{st.session_state['username']}', Senha: '{st.session_state['password']}'")
        
        
        #todo trocar o admin pelo nome de usuario
        #todo trocar o admin123 pela senha
        if hmac.compare_digest(st.session_state["username"].strip(), "cinemind") and \
        hmac.compare_digest(st.session_state["password"].strip(), "edngrupo06"):
            print("DEBUG LOGIN: Autenticação bem-sucedida")
            st.session_state["password_correct"] = True
            st.session_state["auth_cookie"] = {
                #todo talvez trocar o admin pelo nome de usuario
                "user": "admin",
                "exp": time.time() + (7 * 24 * 60 * 60)
            }
            
            try:
                st.query_params["auth"] = base64.b64encode(json.dumps(st.session_state["auth_cookie"]).encode()).decode()
            except:
                pass
                
            del st.session_state["password"]
            del st.session_state["username"]
        else:
            print(f"DEBUG LOGIN: Autenticação falhou - Usuário: '{st.session_state['username']}', Senha: '{st.session_state['password']}'")
            print(f"DEBUG LOGIN: Comparação - Usuário igual: {st.session_state['username'].strip() == 'admin'}")
            print(f"DEBUG LOGIN: Comparação - Senha igual: {st.session_state['password'].strip() == 'admin123'}")
            
            st.session_state["password_correct"] = False
            st.session_state["login_attempt"] = True

    if "auth_cookie" in st.session_state:
        if st.session_state["auth_cookie"].get("exp", 0) > time.time():
            st.session_state["password_correct"] = True
            return True
        else:
            del st.session_state["auth_cookie"]
    
    try:
        if "auth" in st.query_params:
            auth_data = json.loads(base64.b64decode(st.query_params["auth"]).decode())
            if auth_data.get("exp", 0) > time.time():
                st.session_state["auth_cookie"] = auth_data
                st.session_state["password_correct"] = True
                return True
    except:
        pass
    
    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = False
        
    if "login_attempt" not in st.session_state:
        st.session_state["login_attempt"] = False

    if not st.session_state["password_correct"]:
        st.markdown("""
            <style>
                /* Estilo para centralizar e limitar a largura */
                .login-wrapper {
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    min-height: 60vh;
                }
                
                /* Container do login */
                .login-container {
                    width: 100%;
                    max-width: 400px;
                    padding: 2rem;
                    border: 1px solid #ddd;
                    border-radius: 10px;
                    background-color: #f9f9f9;
                    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
                }
                
                .login-title {
                    text-align: center;
                    color: #4CAF50;
                    margin-bottom: 2rem;
                }
                
        
            </style>
        """, unsafe_allow_html=True)
        
        # Cria 3 colunas para centralizar
        col1, col2, col3 = st.columns([1, 3, 1])
        
        with col2:
            with st.container():
                # st.markdown('<div class="login-container">', unsafe_allow_html=True)
                st.markdown('<h1 class="login-title">Login</h1>', unsafe_allow_html=True)
                
                st.text_input("Usuário", key="username")
                st.text_input("Senha", type="password", key="password")
                st.button("Entrar", on_click=password_entered, key="login-button")
                
                if st.session_state.get("login_attempt", False) and not st.session_state["password_correct"]:
                    st.error("Usuário ou senha incorretos")
                
                # st.markdown('</div>', unsafe_allow_html=True)
        
        return False
    else:
        return True

def logout():
    """Faz logout removendo o cookie de autenticação"""
    if "auth_cookie" in st.session_state:
        del st.session_state["auth_cookie"]
    st.session_state["password_correct"] = False
    st.session_state["login_attempt"] = False
    st.rerun()

def get_rag_context():
    """
    Obtém e formata o contexto RAG.    
    """
    if st.session_state.get('use_rag', False):
        if st.session_state.rag_source == "Arquivo":
            if st.session_state.uploaded_file is not None:
                file_type = st.session_state.file_type
                file = st.session_state.uploaded_file
                if file_type == "PDF":
                    return format_context(read_pdf_from_uploaded_file(file), f"Contexto do arquivo PDF: {file.name}")
                elif file_type == "TXT":
                    return format_context(read_txt_from_uploaded_file(file), f"Contexto do arquivo TXT: {file.name}")
                elif file_type == "CSV":
                    return format_context(read_csv_from_uploaded_file(file), f"Contexto do arquivo CSV: {file.name}")
        
        elif st.session_state.rag_source == "Texto Direto":
            if st.session_state.direct_text:
                return format_context(st.session_state.direct_text, "Contexto do Usuário")
    
    return ""






def handle_message():
    """Processa o envio de uma mensagem do usuário"""
    if not st.session_state.user_input or not st.session_state.user_input.strip():
        return
        
    user_message = st.session_state.user_input.strip()
    
    # Marcar para limpar na próxima execução
    st.session_state.clear_input = True
    
    # Verificar duplicatas
    is_duplicate = False
    if len(st.session_state.messages) > 0:
        last_messages = [m for m in st.session_state.messages if m["role"] == "user"]
        if last_messages and last_messages[-1]["content"] == user_message:
            is_duplicate = True
    
    if not is_duplicate:
        timestamp = datetime.now().strftime("%H:%M")
        
        # Adicionar mensagem do usuário
        st.session_state.messages.append({"role": "user", "content": user_message, "time": timestamp})
        
        # Salvar no histórico
        save_current_chat()
        
        is_first_message = len(st.session_state.messages) == 1
        
        with st.chat_message("assistant", avatar=logo_path):
            typing_placeholder = st.empty()
            typing_placeholder.markdown("_Digitando..._")
            
            with st.spinner():
                current_session_id = "" if is_first_message else st.session_state.session_id
                rag_context = get_rag_context()
                result = query_bedrock(user_message, current_session_id, context=rag_context, conversation_history=st.session_state.messages)
            
            if result:
                assistant_message = result.get('answer', 'Não foi possível obter uma resposta.')
                
                if "sessionId" in result:
                    new_session_id = result["sessionId"]
                    st.session_state.session_id = new_session_id
                    
                    if st.session_state.current_chat_index < len(st.session_state.chat_history):
                        st.session_state.chat_history[st.session_state.current_chat_index]["id"] = new_session_id
                
                timestamp = datetime.now().strftime("%H:%M")
                st.session_state.messages.append({
                    "role": "assistant", 
                    "content": assistant_message, 
                    "time": timestamp
                })
                
                # Salvar no histórico
                save_current_chat()
                
                if is_first_message:
                    new_title = extract_title_from_response(assistant_message)
                    st.session_state.chat_title = new_title
                    
                    if st.session_state.current_chat_index < len(st.session_state.chat_history):
                        st.session_state.chat_history[st.session_state.current_chat_index]["title"] = new_title
                
            typing_placeholder.empty()
        
        st.rerun()



def add_javascript():
    """Adiciona JavaScript para melhorar a interação do usuário com o chat"""
    js_code = """
    <script>
    document.addEventListener('DOMContentLoaded', function() {
        function setupEnterKeyListener() {
            const textareas = document.querySelectorAll('textarea');
            textareas.forEach(textarea => {
                textarea.addEventListener('keydown', function(e) {
                    if (e.key === 'Enter' && !e.shiftKey) {
                        e.preventDefault();
                        const sendButton = document.querySelector('button:contains("Enviar")') || 
                                          document.querySelector('[data-testid*="button"]:contains("Enviar")');
                        if (sendButton) {
                            sendButton.click();
                        }
                    }
                });
            });
        }
        
        // Setup inicial
        setTimeout(setupEnterKeyListener, 1000);
        
        // Observer para re-setup quando a página muda
        const observer = new MutationObserver(function(mutations) {
            let shouldSetup = false;
            mutations.forEach(function(mutation) {
                if (mutation.addedNodes.length > 0) {
                    shouldSetup = true;
                }
            });
            if (shouldSetup) {
                setTimeout(setupEnterKeyListener, 100);
            }
        });
        
        observer.observe(document.body, {
            childList: true,
            subtree: true
        });
    });
    </script>
    """
    st.components.v1.html(js_code, height=0)
    
def save_current_chat():
    """Salva a conversa atual no histórico"""
    if st.session_state.current_chat_index < len(st.session_state.chat_history):
        st.session_state.chat_history[st.session_state.current_chat_index]["messages"] = st.session_state.messages.copy()
        st.session_state.chat_history[st.session_state.current_chat_index]["title"] = st.session_state.chat_title
        st.session_state.chat_history[st.session_state.current_chat_index]["id"] = st.session_state.session_id


def extract_title_from_response(response_text):
    """
    Extrai um título resumido da primeira resposta do assistente.
    """
    cleaned_text = re.sub(r'[\U00010000-\U0010ffff]|[\n\r]', '', response_text)
    
    sentences = re.split(r'\.', cleaned_text)
    sentences = [s.strip() for s in sentences if s.strip()]
    
    if not sentences:
        return f"Conversa ({datetime.now().strftime('%d/%m/%Y')})"
    
    sentence = sentences[1] if len(sentences) > 1 and len(sentences[0]) < 15 else sentences[0]
    
    if len(sentence) > 40:
        words = sentence.split()
        title = ""
        for word in words:
            if len(title) + len(word) + 1 <= 40:
                title += " " + word if title else word
            else:
                title += "..."
                break
    else:
        title = sentence
        
    if title and len(title) > 0:
        title = title[0].upper() + title[1:]
        
    return title

def regenerate_message(index):
    """Regenera a resposta a uma mensagem específica"""
    if index < 0 or index >= len(st.session_state.messages) or st.session_state.messages[index]["role"] != "user":
        return
    
    user_message = st.session_state.messages[index]["content"]
    
    status_placeholder = st.empty()
    status_placeholder.info("Regenerando resposta...")
    
    with st.spinner():
        # result = query_bedrock(user_message, st.session_state.session_id, conversation_history=st.session_state.messages)
        result = query_bedrock(user_message, st.session_state.session_id, conversation_history=st.session_state.messages)
        
    if result:
        new_response = result.get('answer', 'Não foi possível regenerar a resposta.')
        
        if index+1 < len(st.session_state.messages) and st.session_state.messages[index+1]["role"] == "assistant":
            timestamp = datetime.now().strftime("%H:%M")
            st.session_state.messages[index+1] = {
                "role": "assistant",
                "content": new_response,
                "time": timestamp
            }
        else:
            timestamp = datetime.now().strftime("%H:%M")
            st.session_state.messages.insert(index+1, {
                "role": "assistant",
                "content": new_response,
                "time": timestamp
            })
    else:
        status_placeholder.error("Não foi possível regenerar a resposta. Por favor, tente novamente.")
        time.sleep(2) 
    
    status_placeholder.empty()
    st.rerun()

def edit_message(index, new_content):
    """Edita uma mensagem e regenera as respostas subsequentes"""
    if index < 0 or index >= len(st.session_state.messages):
        return
    
    st.session_state.messages[index]["content"] = new_content
    st.session_state.messages[index]["time"] = datetime.now().strftime("%H:%M") + " (editada)"
    
    if st.session_state.messages[index]["role"] == "user" and index+1 < len(st.session_state.messages):
        if st.session_state.messages[index+1]["role"] == "assistant":
            regenerate_message(index)
    
    st.rerun()

def create_new_chat():
    """Cria uma nova conversa"""
    st.session_state.session_id = ""
    st.session_state.messages = []
    st.session_state.chat_title = f"Nova Conversa ({datetime.now().strftime('%d/%m/%Y')})"
    
    st.session_state.chat_history.append({
        "id": "",
        "title": st.session_state.chat_title,
        "messages": []
    })
    
    st.session_state.current_chat_index = len(st.session_state.chat_history) - 1

def load_chat(index):
    """Carrega uma conversa existente"""
    st.session_state.current_chat_index = index
    chat = st.session_state.chat_history[index]
    st.session_state.session_id = chat["id"]
    st.session_state.messages = chat["messages"].copy()
    st.session_state.chat_title = chat["title"]
    st.rerun()

def delete_chat(index):
    """Exclui uma conversa"""
    if len(st.session_state.chat_history) > index:
        st.session_state.chat_history.pop(index)
        
        if not st.session_state.chat_history:
            create_new_chat()
        elif st.session_state.current_chat_index >= len(st.session_state.chat_history):
            st.session_state.current_chat_index = len(st.session_state.chat_history) - 1
            load_chat(st.session_state.current_chat_index)
        else:
            load_chat(st.session_state.current_chat_index)

# def rename_chat():
#     """Renomeia uma conversa existente"""
#     if st.session_state.new_chat_title.strip():
#         index = st.session_state.current_chat_index
#         st.session_state.chat_history[index]["title"] = st.session_state.new_chat_title
#         st.session_state.chat_title = st.session_state.new_chat_title
        
#         st.session_state.renaming = False
#         st.rerun()

def rename_chat():
    """Renomeia uma conversa existente"""
    if hasattr(st.session_state, 'new_chat_title') and st.session_state.new_chat_title.strip():
        index = st.session_state.current_chat_index
        st.session_state.chat_history[index]["title"] = st.session_state.new_chat_title
        st.session_state.chat_title = st.session_state.new_chat_title
        
        st.session_state.renaming = False
        st.rerun()

st.markdown("""
    <style>
    /* Estilo Geral */
    .main .block-container {
        padding-top: 1rem;
        padding-bottom: 0;
        max-width: 1200px;
    }
    
    /* Cabeçalho */
    .header {
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        background-color: white;
        z-index: 999;
        padding: 1rem;
        border-bottom: 1px solid #e6e6e6;
    }
    
    /* Mensagens */
    .chat-message {
        padding: 1rem;
        border-radius: 0.5rem;
        margin-bottom: 0.5rem;
        display: flex;
        flex-direction: column;
    }
    
    .user-message {
        background-color: #f0f2f6;
        border-radius: 0.5rem;
        align-self: flex-end;
    }
    
    .assistant-message {
        background-color: #ffffff;
        border: 1px solid #e6e6e6;
        border-radius: 0.5rem;
        align-self: flex-start;
    }
    
    .message-time {
        font-size: 0.8rem;
        color: #666;
        margin-top: 0.5rem;
        align-self: flex-end;
    }
    
    /* Entrada de mensagem */
    .input-container {
        position: fixed;
        bottom: 0;
        left: 50%;
        transform: translateX(-50%);
        width: 90%;
        max-width: 800px;
        background-color: white;
        padding: 1rem;
        border-top: 1px solid #e6e6e6;
        z-index: 998;
    }
    
    /* Sidebar */
    .sidebar .sidebar-content {
        background-color: #f8f9fa;
    }
    
    /* Botões */
    .primary-button {
        background-color: #4CAF50 !important;
        color: white !important;
    }
    
    .secondary-button {
        border: 1px solid #4CAF50 !important;
        color: #4CAF50 !important;
    }
    
    .stButton button {
        border-radius: 4px;
        padding: 0.5rem 1rem;
        font-weight: 500;
    }
    
    /* Message Actions */
    .message-actions {
        display: flex;
        gap: 5px;
        margin-top: 5px;
        justify-content: flex-end;
    }
    
    .action-button {
        background-color: transparent;
        border: none;
        color: #4CAF50;
        cursor: pointer;
        font-size: 12px;
        padding: 2px 5px;
        border-radius: 3px;
    }
    
    .action-button:hover {
        background-color: rgba(76, 175, 80, 0.1);
    }
    
    /* Chat List */
    .chat-item {
        display: flex;
        align-items: center;
        padding: 0.5rem;
        border-radius: 0.25rem;
        margin-bottom: 0.25rem;
        cursor: pointer;
    }
    
    .chat-item:hover {
        background-color: rgba(76, 175, 80, 0.1);
    }
    
    .chat-item.active {
        background-color: rgba(76, 175, 80, 0.2);
        font-weight: bold;
    }
    
    .chat-item-title {
        flex-grow: 1;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
    }
    
    .chat-title {
        text-align: center;
        padding: 1rem;
        font-size: 1.5rem;
        font-weight: bold;
        color: #4CAF50;
    }
    
    /* Custom Scrollbar */
    ::-webkit-scrollbar {
        width: 8px;
        height: 8px;
    }
    ::-webkit-scrollbar-track {
        background: #f1f1f1;
    }
    ::-webkit-scrollbar-thumb {
        background: #4CAF50;
        border-radius: 4px;
    }
    ::-webkit-scrollbar-thumb:hover {
        background: #45a049;
    }
    .attach-icon {
        display: flex;
        align-items: center;
        justify-content: center;
        height: 70px;
        color: #4CAF50;
        cursor: pointer;
        font-size: 20px;
    }
    
    /* Adicionando Font Awesome para o ícone */
    @import url('https://cdnjs.cloudflare.com/ajax/libs/font-awesome/5.15.4/css/all.min.css');
    
    /* Estilo para indicar quando um arquivo foi anexado */
    .file-attached {
        background-color: rgba(76, 175, 80, 0.1);
        border-radius: 4px;
        padding: 4px;
        margin-bottom: 5px;
        font-size: 12px;
        display: flex;
        align-items: center;
        justify-content: space-between;
    }
    
    .file-attached i {
        margin-right: 5px;
    }
    
    /* Estilo para o botão de remover anexo */
    .remove-file {
        color: #f44336;
        cursor: pointer;
    }
    
    /* Esconder elementos Streamlit */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    .stDeployButton {display:none;}
    
    /* Editing message */
    .edit-message-container {
        display: flex;
        flex-direction: column;
        gap: 5px;
        margin-bottom: 10px;
    }
    
    .edit-actions {
        display: flex;
        justify-content: flex-end;
        gap: 5px;
    }
    </style>
""", unsafe_allow_html=True)



if check_password():
    print("DEBUG AUTH: Verificando senha")
    if 'session_id' not in st.session_state:
        st.session_state.session_id = ""
        print("DEBUG: Inicializado session_id vazio")
    else:
        print(f"DEBUG: session_id existente: '{st.session_state.session_id}'")
        
    if 'messages' not in st.session_state:
        st.session_state.messages = []
    
    if 'chat_history' not in st.session_state:
        st.session_state.chat_history = []
        
    if 'current_chat_index' not in st.session_state:
        st.session_state.current_chat_index = 0
        
    if 'chat_title' not in st.session_state:
        st.session_state.chat_title = f"Nova Conversa ({datetime.now().strftime('%d/%m/%Y')})"
        
    if 'renaming' not in st.session_state:
        st.session_state.renaming = False
        
    if 'new_chat_title' not in st.session_state:
        st.session_state.new_chat_title = ""
        
    if 'editing_message' not in st.session_state:
        st.session_state.editing_message = None
        
    if 'edit_content' not in st.session_state:
        st.session_state.edit_content = ""
        
    if not st.session_state.chat_history:
        st.session_state.chat_history.append({
            "id": "",
            "title": st.session_state.chat_title,
            "messages": []
        })

    if 'use_rag' not in st.session_state:
        st.session_state.use_rag = False
    if 'rag_source' not in st.session_state:
        st.session_state.rag_source = "Texto Direto"
    if 'file_type' not in st.session_state:
        st.session_state.file_type = "TXT"
    if 'uploaded_file' not in st.session_state:
        st.session_state.uploaded_file = None
    if 'direct_text' not in st.session_state:
        st.session_state.direct_text = ""

    with st.sidebar:
        # col1, col2 = st.columns([3, 1])
        # with col1:
        st.image(logo_path, width=200)
        # with col2:
        st.markdown('<h2 style="margin:auto; width:100%; padding-top:0px;">Chat IA</h2>', unsafe_allow_html=True)
        
        st.divider()
        
        st.button("🔄 Nova Conversa", on_click=create_new_chat, use_container_width=True)
        
        st.divider()
        
        st.markdown("### Minhas Conversas")
        for idx, chat in enumerate(st.session_state.chat_history):
            col1, col2 = st.columns([5, 1])
            with col1:
                if st.button(f"📝 {chat['title']}", key=f"chat_{idx}", 
                            use_container_width=True,
                            help="Clique para abrir esta conversa"):
                    load_chat(idx)
            with col2:
                if st.button("🗑️", key=f"delete_{idx}", help="Excluir conversa"):
                    delete_chat(idx)
    
    
    #todo se for usar rag descomentar aqui
        #use_rag = st.checkbox("Usar Contexto Adicional (RAG)", value=st.session_state.use_rag)
        use_rag=False
        st.session_state.use_rag = use_rag

        if use_rag:
            rag_source = st.radio(
                "Fonte do Contexto",
                ("Arquivo", "Texto Direto"),
                index=("Arquivo", "Texto Direto").index(st.session_state.rag_source)
            )
            st.session_state.rag_source = rag_source

            if rag_source == "Arquivo":
                file_type = st.selectbox(
                    "Tipo de Arquivo",
                    ("PDF", "TXT", "CSV"),
                    index=("PDF", "TXT", "CSV").index(st.session_state.file_type)
                )
                st.session_state.file_type = file_type
                uploaded_file = st.file_uploader(f"Carregar Arquivo {file_type}", type=file_type, key="file_uploader")
                st.session_state.uploaded_file = uploaded_file

            elif rag_source == "Texto Direto":
                direct_text = st.text_area(
                    "Inserir Texto de Contexto", 
                    value=st.session_state.get('direct_text', ''),
                    height=150, 
                    key="direct_text"
                )
            st.divider()

            if st.button("Logout", use_container_width=True):
                logout()

    main_col1, main_col2, main_col3 = st.columns([1, 10, 1])
    
    with main_col2:
        add_javascript()
        if st.session_state.renaming:
            col1, col2 = st.columns([4, 1])
            with col1:
                st.text_input("Título da Conversa", value=st.session_state.chat_title, key="new_chat_title", label_visibility="collapsed")
            with col2:
                st.button("Salvar", on_click=rename_chat)
        else:
            col1, col2 = st.columns([10, 1])
            with col1:
                st.markdown(f'<div class="chat-title">{st.session_state.chat_title}</div>', unsafe_allow_html=True)
            with col2:
                if st.button("✏️", help="Renomear conversa"):
                    st.session_state.renaming = True
                    st.session_state.new_chat_title = st.session_state.chat_title
                    st.rerun()
        
        messages_container = st.container()
        
        st.markdown("<div style='height: 120px;'></div>", unsafe_allow_html=True)
        

        col1, col2 = st.columns([5,  1])
        if st.session_state.get('clear_input', False):
            st.session_state.user_input = ""
            st.session_state.clear_input = False

        with col1:
            st.text_area("Mensagem", placeholder="Digite sua mensagem aqui...", key="user_input", 
                height=200, label_visibility="collapsed")


        with col2:
                if st.button("Enviar", key="send_button", use_container_width=True):
                    handle_message()
        
        with messages_container:
            for idx, message in enumerate(st.session_state.messages):
                if st.session_state.editing_message == idx:
                    st.markdown('<div class="edit-message-container">', unsafe_allow_html=True)
                    st.text_area("Editar mensagem", value=message["content"], key="edit_content", height=100)
                    
                    st.markdown('<div class="edit-actions">', unsafe_allow_html=True)
                    col1, col2 = st.columns([1, 1])
                    with col1:
                        if st.button("Cancelar", key=f"cancel_edit_{idx}"):
                            st.session_state.editing_message = None
                            st.rerun()
                    with col2:
                        if st.button("Salvar", key=f"save_edit_{idx}"):
                            edit_message(idx, st.session_state.edit_content)
                    st.markdown('</div>', unsafe_allow_html=True)
                    
                    st.markdown('</div>', unsafe_allow_html=True)
                    continue
                
                elif message["role"] == "user":
                    with st.chat_message("user"):
                        st.write(message["content"])
                        st.markdown(f"<div class='message-time'>{message['time']}</div>", unsafe_allow_html=True)
                        
                        st.markdown('<div class="message-actions">', unsafe_allow_html=True)
                        col1, col2 = st.columns([1, 1])
                        with col1:
                            if st.button("Editar", key=f"edit_{idx}"):
                                st.session_state.editing_message = idx
                                st.session_state.edit_content = message["content"]
                                st.rerun()
                        with col2:
                            if idx+1 < len(st.session_state.messages) and message["role"] == "user":
                                if st.button("Regenerar", key=f"regen_{idx}"):
                                    regenerate_message(idx)
                        st.markdown('</div>', unsafe_allow_html=True)
                else:
                    with st.chat_message("assistant", avatar=logo_path):
                        st.write(message["content"])
                        st.markdown(f"<div class='message-time'>{message['time']}</div>", unsafe_allow_html=True)
