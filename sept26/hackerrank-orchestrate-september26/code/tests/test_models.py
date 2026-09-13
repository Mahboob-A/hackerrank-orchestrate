import datetime
import sys
import unittest
from pathlib import Path

# Add code directory to path
CODE_DIR = Path(__file__).resolve().parent.parent
if str(CODE_DIR) not in sys.path:
    sys.path.insert(0, str(CODE_DIR))

from exceptions import (
    ExchangeRateNotFoundError,
    InfeasiblePlanError,
    MissingAmountError,
    SchemaValidationError,
)
from models import (
    CandidatePlan,
    DecisionOutput,
    EvaluationRequest,
    FinancialEvent,
    PaymentOption,
    UserProfile,
)


class TestDomainExceptions(unittest.TestCase):
    def test_missing_amount_error(self):
        err = MissingAmountError("Amount missing for event_253")
        self.assertIsInstance(err, Exception)
        self.assertEqual(str(err), "Amount missing for event_253")

    def test_exchange_rate_not_found_error(self):
        err = ExchangeRateNotFoundError("Rate not found for USD to EUR on 2025-08-01")
        self.assertIsInstance(err, LookupError)
        self.assertEqual(str(err), "Rate not found for USD to EUR on 2025-08-01")

    def test_schema_validation_error(self):
        err = SchemaValidationError("Invalid direction: unknown_dir")
        self.assertIsInstance(err, ValueError)
        self.assertEqual(str(err), "Invalid direction: unknown_dir")

    def test_infeasible_plan_error(self):
        err = InfeasiblePlanError("Plan violates minimum balance on 2025-08-15")
        self.assertIsInstance(err, Exception)
        self.assertEqual(str(err), "Plan violates minimum balance on 2025-08-15")


class TestUserProfileModel(unittest.TestCase):
    def test_user_profile_instantiation(self):
        profile = UserProfile(
            user_id="user_01",
            home_currency="ZAR",
            current_available_balance=58481.10,
            minimum_balance_to_keep=18000.00,
            financial_priorities=("education", "debt_repayment"),
            expense_categories_to_protect=frozenset({"rent", "education", "groceries", "debt_repayment"}),
            expense_categories_user_is_willing_to_reduce=frozenset({"dining"}),
            expense_categories_user_is_willing_to_stop=frozenset({"delivery_membership"}),
            payment_methods_user_will_consider=frozenset({"full_payment"}),
            max_installment_months=None,
        )
        self.assertEqual(profile.user_id, "user_01")
        self.assertEqual(profile.home_currency, "ZAR")
        self.assertEqual(profile.current_available_balance, 58481.10)
        self.assertEqual(profile.minimum_balance_to_keep, 18000.00)
        self.assertEqual(profile.financial_priorities, ("education", "debt_repayment"))
        self.assertIn("rent", profile.expense_categories_to_protect)
        self.assertIn("dining", profile.expense_categories_user_is_willing_to_reduce)
        self.assertIn("delivery_membership", profile.expense_categories_user_is_willing_to_stop)
        self.assertIn("full_payment", profile.payment_methods_user_will_consider)
        self.assertIsNone(profile.max_installment_months)

    def test_user_profile_with_installments(self):
        profile = UserProfile(
            user_id="user_02",
            home_currency="IDR",
            current_available_balance=60383889.20,
            minimum_balance_to_keep=29158400.00,
            financial_priorities=("education", "family_support"),
            expense_categories_to_protect=frozenset({"housing", "utilities", "education"}),
            expense_categories_user_is_willing_to_reduce=frozenset({"entertainment"}),
            expense_categories_user_is_willing_to_stop=frozenset({"cloud_storage"}),
            payment_methods_user_will_consider=frozenset({"partial_payment", "installments"}),
            max_installment_months=7,
        )
        self.assertEqual(profile.max_installment_months, 7)
        self.assertIn("installments", profile.payment_methods_user_will_consider)


