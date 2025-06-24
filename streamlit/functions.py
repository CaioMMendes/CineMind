import boto3
import json
import uuid
from datetime import datetime
import os
import pandas as pd
import PyPDF2

PROFILE_NAME = os.environ.get('AWS_PROFILE', 'edn174')

def get_boto3_client(service_name, region_name='us-east-1', profile_name='edn174'):
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

def read_pdf(file_path):
    """Lê o conteúdo de um arquivo PDF e retorna como string."""
    try:
        with open(file_path, 'rb') as file:
            reader = PyPDF2.PdfReader(file)
            text = ""
            for page in reader.pages:
                text += page.extract_text() + "\n"
        return text
    except Exception as e:
        return f"Erro ao ler PDF: {str(e)}"

def read_txt(file_path):
    """Lê o conteúdo de um arquivo TXT e retorna como string."""
    try:
        with open(file_path, 'r') as file:
            return file.read()
    except Exception as e:
        return f"Erro ao ler TXT: {str(e)}"

def read_csv(file_path):
    """Lê o conteúdo de um arquivo CSV e retorna como string."""
    try:
        df = pd.read_csv(file_path)
        return df.to_string()
    except Exception as e:
        return f"Erro ao ler CSV: {str(e)}"
    
def format_context(context, source="Contexto Adicional"):
    """Formata o contexto para ser adicionado ao prompt."""
    return f"\n\n{source}:\n{context}\n\n"

#ALTERAR
def generate_chat_prompt(user_message, conversation_history=None, context=""):
    """
    Gera um prompt de chat completo com histórico de conversa e contexto opcional.
    """
    
    #todo colocar o prompt aqui
    system_prompt = """
## IDENTIDADE E CONTEXTO
Você é um assistente especializado em recomendações cinematográficas. Seu objetivo é ajudar usuários a descobrir filmes adequados às suas preferências, oferecendo sugestões personalizadas com informações úteis e precisas.

## DIRETRIZES DE COMPORTAMENTO

### Comunicação
- Mantenha sempre um tom amigável, respeitoso e profissional
- Use linguagem clara e acessível para todos os públicos
- Seja entusiástico sobre cinema sem ser exagerado
- Evite jargões técnicos excessivos, explicando termos quando necessário
- Responda em português brasileiro de forma natural

### Segurança de Conteúdo (GUARDRAILS)
- NUNCA recomende filmes com conteúdo explícito, violência gráfica extrema ou temáticas inadequadas
- Evite filmes com classificação indicativa muito restritiva sem avisar o usuário
- Não use linguagem ofensiva, palavrões ou expressões agressivas
- Mantenha sempre uma postura educada e construtiva
- Se questionado sobre filmes inadequados, redirecione educadamente para alternativas apropriadas
- Priorize sempre o bem-estar e a segurança do usuário

### Filtragem de Conteúdo
- Filmes com classificação 18+ apenas se explicitamente solicitado e com aviso claro
- Evite horror extremo, violência gratuita ou conteúdo perturbador
- Priorize filmes com valores positivos e mensagens construtivas
- Para menores, sempre considere a adequação etária

## ESTRUTURA DE RESPOSTA

Para cada solicitação de recomendação, siga este formato:

### Introdução Personalizada
- Cumprimente o usuário de forma calorosa
- Reconheça suas preferências mencionadas
- Demonstre entusiasmo pela tarefa

### Lista de Recomendações (3-5 filmes)
Para cada filme, inclua:

**[TÍTULO DO FILME] ([ANO])**
- **Sinopse:** [7-8 frases descrevendo a história de forma envolvente, sem spoilers]
- **Gênero:** [Gêneros principais]
- **Classificação:** [Classificação indicativa]
- **Onde assistir:** [Plataformas de streaming disponíveis no Brasil]
- **Por que recomendo:** [1-2 frases explicando por que se adequa ao pedido]

### Conclusão
- Pergunte se deseja mais recomendações
- Ofereça ajuda adicional (trailers, curiosidades, etc.)
- Mantenha o engajamento de forma positiva

## INSTRUÇÕES ESPECÍFICAS

### Coleta de Informações
Se o usuário não fornecer preferências claras, pergunte educadamente sobre:
- Gêneros preferidos
- Filmes que gostou recentemente
- Humores ou temas de interesse
- Restrições etárias
- Tempo disponível (filme ou série)

### Verificação de Disponibilidade
- Priorize filmes disponíveis em plataformas brasileiras populares
- Mencione se o filme está disponível gratuitamente ou por aluguel
- Se não souber a disponibilidade atual, seja honesto e sugira verificar

### Diversidade nas Recomendações
- Varie entre produções nacionais e internacionais
- Inclua diferentes épocas e estilos quando apropriado
- Considere representatividade e diversidade cultural

## SITUAÇÕES ESPECIAIS

### Pedidos Inadequados
Se o usuário solicitar conteúdo inapropriado:
"Prefiro focar em filmes que oferecem entretenimento positivo. Que tal explorarmos [alternativa adequada]?"

### Dúvidas sobre Classificação
Sempre informe a classificação e explique brevemente o motivo quando relevante.

### Filmes Não Encontrados
Se não conhecer um filme específico mencionado, seja honesto e peça mais detalhes.

## EXEMPLO DE RESPOSTA

"Olá! Que ótimo que você está procurando por filmes de aventura! Preparei algumas sugestões incríveis que tenho certeza que você vai adorar:

**FILME EXEMPLO (2023)**
- **Sinopse:** Uma jornada épica sobre amizade e coragem em terras místicas.
- **Gênero:** Aventura, Fantasia
- **Classificação:** 12 anos
- **Onde assistir:** Netflix, Amazon Prime Video
- **Por que recomendo:** Combina ação emocionante com uma história tocante sobre superação.

Gostaria de mais recomendações ou tem algum gênero específico em mente?"

## LEMBRETE FINAL
Sempre priorize a experiência positiva do usuário, oferecendo recomendações que enriqueçam sua jornada cinematográfica de forma segura e adequada.
    """

    conversation_context = ""
    if conversation_history and len(conversation_history) > 0:
      conversation_context = "Histórico da conversa:\n"
      recent_messages = conversation_history[-8:]
      for message in recent_messages:
        role = "Usuário" if message.get('role') == 'user' else "Assistente"
        conversation_context += f"{role}: {message.get('content')}\n"
      conversation_context += "\n"

    full_prompt = f"{system_prompt}\n\n{conversation_context}{context}Usuário: {user_message}\n\nAssistente:"
    
    return full_prompt

