# Chatbot de Cobrança com LangChain e Groq

Sistema de resposta automática para mensagens de cobrança usando IA.

## Funcionalidades

- ✅ Recebe mensagens do Twilio via webhook
- ✅ Processa mensagens com LangChain e Groq (Llama 3.1 70B)
- ✅ Responde automaticamente sobre dívidas, parcelas e pagamentos
- ✅ Mantém contexto da conversa
- ✅ Integrado com o sistema de cobrança existente

## Configuração

### 1. Secrets do GitHub (ou variáveis de ambiente)

Adicione no GitHub: Settings → Secrets and variables → Actions

```
GROQ_API_KEY=seu_api_key_groq_aqui
```

### 2. Configurar Webhook no Twilio

1. Acesse o [Console do Twilio](https://console.twilio.com/)
2. Vá em Messaging → Settings → WhatsApp Sandbox (ou WhatsApp Business)
3. Configure o webhook URL:
   - URL: `https://seu-dominio.com/webhook`
   - Método: POST

### 3. Executar o Webhook

#### Opção A: Localmente (para testes)

```bash
# Instalar dependências
pip install -r requirements.txt

# Configurar variáveis de ambiente
export GROQ_API_KEY=sua_chave
export TWILIO_ACCOUNT_SID=seu_sid
export TWILIO_AUTH_TOKEN=seu_token
# ... outras variáveis

# Executar
python webhook.py
```

#### Opção B: Deploy em produção

Recomendado usar serviços como:
- **Railway**: https://railway.app
- **Render**: https://render.com
- **Fly.io**: https://fly.io
- **Heroku**: https://heroku.com

Configure as variáveis de ambiente no serviço escolhido.

## Como Funciona

1. **Mensagem recebida**: Twilio envia POST para `/webhook`
2. **Validação**: Verifica se o número é autorizado
3. **Processamento**: Chatbot usa LangChain + Groq para gerar resposta
4. **Contexto**: Sistema fornece informações atualizadas sobre a dívida
5. **Resposta**: Retorna mensagem formatada via Twilio

## Exemplo de Uso

**Cliente**: "Qual o valor da minha dívida?"

**Bot**: "Olá! Sua dívida total é de R$ 2.319,36, dividida em 6 parcelas de R$ 386,56. Atualmente você tem 1 parcela vencida (Parcela 1 - vencida em 05/01/2026). Para pagar, utilize a chave PIX: 84988910528."

## Variáveis de Ambiente Necessárias

```bash
# Groq
GROQ_API_KEY=seu_api_key

# Twilio (já configurado)
TWILIO_ACCOUNT_SID=...
TWILIO_AUTH_TOKEN=...
TWILIO_FROM=...

# Configurações de cobrança (já configuradas)
DEBTOR_PHONE=...
PIX_KEY=...
# ... outras
```

## Testando Localmente

Use ngrok para expor o webhook localmente:

```bash
# Terminal 1: Iniciar webhook
python webhook.py

# Terminal 2: Expor com ngrok
ngrok http 5000

# Use a URL do ngrok no Twilio webhook
```

## Notas

- O chatbot mantém memória de conversa por número de telefone
- Respostas são geradas usando Llama 3.1 70B via Groq
- Sistema valida se mensagem vem do número autorizado
- Logs detalhados para debugging