class TestFinancialEventModel(unittest.TestCase):
    def test_financial_event_instantiation(self):
        event = FinancialEvent(
            event_id="event_01",
            user_id="user_01",
            event_type="expense",
            description="Apartment rent transfer",
            category="rent",
            direction="debit",
            amount=5148.00,
            currency="ZAR",
            event_date=datetime.date(2023, 10, 2),
            settlement_date=datetime.date(2023, 10, 2),
            status="settled",
            linked_event_id=None,
            flexibility="fixed",
            minimum_allowed_amount=None,
        )
        self.assertEqual(event.event_id, "event_01")
        self.assertEqual(event.direction, "debit")
        self.assertEqual(event.amount, 5148.00)
        self.assertEqual(event.currency, "ZAR")
        self.assertEqual(event.event_date, datetime.date(2023, 10, 2))
        self.assertEqual(event.settlement_date, datetime.date(2023, 10, 2))
        self.assertEqual(event.status, "settled")
        self.assertEqual(event.flexibility, "fixed")
        self.assertIsNone(event.linked_event_id)
        self.assertIsNone(event.minimum_allowed_amount)

    def test_financial_event_flexible_with_minimum(self):
        event = FinancialEvent(
            event_id="event_476",
            user_id="user_06",
            event_type="expense",
            description="Family streaming subscription",
            category="streaming",
            direction="debit",
            amount=29.99,
            currency="EUR",
            event_date=datetime.date(2025, 12, 10),
            settlement_date=datetime.date(2025, 12, 10),
            status="settled",
            linked_event_id=None,
            flexibility="flexible",
            minimum_allowed_amount=10.00,
        )
        self.assertEqual(event.flexibility, "flexible")
        self.assertEqual(event.minimum_allowed_amount, 10.00)


class TestPaymentOptionModel(unittest.TestCase):
    def test_payment_option_instantiation(self):
        opt = PaymentOption(
            payment_option_id="opt_01",
            request_id="request_02",
            option_name="3-Month Installment Plan",
            provider="FlexiPay",
            down_payment_amount=0.00,
            installment_amount=15952906.67,
            number_of_installments=3,
            interval_days=30,
            start_date_offset_days=3,
            total_amount_payable=47858720.01,
            financing_fee=1840720.01,
            apr_percent=12.5,
        )
        self.assertEqual(opt.payment_option_id, "opt_01")
        self.assertEqual(opt.request_id, "request_02")
        self.assertEqual(opt.number_of_installments, 3)
        self.assertEqual(opt.interval_days, 30)
        self.assertEqual(opt.total_amount_payable, 47858720.01)
        self.assertEqual(opt.apr_percent, 12.5)


class TestEvaluationRequestModel(unittest.TestCase):
    def test_evaluation_request_instantiation(self):
        req = EvaluationRequest(
            request_id="request_01",
            user_id="user_01",
            request_date=datetime.date(2024, 3, 3),
            request_type="purchase",
            requested_amount=25256.00,
            desired_completion_date=datetime.date(2024, 3, 20),
            allows_partial_payment=True,
            request_text="Would paying for the laptop today leave enough for my regular expenses?",
        )
        self.assertEqual(req.request_id, "request_01")
        self.assertEqual(req.user_id, "user_01")
        self.assertEqual(req.request_date, datetime.date(2024, 3, 3))
        self.assertEqual(req.requested_amount, 25256.00)
        self.assertTrue(req.allows_partial_payment)


class TestCandidatePlanModel(unittest.TestCase):
    def test_candidate_plan_instantiation(self):
        plan = CandidatePlan(
            method="full_payment",
            schedule=((datetime.date(2024, 3, 3), 25256.00),),
            spending_changes=(),
            total_cost=25256.00,
            first_payment_date=datetime.date(2024, 3, 3),
            completion_date=datetime.date(2024, 3, 3),
            num_payments=1,
            payment_option_id=None,
            is_safe=True,
        )
        self.assertEqual(plan.method, "full_payment")
        self.assertEqual(len(plan.schedule), 1)
        self.assertEqual(plan.total_cost, 25256.00)
        self.assertTrue(plan.is_safe)
        self.assertEqual(plan.num_payments, 1)


class TestDecisionOutputModel(unittest.TestCase):
    def test_decision_output_instantiation(self):
        out = DecisionOutput(
            request_id="request_01",
            amount_safe_to_pay=25256.00,
            affordability_status="affordable_now",
            recommended_payment_method="full_payment",
            payment_plan="2024-03-03:25256",
            earliest_date_for_full_payment="2024-03-03",
            spending_changes_needed="none",
            decision_explanation="Pay ZAR 25,256 today. This leaves at least ZAR 18,000 available over the next 90 days.",
        )
        self.assertEqual(out.request_id, "request_01")
        self.assertEqual(out.amount_safe_to_pay, 25256.00)
        self.assertEqual(out.affordability_status, "affordable_now")
        self.assertEqual(out.recommended_payment_method, "full_payment")
        self.assertEqual(out.payment_plan, "2024-03-03:25256")
        self.assertEqual(out.earliest_date_for_full_payment, "2024-03-03")
        self.assertEqual(out.spending_changes_needed, "none")


if __name__ == "__main__":
    unittest.main()
