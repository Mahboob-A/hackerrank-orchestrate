import datetime
import sys
import unittest
from pathlib import Path

# Add code directory to path
CODE_DIR = Path(__file__).resolve().parent.parent
if str(CODE_DIR) not in sys.path:
    sys.path.insert(0, str(CODE_DIR))

from exceptions import MissingAmountError
from multimodal import parse_message, resolve_image_amount


class TestImageAmountResolution(unittest.TestCase):
    def test_all_16_image_amounts(self):
        expected_amounts = {
            "event_253": 4365000.0,
            "event_1442": 100000.0,
            "event_1545": 41272.0,
            "event_1700": 2854.0,
            "event_1786": 704.05,
            "event_3051": 1995.0,
            "event_3231": 8528.0,
            "event_4535": 15339.0,
            "event_5170": 723.0,
            "event_6033": 79679.26,
            "event_6859": 3650.0,
            "event_7307": 33.50,
            "event_7941": 2298.0,
            "event_9421": 1545.0,
            "event_9806": 9968.0,
            "event_10521": 393.22,
        }
        for event_id, expected_amt in expected_amounts.items():
            resolved = resolve_image_amount(event_id)
            self.assertEqual(
                resolved,
                expected_amt,
                f"Mismatch for {event_id}: expected {expected_amt}, got {resolved}",
            )

    def test_unknown_event_raises_missing_amount_error(self):
        with self.assertRaises(MissingAmountError):
            resolve_image_amount("event_999999")


class TestMessageRegexExtraction(unittest.TestCase):
    def test_indonesian_salary_raise(self):
        msg = (
            "Rincian penggajian Anda di Cobalt Systems telah berubah. "
            "Gaji bulanan Anda naik menjadi IDR 42750000. "
            "Perubahan ini berlaku mulai 2025-08-15. "
            "Jumlah yang diperbarui akan terlihat pada slip gaji berikutnya. Ref payroll EMP-0001."
        )
        parsed = parse_message(msg)
        self.assertEqual(parsed.action, "salary_change")
        self.assertEqual(parsed.new_amount, 42750000.0)
        self.assertEqual(parsed.currency, "IDR")
        self.assertEqual(parsed.effective_date, datetime.date(2025, 8, 15))
        self.assertTrue(parsed.is_confirmed)

    def test_english_salary_reduction(self):
        msg = (
            "Hi, Greenfield Foods payroll here. Your next salary is reduced to EUR 1422.85. "
            "The adjustment is due to approved unpaid leave. "
            "The adjustment will be visible on your next payslip. Payroll ref EMP-0006."
        )
        parsed = parse_message(msg)
        self.assertEqual(parsed.action, "salary_change")
        self.assertEqual(parsed.new_amount, 1422.85)
        self.assertEqual(parsed.currency, "EUR")
        self.assertTrue(parsed.is_confirmed)

    def test_payroll_date_rescheduled(self):
        msg = (
            "BrightPath Media has updated your payroll record. "
            "Your confirmed salary is now expected on 2024-09-23. "
            "This replaces the payroll date shown in the earlier update. Payroll ref EMP-0005."
        )
        parsed = parse_message(msg)
        self.assertEqual(parsed.action, "payroll_date_reschedule")
        self.assertEqual(parsed.effective_date, datetime.date(2024, 9, 23))
        self.assertTrue(parsed.is_confirmed)

    def test_contract_termination(self):
        msg = (
            "A note from Cobalt Systems about your upcoming pay. "
            "The current seasonal contract has ended. No off-season income or renewal has been confirmed. "
            "We'll contact you separately if another shift block or contract is approved. Payroll ref EMP-0009."
        )
        parsed = parse_message(msg)
        self.assertEqual(parsed.action, "contract_termination")
        self.assertEqual(parsed.new_amount, 0.0)
        self.assertTrue(parsed.is_confirmed)

    def test_unapproved_bonus_or_commission(self):
        msg_bonus = (
            "Rincian penggajian Anda di Greenfield Foods telah berubah. "
            "Bonus kuartalan Anda masih menunggu hasil akhir penilaian kinerja. "
            "Jumlah akhir dan tanggal pembayaran belum disetujui. Ref payroll EMP-0003."
        )
        parsed_bonus = parse_message(msg_bonus)
        self.assertEqual(parsed_bonus.action, "unapproved_credit")
        self.assertFalse(parsed_bonus.is_confirmed)

        msg_commission = (
            "Berikut informasi penggajian terbaru dari Greenfield Foods. "
            "Gaji pokok yang dikonfirmasi adalah IDR 38760000. "
            "Komisi dari transaksi yang masih berjalan belum disetujui. "
            "Transaksi yang masih berjalan tidak masuk pembayaran sampai komisinya dinyatakan diperoleh."
        )
        parsed_comm = parse_message(msg_commission)
        # Confirmed base salary is extracted, but pending commission is not credited
        self.assertEqual(parsed_comm.action, "salary_change")
        self.assertEqual(parsed_comm.new_amount, 38760000.0)
        self.assertEqual(parsed_comm.currency, "IDR")
        self.assertTrue(parsed_comm.is_confirmed)


if __name__ == "__main__":
    unittest.main()
