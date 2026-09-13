"""Unit tests for Layer 4: Compliance & Output Formatter (formatter.py)."""

import csv
import datetime
import io
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from exceptions import SchemaValidationError
from models import DecisionOutput, EvaluationRequest


class TestPaymentPlanAndSpendingFormatting(unittest.TestCase):
    """Test format_payment_plan and format_spending_changes."""

    def test_format_payment_plan_empty_or_none(self):
        """Returns 'none' when schedule is empty or None."""
        from formatter import format_payment_plan

        self.assertEqual(format_payment_plan(None), "none")
        self.assertEqual(format_payment_plan(()), "none")
        self.assertEqual(format_payment_plan([]), "none")

    def test_format_payment_plan_single_and_multi_payments(self):
        """Converts schedule tuples to <YYYY-MM-DD>:<amount>|... without float drift."""
        from formatter import format_payment_plan

        single = ((datetime.date(2024, 3, 3), 25256.0),)
        self.assertEqual(format_payment_plan(single), "2024-03-03:25256")

        multi = (
            (datetime.date(2025, 8, 8), 15952906.67),
            (datetime.date(2025, 9, 7), 15952906.67),
            (datetime.date(2025, 10, 7), 15952906.67),
        )
        self.assertEqual(
            format_payment_plan(multi),
            "2025-08-08:15952906.67|2025-09-07:15952906.67|2025-10-07:15952906.67",
        )

        with_decimals = ((datetime.date(2026, 1, 3), 620.4),)
        self.assertEqual(format_payment_plan(with_decimals), "2026-01-03:620.40")

    def test_format_spending_changes_empty_or_none(self):
        """Returns 'none' when spending changes sequence is empty or None."""
        from formatter import format_spending_changes

        self.assertEqual(format_spending_changes(None), "none")
        self.assertEqual(format_spending_changes(()), "none")
        self.assertEqual(format_spending_changes([]), "none")

    def test_format_spending_changes_single_and_multi(self):
        """Joins spending change strings by '|'."""
        from formatter import format_spending_changes

        single = ("stop:event_476",)
        self.assertEqual(format_spending_changes(single), "stop:event_476")

        multi = ("stop:event_1815", "reduce_to:event_1816:23.50")
        self.assertEqual(
            format_spending_changes(multi),
            "stop:event_1815|reduce_to:event_1816:23.50",
        )


class TestValidateOutputRow(unittest.TestCase):
    """Test validate_output_row strict domain and schema validation."""

    def setUp(self):
        self.req = EvaluationRequest(
            request_id="req_01",
            user_id="user_01",
            request_date=datetime.date(2024, 3, 3),
            request_type="purchase",
            requested_amount=25256.0,
            desired_completion_date=datetime.date(2024, 3, 20),
            allows_partial_payment=True,
            request_text="Can I afford the laptop?",
        )
        self.valid_output = DecisionOutput(
            request_id="req_01",
            amount_safe_to_pay=25256.0,
            affordability_status="affordable_now",
            recommended_payment_method="full_payment",
            payment_plan="2024-03-03:25256",
            earliest_date_for_full_payment="2024-03-03",
            spending_changes_needed="none",
            decision_explanation="Pay ZAR 25,256 today. This leaves at least ZAR 18,000 available.",
        )

    def test_validate_output_row_success_on_valid(self):
        """validate_output_row passes on valid output."""
        from formatter import validate_output_row

        # Should execute without raising any exception
        validate_output_row(self.valid_output, self.req)

    def test_validate_output_row_invalid_safe_amount_bounds(self):
        """Raises SchemaValidationError if amount_safe_to_pay < 0 or > requested_amount."""
        from formatter import validate_output_row

        # Below 0
        neg_output = DecisionOutput(
            request_id="req_01",
            amount_safe_to_pay=-10.0,
            affordability_status="not_affordable",
            recommended_payment_method="not_recommended",
            payment_plan="none",
            earliest_date_for_full_payment="",
            spending_changes_needed="none",
            decision_explanation="Negative safe amount.",
        )
        with self.assertRaises(SchemaValidationError):
            validate_output_row(neg_output, self.req)

        # Above requested_amount
        exceed_output = DecisionOutput(
            request_id="req_01",
            amount_safe_to_pay=30000.0,  # requested is 25256.0
            affordability_status="affordable_now",
            recommended_payment_method="full_payment",
            payment_plan="2024-03-03:25256",
            earliest_date_for_full_payment="2024-03-03",
            spending_changes_needed="none",
            decision_explanation="Exceeds requested amount.",
        )
        with self.assertRaises(SchemaValidationError):
            validate_output_row(exceed_output, self.req)

    def test_validate_output_row_affordable_now_earliest_date_mismatch(self):
        """Raises SchemaValidationError if affordable_now has earliest_date != request_date."""
        from formatter import validate_output_row

        bad_earliest = DecisionOutput(
            request_id="req_01",
            amount_safe_to_pay=25256.0,
            affordability_status="affordable_now",
            recommended_payment_method="full_payment",
            payment_plan="2024-03-03:25256",
            earliest_date_for_full_payment="2024-03-15",  # Mismatch: request_date is 2024-03-03
            spending_changes_needed="none",
            decision_explanation="Mismatched earliest date.",
        )
        with self.assertRaises(SchemaValidationError):
            validate_output_row(bad_earliest, self.req)

    def test_validate_output_row_partial_payment_constraints(self):
        """Raises SchemaValidationError if partial_payment doesn't have 2 payments or doesn't sum to requested_amount."""
        from formatter import validate_output_row

        # 3 payments instead of 2
        bad_num_pmts = DecisionOutput(
            request_id="req_01",
            amount_safe_to_pay=10000.0,
            affordability_status="affordable_with_plan",
            recommended_payment_method="partial_payment",
            payment_plan="2024-03-03:10000|2024-03-10:5000|2024-03-15:10256",
            earliest_date_for_full_payment="2024-03-15",
            spending_changes_needed="none",
            decision_explanation="Three payments instead of two.",
        )
        with self.assertRaises(SchemaValidationError):
            validate_output_row(bad_num_pmts, self.req)

        # Sum doesn't match requested_amount (10000 + 10000 = 20000 != 25256)
        bad_sum = DecisionOutput(
            request_id="req_01",
            amount_safe_to_pay=10000.0,
            affordability_status="affordable_with_plan",
            recommended_payment_method="partial_payment",
            payment_plan="2024-03-03:10000|2024-03-15:10000",
            earliest_date_for_full_payment="2024-03-15",
            spending_changes_needed="none",
            decision_explanation="Sum does not match requested amount.",
        )
        with self.assertRaises(SchemaValidationError):
            validate_output_row(bad_sum, self.req)

    def test_validate_output_row_invalid_enums(self):
        """Raises SchemaValidationError on invalid status or method enums."""
        from formatter import validate_output_row

        bad_status = DecisionOutput(
            request_id="req_01",
            amount_safe_to_pay=25256.0,
            affordability_status="affordable_immediately",  # invalid
            recommended_payment_method="full_payment",
            payment_plan="2024-03-03:25256",
            earliest_date_for_full_payment="2024-03-03",
            spending_changes_needed="none",
            decision_explanation="Invalid status enum.",
        )
        with self.assertRaises(SchemaValidationError):
            validate_output_row(bad_status, self.req)

        bad_method = DecisionOutput(
            request_id="req_01",
            amount_safe_to_pay=25256.0,
            affordability_status="affordable_now",
            recommended_payment_method="credit_card",  # invalid
            payment_plan="2024-03-03:25256",
            earliest_date_for_full_payment="2024-03-03",
            spending_changes_needed="none",
            decision_explanation="Invalid method enum.",
        )
        with self.assertRaises(SchemaValidationError):
            validate_output_row(bad_method, self.req)


