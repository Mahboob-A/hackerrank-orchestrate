"""Layer 4: Compliance & Output Formatter for Buy or Wait.

Handles serialization, explanation formatting, schema validation, and CSV output emission.
"""

import csv
import datetime
from pathlib import Path
from typing import Any, List, Optional, Sequence, Set, TextIO, Tuple

from exceptions import SchemaValidationError
from models import DecisionOutput, EvaluationRequest

OUTPUT_COLUMNS = [
    "request_id",
    "amount_safe_to_pay",
    "affordability_status",
    "recommended_payment_method",
    "payment_plan",
    "earliest_date_for_full_payment",
    "spending_changes_needed",
    "decision_explanation",
]

VALID_AFFORDABILITY_STATUSES = frozenset(
    {"affordable_now", "affordable_with_plan", "affordable_later", "not_affordable"}
)

VALID_PAYMENT_METHODS = frozenset(
    {"full_payment", "partial_payment", "installments", "wait", "not_recommended"}
)


def format_amount(val: float) -> str:
    """Format a monetary amount cleanly without floating-point representation drift."""
    r_val = round(val, 2)
    if abs(r_val - int(r_val)) < 1e-5:
        return str(int(r_val))
    return f"{r_val:.2f}"


def format_payment_plan(schedule: Optional[Sequence[Tuple[datetime.date, float]]]) -> str:
    """Serialize payment schedule to <YYYY-MM-DD>:<amount>|... or 'none'."""
    if not schedule:
        return "none"
    return "|".join(f"{d.isoformat()}:{format_amount(amt)}" for d, amt in schedule)


def format_spending_changes(changes: Optional[Sequence[str]]) -> str:
    """Serialize spending modifications joined by '|' or 'none'."""
    if not changes:
        return "none"
    cleaned = [c.strip() for c in changes if c.strip()]
    if not cleaned:
        return "none"
    return "|".join(cleaned)


def validate_output_row(row: DecisionOutput, request: EvaluationRequest) -> None:
    """Enforce strict domain invariants and schema validity on a decision row."""
    # 1. Enums validation
    if row.affordability_status not in VALID_AFFORDABILITY_STATUSES:
        raise SchemaValidationError(
            f"Invalid affordability_status '{row.affordability_status}' for {row.request_id}"
        )
    if row.recommended_payment_method not in VALID_PAYMENT_METHODS:
        raise SchemaValidationError(
            f"Invalid recommended_payment_method '{row.recommended_payment_method}' for {row.request_id}"
        )

    # 2. Safe amount bounds: 0 <= amount_safe_to_pay <= requested_amount
    if row.amount_safe_to_pay < -1e-4:
        raise SchemaValidationError(
            f"Negative amount_safe_to_pay {row.amount_safe_to_pay} for {row.request_id}"
        )
    if row.amount_safe_to_pay > request.requested_amount + 1e-4:
        raise SchemaValidationError(
            f"amount_safe_to_pay {row.amount_safe_to_pay} exceeds requested_amount {request.requested_amount} for {row.request_id}"
        )

    # 3. affordable_now must have earliest_date_for_full_payment equal to request_date
    if row.affordability_status == "affordable_now":
        if row.earliest_date_for_full_payment != request.request_date.isoformat():
            raise SchemaValidationError(
                f"affordable_now must have earliest_date equal to request_date ({request.request_date.isoformat()}), got '{row.earliest_date_for_full_payment}'"
            )

    # 4. partial_payment constraints
    if row.recommended_payment_method == "partial_payment":
        if row.affordability_status != "affordable_with_plan":
            raise SchemaValidationError(
                f"partial_payment must have affordability_status 'affordable_with_plan', got '{row.affordability_status}'"
            )
        parts = row.payment_plan.split("|")
        if len(parts) != 2:
            raise SchemaValidationError(
                f"partial_payment must have exactly two payments, got {len(parts)} in '{row.payment_plan}'"
            )
        try:
            d1_str, a1_str = parts[0].split(":")
            d2_str, a2_str = parts[1].split(":")
            a1, a2 = float(a1_str), float(a2_str)
        except Exception as e:
            raise SchemaValidationError(f"Malformed payment_plan '{row.payment_plan}': {e}")

        if abs((a1 + a2) - request.requested_amount) > 0.05:
            raise SchemaValidationError(
                f"partial_payment parts {a1} + {a2} = {a1 + a2} do not sum to requested_amount {request.requested_amount}"
            )
        if d1_str != request.request_date.isoformat():
            raise SchemaValidationError(
                f"First partial payment date {d1_str} must match request_date {request.request_date.isoformat()}"
            )

    # 5. not_recommended plan constraint
    if row.recommended_payment_method == "not_recommended":
        if row.payment_plan != "none":
            raise SchemaValidationError(
                f"not_recommended method must have payment_plan 'none', got '{row.payment_plan}'"
            )

    # 6. Spending changes constraints
    if row.spending_changes_needed != "none":
        changes = [c.strip() for c in row.spending_changes_needed.split("|") if c.strip()]
        if len(changes) > 3:
            raise SchemaValidationError(
                f"Maximum 3 spending changes allowed, got {len(changes)}: {row.spending_changes_needed}"
            )
        # Check mutual exclusivity on event_id
        target_events: Set[str] = set()
        for ch in changes:
            parts = ch.split(":")
            if len(parts) >= 2:
                ev_id = parts[1].strip()
                if ev_id in target_events:
                    raise SchemaValidationError(
                        f"Mutually exclusive modifications on same event_id '{ev_id}' in '{row.spending_changes_needed}'"
                    )
                target_events.add(ev_id)


def serialize_output_rows(decisions: Sequence[DecisionOutput], target_io_or_file: TextIO | Path | str) -> None:
    """Serialize decisions to CSV format with exact 8 columns in required order."""
    if isinstance(target_io_or_file, (str, Path)):
        with open(target_io_or_file, mode="w", encoding="utf-8", newline="") as f:
            _write_csv(decisions, f)
    else:
        _write_csv(decisions, target_io_or_file)


def _write_csv(decisions: Sequence[DecisionOutput], f: TextIO) -> None:
    writer = csv.writer(f, quoting=csv.QUOTE_MINIMAL)
    writer.writerow(OUTPUT_COLUMNS)
    for d in decisions:
        writer.writerow(
            [
                d.request_id,
                format_amount(d.amount_safe_to_pay),
                d.affordability_status,
                d.recommended_payment_method,
                d.payment_plan,
                d.earliest_date_for_full_payment,
                d.spending_changes_needed,
                d.decision_explanation,
            ]
        )