#todo alterar os parametros do modelo
def invoke_bedrock_model(prompt, inference_profile_arn, model_params=None):
    """
    Invoca um modelo no Amazon Bedrock usando um Inference Profile.
    """
    if model_params is None:
        model_params = {
        "temperature": 0.6,
        "top_p": 0.8,
        "top_k": 50,
        "max_tokens": 800
        }
        


    bedrock_runtime = get_boto3_client('bedrock-runtime')

    if not bedrock_runtime:
        return {
        "error": "Não foi possível conectar ao serviço Bedrock.",
        "answer": "Erro de conexão com o modelo.",
        "sessionId": str(uuid.uuid4())
        }

    try:
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
        modelId=inference_profile_arn,  # Usando o ARN do Inference Profile
        body=body,
        contentType="application/json",
        accept="application/json"
    )
        
        response_body = json.loads(response['body'].read())
        answer = response_body['content'][0]['text']
            
        return {
            "answer": answer,
            "sessionId": str(uuid.uuid4())
        }
        
    except Exception as e:
        print(f"ERRO: Falha na invocação do modelo Bedrock: {str(e)}")
        print(f"ERRO: Exception details: {e}")
        return {
            "error": str(e),
            "answer": f"Ocorreu um erro ao processar sua solicitação: {str(e)}. Por favor, tente novamente.",
            "sessionId": str(uuid.uuid4())
        }
        
        
        
        
def read_pdf_from_uploaded_file(uploaded_file):
    """Lê o conteúdo de um arquivo PDF carregado pelo Streamlit."""
    try:
        import io
        from PyPDF2 import PdfReader
        
        pdf_bytes = io.BytesIO(uploaded_file.getvalue())
        reader = PdfReader(pdf_bytes)
        text = ""
        for page in reader.pages:
            text += page.extract_text() + "\n"
        return text
    except Exception as e:
        return f"Erro ao ler PDF: {str(e)}"
    
    
    
    

def read_txt_from_uploaded_file(uploaded_file):
    """Lê o conteúdo de um arquivo TXT carregado pelo Streamlit."""
    try:
        return uploaded_file.getvalue().decode("utf-8")
    except Exception as e:
        return f"Erro ao ler TXT: {str(e)}"
    
    
    
    

def read_csv_from_uploaded_file(uploaded_file):
    """Lê o conteúdo de um arquivo CSV carregado pelo Streamlit."""
    try:
        import pandas as pd
        import io
        
        df = pd.read_csv(io.StringIO(uploaded_file.getvalue().decode("utf-8")))
        return df.to_string()
    except Exception as e:
        return f"Erro ao ler CSV: {str(e)}"