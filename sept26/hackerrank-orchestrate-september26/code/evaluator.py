"""Layer 3: Decision & Plan Evaluator for Buy or Wait.

Evaluates payment methods, generates candidate plans, optimizes spending modifications,
and ranks recommendations using the strict 6-tier lexicographical comparator.
"""
import calendar
from collections import Counter, defaultdict
import datetime
import itertools
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from forecaster import SimulationResult, simulate_cashflow
from formatter import format_amount
from models import (
    CandidatePlan,
    DecisionOutput,
    EvaluationRequest,
    FinancialEvent,
    PaymentOption,
    UserProfile,
)


def plan_sort_key(
    plan: CandidatePlan,
    desired_completion_date: datetime.date,
) -> Tuple[int, int, float, datetime.date, int, str]:
    """Strict 6-tier lexicographical comparator for CandidatePlan ranking."""
    # Tier 1: Completes on or before desired_completion_date (0 preferred over 1)
    on_time = 0
    if plan.completion_date is not None and plan.completion_date > desired_completion_date:
        on_time = 1

    # Tier 2: Fewer spending changes preferred (0 > 1 > 2 > 3)
    num_changes = len(plan.spending_changes)

    # Tier 3: Lower total payable amount preferred
    cost = round(plan.total_cost, 2)

    # Tier 4: Earlier first payment date preferred
    first_date = plan.first_payment_date if plan.first_payment_date is not None else datetime.date.max

    # Tier 5: Fewer payment transactions preferred
    num_payments = plan.num_payments

    # Tier 6: Lowest payment_option_id string as deterministic tie-breaker
    opt_id = plan.payment_option_id if plan.payment_option_id is not None else ""

    return (on_time, num_changes, cost, first_date, num_payments, opt_id)


def calculate_amount_safe_to_pay(
    profile: UserProfile,
    events: Sequence[FinancialEvent],
    request: EvaluationRequest,
    user_overrides: Optional[Dict[str, Any]] = None,
) -> float:
    """Calculate maximum safe amount payable on request_date before spending changes."""
    sim = simulate_cashflow(
        profile=profile,
        events=events,
        request_date=request.request_date,
        forecast_days=90,
        user_overrides=user_overrides,
    )
    # Headroom bounded between 0.0 and requested_amount
    safe = max(0.0, min(request.requested_amount, sim.min_headroom))
    return round(safe, 2)


def find_earliest_date_for_full_payment(
    profile: UserProfile,
    events: Sequence[FinancialEvent],
    request: EvaluationRequest,
    user_overrides: Optional[Dict[str, Any]] = None,
    skip_request_date: bool = False,
) -> str:
    """Find the earliest date where paying requested_amount in full is safe without spending changes."""
    # Test request_date first only if not skipped and safe_today covers requested_amount
    safe_today = calculate_amount_safe_to_pay(profile, events, request, user_overrides)
    if not skip_request_date and safe_today >= request.requested_amount - 0.05:
        sim_now = simulate_cashflow(
            profile=profile,
            events=events,
            request_date=request.request_date,
            forecast_days=90,
            user_overrides=user_overrides,
            payment_schedule=((request.request_date, request.requested_amount),),
        )
        if sim_now.is_safe:
            return request.request_date.isoformat()

    # Determine recurring payday
    u_overrides = user_overrides or {}
    salaries = [e for e in events if e.category == "salary" and e.direction == "credit" and e.status in ("settled", "scheduled")]
    regular_salaries = [
        e for e in salaries
        if not any(w in e.description.lower() for w in ("bonus", "arrears", "gig", "commission"))
    ]

    end_d = request.request_date + datetime.timedelta(days=90)
    candidate_dates: Set[datetime.date] = set()

    # 1. Recurring paydays and day after payday
    if "payroll_rescheduled_date" in u_overrides:
        sal_day = u_overrides["payroll_rescheduled_date"].day
    elif regular_salaries:
        days = [e.event_date.day for e in regular_salaries if e.event_date]
        sal_day = Counter(days).most_common(1)[0][0] if days else 15
    else:
        sal_day = 15

    y, m = request.request_date.year, request.request_date.month
    for _ in range(4):
        max_d = calendar.monthrange(y, m)[1]
        p_d = datetime.date(y, m, min(sal_day, max_d))
        if request.request_date < p_d <= end_d:
            candidate_dates.add(p_d)
            if p_d + datetime.timedelta(days=1) <= end_d:
                candidate_dates.add(p_d + datetime.timedelta(days=1))
        m += 1
        if m > 12:
            m = 1
            y += 1

    # 2. Weekly candidate dates
    for k in range(1, 14):
        w_d = request.request_date + datetime.timedelta(days=7 * k)
        if w_d <= end_d:
            candidate_dates.add(w_d)

    # 3. Scheduled credit / inflow dates
    for ev in events:
        if ev.direction == "credit" and ev.status in ("settled", "scheduled"):
            c_d = ev.settlement_date if ev.settlement_date else ev.event_date
            if c_d and request.request_date < c_d <= end_d:
                candidate_dates.add(c_d)
                if c_d + datetime.timedelta(days=1) <= end_d:
                    candidate_dates.add(c_d + datetime.timedelta(days=1))

    for cand_d in sorted(candidate_dates):
        sim_cand = simulate_cashflow(
            profile=profile,
            events=events,
            request_date=request.request_date,
            forecast_days=90,
            user_overrides=user_overrides,
            payment_schedule=((cand_d, request.requested_amount),),
        )
        if sim_cand.is_safe:
            return cand_d.isoformat()

    return ""


