#!/usr/bin/env python3
"""
cobranca_single.py

Sistema automatizado de cobrança para um único devedor.
- Calcula parcelas com ajuste para dias úteis
- Calcula multa e juros de mora conforme contrato
- Envia notificações via WhatsApp (Twilio) e Email

Configurações via variáveis de ambiente:
- START_YEAR, START_MONTH, START_DAY: Data inicial (padrão: 2026-01-05)
- INSTALLMENTS: Número de parcelas (padrão: 6)
- INSTALLMENT_VALUE: Valor da parcela (padrão: 386.56)
- DEBTOR_NAME, DEBTOR_CPF, DEBTOR_EMAIL, DEBTOR_PHONE: Dados do devedor
- TIMEZONE: Fuso horário (padrão: America/Sao_Paulo)
- TEST_MODE: Modo de teste true/false (padrão: false)
- MULTA_PERCENT: Percentual de multa (padrão: 2.0)
- INTEREST_MONTHLY_PERCENT: Juros mensais (padrão: 1.0)
- GRACE_DAYS: Dias de carência (padrão: 0)
- NOW_OVERRIDE: Data forçada para testes (formato: YYYY-MM-DD)
- WHATSAPP_PROVIDER: Provedor WhatsApp (padrão: none, opções: twilio)
- TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_FROM: Credenciais Twilio
"""
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
import os
import sys
import logging
from typing import Dict, List, Optional, Tuple

import pytz
from dateutil.relativedelta import relativedelta

try:
    import holidays
except ImportError:
    holidays = None
    logging.warning("Biblioteca 'holidays' não encontrada. Feriados não serão considerados.")

try:
    from twilio.rest import Client as TwilioClient
    from twilio.base.exceptions import TwilioException
except ImportError:
    TwilioClient = None
    TwilioException = None

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
log = logging.getLogger("cobranca_single")


class ConfigError(Exception):
    """Exceção para erros de configuração."""
    pass


class ValidationError(Exception):
    """Exceção para erros de validação."""
    pass


