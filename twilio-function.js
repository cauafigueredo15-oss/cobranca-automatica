/**
 * Twilio Function para responder mensagens WhatsApp usando Groq AI
 * 
 * Configuração:
 * 1. No Twilio Console, vá em Functions & Assets
 * 2. Crie uma nova Function
 * 3. Cole este código
 * 4. Adicione as Environment Variables:
 *    - GROQ_API_KEY: sua chave da Groq
 *    - DEBTOR_NAME: nome do devedor
 *    - INSTALLMENT_VALUE: valor da parcela
 *    - PIX_KEY: chave PIX
 * 5. Configure o webhook do WhatsApp Sandbox para apontar para esta função
 */

const https = require('https');

exports.handler = async function(context, event, callback) {
    // Se for acesso direto via GET (não é webhook do Twilio)
    if (!event.Body && !event.From) {
        const response = new Twilio.Response();
        response.setStatusCode(200);
        response.setBody('Function está funcionando! Configure o webhook do WhatsApp Sandbox para usar esta função.');
        response.appendHeader('Content-Type', 'text/plain');
        return callback(null, response);
    }
    
    const twiml = new Twilio.twiml.MessagingResponse();
    
    try {
        // Obter mensagem recebida
        const incomingMessage = event.Body || '';
        const fromNumber = event.From || '';
        
        console.log(`=== Nova mensagem ===`);
        console.log(`De: ${fromNumber}`);
        console.log(`Mensagem: ${incomingMessage}`);
        console.log(`Event completo:`, JSON.stringify(event));
        
        // Verificar se GROQ_API_KEY está configurada
        const groqApiKey = context.GROQ_API_KEY;
        console.log(`GROQ_API_KEY configurada: ${groqApiKey ? 'SIM (primeiros 10 chars: ' + groqApiKey.substring(0, 10) + '...)' : 'NÃO'}`);
        
        if (!groqApiKey) {
            console.error('ERRO: GROQ_API_KEY não configurada nas Environment Variables');
            twiml.message('⚠️ Erro de configuração: GROQ_API_KEY não encontrada. Verifique as Environment Variables no Twilio Console.');
            return callback(null, twiml);
        }
        
        // Verificar outras variáveis
        console.log(`DEBTOR_NAME: ${context.DEBTOR_NAME || 'não configurado'}`);
        console.log(`PIX_KEY: ${context.PIX_KEY || 'não configurado'}`);
        
        // Obter contexto da cobrança
        const contextInfo = getCobrancaContext(context);
        console.log('Contexto gerado (primeiros 200 chars):', contextInfo.substring(0, 200));
        
        // Gerar resposta com Groq
        console.log('Chamando API Groq...');
        const aiResponse = await callGroqAPI(groqApiKey, incomingMessage, contextInfo);
        console.log('✅ Resposta recebida (primeiros 200 chars):', aiResponse.substring(0, 200));
        
        twiml.message(aiResponse);
        
    } catch (error) {
        console.error('❌ ERRO na Function:');
        console.error('Tipo:', error.constructor.name);
        console.error('Mensagem:', error.message);
        console.error('Stack:', error.stack);
        console.error('Error completo:', JSON.stringify(error, Object.getOwnPropertyNames(error)));
        
        // Mensagem de erro mais informativa
        let errorMessage = 'Desculpe, ocorreu um erro ao processar sua mensagem.';
        
        // Se for erro específico da API, dar mais detalhes
        if (error.message && error.message.includes('Groq API')) {
            errorMessage += ' Erro na API Groq. Verifique os logs no Twilio Console.';
        } else if (error.message && error.message.includes('Timeout')) {
            errorMessage += ' A requisição demorou muito. Tente novamente.';
        }
        
        twiml.message(errorMessage + ' Tente novamente mais tarde.');
    }
    
    return callback(null, twiml);
};

/**
 * Obtém contexto da cobrança
 * Nota: Em produção, você pode buscar isso de uma API ou banco de dados
 */
function getCobrancaContext(context) {
    const debtorName = context.DEBTOR_NAME || 'Cliente';
    const installmentValue = context.INSTALLMENT_VALUE || '386.56';
    const pixKey = context.PIX_KEY || '84988910528';
    const installments = context.INSTALLMENTS || '6';
    
    const totalDebt = (parseFloat(installmentValue) * parseInt(installments)).toFixed(2);
    
    return `Informações da Cobrança:
- Devedor: ${debtorName}
- Total de parcelas: ${installments}
- Valor por parcela: R$ ${installmentValue}
- Total da dívida: R$ ${totalDebt}
- Chave PIX: ${pixKey}

Para mais informações sobre parcelas específicas, pergunte diretamente.`;
}

