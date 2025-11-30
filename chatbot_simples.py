#!/usr/bin/env python3
"""
chatbot_simples.py

Chatbot simplificado usando apenas a API do Groq diretamente (sem LangChain).
Mais simples, mais confiável e sem dependências complexas.
"""
import os
import logging
from typing import Dict, Optional
from datetime import datetime

try:
    from groq import Groq
    GROQ_AVAILABLE = True
except ImportError:
    Groq = None
    GROQ_AVAILABLE = False

from cobranca_single import Config, CobrancaProcessor, ScheduleItem

log = logging.getLogger("chatbot_simples")


class CobrancaChatbotSimples:
    """Chatbot simplificado para responder mensagens relacionadas à cobrança."""
    
    def __init__(self, config: Config, processor: CobrancaProcessor):
        self.config = config
        self.processor = processor
        self.client = None
        self.conversation_history = {}  # Histórico por número de telefone
        
        if not GROQ_AVAILABLE:
            log.warning("Groq não instalado. Chatbot desabilitado.")
            log.warning("Instale com: pip install groq")
            return
        
        self._initialize_client()
    
    def _initialize_client(self):
        """Inicializa o cliente Groq."""
        groq_api_key = os.environ.get("GROQ_API_KEY")
        if not groq_api_key:
            log.warning("GROQ_API_KEY não configurada. Chatbot desabilitado.")
            return
        
        try:
            self.client = Groq(api_key=groq_api_key)
            log.info("Cliente Groq inicializado com sucesso")
        except Exception as e:
            log.error("Erro ao inicializar Groq: %s", e)
            self.client = None
    
    def _get_context(self) -> str:
        """Obtém contexto atual da cobrança."""
        try:
            schedule = self.processor.build_schedule()
            current_date = self.processor.get_current_date()
            
            # Encontrar parcelas vencidas e próximas
            overdue = []
            upcoming = []
            
            for item in schedule:
                if current_date > item.adjusted_due:
                    overdue.append(f"Parcela {item.installment} vencida em {item.adjusted_due.strftime('%d/%m/%Y')} - R$ {item.amount:.2f}")
                elif current_date == item.adjusted_due:
                    upcoming.append(f"Parcela {item.installment} vencendo HOJE ({item.adjusted_due.strftime('%d/%m/%Y')}) - R$ {item.amount:.2f}")
                elif (item.adjusted_due - current_date).days <= 7:
                    upcoming.append(f"Parcela {item.installment} vence em {item.adjusted_due.strftime('%d/%m/%Y')} - R$ {item.amount:.2f}")
            
            total_debt = sum(item.amount for item in schedule)
            
            context = f"""Informações da Cobrança:
- Devedor: {self.config.debtor_name}
- Total de parcelas: {len(schedule)}
- Valor por parcela: R$ {self.config.installment_value:.2f}
- Total da dívida: R$ {total_debt:.2f}
- Chave PIX: {self.config.pix_key}
- Data atual: {current_date.strftime('%d/%m/%Y')}

"""
            
            if overdue:
                context += f"Parcelas Vencidas:\n" + "\n".join(f"  - {p}" for p in overdue) + "\n\n"
            
            if upcoming:
                context += f"Próximas Parcelas:\n" + "\n".join(f"  - {p}" for p in upcoming) + "\n\n"
            
            if not overdue and not upcoming:
                context += "Nenhuma parcela vencida ou próxima do vencimento.\n\n"
            
            return context
        except Exception as e:
            log.error("Erro ao obter contexto: %s", e)
            return "Erro ao obter informações da cobrança."
    
    def _get_system_prompt(self) -> str:
        """Retorna o prompt do sistema."""
        return """Você é um assistente virtual profissional e educado para cobrança de dívidas.

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

Responda de forma concisa, clara e profissional. Use emojis moderadamente."""
    
    def _get_conversation_history(self, phone: str) -> list:
        """Obtém histórico de conversa para um número."""
        if phone not in self.conversation_history:
            self.conversation_history[phone] = []
        return self.conversation_history[phone]
    
    def process_message(self, phone: str, message: str) -> Optional[str]:
        """
        Processa mensagem recebida e retorna resposta.
        
        Args:
            phone: Número de telefone do remetente
            message: Texto da mensagem recebida
        
        Returns:
            Resposta gerada pela IA ou None se houver erro
        """
        if not self.client:
            return "Desculpe, o sistema de resposta automática está temporariamente indisponível."
        
        try:
            # Obter contexto atual
            context = self._get_context()
            
            # Obter histórico da conversa
            history = self._get_conversation_history(phone)
            
            # Construir mensagens para o Groq
            messages = [
                {
                    "role": "system",
                    "content": f"{self._get_system_prompt()}\n\n{context}"
                }
            ]
            
            # Adicionar histórico (últimas 5 mensagens para não exceder tokens)
            for hist_msg in history[-5:]:
                messages.append(hist_msg)
            
            # Adicionar mensagem atual
            messages.append({
                "role": "user",
                "content": message
            })
            
            # Chamar API do Groq
            # Usando modelo mais inteligente (Mixtral 8x7B - MoE architecture)
            response = self.client.chat.completions.create(
                model="mixtral-8x7b-32768",
                messages=messages,
                temperature=0.7,
                max_tokens=500
            )
            
            # Extrair resposta
            ai_response = response.choices[0].message.content.strip()
            
            # Salvar no histórico
            history.append({"role": "user", "content": message})
            history.append({"role": "assistant", "content": ai_response})
            
            # Manter apenas últimas 10 mensagens no histórico
            if len(history) > 10:
                history[:] = history[-10:]
            
            log.info("Resposta gerada para %s: %s", phone, ai_response[:100])
            return ai_response
            
        except Exception as e:
            log.exception("Erro ao processar mensagem com IA")
            return "Desculpe, ocorreu um erro ao processar sua mensagem. Por favor, tente novamente mais tarde."
    
    def clear_history(self, phone: str):
        """Limpa o histórico de conversa de um número."""
        if phone in self.conversation_history:
            del self.conversation_history[phone]
            log.info("Histórico limpo para %s", phone)


def create_chatbot(config: Config) -> Optional[CobrancaChatbotSimples]:
    """Cria instância do chatbot simplificado."""
    try:
        processor = CobrancaProcessor(config)
        chatbot = CobrancaChatbotSimples(config, processor)
        return chatbot if chatbot.client else None
    except Exception as e:
        log.error("Erro ao criar chatbot: %s", e)
        return None