class Config:
    """Classe para gerenciar configurações do sistema."""
    
    def __init__(self):
        self.start_year = self._get_int("START_YEAR", 2026)
        self.start_month = self._get_int("START_MONTH", 1)
        self.business_days_after_month_start = self._get_int("BUSINESS_DAYS_AFTER_MONTH_START", 5)
        self.installments = self._get_int("INSTALLMENTS", 6)
        self.installment_value = self._get_decimal("INSTALLMENT_VALUE", "386.56")
        self.debtor_name = os.environ.get("DEBTOR_NAME", "Samuel Cassiano de Carvalho")
        self.debtor_cpf = os.environ.get("DEBTOR_CPF", "REDACTED")
        self.debtor_email = os.environ.get("DEBTOR_EMAIL", "samuelsamuelheibr@hotmail.com")
        self.debtor_phone = os.environ.get("DEBTOR_PHONE", "+558487796531")
        self.timezone = os.environ.get("TIMEZONE", "America/Sao_Paulo")
        self.test_mode = os.environ.get("TEST_MODE", "false").lower() in ("1", "true", "yes")
        self.multa_percent = self._get_decimal("MULTA_PERCENT", "2.0")
        self.interest_monthly_percent = self._get_decimal("INTEREST_MONTHLY_PERCENT", "1.0")
        self.grace_days = self._get_int("GRACE_DAYS", 0)
        self.currency = os.environ.get("CURRENCY", "BRL")
        self.now_override = os.environ.get("NOW_OVERRIDE")
        self.pix_key = os.environ.get("PIX_KEY", "84988910528")
        
        # Twilio
        self.whatsapp_provider = os.environ.get("WHATSAPP_PROVIDER", "none")
        self.twilio_account_sid = os.environ.get("TWILIO_ACCOUNT_SID")
        self.twilio_auth_token = os.environ.get("TWILIO_AUTH_TOKEN")
        self.twilio_from = os.environ.get("TWILIO_FROM")
        
        self._validate()
        self.tz = pytz.timezone(self.timezone)
    
    def _get_int(self, key: str, default: int) -> int:
        """Obtém valor inteiro da variável de ambiente."""
        try:
            return int(os.environ.get(key, str(default)))
        except ValueError:
            log.warning("Valor inválido para %s, usando padrão: %d", key, default)
            return default
    
    def _get_decimal(self, key: str, default: str) -> Decimal:
        """Obtém valor decimal da variável de ambiente."""
        try:
            return Decimal(os.environ.get(key, default))
        except (ValueError, InvalidOperation):
            log.warning("Valor inválido para %s, usando padrão: %s", key, default)
            return Decimal(default)
    
    def _validate(self):
        """Valida as configurações."""
        errors = []
        
        if not (1 <= self.start_month <= 12):
            errors.append(f"Mês inicial inválido: {self.start_month}")
        
        if self.business_days_after_month_start < 1:
            errors.append(f"Dias úteis após início do mês deve ser >= 1: {self.business_days_after_month_start}")
        
        if self.installments < 1:
            errors.append(f"Número de parcelas inválido: {self.installments}")
        
        if self.installment_value <= 0:
            errors.append(f"Valor da parcela deve ser positivo: {self.installment_value}")
        
        if self.multa_percent < 0:
            errors.append(f"Percentual de multa não pode ser negativo: {self.multa_percent}")
        
        if self.interest_monthly_percent < 0:
            errors.append(f"Percentual de juros não pode ser negativo: {self.interest_monthly_percent}")
        
        if self.grace_days < 0:
            errors.append(f"Dias de carência não podem ser negativos: {self.grace_days}")
        
        if not self.debtor_phone or not self.debtor_phone.startswith("+"):
            errors.append(f"Telefone deve estar no formato internacional (+55...): {self.debtor_phone}")
        
        if self.whatsapp_provider == "twilio" and not self.test_mode:
            if not all([self.twilio_account_sid, self.twilio_auth_token, self.twilio_from]):
                errors.append("Credenciais Twilio não configuradas (necessárias quando TEST_MODE=false)")
        
        if errors:
            raise ConfigError("Erros de configuração:\n" + "\n".join(f"  - {e}" for e in errors))


class ScheduleItem:
    """Representa um item do cronograma de pagamento."""
    
    def __init__(self, installment: int, original_due: date, adjusted_due: date, amount: Decimal):
        self.installment = installment
        self.original_due = original_due
        self.adjusted_due = adjusted_due
        self.amount = amount
    
    def __repr__(self):
        return (f"ScheduleItem(installment={self.installment}, "
                f"original={self.original_due.isoformat()}, "
                f"adjusted={self.adjusted_due.isoformat()}, "
                f"amount={self.amount})")


class PaymentCalculator:
    """Calcula multas e juros de mora."""
    
    def __init__(self, multa_percent: Decimal, interest_monthly_percent: Decimal, grace_days: int):
        self.multa_percent = multa_percent
        self.interest_monthly_percent = interest_monthly_percent
        self.grace_days = grace_days
    
    def calculate_late_fees(self, amount: Decimal, days_overdue: int) -> Dict[str, Decimal]:
        """
        Calcula multa e juros de mora.
        
        Args:
            amount: Valor base da parcela
            days_overdue: Dias em atraso (já considerando grace_days)
        
        Returns:
            Dict com 'multa', 'juros' e 'total'
        """
        if days_overdue <= 0:
            return {
                "multa": Decimal("0.00"),
                "juros": Decimal("0.00"),
                "total": amount
            }
        
        # Multa fixa (percentual sobre o valor)
        multa = (amount * self.multa_percent / Decimal("100")).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        
        # Juros pro rata (1% ao mês = monthly_rate/30 por dia)
        monthly_rate = self.interest_monthly_percent / Decimal("100")
        daily_rate = monthly_rate / Decimal("30")
        juros = (amount * daily_rate * Decimal(days_overdue)).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        
        total = (amount + multa + juros).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        
        return {
            "multa": multa,
            "juros": juros,
            "total": total
        }
    
    def get_days_overdue(self, due_date: date, current_date: date) -> int:
        """Calcula dias em atraso considerando grace_days."""
        return max(0, (current_date - due_date).days - self.grace_days)