/**
 * Chama a API do Groq para gerar resposta
 */
function callGroqAPI(apiKey, userMessage, contextInfo) {
    return new Promise((resolve, reject) => {
        const systemPrompt = `Você é um assistente virtual profissional e educado para cobrança de dívidas.

Sua função é:
1. Responder perguntas sobre a dívida de forma clara e objetiva
2. Fornecer informações sobre parcelas, valores e vencimentos
3. Orientar sobre formas de pagamento (PIX)
4. Ser empático e profissional, mas firme quando necessário
5. NUNCA ser agressivo ou ameaçador
6. Sempre manter tom respeitoso e profissional

Informações importantes:
- Use a chave PIX fornecida no contexto para pagamentos
- Sempre mencione valores em Reais (R$)
- Seja claro sobre datas de vencimento
- Se houver parcelas vencidas, mencione mas seja educado

Responda de forma concisa, clara e profissional. Use emojis moderadamente.`;

        const requestData = JSON.stringify({
            model: "llama-3.1-70b-versatile",
            messages: [
                {
                    role: "system",
                    content: `${systemPrompt}\n\n${contextInfo}`
                },
                {
                    role: "user",
                    content: userMessage
                }
            ],
            temperature: 0.7,
            max_tokens: 500
        });

        const options = {
            hostname: 'api.groq.com',
            path: '/openai/v1/chat/completions',
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${apiKey}`,
                'Content-Length': Buffer.byteLength(requestData),
                'User-Agent': 'Twilio-Function/1.0'
            }
        };
        
        console.log('Requisição Groq - URL: https://api.groq.com/openai/v1/chat/completions');
        console.log('Requisição Groq - Model: llama-3.1-70b-versatile');
        console.log('Requisição Groq - Request data (primeiros 300 chars):', requestData.substring(0, 300));

        const req = https.request(options, (res) => {
            let data = '';

            res.on('data', (chunk) => {
                data += chunk;
            });

            res.on('end', () => {
                console.log(`Groq API resposta - Status: ${res.statusCode}`);
                console.log(`Groq API resposta - Headers:`, JSON.stringify(res.headers));
                console.log(`Groq API resposta - Data (primeiros 500 chars):`, data.substring(0, 500));
                
                try {
                    if (res.statusCode !== 200) {
                        console.error(`❌ Erro HTTP da Groq: ${res.statusCode}`);
                        console.error(`Resposta completa:`, data);
                        
                        // Tentar parsear erro da Groq
                        try {
                            const errorResponse = JSON.parse(data);
                            if (errorResponse.error) {
                                reject(new Error(`Groq API Error (${res.statusCode}): ${errorResponse.error.message || JSON.stringify(errorResponse.error)}`));
                            } else {
                                reject(new Error(`Groq API retornou status ${res.statusCode}: ${data.substring(0, 500)}`));
                            }
                        } catch (e) {
                            reject(new Error(`Groq API retornou status ${res.statusCode}: ${data.substring(0, 500)}`));
                        }
                        return;
                    }
                    
                    const response = JSON.parse(data);
                    console.log('✅ Resposta Groq parseada (primeiros 300 chars):', JSON.stringify(response).substring(0, 300));
                    
                    if (response.choices && response.choices[0] && response.choices[0].message) {
                        const content = response.choices[0].message.content.trim();
                        console.log(`✅ Conteúdo extraído (primeiros 200 chars):`, content.substring(0, 200));
                        resolve(content);
                    } else if (response.error) {
                        console.error('❌ Erro na resposta Groq:', response.error);
                        reject(new Error(`Groq API Error: ${response.error.message || JSON.stringify(response.error)}`));
                    } else {
                        console.error('❌ Resposta inválida da Groq:', JSON.stringify(response).substring(0, 500));
                        reject(new Error('Resposta inválida da Groq: ' + JSON.stringify(response).substring(0, 500)));
                    }
                } catch (error) {
                    console.error('❌ Erro ao parsear resposta:', error.message);
                    console.error('Data recebida (primeiros 1000 chars):', data.substring(0, 1000));
                    reject(new Error('Erro ao parsear resposta: ' + error.message));
                }
            });
        });

        req.on('error', (error) => {
            console.error('Erro na requisição HTTPS:', error);
            reject(error);
        });

        // Timeout de 8 segundos (Functions têm limite de 10s)
        req.setTimeout(8000, () => {
            req.destroy();
            reject(new Error('Timeout ao chamar API Groq'));
        });

        req.write(requestData);
        req.end();
    });
}

