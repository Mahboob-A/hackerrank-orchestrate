"""Unit tests for Layer 3: Decision & Plan Evaluator (evaluator.py)."""

import datetime
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from exceptions import SchemaValidationError
from models import (
    CandidatePlan,
    DecisionOutput,
    EvaluationRequest,
    FinancialEvent,
    PaymentOption,
    UserProfile,
)


class TestPlanRankingComparator(unittest.TestCase):
    """Test 6-tier lexicographical comparator for CandidatePlan ranking."""

    def test_ranking_tier_1_deadline_completion(self):
        """Tier 1: Completing by desired_completion_date strictly preferred."""
        from evaluator import plan_sort_key

        d_dead = datetime.date(2024, 4, 1)
        plan_on_time = CandidatePlan(
            method="installments",
            schedule=((datetime.date(2024, 3, 1), 50.0), (datetime.date(2024, 3, 20), 50.0)),
            spending_changes=(),
            total_cost=100.0,
            first_payment_date=datetime.date(2024, 3, 1),
            completion_date=datetime.date(2024, 3, 20),
            num_payments=2,
            payment_option_id="opt_1",
            is_safe=True,
        )
        plan_late = CandidatePlan(
            method="installments",
            schedule=((datetime.date(2024, 3, 1), 50.0), (datetime.date(2024, 4, 15), 50.0)),
            spending_changes=(),
            total_cost=100.0,
            first_payment_date=datetime.date(2024, 3, 1),
            completion_date=datetime.date(2024, 4, 15),
            num_payments=2,
            payment_option_id="opt_2",
            is_safe=True,
        )

        key_on_time = plan_sort_key(plan_on_time, d_dead)
        key_late = plan_sort_key(plan_late, d_dead)
        self.assertLess(key_on_time, key_late)

    def test_ranking_tier_2_spending_changes_count(self):
        """Tier 2: Fewer spending changes preferred (0 > 1 > 2 > 3)."""
        from evaluator import plan_sort_key

        d_dead = datetime.date(2024, 4, 1)
        plan_no_changes = CandidatePlan(
            method="full_payment",
            schedule=((datetime.date(2024, 3, 1), 100.0),),
            spending_changes=(),
            total_cost=100.0,
            first_payment_date=datetime.date(2024, 3, 1),
            completion_date=datetime.date(2024, 3, 1),
            num_payments=1,
            payment_option_id=None,
            is_safe=True,
        )
        plan_with_change = CandidatePlan(
            method="full_payment",
            schedule=((datetime.date(2024, 3, 1), 100.0),),
            spending_changes=("stop:event_476",),
            total_cost=100.0,
            first_payment_date=datetime.date(2024, 3, 1),
            completion_date=datetime.date(2024, 3, 1),
            num_payments=1,
            payment_option_id=None,
            is_safe=True,
        )

        self.assertLess(plan_sort_key(plan_no_changes, d_dead), plan_sort_key(plan_with_change, d_dead))

    def test_ranking_tier_3_total_cost(self):
        """Tier 3: Lower total cost (including financing fees) preferred."""
        from evaluator import plan_sort_key

        d_dead = datetime.date(2024, 4, 1)
        plan_cheaper = CandidatePlan(
            method="full_payment",
            schedule=((datetime.date(2024, 3, 1), 1000.0),),
            spending_changes=(),
            total_cost=1000.0,
            first_payment_date=datetime.date(2024, 3, 1),
            completion_date=datetime.date(2024, 3, 1),
            num_payments=1,
            payment_option_id=None,
            is_safe=True,
        )
        plan_fee = CandidatePlan(
            method="installments",
            schedule=((datetime.date(2024, 3, 1), 525.0), (datetime.date(2024, 3, 15), 525.0)),
            spending_changes=(),
            total_cost=1050.0,
            first_payment_date=datetime.date(2024, 3, 1),
            completion_date=datetime.date(2024, 3, 15),
            num_payments=2,
            payment_option_id="opt_inst",
            is_safe=True,
        )

        self.assertLess(plan_sort_key(plan_cheaper, d_dead), plan_sort_key(plan_fee, d_dead))

    def test_ranking_tier_4_and_5_start_date_and_fewer_payments(self):
        """Tier 4: Earlier start date; Tier 5: Fewer payments."""
        from evaluator import plan_sort_key

        d_dead = datetime.date(2024, 4, 1)
        plan_earlier = CandidatePlan(
            method="installments",
            schedule=((datetime.date(2024, 3, 1), 50.0), (datetime.date(2024, 3, 15), 50.0)),
            spending_changes=(),
            total_cost=100.0,
            first_payment_date=datetime.date(2024, 3, 1),
            completion_date=datetime.date(2024, 3, 15),
            num_payments=2,
            payment_option_id="opt_1",
            is_safe=True,
        )
        plan_later = CandidatePlan(
            method="installments",
            schedule=((datetime.date(2024, 3, 5), 50.0), (datetime.date(2024, 3, 15), 50.0)),
            spending_changes=(),
            total_cost=100.0,
            first_payment_date=datetime.date(2024, 3, 5),
            completion_date=datetime.date(2024, 3, 15),
            num_payments=2,
            payment_option_id="opt_2",
            is_safe=True,
        )
        self.assertLess(plan_sort_key(plan_earlier, d_dead), plan_sort_key(plan_later, d_dead))

        plan_1_payment = CandidatePlan(
            method="full_payment",
            schedule=((datetime.date(2024, 3, 1), 100.0),),
            spending_changes=(),
            total_cost=100.0,
            first_payment_date=datetime.date(2024, 3, 1),
            completion_date=datetime.date(2024, 3, 1),
            num_payments=1,
            payment_option_id=None,
            is_safe=True,
        )
        self.assertLess(plan_sort_key(plan_1_payment, d_dead), plan_sort_key(plan_earlier, d_dead))


