#!/usr/bin/env python3
"""
cobranca_single.py

Script mínimo para um único devedor, baseado no contrato que você forneceu.
- Parcelas: 6x de R$ 386,56
- Vencimentos: 05/01/... até 05/06/... (assumi Jan-Jun de 2026)
- Se cair em dia não útil, o vencimento é adiado para o próximo dia útil (sem acréscimos)
- Multa por atraso: 2% sobre a parcela
- Juros de mora: 1% ao mês, pro rata por dia (usado como monthly_rate/30 por dia)
- TEST_MODE=True por padrão (imprime payloads, não envia nada)

Configurações por ENV:
- START_YEAR, START_MONTH, START_DAY (padrões 2026,1,5)
- INSTALLMENTS (padrão 6)
- INSTALLMENT_VALUE (padrão 386.56)
- DEBTOR_NAME, DEBTOR_CPF, DEBTOR_EMAIL, DEBTOR_PHONE
- TIMEZONE (padrão America/Sao_Paulo)
- TEST_MODE (true/false)
- MULTA_PERCENT (2.0), INTEREST_MONTHLY_PERCENT (1.0), GRACE_DAYS (0)
- NOW_OVERRIDE (opcional) - form YYYY-MM-DD to force "today" for testing
"""
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
import os
import logging

import pytz
from dateutil.relativedelta import relativedelta

try:
    import holidays
except Exception:
    holidays = None

# Optional Twilio import; only required if sending real messages
try:
    from twilio.rest import Client as TwilioClient
except Exception:
    TwilioClient = None

# Logger
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("cobranca_single")

# Config via ENV (valores padrão baseados no contrato que você forneceu)
START_YEAR = int(os.environ.get("START_YEAR", "2026"))
START_MONTH = int(os.environ.get("START_MONTH", "1"))
START_DAY = int(os.environ.get("START_DAY", "5"))
INSTALLMENTS = int(os.environ.get("INSTALLMENTS", "6"))
INSTALLMENT_VALUE = Decimal(os.environ.get("INSTALLMENT_VALUE", "386.56"))
DEBTOR_NAME = os.environ.get("DEBTOR_NAME", "Samuel Cassiano de Carvalho")
DEBTOR_CPF = os.environ.get("DEBTOR_CPF", "REDACTED")
DEBTOR_EMAIL = os.environ.get("DEBTOR_EMAIL", "samuelsamuelheibr@hotmail.com")
DEBTOR_PHONE = os.environ.get("DEBTOR_PHONE", "+558487796531")

# Provider and Twilio creds (read from env -> should be mapped to repository secrets in workflow)
WHATSAPP_PROVIDER = os.environ.get("WHATSAPP_PROVIDER", "none")
TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN")
TWILIO_FROM = os.environ.get("TWILIO_FROM")

# Optional override for "today" used in testing: YYYY-MM-DD
NOW_OVERRIDE = os.environ.get("NOW_OVERRIDE")

TIMEZONE = os.environ.get("TIMEZONE", "America/Sao_Paulo")
TEST_MODE = os.environ.get("TEST_MODE", "true").lower() in ("1", "true", "yes")
MULTA_PERCENT = Decimal(os.environ.get("MULTA_PERCENT", "2.0"))  # 2%
INTEREST_MONTHLY_PERCENT = Decimal(os.environ.get("INTEREST_MONTHLY_PERCENT", "1.0"))  # 1% ao mês
GRACE_DAYS = int(os.environ.get("GRACE_DAYS", "0"))
CURRENCY = os.environ.get("CURRENCY", "BRL")

TZ = pytz.timezone(TIMEZONE)

def is_business_day(d: date, br_holidays):
    if d.weekday() >= 5:
        return False
    if br_holidays and d in br_holidays:
        return False
    return True

def adjust_to_next_business_day(d: date, br_holidays):
    # Se cair em dia não útil, avança para o próximo dia útil (sem acréscimos)
    while not is_business_day(d, br_holidays):
        d = d + timedelta(days=1)
    return d

def decimal_money(v):
    return Decimal(v).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

def build_schedule():
    """
    Gera a lista de vencimentos ajustados para dias úteis, a partir da data inicial.
    Retorna lista de dicts: {installment, original_due, adjusted_due, amount}
    """
    br_holidays = None
    if holidays:
        try:
            br_holidays = holidays.Brazil(years=[START_YEAR, START_YEAR + 1])
        except Exception:
            br_holidays = None

    schedule = []
    base = date(START_YEAR, START_MONTH, START_DAY)
    for i in range(INSTALLMENTS):
        orig = base + relativedelta(months=i)
        adj = adjust_to_next_business_day(orig, br_holidays)
        schedule.append(
            {
                "installment": i + 1,
                "original_due": orig,
                "adjusted_due": adj,
                "amount": decimal_money(INSTALLMENT_VALUE),
            }
        )
    return schedule

