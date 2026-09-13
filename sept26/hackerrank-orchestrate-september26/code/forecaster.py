"""90-day cashflow simulation engine and safety verification for Buy or Wait."""

import calendar
from collections import Counter, defaultdict
from dataclasses import dataclass
import datetime
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from models import FinancialEvent, UserProfile

RECURRING_FIXED_CATEGORIES = frozenset(
    {
        "rent",
        "housing",
        "insurance",
        "education",
        "debt_repayment",
        "family_support",
        "healthcare",
        "streaming",
        "cloud_storage",
        "gym",
        "music_subscription",
        "delivery_membership",
        "entertainment",
        "shopping",
    }
)


@dataclass(frozen=True)
class SimulationResult:
    """Outcome of 90-day daily cashflow projection."""
    is_safe: bool
    min_headroom: float
    bottleneck_date: Optional[datetime.date]
    daily_balances: Dict[datetime.date, float]


def simulate_cashflow(
    profile: UserProfile,
    events: Sequence[FinancialEvent],
    request_date: datetime.date,
    forecast_days: int = 90,
    user_overrides: Optional[Dict[str, Any]] = None,
    payment_schedule: Optional[Sequence[Tuple[datetime.date, float]]] = None,
    spending_changes: Optional[Sequence[str]] = None,
) -> SimulationResult:
    """Simulate day-by-day cash balance B(t) from request_date to request_date + forecast_days."""
    # 1. Parse spending change instructions
    stopped_event_ids: Set[str] = set()
    reduced_event_amounts: Dict[str, float] = {}

    if spending_changes:
        for change in spending_changes:
            parts = change.strip().split(":")
            if not parts or not parts[0]:
                continue
            action = parts[0]
            if action == "stop" and len(parts) >= 2:
                stopped_event_ids.add(parts[1].strip())
            elif action == "reduce_to" and len(parts) >= 3:
                reduced_event_amounts[parts[1].strip()] = float(parts[2].strip())

    # Map stopped and reduced changes to categories and series
    stopped_cats: Set[str] = set()
    stopped_series: Set[Tuple[str, str]] = set()
    reduced_cats: Dict[str, float] = {}
    reduced_series: Dict[Tuple[str, str], float] = {}
    for ev in events:
        if ev.event_id in stopped_event_ids:
            stopped_cats.add(ev.category)
            stopped_series.add((ev.category, ev.description))
        if ev.event_id in reduced_event_amounts:
            reduced_cats[ev.category] = reduced_event_amounts[ev.event_id]
            reduced_series[(ev.category, ev.description)] = reduced_event_amounts[ev.event_id]

    def get_effective_outflow(ev_id: str, cat: str, desc: str, orig_amount: float) -> float:
        if ev_id in stopped_event_ids or (cat, desc) in stopped_series or cat in stopped_cats:
            return 0.0
        if ev_id in reduced_event_amounts:
            return min(orig_amount, reduced_event_amounts[ev_id])
        if (cat, desc) in reduced_series:
            return min(orig_amount, reduced_series[(cat, desc)])
        if cat in reduced_cats:
            return min(orig_amount, reduced_cats[cat])
        return orig_amount

    # 2. Extract user-level overrides if available
    u_overrides: Dict[str, Any] = {}
    if user_overrides:
        if profile.user_id in user_overrides:
            u_overrides = user_overrides[profile.user_id]
        elif any(k in user_overrides for k in ("confirmed_salary", "payroll_rescheduled_date", "contract_terminated")):
            u_overrides = user_overrides

    # 3. Initialize start balance on T0 and reserve all pending debits immediately
    current_balance = float(profile.current_available_balance)
    reserved_pending_debit_ids: Set[str] = set()

    for ev in events:
        if ev.direction == "debit" and ev.status == "pending":
            current_balance -= ev.amount
            reserved_pending_debit_ids.add(ev.event_id)

    # 4. Map candidate plan payments by date
    plan_payments_by_date: Dict[datetime.date, float] = defaultdict(float)
    if payment_schedule:
        for p_date, p_amt in payment_schedule:
            plan_payments_by_date[p_date] += float(p_amt)

    # 5. Group eligible inflows and outflows by date
    daily_inflows: Dict[datetime.date, float] = defaultdict(float)
    daily_outflows: Dict[datetime.date, float] = defaultdict(float)
    explicit_event_dates: Set[Tuple[str, datetime.date]] = set()

    for ev in events:
        eff_date = ev.settlement_date if ev.settlement_date is not None else ev.event_date

        if ev.direction == "credit":
            if ev.status in ("pending", "unrealized") or ev.direction == "non_cash":
                continue

            if ev.category == "salary":
                amt = ev.amount
                salary_date = eff_date
                if "payroll_rescheduled_date" in u_overrides:
                    salary_date = u_overrides["payroll_rescheduled_date"]
                if "confirmed_salary" in u_overrides:
                    eff = u_overrides.get("salary_effective_date")
                    if eff is None or salary_date >= eff:
                        amt = float(u_overrides["confirmed_salary"])
                if u_overrides.get("contract_terminated") or "final" in ev.description.lower():
                    amt = 0.0
                daily_inflows[salary_date] += amt
                explicit_event_dates.add(("salary", salary_date))
            else:
                daily_inflows[eff_date] += ev.amount

        elif ev.direction == "debit":
            if ev.event_id in reserved_pending_debit_ids:
                continue

            if ev.status in ("settled", "scheduled"):
                outflow = get_effective_outflow(ev.event_id, ev.category, ev.description, ev.amount)
                daily_outflows[eff_date] += outflow
                explicit_event_dates.add((ev.event_id, eff_date))

    # 6. Forward 90-day recurrence projections
    end_forecast_date = request_date + datetime.timedelta(days=forecast_days)

    # 6a. Forward salary projection
    salaries = [e for e in events if e.category == "salary" and e.direction == "credit" and e.status in ("settled", "scheduled")]
    regular_salaries = [
        e for e in salaries
        if not any(w in e.description.lower() for w in ("bonus", "arrears", "gig", "commission"))
    ]
    if regular_salaries:
        latest_sal = regular_salaries[-1]
        is_final = "final" in latest_sal.description.lower() or u_overrides.get("contract_terminated", False)
        if not is_final:
            if "payroll_rescheduled_date" in u_overrides:
                sal_day = u_overrides["payroll_rescheduled_date"].day
            else:
                s_days = [e.event_date.day for e in regular_salaries if e.event_date]
                sal_day = Counter(s_days).most_common(1)[0][0] if s_days else 15
            sal_amt = latest_sal.amount
            if "confirmed_salary" in u_overrides:
                sal_amt = float(u_overrides["confirmed_salary"])
            if sal_amt > 0:
                y, m = request_date.year, request_date.month
                for _ in range(4):
                    max_d = calendar.monthrange(y, m)[1]
                    p_date = datetime.date(y, m, min(sal_day, max_d))
                    if request_date <= p_date <= end_forecast_date:
                        if ("salary", p_date) not in explicit_event_dates:
                            daily_inflows[p_date] += sal_amt
                            explicit_event_dates.add(("salary", p_date))
                    m += 1
                    if m > 12:
                        m = 1
                        y += 1

    # 6b. Utilities: monthly on historical billing day
    util_events = [e for e in events if e.category == "utilities" and e.direction == "debit" and e.status in ("settled", "scheduled")]
    if util_events:
        u_days = [e.event_date.day for e in util_events if e.event_date]
        billing_day = Counter(u_days).most_common(1)[0][0] if u_days else 1
        u_mean = sum(e.amount for e in util_events) / len(util_events)
        latest_u = util_events[-1]
        y, m = request_date.year, request_date.month
        for _ in range(4):
            max_d = calendar.monthrange(y, m)[1]
            f_date = datetime.date(y, m, min(billing_day, max_d))
            if request_date <= f_date <= end_forecast_date:
                if (latest_u.event_id, f_date) not in explicit_event_dates:
                    out = get_effective_outflow(latest_u.event_id, "utilities", latest_u.description, u_mean)
                    daily_outflows[f_date] += out
                    explicit_event_dates.add((latest_u.event_id, f_date))
            m += 1
            if m > 12:
                m = 1
                y += 1

    # Helper to check if user permits / actively manages a discretionary category
    def user_allows_discretionary(cat_name: str) -> bool:
        return (
            cat_name in profile.expense_categories_to_protect
            or cat_name in profile.expense_categories_user_is_willing_to_reduce
            or cat_name in profile.expense_categories_user_is_willing_to_stop
        )

    # 6c. Groceries, Transport & Dining: cadence-based projection
    # Groceries and transport are essential (always projected); dining is discretionary
    first_payday: Optional[datetime.date] = None
    if "payroll_rescheduled_date" in u_overrides:
        sal_day_fc = u_overrides["payroll_rescheduled_date"].day
    elif regular_salaries:
        s_days_fc = [e.event_date.day for e in regular_salaries if e.event_date]
        sal_day_fc = Counter(s_days_fc).most_common(1)[0][0] if s_days_fc else 15
    else:
        sal_day_fc = 15

    y_p, m_p = request_date.year, request_date.month
    for _ in range(4):
        max_d_p = calendar.monthrange(y_p, m_p)[1]
        cand_p = datetime.date(y_p, m_p, min(sal_day_fc, max_d_p))
        if cand_p >= request_date:
            first_payday = cand_p
            break
        m_p += 1
        if m_p > 12:
            m_p = 1
            y_p += 1

    for cat in ("groceries", "transport", "dining"):
        if cat == "dining" and not user_allows_discretionary("dining"):
            continue
        cat_events = sorted(
            [e for e in events if e.category == cat and e.direction == "debit" and e.status in ("settled", "scheduled")],
            key=lambda x: x.event_date,
        )
        if len(cat_events) >= 2:
            dates = [e.event_date for e in cat_events if e.event_date]
            intervals = [(dates[i + 1] - dates[i]).days for i in range(len(dates) - 1) if (dates[i + 1] - dates[i]).days > 0]
            if intervals:
                cadence = max(3, round(sum(intervals) / len(intervals)))
                mean_amt = sum(e.amount for e in cat_events) / len(cat_events)
                last_ev = cat_events[-1]
                cur_date = last_ev.event_date + datetime.timedelta(days=cadence)
                cat_has_pre_payday = False
                while cur_date <= end_forecast_date:
                    if cur_date >= request_date and (last_ev.event_id, cur_date) not in explicit_event_dates:
                        out = get_effective_outflow(last_ev.event_id, cat, last_ev.description, mean_amt)
                        daily_outflows[cur_date] += out
                        explicit_event_dates.add((last_ev.event_id, cur_date))
                        if first_payday and request_date <= cur_date < first_payday:
                            cat_has_pre_payday = True
                    cur_date += datetime.timedelta(days=cadence)

                # Ensure essential groceries and transport have at least one baseline cadence cycle before payday
                if cat in ("groceries", "transport") and first_payday and first_payday > request_date and not cat_has_pre_payday:
                    baseline_d = request_date + datetime.timedelta(days=max(1, (first_payday - request_date).days // 2))
                    if (last_ev.event_id, baseline_d) not in explicit_event_dates:
                        out = get_effective_outflow(last_ev.event_id, cat, last_ev.description, mean_amt)
                        daily_outflows[baseline_d] += out
                        explicit_event_dates.add((last_ev.event_id, baseline_d))

    # 6d. Fixed recurring commitments (rent, housing, subscriptions, etc.)
    # Discretionary shopping and entertainment are projected only if permitted by user profile
    series_events: Dict[Tuple[str, str], List[FinancialEvent]] = defaultdict(list)
    for ev in events:
        if ev.direction == "debit" and ev.category in RECURRING_FIXED_CATEGORIES and ev.status in ("settled", "scheduled"):
            if ev.category in ("shopping", "entertainment") and not user_allows_discretionary(ev.category):
                continue
            series_events[(ev.category, ev.description)].append(ev)

    for (cat, desc), s_events in series_events.items():
        if len(s_events) < 2:
            continue
        ev = s_events[-1]
        ev_days = [e.event_date.day for e in s_events if e.event_date]
        ev_day = Counter(ev_days).most_common(1)[0][0] if ev_days else (ev.event_date.day if ev.event_date else 1)
        y, m = request_date.year, request_date.month
        for _ in range(4):
            max_d = calendar.monthrange(y, m)[1]
            f_date = datetime.date(y, m, min(ev_day, max_d))
            if request_date <= f_date <= end_forecast_date:
                if (ev.event_id, f_date) not in explicit_event_dates:
                    out = get_effective_outflow(ev.event_id, cat, desc, ev.amount)
                    daily_outflows[f_date] += out
                    explicit_event_dates.add((ev.event_id, f_date))
            m += 1
            if m > 12:
                m = 1
                y += 1

    # 7. Step through daily forecast window [T0, T0 + forecast_days]
    daily_balances: Dict[datetime.date, float] = {}
    min_headroom = float("inf")
    bottleneck_date: Optional[datetime.date] = None

    for day_offset in range(forecast_days + 1):
        d = request_date + datetime.timedelta(days=day_offset)

        # Apply confirmed daily inflows
        current_balance += daily_inflows.get(d, 0.0)

        # Apply daily outflows
        current_balance -= daily_outflows.get(d, 0.0)

        # Apply candidate plan payment
        current_balance -= plan_payments_by_date.get(d, 0.0)

        daily_balances[d] = current_balance
        headroom = current_balance - profile.minimum_balance_to_keep

        if headroom < min_headroom:
            min_headroom = headroom
            bottleneck_date = d

    is_safe = (min_headroom >= 0.0)
    return SimulationResult(
        is_safe=is_safe,
        min_headroom=min_headroom,
        bottleneck_date=bottleneck_date,
        daily_balances=daily_balances,
    )