class TestEvaluatorLogic(unittest.TestCase):
    """Test candidate plan generation, safe amount calculation, and spending optimizer."""

    def setUp(self):
        self.profile = UserProfile(
            user_id="user_t",
            home_currency="USD",
            current_available_balance=5000.0,
            minimum_balance_to_keep=1000.0,
            financial_priorities=("emergency_savings",),
            expense_categories_to_protect=frozenset({"rent", "groceries"}),
            expense_categories_user_is_willing_to_reduce=frozenset({"dining"}),
            expense_categories_user_is_willing_to_stop=frozenset({"streaming"}),
            payment_methods_user_will_consider=frozenset({"full_payment", "partial_payment", "installments"}),
            max_installment_months=3,
        )
        self.events = [
            FinancialEvent(
                event_id="ev_rent",
                user_id="user_t",
                event_type="expense",
                description="Monthly rent",
                category="rent",
                direction="debit",
                amount=1200.0,
                currency="USD",
                event_date=datetime.date(2024, 3, 1),
                settlement_date=datetime.date(2024, 3, 1),
                status="settled",
                flexibility="fixed",
            ),
            FinancialEvent(
                event_id="ev_stream",
                user_id="user_t",
                event_type="subscription",
                description="Video streaming",
                category="streaming",
                direction="debit",
                amount=50.0,
                currency="USD",
                event_date=datetime.date(2024, 3, 10),
                settlement_date=datetime.date(2024, 3, 10),
                status="settled",
                flexibility="stoppable",
            ),
            FinancialEvent(
                event_id="ev_salary",
                user_id="user_t",
                event_type="income",
                description="Payroll credit",
                category="salary",
                direction="credit",
                amount=3000.0,
                currency="USD",
                event_date=datetime.date(2024, 3, 15),
                settlement_date=datetime.date(2024, 3, 15),
                status="settled",
                flexibility="fixed",
            ),
        ]

    def test_amount_safe_to_pay_bounds(self):
        """amount_safe_to_pay must always satisfy 0 <= safe <= requested_amount."""
        from evaluator import calculate_amount_safe_to_pay

        req = EvaluationRequest(
            request_id="req_test",
            user_id="user_t",
            request_date=datetime.date(2024, 3, 3),
            request_type="purchase",
            requested_amount=2000.0,
            desired_completion_date=datetime.date(2024, 3, 20),
            allows_partial_payment=True,
            request_text="Can I buy this?",
        )
        safe = calculate_amount_safe_to_pay(self.profile, self.events, req)
        self.assertGreaterEqual(safe, 0.0)
        self.assertLessEqual(safe, req.requested_amount)

    def test_find_earliest_date_for_full_payment(self):
        """Finds the earliest date when full payment is safe without spending changes."""
        from evaluator import find_earliest_date_for_full_payment

        # When already safe today on request_date
        req_small = EvaluationRequest(
            request_id="req_small",
            user_id="user_t",
            request_date=datetime.date(2024, 3, 3),
            request_type="purchase",
            requested_amount=500.0,
            desired_completion_date=datetime.date(2024, 3, 20),
            allows_partial_payment=True,
            request_text="Small purchase",
        )
        earliest = find_earliest_date_for_full_payment(self.profile, self.events, req_small)
        self.assertEqual(earliest, "2024-03-03")

        # When safe only after salary settlement on 2024-03-15
        low_balance_profile = UserProfile(
            user_id="user_t",
            home_currency="USD",
            current_available_balance=1200.0,
            minimum_balance_to_keep=1000.0,
            financial_priorities=("emergency_savings",),
            expense_categories_to_protect=frozenset({"rent"}),
            expense_categories_user_is_willing_to_reduce=frozenset(),
            expense_categories_user_is_willing_to_stop=frozenset(),
            payment_methods_user_will_consider=frozenset({"full_payment"}),
            max_installment_months=None,
        )
        req_after_sal = EvaluationRequest(
            request_id="req_med",
            user_id="user_t",
            request_date=datetime.date(2024, 3, 3),
            request_type="purchase",
            requested_amount=1500.0,
            desired_completion_date=datetime.date(2024, 3, 25),
            allows_partial_payment=False,
            request_text="Wait for salary",
        )
        earliest_sal = find_earliest_date_for_full_payment(low_balance_profile, self.events, req_after_sal)
        self.assertEqual(earliest_sal, "2024-03-15")

    def test_partial_payment_schedule_and_invariants(self):
        """Partial payment must have exactly two payments summing to requested_amount."""
        from evaluator import generate_partial_payment_plan

        req = EvaluationRequest(
            request_id="req_part",
            user_id="user_t",
            request_date=datetime.date(2024, 3, 3),
            request_type="purchase",
            requested_amount=1000.0,
            desired_completion_date=datetime.date(2024, 3, 25),
            allows_partial_payment=True,
            request_text="Partial payment please",
        )
        plan = generate_partial_payment_plan(
            self.profile, self.events, req, safe_today=400.0, earliest_date="2024-03-15"
        )
        self.assertIsNotNone(plan)
        self.assertEqual(plan.method, "partial_payment")
        self.assertEqual(len(plan.schedule), 2)
        self.assertEqual(plan.schedule[0], (datetime.date(2024, 3, 3), 400.0))
        self.assertEqual(plan.schedule[1], (datetime.date(2024, 3, 15), 600.0))
        self.assertEqual(sum(p[1] for p in plan.schedule), 1000.0)

    def test_installments_filter_by_max_installment_months(self):
        """Installment options exceeding max_installment_months must be rejected."""
        from evaluator import evaluate_installment_options

        req = EvaluationRequest(
            request_id="req_inst",
            user_id="user_t",
            request_date=datetime.date(2024, 3, 3),
            request_type="purchase",
            requested_amount=1200.0,
            desired_completion_date=datetime.date(2024, 6, 30),
            allows_partial_payment=False,
            request_text="Check installments",
        )
        options = [
            PaymentOption(
                payment_option_id="opt_valid_3m",
                request_id="req_inst",
                payment_method="installments",
                payment_amount=400.0,
                number_of_payments=3,
                first_payment_date=datetime.date(2024, 3, 5),
                payment_frequency_days=30,
                financing_fee=0.0,
                total_payable_amount=1200.0,
            ),
            PaymentOption(
                payment_option_id="opt_invalid_6m",
                request_id="req_inst",
                payment_method="installments",
                payment_amount=210.0,
                number_of_payments=6,
                first_payment_date=datetime.date(2024, 3, 5),
                payment_frequency_days=30,
                financing_fee=60.0,
                total_payable_amount=1260.0,
            ),
        ]
        valid_plans = evaluate_installment_options(self.profile, self.events, req, options)
        # opt_invalid_6m exceeds max_installment_months (3) and must not be considered
        opt_ids = [p.payment_option_id for p in valid_plans]
        self.assertIn("opt_valid_3m", opt_ids)
        self.assertNotIn("opt_invalid_6m", opt_ids)

    def test_spending_changes_optimizer_picks_minimal_stoppable_subscription(self):
        """Optimizer finds minimal non-protected flexible expense to stop/reduce."""
        from evaluator import find_optimal_spending_changes

        # Headroom shortage of 30 USD
        changes = find_optimal_spending_changes(self.profile, self.events, shortage=30.0)
        self.assertIsNotNone(changes)
        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0], "stop:ev_stream")

    def test_end_to_end_evaluate_request_affordable_now(self):
        """End-to-end evaluation for affordable_now case."""
        from evaluator import evaluate_request

        req = EvaluationRequest(
            request_id="req_e2e_now",
            user_id="user_t",
            request_date=datetime.date(2024, 3, 3),
            request_type="purchase",
            requested_amount=500.0,
            desired_completion_date=datetime.date(2024, 3, 20),
            allows_partial_payment=True,
            request_text="Buy today",
        )
        decision = evaluate_request(req, self.profile, self.events, [])
        self.assertIsInstance(decision, DecisionOutput)
        self.assertEqual(decision.affordability_status, "affordable_now")
        self.assertEqual(decision.recommended_payment_method, "full_payment")
        self.assertEqual(decision.earliest_date_for_full_payment, "2024-03-03")
        self.assertEqual(decision.spending_changes_needed, "none")
        self.assertEqual(decision.payment_plan, "2024-03-03:500")
        self.assertIn("1,000", decision.decision_explanation)


if __name__ == "__main__":
    unittest.main()