class BusinessDayAdjuster:
    """Ajusta datas para dias úteis."""
    
    def __init__(self, timezone: str):
        self.timezone = timezone
        self.br_holidays = self._load_holidays()
    
    def _load_holidays(self):
        """Carrega feriados brasileiros."""
        if holidays is None:
            return None
        try:
            # Carrega feriados para os próximos 2 anos
            current_year = datetime.now().year
            return holidays.Brazil(years=[current_year, current_year + 1])
        except Exception as e:
            log.warning("Não foi possível carregar feriados: %s", e)
            return None
    
    def is_business_day(self, d: date) -> bool:
        """Verifica se a data é um dia útil."""
        # Finais de semana
        if d.weekday() >= 5:
            return False
        # Feriados
        if self.br_holidays and d in self.br_holidays:
            return False
        return True
    
    def adjust_to_next_business_day(self, d: date) -> date:
        """Ajusta a data para o próximo dia útil."""
        original = d
        while not self.is_business_day(d):
            d = d + timedelta(days=1)
        if d != original:
            log.debug("Data ajustada: %s -> %s", original.isoformat(), d.isoformat())
        return d
    
    def get_nth_business_day_of_month(self, year: int, month: int, n: int) -> date:
        """
        Retorna o N-ésimo dia útil do mês.
        
        Args:
            year: Ano
            month: Mês (1-12)
            n: Número do dia útil (1 = primeiro dia útil do mês)
        
        Returns:
            Data do N-ésimo dia útil
        """
        # Começa no dia 1 do mês
        current = date(year, month, 1)
        business_days_count = 0
        
        while business_days_count < n:
            if self.is_business_day(current):
                business_days_count += 1
                if business_days_count == n:
                    return current
            current = current + timedelta(days=1)
        
        return current


class MessageBuilder:
    """Constrói mensagens de cobrança."""
    
    def __init__(self, currency: str = "BRL", pix_key: str = ""):
        self.currency = currency
        self.pix_key = pix_key
    
    def build_message(self, debtor_name: str, installment: int, amount: Decimal,
                     due_date: date, schedule: List[ScheduleItem], current_date: date,
                     fines: Optional[Dict[str, Decimal]] = None) -> str:
        """
        Constrói mensagem de cobrança formatada.
        
        Args:
            debtor_name: Nome do devedor
            installment: Número da parcela atual
            amount: Valor da parcela
            due_date: Data de vencimento
            schedule: Lista completa de parcelas
            current_date: Data atual
            fines: Dict com multa, juros e total (opcional)
        
        Returns:
            Mensagem formatada
        """
        # Calcular total da dívida
        total_debt = sum(item.amount for item in schedule)
        
        # Construir mensagem
        lines = [
            f"💳 *Cobrança*",
            f"",
            f"*{debtor_name}*",
            f"{self.currency} {total_debt:.2f} ({len(schedule)}x de {self.currency} {amount:.2f})",
            f"",
            f"━━━━━━━━━━━━━━━━━━━━",
            f"",
        ]
        
        # Lista de parcelas
        for item in schedule:
            status = "✅" if current_date > item.adjusted_due else ("📅" if current_date == item.adjusted_due else "⏳")
            month_name = self._get_month_name_pt(item.adjusted_due.month)
            date_str = f"{item.adjusted_due.day:02d} {month_name}"
            
            if current_date >= item.adjusted_due:
                lines.append(f"{date_str} - {self.currency} {item.amount:.2f} {status}")
            else:
                lines.append(f"{date_str} - {self.currency} {item.amount:.2f}")
        
        lines.extend([
            f"",
            f"━━━━━━━━━━━━━━━━━━━━",
            f"",
            f"📌 *Parcela {installment} vencendo:*",
            f"💵 {self.currency} {amount:.2f}",
            f"📅 {due_date.strftime('%d/%m/%Y')}",
        ])
        
        if fines and fines.get("total", amount) > amount:
            lines.extend([
                f"",
                f"⚠️ *Valor com multa e juros:*",
                f"Multa: {self.currency} {fines['multa']:.2f}",
                f"Juros: {self.currency} {fines['juros']:.2f}",
                f"*Total: {self.currency} {fines['total']:.2f}*",
            ])
        
        lines.extend([
            f"",
            f"━━━━━━━━━━━━━━━━━━━━",
            f"",
            f"💸 *Forma de Pagamento:*",
            f"",
            f"📱 *PIX:*",
            f"`{self.pix_key}`",
            f"",
            f"Por favor, efetue o pagamento.",
        ])
        
        return "\n".join(lines)
    
    def _get_month_name_pt(self, month: int) -> str:
        """Retorna nome do mês em português abreviado."""
        months = ["", "Jan", "Fev", "Mar", "Abr", "Mai", "Jun",
                 "Jul", "Ago", "Set", "Out", "Nov", "Dez"]
        return months[month] if 1 <= month <= 12 else str(month)