def calculate_late_fees(amount: Decimal, days_overdue: int):
    """
    Multa fixa sobre o valor + juros pro rata (monthly_rate/30 * days)
    Juros simples conforme cláusula ("1% ao mês, até o efetivo pagamento").
    """
    if days_overdue <= 0:
        return {"multa": Decimal("0.00"), "juros": Decimal("0.00"), "total": amount}
    multa = (amount * MULTA_PERCENT / Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    monthly_rate = INTEREST_MONTHLY_PERCENT / Decimal("100")
    daily_rate = (monthly_rate / Decimal("30"))  # aproximação pro rata
    juros = (amount * daily_rate * Decimal(days_overdue)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    total = (amount + multa + juros).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return {"multa": multa, "juros": juros, "total": total}

def build_message(debtor_name, installment, amount, due_date, fines=None):
    amt_str = f"{CURRENCY} {amount:.2f}"
    msg = [
        f"Olá {debtor_name},",
        f"Parcela {installment}: {amt_str}",
        f"Vencimento (ajustado para dia útil): {due_date.strftime('%d/%m/%Y')}",
    ]
    if fines:
        msg.append(f"Multa: {fines['multa']:.2f} | Juros acumulados: {fines['juros']:.2f}")
        msg.append(f"Total devido neste momento: {fines['total']:.2f}")
    msg.append("Por favor, efetue o pagamento.")
    return "\n".join(msg)

def send_whatsapp_twilio(phone, text):
    """Send a WhatsApp message via Twilio REST API using environment secrets.
    Returns a dict with status info.
    """  
    if TEST_MODE:
        log.info("[TEST_MODE] (Twilio) WhatsApp para %s:\n%s", phone, text)
        return {"status": "test_printed"}

    if not TwilioClient:
        log.error("twilio library is not installed")
        return {"status": "error", "reason": "twilio_not_installed"}

    if not (TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN and TWILIO_FROM):
        log.error("Twilio credentials not configured in env")
        return {"status": "error", "reason": "missing_credentials"}

    try:
        client = TwilioClient(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        msg = client.messages.create(
            from_=TWILIO_FROM,
            body=text,
            to=f"whatsapp:{phone}"
        )
        return {"status": "sent", "sid": getattr(msg, "sid", None)}
    except Exception as e:
        log.exception("Erro ao enviar via Twilio")
        return {"status": "error", "reason": str(e)}

def send_whatsapp_sim(phone, text):
    # kept for compatibility; calls provider-specific function when configured
    if WHATSAPP_PROVIDER == "twilio":
        return send_whatsapp_twilio(phone, text)
    # other providers could be implemented similarly
    log.warning("Provedor de WhatsApp não configurado ou não suportado: %s", WHATSAPP_PROVIDER)
    return {"status": "provider_not_configured"}

def send_email_sim(email, subject, body):
    if TEST_MODE:
        log.info("[TEST] Email para %s | %s\n%s", email, subject, body)
        return {"status": "printed"}
    return {"status": "not_implemented"}

def process():
    # Determine "today" - allow override for testing
    if NOW_OVERRIDE:
        try:
            now = datetime.strptime(NOW_OVERRIDE, "%Y-%m-%d").date()
            log.info("NOW_OVERRIDE in use: %s", now.isoformat())
        except Exception:
            log.warning("NOW_OVERRIDE value invalid, falling back to system date: %s", NOW_OVERRIDE)
            now = datetime.now(TZ).date()
    else:
        now = datetime.now(TZ).date()

    schedule = build_schedule()
    log.info("Agenda de vencimentos gerada (%d parcelas). Hoje: %s", len(schedule), now.isoformat())

    found_due_today = False
    for item in schedule:
        installment = item["installment"]
        orig = item["original_due"]
        adj = item["adjusted_due"]
        amount = item["amount"]

        # Consideramos vencimento efetivo como adj
        if now == adj:
            found_due_today = True
            fines = None
            days_overdue = max(0, (now - adj).days - GRACE_DAYS)
            if days_overdue > 0:
                fines = calculate_late_fees(amount, days_overdue)
            text = build_message(DEBTOR_NAME, installment, amount, adj, fines)
            # "Enviar"
            wa = send_whatsapp_sim(DEBTOR_PHONE, text)
            em = send_email_sim(DEBTOR_EMAIL, f"Cobrança parcela {installment}", text)
            log.info("Ação para parcela %d: wa=%s email=%s", installment, wa, em)
        else:
            # Se já passou o vencimento ajustado e não é hoje, podemos sinalizar atraso
            if now > adj:
                days_overdue = max(0, (now - adj).days - GRACE_DAYS)
                if days_overdue > 0:
                    fines = calculate_late_fees(amount, days_overdue)
                    log.info(
                        "Parcela %d vencida (ajustada: %s). Dias em atraso: %d. Multa %s | Juros %s | Total %s",
                        installment,
                        adj.isoformat(),
                        days_overdue,
                        fines["multa"],
                        fines["juros"],
                        fines["total"],
                    )

    if not found_due_today:
        log.info("Nenhuma parcela vencendo hoje.")

    # Para ver o cronograma completo (útil para logs)
    log.info("Cronograma completo (original -> ajustado):")
    for item in schedule:
        log.info(
            "Parcela %d | %s -> %s | Valor: %s",
            item["installment"],
            item["original_due"].isoformat(),
            item["adjusted_due"].isoformat(),
            f"{item['amount']:.2f}",
        )

if __name__ == "__main__":
    process()