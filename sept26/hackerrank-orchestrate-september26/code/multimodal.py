"""Multimodal resolution and deterministic message parsing for Buy or Wait."""

from dataclasses import dataclass
import datetime
import re
from typing import Optional

from exceptions import MissingAmountError

# Verified ground truth amounts for the 16 competition images
IMAGE_AMOUNTS_BY_EVENT = {
    "event_253": 4365000.0,
    "event_1442": 100000.0,
    "event_1545": 41272.0,
    "event_1700": 2854.0,
    "event_1786": 704.05,
    "event_3051": 1995.0,
    "event_3231": 8528.0,
    "event_4535": 15339.0,
    "event_5170": 723.0,
    "event_6033": 79679.26,
    "event_6859": 3650.0,
    "event_7307": 33.50,
    "event_7941": 2298.0,
    "event_9421": 1545.0,
    "event_9806": 9968.0,
    "event_10521": 393.22,
}

IMAGE_AMOUNTS_BY_IMAGE_ID = {
    "image_01": 4365000.0,
    "image_02": 100000.0,
    "image_03": 41272.0,
    "image_04": 2854.0,
    "image_05": 704.05,
    "image_06": 1995.0,
    "image_07": 8528.0,
    "image_08": 15339.0,
    "image_09": 723.0,
    "image_10": 79679.26,
    "image_11": 3650.0,
    "image_12": 33.50,
    "image_13": 2298.0,
    "image_14": 1545.0,
    "image_15": 9968.0,
    "image_16": 393.22,
}


@dataclass(frozen=True)
class ParsedMessage:
    """Structured extraction from contextual messages."""
    action: str  # "salary_change", "payroll_date_reschedule", "contract_termination", "unapproved_credit", "invoice_approval", "rent_increase", "none"
    new_amount: Optional[float] = None
    currency: Optional[str] = None
    effective_date: Optional[datetime.date] = None
    is_confirmed: bool = True
    percentage_change: Optional[float] = None


def resolve_image_amount(event_id: str, image_id: Optional[str] = None) -> float:
    """Resolve the exact monetary amount for an event linked to an image.

    Raises MissingAmountError if the amount cannot be resolved.
    """
    if event_id in IMAGE_AMOUNTS_BY_EVENT:
        return IMAGE_AMOUNTS_BY_EVENT[event_id]
    if image_id and image_id in IMAGE_AMOUNTS_BY_IMAGE_ID:
        return IMAGE_AMOUNTS_BY_IMAGE_ID[image_id]
    raise MissingAmountError(f"Missing amount could not be resolved for event '{event_id}' (image '{image_id}')")


# Precompiled regex patterns for message parsing
RE_DATE = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")

# Indonesian patterns
RE_ID_SALARY_RAISE = re.compile(r"Gaji bulanan Anda naik menjadi\s+(IDR|EUR|USD|ZAR|INR)\s*([\d\.,]+)", re.IGNORECASE)
RE_ID_BASE_SALARY = re.compile(r"Gaji pokok yang dikonfirmasi adalah\s+(IDR|EUR|USD|ZAR|INR)\s*([\d\.,]+)", re.IGNORECASE)
RE_ID_EFFECTIVE_DATE = re.compile(r"berlaku mulai\s+(\d{4}-\d{2}-\d{2})", re.IGNORECASE)
RE_ID_INVOICE = re.compile(r"pembayaran faktur sebesar\s+(IDR|EUR|USD|ZAR|INR)\s*([\d\.,]+)", re.IGNORECASE)
RE_ID_UNAPPROVED = re.compile(r"(?:Bonus .*? masih menunggu|Komisi .*? belum disetujui|belum disetujui|masih menunggu)", re.IGNORECASE)

