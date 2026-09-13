"""Data loading, currency normalization, and message override integration for Buy or Wait."""

import csv
import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from exceptions import ExchangeRateNotFoundError
from models import (
    EvaluationRequest,
    FinancialEvent,
    PaymentOption,
    UserProfile,
)
from multimodal import parse_message, resolve_image_amount


def load_financial_profiles(filepath: Path | str) -> Dict[str, UserProfile]:
    """Load user profiles from financial_profiles.csv."""
    profiles: Dict[str, UserProfile] = {}
    with open(filepath, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            user_id = row["user_id"].strip()
            priorities = tuple(p.strip() for p in row["financial_priorities"].split("|") if p.strip())
            protect = frozenset(c.strip() for c in row["expense_categories_to_protect"].split("|") if c.strip())
            reduce_cats = frozenset(c.strip() for c in row["expense_categories_user_is_willing_to_reduce"].split("|") if c.strip())
            stop_cats = frozenset(c.strip() for c in row["expense_categories_user_is_willing_to_stop"].split("|") if c.strip())
            methods = frozenset(m.strip() for m in row["payment_methods_user_will_consider"].split("|") if m.strip())

            raw_months = row.get("max_installment_months", "").strip()
            max_months = int(raw_months) if raw_months else None

            profiles[user_id] = UserProfile(
                user_id=user_id,
                home_currency=row["home_currency"].strip(),
                current_available_balance=float(row["current_available_balance"]),
                minimum_balance_to_keep=float(row["minimum_balance_to_keep"]),
                financial_priorities=priorities,
                expense_categories_to_protect=protect,
                expense_categories_user_is_willing_to_reduce=reduce_cats,
                expense_categories_user_is_willing_to_stop=stop_cats,
                payment_methods_user_will_consider=methods,
                max_installment_months=max_months,
            )
    return profiles


def load_exchange_rates(filepath: Path | str) -> Dict[Tuple[datetime.date, str, str], float]:
    """Load dated exchange rates from exchange_rates.csv."""
    rates: Dict[Tuple[datetime.date, str, str], float] = {}
    with open(filepath, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rate_date = datetime.date.fromisoformat(row["rate_date"].strip())
            from_curr = row["from_currency"].strip()
            to_curr = row["to_currency"].strip()
            rate = float(row["rate"])
            rates[(rate_date, from_curr, to_curr)] = rate
    return rates


def load_financial_events(
    filepath: Path | str,
    profiles: Dict[str, UserProfile],
    rates: Dict[Tuple[datetime.date, str, str], float],
) -> List[FinancialEvent]:
    """Load financial events, resolve missing amounts from images, and normalize to home currency."""
    events: List[FinancialEvent] = []
    with open(filepath, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            event_id = row["event_id"].strip()
            user_id = row["user_id"].strip()
            event_date = datetime.date.fromisoformat(row["event_date"].strip())

            raw_settle = row["settlement_date"].strip()
            settlement_date = datetime.date.fromisoformat(raw_settle) if raw_settle else None
            currency = row["currency"].strip()

            # Resolve missing amount via multimodal resolution
            raw_amount = row["amount"].strip()
            if not raw_amount:
                amount = resolve_image_amount(event_id)
            else:
                amount = float(raw_amount)

            # Currency normalization to user's home currency
            profile = profiles.get(user_id)
            home_curr = profile.home_currency if profile else currency
            final_currency = currency

            if currency and home_curr and currency != home_curr:
                lookup_date = settlement_date if settlement_date is not None else event_date
                rate_key = (lookup_date, currency, home_curr)
                if rate_key not in rates:
                    raise ExchangeRateNotFoundError(
                        f"Exchange rate not found for {currency} to {home_curr} on {lookup_date} for event {event_id}"
                    )
                amount = amount * rates[rate_key]
                final_currency = home_curr

            raw_min_allowed = row.get("minimum_allowed_amount", "").strip()
            min_allowed = float(raw_min_allowed) if raw_min_allowed else None

            events.append(
                FinancialEvent(
                    event_id=event_id,
                    user_id=user_id,
                    event_type=row["event_type"].strip(),
                    description=row["description"].strip(),
                    category=row["category"].strip(),
                    direction=row["direction"].strip(),
                    amount=amount,
                    currency=final_currency,
                    event_date=event_date,
                    settlement_date=settlement_date,
                    status=row["status"].strip(),
                    linked_event_id=row.get("linked_event_id", "").strip() or None,
                    flexibility=row.get("flexibility", "fixed").strip() or "fixed",
                    minimum_allowed_amount=min_allowed,
                )
            )
    return events


def load_payment_options(filepath: Path | str) -> Dict[str, List[PaymentOption]]:
    """Load available financing options from request_payment_options.csv grouped by request_id."""
    options_by_request: Dict[str, List[PaymentOption]] = {}
    with open(filepath, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            req_id = row["request_id"].strip()
            p_amount = float(row["payment_amount"])
            n_payments = int(row["number_of_payments"])

            raw_freq = row.get("payment_frequency_days", "").strip()
            freq = int(raw_freq) if raw_freq else None

            raw_fee = row.get("financing_fee", "").strip()
            fee = float(raw_fee) if raw_fee else 0.0

            raw_total = row.get("total_payable_amount", "").strip()
            total_pay = float(raw_total) if raw_total else 0.0

            raw_first_date = row.get("first_payment_date", "").strip()
            first_date = datetime.date.fromisoformat(raw_first_date) if raw_first_date else None

            opt = PaymentOption(
                payment_option_id=row["payment_option_id"].strip(),
                request_id=req_id,
                payment_method=row.get("payment_method", "").strip(),
                payment_amount=p_amount,
                number_of_payments=n_payments,
                first_payment_date=first_date,
                payment_frequency_days=freq,
                financing_fee=fee,
                total_payable_amount=total_pay,
                # Aliases
                installment_amount=p_amount,
                number_of_installments=n_payments,
                interval_days=freq,
                total_amount_payable=total_pay,
            )
            if req_id not in options_by_request:
                options_by_request[req_id] = []
            options_by_request[req_id].append(opt)
    return options_by_request


def load_evaluation_requests(filepath: Path | str) -> List[EvaluationRequest]:
    """Load evaluation requests from requests.csv or sample_requests.csv."""
    requests: List[EvaluationRequest] = []
    with open(filepath, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            allows_partial = row["allows_partial_payment"].strip().lower() in ("true", "1", "yes")
            requests.append(
                EvaluationRequest(
                    request_id=row["request_id"].strip(),
                    user_id=row["user_id"].strip(),
                    request_date=datetime.date.fromisoformat(row["request_date"].strip()),
                    request_type=row["request_type"].strip(),
                    requested_amount=float(row["requested_amount"]),
                    desired_completion_date=datetime.date.fromisoformat(row["desired_completion_date"].strip()),
                    allows_partial_payment=allows_partial,
                    request_text=row["request_text"].strip(),
                )
            )
    return requests


def load_messages(filepath: Path | str) -> List[Dict[str, str]]:
    """Load raw contextual messages from messages.csv."""
    messages: List[Dict[str, str]] = []
    with open(filepath, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            messages.append({k: v.strip() for k, v in row.items()})
    return messages


def apply_message_overrides(
    events: List[FinancialEvent],
    messages: List[Dict[str, str]],
) -> Tuple[List[FinancialEvent], Dict[str, Dict[str, Any]]]:
    """Parse messages and compile user-level and event-level financial overrides."""
    user_overrides: Dict[str, Dict[str, Any]] = {}
    updated_events: List[FinancialEvent] = []

    # Process each message through multimodal parser
    for msg in messages:
        user_id = msg.get("user_id")
        if not user_id:
            continue

        parsed = parse_message(msg["message_text"], msg.get("sent_at"))
        if user_id not in user_overrides:
            user_overrides[user_id] = {}

        if parsed.action == "salary_change" and parsed.is_confirmed:
            if parsed.new_amount is not None:
                user_overrides[user_id]["confirmed_salary"] = parsed.new_amount
            if parsed.effective_date is not None:
                user_overrides[user_id]["salary_effective_date"] = parsed.effective_date
        elif parsed.action == "payroll_date_reschedule" and parsed.effective_date:
            user_overrides[user_id]["payroll_rescheduled_date"] = parsed.effective_date
        elif parsed.action == "contract_termination":
            user_overrides[user_id]["confirmed_salary"] = 0.0
            user_overrides[user_id]["contract_terminated"] = True
        elif parsed.action == "rent_increase" and parsed.percentage_change:
            user_overrides[user_id]["rent_increase_pct"] = parsed.percentage_change
        elif parsed.action == "unapproved_credit":
            user_overrides[user_id]["has_unapproved_credit"] = True

    updated_events = list(events)
    return updated_events, user_overrides