def generate_partial_payment_plan(
    profile: UserProfile,
    events: Sequence[FinancialEvent],
    request: EvaluationRequest,
    safe_today: float,
    earliest_date: str,
    user_overrides: Optional[Dict[str, Any]] = None,
) -> Optional[CandidatePlan]:
    """Generate 2-payment partial payment plan if eligible and safe."""
    if not request.allows_partial_payment:
        return None
    if "partial_payment" not in profile.payment_methods_user_will_consider:
        return None
    if not (0.0 < safe_today < request.requested_amount):
        return None
    if not earliest_date:
        return None

    d_second = datetime.date.fromisoformat(earliest_date)
    if d_second > request.desired_completion_date:
        return None

    second_amount = round(request.requested_amount - safe_today, 2)
    schedule = (
        (request.request_date, safe_today),
        (d_second, second_amount),
    )

    sim = simulate_cashflow(
        profile=profile,
        events=events,
        request_date=request.request_date,
        forecast_days=90,
        user_overrides=user_overrides,
        payment_schedule=schedule,
    )
    if not sim.is_safe:
        return None

    return CandidatePlan(
        method="partial_payment",
        schedule=schedule,
        spending_changes=(),
        total_cost=request.requested_amount,
        first_payment_date=request.request_date,
        completion_date=d_second,
        num_payments=2,
        payment_option_id=None,
        is_safe=True,
    )


def evaluate_installment_options(
    profile: UserProfile,
    events: Sequence[FinancialEvent],
    request: EvaluationRequest,
    options: Sequence[PaymentOption],
    spending_changes: Optional[Sequence[str]] = None,
    user_overrides: Optional[Dict[str, Any]] = None,
) -> List[CandidatePlan]:
    """Evaluate candidate installment options respecting user max_installment_months."""
    if "installments" not in profile.payment_methods_user_will_consider:
        return []

    plans: List[CandidatePlan] = []
    for opt in options:
        if opt.payment_method != "installments":
            continue

        num_pmts = opt.number_of_payments
        freq_days = opt.payment_frequency_days if opt.payment_frequency_days else 30
        first_date = opt.first_payment_date if opt.first_payment_date else request.request_date

        # Check max_installment_months constraint
        if profile.max_installment_months is not None:
            # Approximate months as num_pmts or total days / 30
            total_days = (num_pmts - 1) * freq_days
            duration_months = (total_days + 29) // 30
            if duration_months > profile.max_installment_months and num_pmts > profile.max_installment_months:
                continue

        # Build schedule
        sched_list: List[Tuple[datetime.date, float]] = []
        for i in range(num_pmts):
            p_date = first_date + datetime.timedelta(days=i * freq_days)
            sched_list.append((p_date, opt.payment_amount))
        schedule = tuple(sched_list)

        sim = simulate_cashflow(
            profile=profile,
            events=events,
            request_date=request.request_date,
            forecast_days=90,
            user_overrides=user_overrides,
            payment_schedule=schedule,
            spending_changes=spending_changes,
        )
        if sim.is_safe:
            plans.append(
                CandidatePlan(
                    method="installments",
                    schedule=schedule,
                    spending_changes=tuple(spending_changes or ()),
                    total_cost=opt.total_payable_amount,
                    first_payment_date=schedule[0][0],
                    completion_date=schedule[-1][0],
                    num_payments=len(schedule),
                    payment_option_id=opt.payment_option_id,
                    is_safe=True,
                )
            )

    return plans


