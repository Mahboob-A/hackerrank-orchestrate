import datetime
import sys
import unittest
from pathlib import Path

# Add code directory to path
CODE_DIR = Path(__file__).resolve().parent.parent
if str(CODE_DIR) not in sys.path:
    sys.path.insert(0, str(CODE_DIR))

from forecaster import SimulationResult, simulate_cashflow
from models import FinancialEvent, UserProfile


class TestCashflowForecaster(unittest.TestCase):
    def setUp(self):
        self.profile = UserProfile(
            user_id="user_test",
            home_currency="EUR",
            current_available_balance=50000.0,
            minimum_balance_to_keep=10000.0,
            financial_priorities=("emergency_savings",),
            expense_categories_to_protect=frozenset({"rent"}),
            expense_categories_user_is_willing_to_reduce=frozenset({"dining"}),
            expense_categories_user_is_willing_to_stop=frozenset({"streaming"}),
            payment_methods_user_will_consider=frozenset({"full_payment", "installments"}),
            max_installment_months=3,
        )
        self.request_date = datetime.date(2025, 8, 1)

    def test_daily_balance_simulation_90_days(self):
        result = simulate_cashflow(
            profile=self.profile,
            events=[],
            request_date=self.request_date,
            forecast_days=90,
        )
        self.assertIsInstance(result, SimulationResult)
        self.assertTrue(result.is_safe)
        # Exactly 91 days from T0 to T0+90 inclusive
        self.assertEqual(len(result.daily_balances), 91)
        self.assertEqual(result.daily_balances[self.request_date], 50000.0)
        end_date = self.request_date + datetime.timedelta(days=90)
        self.assertEqual(result.daily_balances[end_date], 50000.0)
        self.assertEqual(result.min_headroom, 40000.0)

    def test_pending_debits_reserved_immediately(self):
        pending_debit = FinancialEvent(
            event_id="ev_debit_01",
            user_id="user_test",
            event_type="expense",
            description="Pending card charge",
            category="dining",
            direction="debit",
            amount=15000.0,
            currency="EUR",
            event_date=self.request_date,
            settlement_date=self.request_date + datetime.timedelta(days=2),
            status="pending",
        )
        result = simulate_cashflow(
            profile=self.profile,
            events=[pending_debit],
            request_date=self.request_date,
        )
        # Pending debit must be reserved immediately on T0 (50,000 - 15,000 = 35,000)
        self.assertEqual(result.daily_balances[self.request_date], 35000.0)
        self.assertEqual(result.min_headroom, 25000.0)
        self.assertTrue(result.is_safe)

    def test_speculative_inflows_ignored(self):
        pending_credit = FinancialEvent(
            event_id="ev_credit_01",
            user_id="user_test",
            event_type="income",
            description="Pending quarterly bonus",
            category="bonus",
            direction="credit",
            amount=20000.0,
            currency="EUR",
            event_date=self.request_date,
            settlement_date=self.request_date + datetime.timedelta(days=5),
            status="pending",
        )
        unrealized_inv = FinancialEvent(
            event_id="ev_inv_01",
            user_id="user_test",
            event_type="investment_valuation",
            description="Portfolio value gain",
            category="investment",
            direction="non_cash",
            amount=30000.0,
            currency="EUR",
            event_date=self.request_date,
            settlement_date=None,
            status="unrealized",
        )
        result = simulate_cashflow(
            profile=self.profile,
            events=[pending_credit, unrealized_inv],
            request_date=self.request_date,
        )
        # Pending credits and unrealized gains must NOT increase liquid cash balance
        self.assertEqual(result.daily_balances[self.request_date], 50000.0)
        self.assertEqual(result.daily_balances[self.request_date + datetime.timedelta(days=5)], 50000.0)

    def test_safety_invariant_breach_and_bottleneck(self):
        tight_profile = UserProfile(
            user_id="user_tight",
            home_currency="EUR",
            current_available_balance=20000.0,
            minimum_balance_to_keep=15000.0,
            financial_priorities=(),
            expense_categories_to_protect=frozenset(),
            expense_categories_user_is_willing_to_reduce=frozenset(),
            expense_categories_user_is_willing_to_stop=frozenset(),
            payment_methods_user_will_consider=frozenset({"full_payment"}),
        )
        breach_date = self.request_date + datetime.timedelta(days=10)
        scheduled_bill = FinancialEvent(
            event_id="ev_bill_01",
            user_id="user_tight",
            event_type="expense",
            description="Large insurance premium",
            category="insurance",
            direction="debit",
            amount=10000.0,
            currency="EUR",
            event_date=breach_date,
            settlement_date=breach_date,
            status="settled",
        )
        result = simulate_cashflow(
            profile=tight_profile,
            events=[scheduled_bill],
            request_date=self.request_date,
        )
        # Balance drops to 10,000 on breach_date, which is below 15,000 minimum
        self.assertFalse(result.is_safe)
        self.assertEqual(result.bottleneck_date, breach_date)
        self.assertEqual(result.min_headroom, -5000.0)

    def test_confirmed_salary_with_message_overrides(self):
        salary_date = self.request_date + datetime.timedelta(days=14)
        salary_event = FinancialEvent(
            event_id="ev_sal_01",
            user_id="user_test",
            event_type="income",
            description="Monthly payroll",
            category="salary",
            direction="credit",
            amount=2500.0,
            currency="EUR",
            event_date=salary_date,
            settlement_date=salary_date,
            status="settled",
        )
        # Case 1: Baseline confirmed salary credited on settlement date
        res_baseline = simulate_cashflow(
            profile=self.profile,
            events=[salary_event],
            request_date=self.request_date,
        )
        self.assertEqual(res_baseline.daily_balances[salary_date], 52500.0)

        # Case 2: Message override updates salary amount
        user_overrides = {
            "user_test": {
                "confirmed_salary": 3200.0,
                "salary_effective_date": salary_date,
            }
        }
        res_override = simulate_cashflow(
            profile=self.profile,
            events=[salary_event],
            request_date=self.request_date,
            user_overrides=user_overrides,
        )
        self.assertEqual(res_override.daily_balances[salary_date], 53200.0)

    def test_payment_schedules_and_spending_changes(self):
        tight_profile = UserProfile(
            user_id="user_test",
            home_currency="EUR",
            current_available_balance=20000.0,
            minimum_balance_to_keep=15000.0,
            financial_priorities=(),
            expense_categories_to_protect=frozenset(),
            expense_categories_user_is_willing_to_reduce=frozenset(),
            expense_categories_user_is_willing_to_stop=frozenset({"streaming"}),
            payment_methods_user_will_consider=frozenset({"full_payment"}),
        )
        bill_date = self.request_date + datetime.timedelta(days=5)
        flexible_expense = FinancialEvent(
            event_id="ev_flex_01",
            user_id="user_test",
            event_type="expense",
            description="Streaming subscription",
            category="streaming",
            direction="debit",
            amount=4000.0,
            currency="EUR",
            event_date=bill_date,
            settlement_date=bill_date,
            status="settled",
            flexibility="flexible",
        )
        plan_payment_date = self.request_date + datetime.timedelta(days=3)
        plan_schedule = ((plan_payment_date, 3000.0),)

        # Without spending changes: balance drops by 3,000 on day 3 (to 17,000), then by 4,000 on day 5 (to 13,000 < 15,000)
        res_fail = simulate_cashflow(
            profile=tight_profile,
            events=[flexible_expense],
            request_date=self.request_date,
            payment_schedule=plan_schedule,
        )
        self.assertFalse(res_fail.is_safe)
        self.assertEqual(res_fail.min_headroom, -2000.0)

        # With spending change stop:ev_flex_01: the 4,000 expense is stopped, keeping balance at 17,000 >= 15,000
        res_pass = simulate_cashflow(
            profile=tight_profile,
            events=[flexible_expense],
            request_date=self.request_date,
            payment_schedule=plan_schedule,
            spending_changes=("stop:ev_flex_01",),
        )
        self.assertTrue(res_pass.is_safe)
        self.assertEqual(res_pass.min_headroom, 2000.0)


if __name__ == "__main__":
    unittest.main()