class WhatsAppSender:
    """Gerencia envio de mensagens WhatsApp."""
    
    def __init__(self, config: Config):
        self.config = config
        self.provider = config.whatsapp_provider
    
    def send(self, phone: str, text: str) -> Dict[str, str]:
        """
        Envia mensagem WhatsApp.
        
        Args:
            phone: Número de telefone (formato internacional)
            text: Texto da mensagem
        
        Returns:
            Dict com status da operação
        """
        if self.config.test_mode:
            log.info("[TEST_MODE] WhatsApp para %s:\n%s", phone, text)
            return {"status": "test_printed", "provider": self.provider}
        
        if self.provider == "twilio":
            return self._send_twilio(phone, text)
        
        log.warning("Provedor de WhatsApp não configurado: %s", self.provider)
        return {"status": "provider_not_configured", "provider": self.provider}
    
    def _normalize_phone(self, phone: str) -> str:
        """Normaliza número de telefone removendo prefixo whatsapp: se existir."""
        phone = phone.strip()
        if phone.startswith("whatsapp:"):
            phone = phone[9:]  # Remove "whatsapp:"
        return phone
    
    def _validate_phone_format(self, phone: str) -> bool:
        """Valida se o número está no formato E.164 (+5511999999999)."""
        if not phone:
            return False
        # Remove espaços e hífens
        phone = phone.replace(" ", "").replace("-", "")
        # Deve começar com + e ter pelo menos 10 dígitos
        return phone.startswith("+") and len(phone) >= 11 and phone[1:].isdigit()
    
    def _send_twilio(self, phone: str, text: str) -> Dict[str, str]:
        """Envia mensagem via Twilio."""
        if not TwilioClient:
            log.error("Biblioteca Twilio não instalada")
            return {"status": "error", "reason": "twilio_not_installed"}
        
        if not all([self.config.twilio_account_sid, 
                   self.config.twilio_auth_token, 
                   self.config.twilio_from]):
            log.error("Credenciais Twilio não configuradas completamente")
            missing = []
            if not self.config.twilio_account_sid:
                missing.append("TWILIO_ACCOUNT_SID")
            if not self.config.twilio_auth_token:
                missing.append("TWILIO_AUTH_TOKEN")
            if not self.config.twilio_from:
                missing.append("TWILIO_FROM")
            log.error("Secrets faltando: %s", ", ".join(missing))
            return {"status": "error", "reason": f"missing_credentials: {', '.join(missing)}"}
        
        # Normalizar e validar números
        twilio_from = self._normalize_phone(self.config.twilio_from)
        phone_to = self._normalize_phone(phone)
        
        if not self._validate_phone_format(twilio_from):
            log.error("TWILIO_FROM inválido: '%s'. Deve estar no formato E.164 (ex: +5511999999999)", 
                     self.config.twilio_from)
            return {"status": "error", "reason": f"invalid_from_number: {self.config.twilio_from}"}
        
        if not self._validate_phone_format(phone_to):
            log.error("Número de destino inválido: '%s'. Deve estar no formato E.164 (ex: +5511999999999)", phone)
            return {"status": "error", "reason": f"invalid_to_number: {phone}"}
        
        try:
            client = TwilioClient(
                self.config.twilio_account_sid,
                self.config.twilio_auth_token
            )
            
            from_number = f"whatsapp:{twilio_from}"
            to_number = f"whatsapp:{phone_to}"
            
            log.debug("Enviando WhatsApp via Twilio: de %s para %s", from_number, to_number)
            
            message = client.messages.create(
                from_=from_number,
                body=text,
                to=to_number
            )
            log.info("Mensagem WhatsApp enviada via Twilio. SID: %s", message.sid)
            return {"status": "sent", "sid": message.sid, "provider": "twilio"}
        except TwilioException as e:
            error_msg = str(e)
            log.error("Erro ao enviar mensagem via Twilio: %s", error_msg)
            
            # Mensagens de erro mais amigáveis
            if "not a valid phone number" in error_msg:
                log.error("O número TWILIO_FROM não é válido ou não está habilitado para WhatsApp no Twilio")
                log.error("Verifique se o número está no formato E.164 (+5511999999999)")
                log.error("E se está habilitado para WhatsApp no console do Twilio")
            
            return {"status": "error", "reason": error_msg, "provider": "twilio"}
        except Exception as e:
            log.exception("Erro inesperado ao enviar via Twilio")
            return {"status": "error", "reason": str(e), "provider": "twilio"}