def find_optimal_spending_changes(
    profile: UserProfile,
    events: Sequence[FinancialEvent],
    shortage: float,
    request_date: Optional[datetime.date] = None,
    payment_schedule: Optional[Sequence[Tuple[datetime.date, float]]] = None,
    user_overrides: Optional[Dict[str, Any]] = None,
) -> Optional[Tuple[str, ...]]:
    """Find minimal permitted flexible spending changes to cover shortage (up to 3 changes)."""
    candidates: List[Tuple[str, float, str]] = []  # (instruction, savings, event_id)

    seen_events: Set[str] = set()
    seen_series: Set[Tuple[str, str]] = set()
    for ev in reversed(events):
        if ev.direction != "debit" or ev.status != "settled" or ev.event_id in seen_events:
            continue
        if ev.category in profile.expense_categories_to_protect:
            continue

        series_key = (ev.category, ev.description)
        if series_key in seen_series:
            continue
        seen_series.add(series_key)
        seen_events.add(ev.event_id)

        # Check stoppable
        if (
            ev.category in profile.expense_categories_user_is_willing_to_stop
            and ev.flexibility in ("stoppable", "reducible_or_stoppable")
        ):
            candidates.append((f"stop:{ev.event_id}", ev.amount, ev.event_id))

        # Check reducible
        if (
            ev.category in profile.expense_categories_user_is_willing_to_reduce
            and ev.flexibility in ("reducible", "reducible_or_stoppable")
        ):
            min_amt = ev.minimum_allowed_amount if ev.minimum_allowed_amount is not None else round(ev.amount * 0.5, 2)
            savings = round(ev.amount - min_amt, 2)
            if savings > 0:
                candidates.append((f"reduce_to:{ev.event_id}:{min_amt}", savings, ev.event_id))

    # Evaluate combinations from size 1 to 3
    for k in range(1, min(4, len(candidates) + 1)):
        for comb in itertools.combinations(candidates, k):
            # Mutual exclusivity: cannot stop and reduce the same event
            ev_ids = [item[2] for item in comb]
            if len(set(ev_ids)) < len(ev_ids):
                continue
            instructions = tuple(item[0] for item in comb)
            if request_date is not None and payment_schedule is not None:
                sim_test = simulate_cashflow(
                    profile=profile,
                    events=events,
                    request_date=request_date,
                    forecast_days=90,
                    user_overrides=user_overrides,
                    payment_schedule=payment_schedule,
                    spending_changes=instructions,
                )
                if sim_test.is_safe:
                    return instructions
            else:
                total_savings = sum(item[1] for item in comb)
                if total_savings >= shortage - 1e-4:
                    return instructions

    return None


