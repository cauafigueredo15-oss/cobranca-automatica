#!/usr/bin/env python3
"""
chatbot_cobranca.py

Chatbot inteligente para responder mensagens de cobrança usando LangChain e Groq.
Processa mensagens recebidas do Twilio e responde automaticamente usando IA.
"""
import os
import logging
from typing import Dict, Optional
from datetime import date, datetime

try:
    from langchain_groq import ChatGroq
    from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
    from langchain.chains import LLMChain
    from langchain.memory import ConversationBufferMemory
    from langchain_core.messages import HumanMessage, AIMessage
except ImportError:
    try:
        # Fallback para versões antigas
        from langchain.chat_models import ChatGroq
        from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
        from langchain.chains import LLMChain
        from langchain.memory import ConversationBufferMemory
        from langchain.schema import HumanMessage, AIMessage
    except ImportError:
        ChatGroq = None
        ChatPromptTemplate = None
        MessagesPlaceholder = None
        LLMChain = None
        ConversationBufferMemory = None

from cobranca_single import Config, CobrancaProcessor, ScheduleItem

log = logging.getLogger("chatbot_cobranca")


class CobrancaChatbot:
    """Chatbot para responder mensagens relacionadas à cobrança."""
    
    def __init__(self, config: Config, processor: CobrancaProcessor):
        self.config = config
        self.processor = processor
        self.llm = None
        self.memory = {}
        
        if ChatGroq is None:
            log.warning("LangChain/Groq não instalado. Chatbot desabilitado.")
            return
        
        self._initialize_llm()
    
    def _initialize_llm(self):
        """Inicializa o modelo Groq."""
        groq_api_key = os.environ.get("GROQ_API_KEY")
        if not groq_api_key:
            log.warning("GROQ_API_KEY não configurada. Chatbot desabilitado.")
            return
        
        try:
            self.llm = ChatGroq(
                temperature=0.7,
                model_name="llama-3.1-70b-versatile",
                groq_api_key=groq_api_key
            )
            log.info("Chatbot Groq inicializado com sucesso")
        except Exception as e:
            log.error("Erro ao inicializar Groq: %s", e)
            self.llm = None
    
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
            
            context = f"""
Informações da Cobrança:
- Devedor: {self.config.debtor_name}
- Total de parcelas: {len(schedule)}
- Valor por parcela: R$ {self.config.installment_value:.2f}
- Total da dívida: R$ {sum(item.amount for item in schedule):.2f}
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
    
    def _get_prompt_template(self) -> ChatPromptTemplate:
        """Cria template de prompt para o chatbot."""
        system_message = """Você é um assistente virtual profissional e educado para cobrança de dívidas.

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
        
        return ChatPromptTemplate.from_messages([
            ("system", system_message),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{input}")
        ])
    
    def _get_memory(self, phone: str) -> ConversationBufferMemory:
        """Obtém ou cria memória de conversa para um número."""
        if phone not in self.memory:
            self.memory[phone] = ConversationBufferMemory(
                return_messages=True,
                memory_key="chat_history"
            )
        return self.memory[phone]
    
    def process_message(self, phone: str, message: str) -> Optional[str]:
        """
        Processa mensagem recebida e retorna resposta.
        
        Args:
            phone: Número de telefone do remetente
            message: Texto da mensagem recebida
        
        Returns:
            Resposta gerada pela IA ou None se houver erro
        """
        if not self.llm:
            return "Desculpe, o sistema de resposta automática está temporariamente indisponível."
        
        try:
            # Obter contexto atual
            context = self._get_context()
            
            # Obter memória da conversa
            memory = self._get_memory(phone)
            
            # Criar prompt com contexto
            prompt = self._get_prompt_template()
            
            # Adicionar contexto à mensagem
            full_message = f"{context}\n\nMensagem do cliente: {message}"
            
            # Criar chain
            chain = LLMChain(
                llm=self.llm,
                prompt=prompt,
                memory=memory,
                verbose=False
            )
            
            # Gerar resposta
            response = chain.run(input=full_message)
            
            log.info("Resposta gerada para %s: %s", phone, response[:100])
            return response
            
        except Exception as e:
            log.exception("Erro ao processar mensagem com IA")
            return "Desculpe, ocorreu um erro ao processar sua mensagem. Por favor, tente novamente mais tarde."
    
    def clear_memory(self, phone: str):
        """Limpa a memória de conversa de um número."""
        if phone in self.memory:
            del self.memory[phone]
            log.info("Memória limpa para %s", phone)


def create_chatbot(config: Config) -> Optional[CobrancaChatbot]:
    """Cria instância do chatbot."""
    try:
        processor = CobrancaProcessor(config)
        chatbot = CobrancaChatbot(config, processor)
        return chatbot if chatbot.llm else None
    except Exception as e:
        log.error("Erro ao criar chatbot: %s", e)
        return None

