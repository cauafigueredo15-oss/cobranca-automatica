# Configurar Webhook do Twilio com Groq AI

Esta solução usa **Twilio Functions** (serverless) para responder mensagens automaticamente usando Groq AI, **sem precisar de servidor próprio ou domínio**.

## Vantagens

✅ **Sem servidor 24/7** - Roda na infraestrutura do Twilio  
✅ **Sem domínio** - Usa URL do Twilio  
✅ **Gratuito** - Twilio Functions tem tier gratuito generoso  
✅ **Instantâneo** - Responde em tempo real  
✅ **Simples** - Tudo em um arquivo JavaScript  

## Passo a Passo

### 1. Criar Twilio Function

1. Acesse o [Twilio Console](https://console.twilio.com/)
2. Vá em **Functions & Assets** → **Services**
3. Clique em **Create Service**
4. Dê um nome (ex: "cobranca-chatbot")
5. Clique em **Add** → **Add Function**
6. Dê um nome (ex: "whatsapp-responder")
7. Cole o código de `twilio-function.js`
8. Clique em **Deploy**

### 2. Configurar Environment Variables

Na página da Function, vá em **Environment Variables** e adicione:

```
GROQ_API_KEY=sua_chave_groq_aqui
DEBTOR_NAME=Samuel Cassiano de Carvalho
INSTALLMENT_VALUE=386.56
INSTALLMENTS=6
PIX_KEY=84988910528
DEBTOR_PHONE=+558488910528
```

### 3. Obter URL da Function

1. Na página da Function, copie a **Function URL**
2. Será algo como: `https://cobranca-chatbot-xxxxx.twil.io/whatsapp-responder`

### 4. Configurar Webhook no WhatsApp Sandbox

1. No Twilio Console, vá em **Messaging** → **Try it out** → **Send a WhatsApp message**
2. Clique na aba **Sandbox settings**
3. No campo **"When a message comes in"**, cole a URL da Function
4. Método: **POST**
5. Clique em **Save**

### 5. Testar

1. Envie uma mensagem do seu WhatsApp para o número do Sandbox: `+1 415 523 8886`
2. Com o código: `join pink-union`
3. Envie uma mensagem como: "Qual o valor da minha dívida?"
4. Você deve receber uma resposta automática da IA!

## Como Funciona

```
1. Cliente envia mensagem → Twilio recebe
2. Twilio chama sua Function → Via webhook
3. Function chama Groq API → Gera resposta com IA
4. Function retorna resposta → Via TwiML
5. Twilio envia resposta → Para o cliente
```

## Customização

Você pode melhorar a Function para:

- **Buscar dados reais**: Conectar com API ou banco de dados para obter informações atualizadas
- **Manter histórico**: Usar Twilio Sync para manter contexto de conversa
- **Validações**: Verificar se número está autorizado
- **Logs**: Adicionar mais logging para debugging

## Limites do Twilio Functions (Gratuito)

- **10 segundos** de execução máxima
- **10 MB** de memória
- **Sufficient para este caso** - Chamadas à Groq são rápidas

## Troubleshooting

### Function não responde
- Verifique se a URL está correta no webhook
- Verifique os logs da Function no Twilio Console
- Verifique se `GROQ_API_KEY` está configurada

### Resposta genérica
- Verifique se as Environment Variables estão configuradas
- Verifique os logs para erros da API Groq

### Erro 500
- Verifique se a `GROQ_API_KEY` é válida
- Verifique se o formato da requisição está correto

## Próximos Passos

1. **Produção**: Quando aprovar sua conta WhatsApp Business, use a mesma Function
2. **Melhorias**: Adicione busca de dados em tempo real
3. **Histórico**: Use Twilio Sync para manter contexto entre mensagens