def evaluate_request(
    request: EvaluationRequest,
    profile: UserProfile,
    events: Sequence[FinancialEvent],
    payment_options: Sequence[PaymentOption],
    user_overrides: Optional[Dict[str, Any]] = None,
) -> DecisionOutput:
    """Evaluate financial request and select the optimal safe recommendation."""
    safe_today = calculate_amount_safe_to_pay(profile, events, request, user_overrides)
    earliest_full = find_earliest_date_for_full_payment(profile, events, request, user_overrides)

    candidate_plans: List[CandidatePlan] = []

    # 1. Evaluate immediate full payment without spending changes
    if "full_payment" in profile.payment_methods_user_will_consider:
        sim_full = simulate_cashflow(
            profile=profile,
            events=events,
            request_date=request.request_date,
            forecast_days=90,
            user_overrides=user_overrides,
            payment_schedule=((request.request_date, request.requested_amount),),
        )
        if sim_full.is_safe:
            candidate_plans.append(
                CandidatePlan(
                    method="full_payment",
                    schedule=((request.request_date, request.requested_amount),),
                    spending_changes=(),
                    total_cost=request.requested_amount,
                    first_payment_date=request.request_date,
                    completion_date=request.request_date,
                    num_payments=1,
                    payment_option_id=None,
                    is_safe=True,
                )
            )
        else:
            # Check with spending changes
            shortage = abs(sim_full.min_headroom)
            changes = find_optimal_spending_changes(
                profile=profile,
                events=events,
                shortage=shortage,
                request_date=request.request_date,
                payment_schedule=((request.request_date, request.requested_amount),),
                user_overrides=user_overrides,
            )
            if changes:
                sim_with_changes = simulate_cashflow(
                    profile=profile,
                    events=events,
                    request_date=request.request_date,
                    forecast_days=90,
                    user_overrides=user_overrides,
                    payment_schedule=((request.request_date, request.requested_amount),),
                    spending_changes=changes,
                )
                if sim_with_changes.is_safe:
                    candidate_plans.append(
                        CandidatePlan(
                            method="full_payment",
                            schedule=((request.request_date, request.requested_amount),),
                            spending_changes=changes,
                            total_cost=request.requested_amount,
                            first_payment_date=request.request_date,
                            completion_date=request.request_date,
                            num_payments=1,
                            payment_option_id=None,
                            is_safe=True,
                        )
                    )

    # 2. Evaluate partial payment
    plan_part = generate_partial_payment_plan(
        profile, events, request, safe_today, earliest_full, user_overrides
    )
    if plan_part:
        candidate_plans.append(plan_part)

    # 3. Evaluate installment options (without and with spending changes)
    inst_plans = evaluate_installment_options(profile, events, request, payment_options, user_overrides=user_overrides)
    candidate_plans.extend(inst_plans)

    # 4. Evaluate wait option
    if earliest_full and "full_payment" in profile.payment_methods_user_will_consider:
        d_wait = datetime.date.fromisoformat(earliest_full)
        if d_wait <= request.desired_completion_date:
            sim_wait = simulate_cashflow(
                profile=profile,
                events=events,
                request_date=request.request_date,
                forecast_days=90,
                user_overrides=user_overrides,
                payment_schedule=((d_wait, request.requested_amount),),
            )
            if sim_wait.is_safe:
                candidate_plans.append(
                    CandidatePlan(
                        method="wait",
                        schedule=((d_wait, request.requested_amount),),
                        spending_changes=(),
                        total_cost=request.requested_amount,
                        first_payment_date=d_wait,
                        completion_date=d_wait,
                        num_payments=1,
                        payment_option_id=None,
                        is_safe=True,
                    )
                )

    # Rank safe candidates
    if candidate_plans:
        candidate_plans.sort(key=lambda p: plan_sort_key(p, request.desired_completion_date))
        best_plan = candidate_plans[0]

        # Determine affordability status
        if best_plan.method == "full_payment" and len(best_plan.spending_changes) == 0:
            status = "affordable_now"
        elif best_plan.method == "wait":
            status = "affordable_later"
        else:
            status = "affordable_with_plan"

        plan_str = "|".join(f"{d.isoformat()}:{format_amount(amt)}" for d, amt in best_plan.schedule)
        changes_str = "|".join(best_plan.spending_changes) if best_plan.spending_changes else "none"

        # Concise grounded explanation
        min_b = profile.minimum_balance_to_keep
        cur = profile.home_currency
        if status == "affordable_now":
            explanation = f"Pay {cur} {request.requested_amount:,.2f} today. This leaves at least {cur} {min_b:,.2f} available over the next 90 days."
        elif best_plan.method == "installments":
            pmt_amt = best_plan.schedule[0][1]
            explanation = f"Use {best_plan.num_payments} installments of {cur} {pmt_amt:,.2f}, starting {best_plan.first_payment_date}. This leaves at least {cur} {min_b:,.2f} available."
        elif best_plan.method == "partial_payment":
            p1_amt, p2_amt = best_plan.schedule[0][1], best_plan.schedule[1][1]
            p2_date = best_plan.schedule[1][0]
            explanation = f"Pay {cur} {p1_amt:,.2f} today and the remaining {cur} {p2_amt:,.2f} on {p2_date}. This completes the full request and keeps the {cur} {min_b:,.2f} minimum protected."
        elif best_plan.method == "wait":
            explanation = f"Pay {cur} {request.requested_amount:,.2f} in full on {best_plan.first_payment_date}. Paying earlier would take the balance below the {cur} {min_b:,.2f} minimum."
        else:
            explanation = f"Apply spending changes, then complete the request. This leaves at least {cur} {min_b:,.2f} available."

        # If spending changes are required, earliest_date_for_full_payment must reflect the safe date without changes
        if best_plan.spending_changes and earliest_full == request.request_date.isoformat():
            earliest_full = find_earliest_date_for_full_payment(
                profile=profile,
                events=events,
                request=request,
                user_overrides=user_overrides,
                skip_request_date=True,
            )

        return DecisionOutput(
            request_id=request.request_id,
            amount_safe_to_pay=safe_today,
            affordability_status=status,
            recommended_payment_method=best_plan.method,
            payment_plan=plan_str,
            earliest_date_for_full_payment=earliest_full,
            spending_changes_needed=changes_str,
            decision_explanation=explanation,
        )

    # Fallback: not_recommended
    min_b = profile.minimum_balance_to_keep
    cur = profile.home_currency
    return DecisionOutput(
        request_id=request.request_id,
        amount_safe_to_pay=safe_today,
        affordability_status="not_affordable",
        recommended_payment_method="not_recommended",
        payment_plan="none",
        earliest_date_for_full_payment="",
        spending_changes_needed="none",
        decision_explanation=f"Do not make this payment by {request.desired_completion_date}. None of the available options keeps the {cur} {min_b:,.2f} minimum protected.",
    )
