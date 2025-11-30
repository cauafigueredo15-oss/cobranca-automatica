#!/usr/bin/env python3
"""
verificar_respostas.py

Verifica mensagens recebidas no Twilio e responde automaticamente usando IA.
Pode ser executado periodicamente via GitHub Actions (não precisa de servidor 24/7).
"""
import os
import sys
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional

try:
    from twilio.rest import Client as TwilioClient
    from twilio.base.exceptions import TwilioException
except ImportError:
    TwilioClient = None
    TwilioException = None

from cobranca_single import Config
from chatbot_cobranca import create_chatbot, CobrancaChatbot

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
log = logging.getLogger("verificar_respostas")


class MessageChecker:
    """Verifica e responde mensagens recebidas no Twilio."""
    
    def __init__(self, config: Config, chatbot: Optional[CobrancaChatbot] = None):
        self.config = config
        self.chatbot = chatbot
        
        if not TwilioClient:
            log.error("Twilio não está instalado")
            return
        
        if not all([config.twilio_account_sid, config.twilio_auth_token]):
            log.error("Credenciais Twilio não configuradas")
            return
        
        try:
            self.client = TwilioClient(config.twilio_account_sid, config.twilio_auth_token)
            log.info("Cliente Twilio inicializado")
        except Exception as e:
            log.error("Erro ao inicializar Twilio: %s", e)
            self.client = None
    
    def get_recent_messages(self, hours: int = 24) -> List[Dict]:
        """
        Obtém mensagens recebidas nas últimas N horas.
        
        Args:
            hours: Número de horas para buscar mensagens
        
        Returns:
            Lista de mensagens recebidas
        """
        if not self.client:
            return []
        
        try:
            # Calcular data de início
            since = datetime.now() - timedelta(hours=hours)
            
            # Buscar mensagens recebidas (inbound)
            # Nota: Twilio busca mensagens onde nosso número é o destinatário
            messages = self.client.messages.list(
                date_sent_after=since,
                to=f"whatsapp:{self.config.twilio_from}"
            )
            
            received_messages = []
            for msg in messages:
                # Filtrar apenas mensagens recebidas (inbound)
                # direction pode ser 'inbound' ou 'inbound-api'
                if msg.direction and "inbound" in msg.direction.lower():
                    received_messages.append({
                        "sid": msg.sid,
                        "from": msg.from_,
                        "body": msg.body or "",
                        "date_sent": msg.date_sent,
                        "status": msg.status
                    })
            
            log.info("Encontradas %d mensagens recebidas nas últimas %d horas", 
                    len(received_messages), hours)
            return received_messages
            
        except TwilioException as e:
            log.error("Erro ao buscar mensagens: %s", e)
            return []
        except Exception as e:
            log.exception("Erro inesperado ao buscar mensagens")
            return []
    
    def send_response(self, to_phone: str, message: str) -> bool:
        """
        Envia resposta via Twilio.
        
        Args:
            to_phone: Número de destino
            message: Mensagem a enviar
        
        Returns:
            True se enviado com sucesso
        """
        if not self.client:
            return False
        
        try:
            response = self.client.messages.create(
                from_=f"whatsapp:{self.config.twilio_from}",
                body=message,
                to=f"whatsapp:{to_phone}"
            )
            log.info("Resposta enviada para %s. SID: %s", to_phone, response.sid)
            return True
        except Exception as e:
            log.error("Erro ao enviar resposta: %s", e)
            return False
    
    def process_messages(self, hours: int = 24):
        """
        Processa mensagens recebidas e responde automaticamente.
        
        Args:
            hours: Horas para verificar mensagens
        """
        if not self.chatbot:
            log.warning("Chatbot não disponível. Respostas automáticas desabilitadas.")
            return
        
        messages = self.get_recent_messages(hours)
        
        if not messages:
            log.info("Nenhuma mensagem nova para processar")
            return
        
        processed = 0
        for msg in messages:
            from_phone = msg["from"].replace("whatsapp:", "")
            message_body = msg["body"]
            
            # Verificar se é do número autorizado
            expected_phone = self.config.debtor_phone.replace("+", "").replace(" ", "")
            received_phone = from_phone.replace("+", "").replace(" ", "")
            
            if expected_phone not in received_phone and received_phone not in expected_phone:
                log.warning("Mensagem de número não autorizado: %s", from_phone)
                continue
            
            log.info("Processando mensagem de %s: %s", from_phone, message_body[:50])
            
            # Gerar resposta com chatbot
            try:
                response = self.chatbot.process_message(from_phone, message_body)
                
                if response:
                    self.send_response(from_phone, response)
                    processed += 1
                else:
                    log.warning("Chatbot não retornou resposta")
            except Exception as e:
                log.exception("Erro ao processar mensagem com chatbot")
        
        log.info("Processadas %d mensagens de %d recebidas", processed, len(messages))


def main():
    """Função principal."""
    try:
        config = Config()
        chatbot = create_chatbot(config)
        
        checker = MessageChecker(config, chatbot)
        checker.process_messages(hours=24)
        
        return 0
    except Exception as e:
        log.exception("Erro fatal ao verificar respostas")
        return 1


if __name__ == "__main__":
    sys.exit(main())