class EmailSender:
    """Gerencia envio de emails (placeholder para implementação futura)."""
    
    def __init__(self, config: Config):
        self.config = config
    
    def send(self, email: str, subject: str, body: str) -> Dict[str, str]:
        """Envia email (implementação futura)."""
        if self.config.test_mode:
            log.info("[TEST_MODE] Email para %s | %s\n%s", email, subject, body)
            return {"status": "test_printed"}
        
        log.warning("Envio de email não implementado")
        return {"status": "not_implemented"}


class CobrancaProcessor:
    """Processador principal do sistema de cobrança."""
    
    def __init__(self, config: Config):
        self.config = config
        self.calculator = PaymentCalculator(
            config.multa_percent,
            config.interest_monthly_percent,
            config.grace_days
        )
        self.adjuster = BusinessDayAdjuster(config.timezone)
        self.message_builder = MessageBuilder(config.currency, config.pix_key)
        self.whatsapp_sender = WhatsAppSender(config)
        self.email_sender = EmailSender(config)
    
    def build_schedule(self) -> List[ScheduleItem]:
        """
        Gera o cronograma de pagamentos.
        Cada parcela vence no N-ésimo dia útil do mês (ex: 5º dia útil).
        """
        schedule = []
        
        for i in range(self.config.installments):
            # Calcular mês e ano da parcela
            target_date = date(self.config.start_year, self.config.start_month, 1) + relativedelta(months=i)
            year = target_date.year
            month = target_date.month
            
            # Calcular o N-ésimo dia útil do mês
            adjusted_due = self.adjuster.get_nth_business_day_of_month(
                year, 
                month, 
                self.config.business_days_after_month_start
            )
            
            # Original é o mesmo que adjusted (não há "original" na nova lógica)
            original_due = adjusted_due
            
            schedule.append(ScheduleItem(
                installment=i + 1,
                original_due=original_due,
                adjusted_due=adjusted_due,
                amount=self.config.installment_value
            ))
        
        return schedule
    
    def get_current_date(self) -> date:
        """Obtém a data atual (ou override para testes)."""
        if self.config.now_override:
            try:
                return datetime.strptime(self.config.now_override, "%Y-%m-%d").date()
            except ValueError:
                log.warning("NOW_OVERRIDE inválido: %s. Usando data atual.", self.config.now_override)
        
        return datetime.now(self.config.tz).date()
    
    def process(self) -> bool:
        """
        Processa as cobranças do dia.
        
        Returns:
            True se alguma ação foi tomada, False caso contrário
        """
        try:
            current_date = self.get_current_date()
            schedule = self.build_schedule()
            
            log.info("Processando cobranças. Data atual: %s | Parcelas: %d",
                    current_date.isoformat(), len(schedule))
            
            action_taken = False
            
            for item in schedule:
                if current_date == item.adjusted_due:
                    # Parcela vencendo hoje
                    action_taken = True
                    self._process_due_today(item, current_date, schedule)
                elif current_date > item.adjusted_due:
                    # Parcela vencida
                    self._log_overdue(item, current_date)
            
            if not action_taken:
                log.info("Nenhuma parcela vencendo hoje.")
            
            self._log_schedule(schedule)
            return action_taken
            
        except Exception as e:
            log.exception("Erro ao processar cobranças")
            raise
    
    def _process_due_today(self, item: ScheduleItem, current_date: date, schedule: List[ScheduleItem]):
        """Processa parcela vencendo hoje."""
        days_overdue = self.calculator.get_days_overdue(item.adjusted_due, current_date)
        fines = None
        
        if days_overdue > 0:
            fines = self.calculator.calculate_late_fees(item.amount, days_overdue)
        
        message = self.message_builder.build_message(
            self.config.debtor_name,
            item.installment,
            item.amount,
            item.adjusted_due,
            schedule,
            current_date,
            fines
        )
        
        # Enviar notificações
        wa_result = self.whatsapp_sender.send(self.config.debtor_phone, message)
        email_result = self.email_sender.send(
            self.config.debtor_email,
            f"Cobrança - Parcela {item.installment}",
            message
        )
        
        log.info("Parcela %d processada: WhatsApp=%s | Email=%s",
                item.installment, wa_result.get("status"), email_result.get("status"))
    
    def _log_overdue(self, item: ScheduleItem, current_date: date):
        """Registra parcela vencida."""
        days_overdue = self.calculator.get_days_overdue(item.adjusted_due, current_date)
        
        if days_overdue > 0:
            fines = self.calculator.calculate_late_fees(item.amount, days_overdue)
            log.info(
                "Parcela %d vencida (ajustada: %s). Dias em atraso: %d. "
                "Multa: %s | Juros: %s | Total: %s",
                item.installment,
                item.adjusted_due.isoformat(),
                days_overdue,
                fines["multa"],
                fines["juros"],
                fines["total"]
            )
    
    def _log_schedule(self, schedule: List[ScheduleItem]):
        """Registra o cronograma completo."""
        log.info("Cronograma completo (original -> ajustado):")
        for item in schedule:
            log.info(
                "Parcela %d | %s -> %s | Valor: %s",
                item.installment,
                item.original_due.isoformat(),
                item.adjusted_due.isoformat(),
                f"{item.amount:.2f}"
            )


def main():
    """Função principal."""
    try:
        config = Config()
        processor = CobrancaProcessor(config)
        processor.process()
        return 0
    except ConfigError as e:
        log.error("Erro de configuração: %s", e)
        return 1
    except Exception as e:
        log.exception("Erro fatal ao executar sistema de cobrança")
        return 1


if __name__ == "__main__":
    sys.exit(main())
