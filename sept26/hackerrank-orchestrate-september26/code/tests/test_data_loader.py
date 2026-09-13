import datetime
import sys
import unittest
from pathlib import Path

# Add code directory to path
CODE_DIR = Path(__file__).resolve().parent.parent
if str(CODE_DIR) not in sys.path:
    sys.path.insert(0, str(CODE_DIR))

from exceptions import ExchangeRateNotFoundError
from data_loader import (
    apply_message_overrides,
    load_evaluation_requests,
    load_exchange_rates,
    load_financial_events,
    load_financial_profiles,
    load_messages,
    load_payment_options,
)


class TestDataLoader(unittest.TestCase):
    def setUp(self):
        self.dataset_dir = Path(__file__).resolve().parent.parent.parent / "dataset"

    def test_load_financial_profiles(self):
        profiles = load_financial_profiles(self.dataset_dir / "financial_profiles.csv")
        self.assertIn("user_01", profiles)
        u1 = profiles["user_01"]
        self.assertEqual(u1.home_currency, "ZAR")
        self.assertEqual(u1.current_available_balance, 58481.10)
        self.assertEqual(u1.minimum_balance_to_keep, 18000.00)
        self.assertIsInstance(u1.expense_categories_to_protect, frozenset)
        self.assertIn("rent", u1.expense_categories_to_protect)
        self.assertIsNone(u1.max_installment_months)

        self.assertIn("user_02", profiles)
        u2 = profiles["user_02"]
        self.assertEqual(u2.max_installment_months, 7)
        self.assertIn("installments", u2.payment_methods_user_will_consider)

    def test_load_financial_events_with_image_amounts(self):
        profiles = load_financial_profiles(self.dataset_dir / "financial_profiles.csv")
        rates = load_exchange_rates(self.dataset_dir / "exchange_rates.csv")
        events = load_financial_events(
            self.dataset_dir / "financial_events.csv",
            profiles=profiles,
            rates=rates,
        )

        # Event 253 had a blank amount in CSV, must be resolved from image_01 to 4365000.0
        ev253 = next((e for e in events if e.event_id == "event_253"), None)
        self.assertIsNotNone(ev253)
        self.assertEqual(ev253.amount, 4365000.0)
        self.assertEqual(ev253.user_id, "user_03")

    def test_cross_currency_conversion(self):
        profiles = load_financial_profiles(self.dataset_dir / "financial_profiles.csv")
        rates = load_exchange_rates(self.dataset_dir / "exchange_rates.csv")
        events = load_financial_events(
            self.dataset_dir / "financial_events.csv",
            profiles=profiles,
            rates=rates,
        )

        # Event 2167 for user_25 (home_currency=IDR) has USD 1800 on 2023-10-15.
        # Rate for USD to IDR on 2023-10-15 is 15833.33.
        # Converted amount: 1800 * 15833.33 = 28499994.0
        ev2167 = next((e for e in events if e.event_id == "event_2167"), None)
        self.assertIsNotNone(ev2167)
        self.assertAlmostEqual(ev2167.amount, 28499994.0, places=1)
        self.assertEqual(ev2167.currency, "IDR")

    def test_missing_exchange_rate_raises_error(self):
        profiles = load_financial_profiles(self.dataset_dir / "financial_profiles.csv")
        # Empty rates dictionary should fail when cross-currency event is processed
        with self.assertRaises(ExchangeRateNotFoundError):
            load_financial_events(
                self.dataset_dir / "financial_events.csv",
                profiles=profiles,
                rates={},
            )

    def test_load_payment_options_and_requests(self):
        options = load_payment_options(self.dataset_dir / "request_payment_options.csv")
        self.assertIn("request_02", options)
        self.assertGreater(len(options["request_02"]), 0)
        opt = options["request_02"][0]
        self.assertEqual(opt.request_id, "request_02")
        self.assertIsInstance(opt.installment_amount, float)
        self.assertIsInstance(opt.number_of_installments, int)

        # Load requests
        reqs = load_evaluation_requests(self.dataset_dir / "requests.csv")
        self.assertEqual(len(reqs), 250)
        self.assertEqual(reqs[0].request_id, "request_26")

        # Load sample requests
        samples = load_evaluation_requests(self.dataset_dir / "sample_requests.csv")
        self.assertEqual(len(samples), 25)
        self.assertEqual(samples[0].request_id, "request_01")

    def test_apply_message_overrides(self):
        profiles = load_financial_profiles(self.dataset_dir / "financial_profiles.csv")
        rates = load_exchange_rates(self.dataset_dir / "exchange_rates.csv")
        events = load_financial_events(
            self.dataset_dir / "financial_events.csv",
            profiles=profiles,
            rates=rates,
        )
        messages = load_messages(self.dataset_dir / "messages.csv")

        # Apply message overrides
        updated_events, user_overrides = apply_message_overrides(events, messages)

        # message_01 for user_02 specifies salary increase to 42750000.0 from 2025-08-15
        self.assertIn("user_02", user_overrides)
        u2_override = user_overrides["user_02"]
        self.assertEqual(u2_override.get("confirmed_salary"), 42750000.0)
        self.assertEqual(u2_override.get("salary_effective_date"), datetime.date(2025, 8, 15))


if __name__ == "__main__":
    unittest.main()