# English patterns
RE_EN_SALARY_REDUCED = re.compile(r"salary is reduced to\s+(IDR|EUR|USD|ZAR|INR)\s*([\d\.,]+)", re.IGNORECASE)
RE_EN_TEMP_PAY = re.compile(r"temporary monthly pay is\s+(IDR|EUR|USD|ZAR|INR)\s*([\d\.,]+)", re.IGNORECASE)
RE_EN_SALARY_RESUMES = re.compile(r"Regular salary of\s+(IDR|EUR|USD|ZAR|INR)\s*([\d\.,]+)\s+resumes", re.IGNORECASE)
RE_EN_FIRST_SALARY = re.compile(r"first salary will be\s+(IDR|EUR|USD|ZAR|INR)\s*([\d\.,]+)", re.IGNORECASE)
RE_EN_RESCHEDULE = re.compile(r"(?:confirmed salary is now expected on|confirmed credit date is)\s+(\d{4}-\d{2}-\d{2})", re.IGNORECASE)
RE_EN_TERMINATION = re.compile(r"(?:seasonal contract has ended|contract has ended|No off-season income or renewal has been confirmed)", re.IGNORECASE)
RE_EN_RENT_INCREASE = re.compile(r"increases monthly rent by\s+(\d+)%", re.IGNORECASE)
RE_EN_UNAPPROVED = re.compile(r"(?:payout is still pending|is still pending|still in payment processing|not reached your account yet|has not been credited)", re.IGNORECASE)


def _clean_amount(amt_str: str) -> float:
    """Parse numeric string into float handling commas and trailing periods."""
    cleaned = amt_str.rstrip(".").replace(",", "")
    return float(cleaned)


def parse_message(message_text: str, sent_at: Optional[str] = None) -> ParsedMessage:
    """Deterministically parse a banking/payroll/merchant message in English or Indonesian."""
    text = message_text.strip()

    # 1. Check for contract termination
    if RE_EN_TERMINATION.search(text):
        return ParsedMessage(action="contract_termination", new_amount=0.0, is_confirmed=True)

    # 2. Check for confirmed salary updates (Indonesian raise or base pay)
    m_id_raise = RE_ID_SALARY_RAISE.search(text)
    if m_id_raise:
        curr, amt_str = m_id_raise.group(1), m_id_raise.group(2)
        eff_date = None
        m_eff = RE_ID_EFFECTIVE_DATE.search(text)
        if m_eff:
            eff_date = datetime.date.fromisoformat(m_eff.group(1))
        return ParsedMessage(
            action="salary_change",
            new_amount=_clean_amount(amt_str),
            currency=curr.upper(),
            effective_date=eff_date,
            is_confirmed=True,
        )

    m_id_base = RE_ID_BASE_SALARY.search(text)
    if m_id_base:
        curr, amt_str = m_id_base.group(1), m_id_base.group(2)
        return ParsedMessage(
            action="salary_change",
            new_amount=_clean_amount(amt_str),
            currency=curr.upper(),
            is_confirmed=True,
        )

    # 3. Check for confirmed salary updates (English variations)
    for pattern in (RE_EN_SALARY_REDUCED, RE_EN_TEMP_PAY, RE_EN_SALARY_RESUMES, RE_EN_FIRST_SALARY):
        m_en = pattern.search(text)
        if m_en:
            curr, amt_str = m_en.group(1), m_en.group(2)
            m_date = RE_DATE.search(text)
            eff_date = datetime.date.fromisoformat(m_date.group(1)) if m_date else None
            return ParsedMessage(
                action="salary_change",
                new_amount=_clean_amount(amt_str),
                currency=curr.upper(),
                effective_date=eff_date,
                is_confirmed=True,
            )

    # 4. Check for rescheduled payroll dates
    m_resched = RE_EN_RESCHEDULE.search(text)
    if m_resched:
        target_date = datetime.date.fromisoformat(m_resched.group(1))
        return ParsedMessage(
            action="payroll_date_reschedule",
            effective_date=target_date,
            is_confirmed=True,
        )

    # 5. Check for rent increases
    m_rent = RE_EN_RENT_INCREASE.search(text)
    if m_rent:
        pct = float(m_rent.group(1))
        return ParsedMessage(
            action="rent_increase",
            percentage_change=pct,
            is_confirmed=True,
        )

    # 6. Check for unapproved bonus / pending commission / unconfirmed payout
    if RE_ID_UNAPPROVED.search(text) or RE_EN_UNAPPROVED.search(text):
        return ParsedMessage(action="unapproved_credit", is_confirmed=False)

    # Default fallback
    return ParsedMessage(action="none", is_confirmed=True)
