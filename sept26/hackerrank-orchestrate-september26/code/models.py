"""Strongly typed domain dataclasses for Buy or Wait financial decision engine."""

from dataclasses import dataclass, field
import datetime
from typing import Optional


@dataclass(frozen=True)
class UserProfile:
    """User financial profile, priorities, and preferences."""
    user_id: str
    home_currency: str
    current_available_balance: float
    minimum_balance_to_keep: float
    financial_priorities: tuple[str, ...]
    expense_categories_to_protect: frozenset[str]
    expense_categories_user_is_willing_to_reduce: frozenset[str]
    expense_categories_user_is_willing_to_stop: frozenset[str]
    payment_methods_user_will_consider: frozenset[str]
    max_installment_months: Optional[int] = None


@dataclass(frozen=True)
class FinancialEvent:
    """Historical, pending, or scheduled financial transaction."""
    event_id: str
    user_id: str
    event_type: str
    description: str
    category: str
    direction: str  # "debit", "credit", or "non_cash"
    amount: float
    currency: str
    event_date: datetime.date
    settlement_date: Optional[datetime.date] = None
    status: str = "settled"
    linked_event_id: Optional[str] = None
    flexibility: str = "fixed"  # "fixed" or "flexible"
    minimum_allowed_amount: Optional[float] = None


@dataclass(frozen=True)
class PaymentOption:
    """Financing or installment option offered by seller/provider."""
    payment_option_id: str
    request_id: str
    payment_method: str = "full_payment"
    payment_amount: float = 0.0
    number_of_payments: int = 1
    first_payment_date: Optional[datetime.date] = None
    payment_frequency_days: Optional[int] = None
    financing_fee: float = 0.0
    total_payable_amount: float = 0.0
    # Field aliases for backwards and cross-spec compatibility
    option_name: Optional[str] = None
    provider: Optional[str] = None
    down_payment_amount: float = 0.0
    installment_amount: Optional[float] = None
    number_of_installments: Optional[int] = None
    interval_days: Optional[int] = None
    start_date_offset_days: Optional[int] = None
    total_amount_payable: Optional[float] = None
    apr_percent: Optional[float] = None


@dataclass(frozen=True)
class EvaluationRequest:
    """Evaluation request from requests.csv."""
    request_id: str
    user_id: str
    request_date: datetime.date
    request_type: str
    requested_amount: float
    desired_completion_date: datetime.date
    allows_partial_payment: bool
    request_text: str


@dataclass(frozen=True)
class CandidatePlan:
    """Candidate payment plan evaluated by the decision engine."""
    method: str  # "full_payment", "partial_payment", "installments", "wait", "not_recommended"
    schedule: tuple[tuple[datetime.date, float], ...]
    spending_changes: tuple[str, ...] = field(default_factory=tuple)
    total_cost: float = 0.0
    first_payment_date: Optional[datetime.date] = None
    completion_date: Optional[datetime.date] = None
    num_payments: int = 0
    payment_option_id: Optional[str] = None
    is_safe: bool = True


@dataclass(frozen=True)
class DecisionOutput:
    """Final prediction record adhering strictly to output.csv contract."""
    request_id: str
    amount_safe_to_pay: float
    affordability_status: str
    recommended_payment_method: str
    payment_plan: str
    earliest_date_for_full_payment: str
    spending_changes_needed: str
    decision_explanation: str
