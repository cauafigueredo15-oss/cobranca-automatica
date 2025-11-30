#!/usr/bin/env python3
"""
webhook.py

Webhook Flask para receber mensagens do Twilio e responder automaticamente usando IA.
"""
import os
import logging
from flask import Flask, request, Response
from twilio.twiml.messaging_response import MessagingResponse

from cobranca_single import Config
from chatbot_cobranca import create_chatbot, CobrancaChatbot

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
log = logging.getLogger("webhook")

app = Flask(__name__)

# Variáveis globais
chatbot: CobrancaChatbot = None
config: Config = None


def initialize_app():
    """Inicializa configuração e chatbot."""
    global chatbot, config
    
    try:
        config = Config()
        chatbot = create_chatbot(config)
        
        if chatbot:
            log.info("Webhook inicializado com sucesso. Chatbot ativo.")
        else:
            log.warning("Webhook inicializado, mas chatbot não está disponível.")
    except Exception as e:
        log.error("Erro ao inicializar webhook: %s", e)
        chatbot = None


@app.route('/webhook', methods=['POST'])
def webhook():
    """Endpoint para receber mensagens do Twilio."""
    try:
        # Obter dados da mensagem
        incoming_message = request.values.get('Body', '').strip()
        from_number = request.values.get('From', '').replace('whatsapp:', '')
        to_number = request.values.get('To', '').replace('whatsapp:', '')
        
        log.info("Mensagem recebida de %s: %s", from_number, incoming_message[:100])
        
        # Verificar se é do número esperado
        expected_phone = config.debtor_phone.replace('+', '')
        received_phone = from_number.replace('+', '').replace(' ', '')
        
        if expected_phone not in received_phone and received_phone not in expected_phone:
            log.warning("Mensagem de número não autorizado: %s (esperado: %s)", from_number, config.debtor_phone)
            response = MessagingResponse()
            response.message("Desculpe, este número não está autorizado a usar este serviço.")
            return str(response)
        
        # Processar mensagem com chatbot
        if chatbot:
            ai_response = chatbot.process_message(from_number, incoming_message)
        else:
            ai_response = "Desculpe, o sistema de resposta automática está temporariamente indisponível. Entre em contato pelo número principal."
        
        # Criar resposta Twilio
        response = MessagingResponse()
        response.message(ai_response)
        
        log.info("Resposta enviada para %s: %s", from_number, ai_response[:100])
        
        return Response(str(response), mimetype='text/xml')
        
    except Exception as e:
        log.exception("Erro ao processar webhook")
        response = MessagingResponse()
        response.message("Desculpe, ocorreu um erro ao processar sua mensagem.")
        return Response(str(response), mimetype='text/xml')


@app.route('/health', methods=['GET'])
def health():
    """Endpoint de health check."""
    status = {
        "status": "ok",
        "chatbot_available": chatbot is not None,
        "config_loaded": config is not None
    }
    return status, 200


@app.route('/', methods=['GET'])
def index():
    """Página inicial."""
    return {
        "service": "Cobrança Automática - Webhook",
        "status": "running",
        "chatbot": "active" if chatbot else "inactive"
    }, 200


if __name__ == '__main__':
    initialize_app()
    
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
    
    log.info("Iniciando servidor webhook na porta %d", port)
    app.run(host='0.0.0.0', port=port, debug=debug)