class TestCsvSerialization(unittest.TestCase):
    """Test CSV serialization for exact 8 required columns and ordering."""

    def test_serialize_output_csv_header_and_order(self):
        """Ensures exact 8 columns in exact required order."""
        from formatter import serialize_output_rows

        decisions = [
            DecisionOutput(
                request_id="request_01",
                amount_safe_to_pay=25256.0,
                affordability_status="affordable_now",
                recommended_payment_method="full_payment",
                payment_plan="2024-03-03:25256",
                earliest_date_for_full_payment="2024-03-03",
                spending_changes_needed="none",
                decision_explanation="Pay ZAR 25,256 today. This leaves at least ZAR 18,000 available.",
            ),
            DecisionOutput(
                request_id="request_05",
                amount_safe_to_pay=737.0,
                affordability_status="not_affordable",
                recommended_payment_method="not_recommended",
                payment_plan="none",
                earliest_date_for_full_payment="",
                spending_changes_needed="none",
                decision_explanation="Do not make this payment by 12 January 2026.",
            ),
        ]

        expected_columns = [
            "request_id",
            "amount_safe_to_pay",
            "affordability_status",
            "recommended_payment_method",
            "payment_plan",
            "earliest_date_for_full_payment",
            "spending_changes_needed",
            "decision_explanation",
        ]

        out_buffer = io.StringIO()
        serialize_output_rows(decisions, out_buffer)
        out_buffer.seek(0)

        reader = csv.reader(out_buffer)
        header = next(reader)
        self.assertEqual(header, expected_columns)

        row1 = next(reader)
        self.assertEqual(row1[0], "request_01")
        self.assertEqual(row1[1], "25256")
        self.assertEqual(row1[2], "affordable_now")
        self.assertEqual(row1[3], "full_payment")
        self.assertEqual(row1[4], "2024-03-03:25256")
        self.assertEqual(row1[5], "2024-03-03")
        self.assertEqual(row1[6], "none")

        row2 = next(reader)
        self.assertEqual(row2[0], "request_05")
        self.assertEqual(row2[1], "737")
        self.assertEqual(row2[2], "not_affordable")
        self.assertEqual(row2[3], "not_recommended")
        self.assertEqual(row2[4], "none")
        self.assertEqual(row2[5], "")
        self.assertEqual(row2[6], "none")


if __name__ == "__main__":
    unittest.main()
