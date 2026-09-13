"""Golden Benchmark Harness for Buy or Wait.

Evaluates the end-to-end decision pipeline against the 25 ground-truth requests
in dataset/sample_requests.csv and displays a detailed accuracy scorecard.
"""

import csv
import math
from pathlib import Path
import sys
from typing import Any, Dict, List, Tuple

# Add code directory to path
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
CODE_DIR = REPO_ROOT / "code"
if str(CODE_DIR) not in sys.path:
    sys.path.insert(0, str(CODE_DIR))

from data_loader import (
    apply_message_overrides,
    load_evaluation_requests,
    load_exchange_rates,
    load_financial_events,
    load_financial_profiles,
    load_messages,
    load_payment_options,
)
from evaluator import evaluate_request
from formatter import format_amount, validate_output_row
from models import DecisionOutput, EvaluationRequest


def run_benchmark() -> Tuple[int, int, Dict[str, float]]:
    """Run benchmark against dataset/sample_requests.csv and print scorecard."""
    data_dir = REPO_ROOT / "dataset"
    sample_file = data_dir / "sample_requests.csv"

    print("=" * 80)
    print(" BUY OR WAIT? GOLDEN BENCHMARK HARNESS")
    print(f" Dataset source: {sample_file.relative_to(REPO_ROOT)}")
    print("=" * 80)

    # 1. Ingest datasets
    print("[1/3] Loading dataset tables...")
    profiles = load_financial_profiles(data_dir / "financial_profiles.csv")
    rates = load_exchange_rates(data_dir / "exchange_rates.csv")
    events = load_financial_events(data_dir / "financial_events.csv", profiles, rates)
    messages = load_messages(data_dir / "messages.csv")
    options = load_payment_options(data_dir / "request_payment_options.csv")
    sample_requests = load_evaluation_requests(sample_file)

    # Apply multimodal message adjustments
    updated_events, user_overrides = apply_message_overrides(events, messages)
    print(f"      Loaded {len(profiles)} profiles, {len(updated_events)} events, {len(sample_requests)} sample requests.")

    # Load raw expected rows from sample_requests.csv
    with open(sample_file, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        expected_rows = list(reader)

    print("[2/3] Evaluating sample requests against ground truth...")
    total_samples = len(sample_requests)
    counts = {
        "status": 0,
        "method": 0,
        "safe_amt": 0,
        "safe_rel_amt": 0,
        "plan": 0,
        "earliest": 0,
        "changes": 0,
        "all_match": 0,
    }

    results: List[Dict[str, Any]] = []

    for req, exp in zip(sample_requests, expected_rows):
        profile = profiles[req.user_id]
        u_events = [e for e in updated_events if e.user_id == req.user_id]
        u_options = options.get(req.request_id, [])
        u_overrides = user_overrides.get(req.user_id, {})

        pred = evaluate_request(
            request=req,
            profile=profile,
            events=u_events,
            payment_options=u_options,
            user_overrides=u_overrides,
        )

        # Validate invariants with Layer 4 validator
        validate_output_row(pred, req)

        exp_safe = float(exp["amount_safe_to_pay"])
        safe_match = abs(pred.amount_safe_to_pay - exp_safe) <= 0.05
        safe_rel_match = abs(pred.amount_safe_to_pay - exp_safe) <= max(1.0, 0.05 * req.requested_amount)
        status_match = (pred.affordability_status == exp["affordability_status"])
        method_match = (pred.recommended_payment_method == exp["recommended_payment_method"])
        plan_match = (pred.payment_plan == exp["payment_plan"])
        earliest_match = (pred.earliest_date_for_full_payment == exp["earliest_date_for_full_payment"])
        changes_match = (pred.spending_changes_needed == exp["spending_changes_needed"])

        all_match = (
            safe_match and status_match and method_match and plan_match and earliest_match and changes_match
        )

        if status_match:
            counts["status"] += 1
        if method_match:
            counts["method"] += 1
        if safe_match:
            counts["safe_amt"] += 1
        if safe_rel_match:
            counts["safe_rel_amt"] += 1
        if plan_match:
            counts["plan"] += 1
        if earliest_match:
            counts["earliest"] += 1
        if changes_match:
            counts["changes"] += 1
        if all_match:
            counts["all_match"] += 1

        results.append({
            "request_id": req.request_id,
            "user_id": req.user_id,
            "req_amt": req.requested_amount,
            "pred_safe": pred.amount_safe_to_pay,
            "exp_safe": exp_safe,
            "safe_match": safe_match,
            "pred_status": pred.affordability_status,
            "exp_status": exp["affordability_status"],
            "status_match": status_match,
            "pred_method": pred.recommended_payment_method,
            "exp_method": exp["recommended_payment_method"],
            "method_match": method_match,
            "pred_plan": pred.payment_plan,
            "exp_plan": exp["payment_plan"],
            "plan_match": plan_match,
            "pred_earliest": pred.earliest_date_for_full_payment,
            "exp_earliest": exp["earliest_date_for_full_payment"],
            "earliest_match": earliest_match,
            "pred_changes": pred.spending_changes_needed,
            "exp_changes": exp["spending_changes_needed"],
            "changes_match": changes_match,
            "all_match": all_match,
        })

    # 3. Print clean formatted scorecard
    print("\n[3/3] BENCHMARK SCORECARD:")
    print("-" * 110)
    header = f"{'Req ID':<11} | {'Status':<7} | {'Method':<7} | {'SafeAmt':<7} | {'Plan':<7} | {'Earliest':<8} | {'Changes':<7} | {'Overall':<7}"
    print(header)
    print("-" * 110)

    for r in results:
        s_ok = "PASS" if r["status_match"] else "FAIL"
        m_ok = "PASS" if r["method_match"] else "FAIL"
        a_ok = "PASS" if r["safe_match"] else "FAIL"
        p_ok = "PASS" if r["plan_match"] else "FAIL"
        e_ok = "PASS" if r["earliest_match"] else "FAIL"
        c_ok = "PASS" if r["changes_match"] else "FAIL"
        all_ok = "PASS" if r["all_match"] else "FAIL"

        print(
            f"{r['request_id']:<11} | {s_ok:<7} | {m_ok:<7} | {a_ok:<7} | {p_ok:<7} | {e_ok:<8} | {c_ok:<7} | {all_ok:<7}"
        )

    print("-" * 110)
    print("\nFIELD-LEVEL ACCURACY SUMMARY:")
    print(f"  affordability_status:           {counts['status']:2d} / {total_samples} ({counts['status']/total_samples*100:5.1f}%)")
    print(f"  recommended_payment_method:     {counts['method']:2d} / {total_samples} ({counts['method']/total_samples*100:5.1f}%)")
    print(f"  amount_safe_to_pay (exact <=0.05):{counts['safe_amt']:2d} / {total_samples} ({counts['safe_amt']/total_samples*100:5.1f}%)")
    print(f"  amount_safe_to_pay (rel <= 5%):  {counts['safe_rel_amt']:2d} / {total_samples} ({counts['safe_rel_amt']/total_samples*100:5.1f}%)")
    print(f"  payment_plan:                   {counts['plan']:2d} / {total_samples} ({counts['plan']/total_samples*100:5.1f}%)")
    print(f"  earliest_date_for_full_payment: {counts['earliest']:2d} / {total_samples} ({counts['earliest']/total_samples*100:5.1f}%)")
    print(f"  spending_changes_needed:        {counts['changes']:2d} / {total_samples} ({counts['changes']/total_samples*100:5.1f}%)")
    print("-" * 55)
    print(f"  PERFECT MATCHES (ALL FIELDS):   {counts['all_match']:2d} / {total_samples} ({counts['all_match']/total_samples*100:5.1f}%)")
    print("=" * 80)

    # Print target requests spotlight
    target_ids = {"request_04", "request_06", "request_11", "request_21"}
    print("\nTARGET REQUESTS SPOTLIGHT (request_04, request_06, request_11, request_21):")
    print("-" * 110)
    for r in results:
        if r["request_id"] in target_ids:
            all_ok = "PASS" if r["all_match"] else "FAIL"
            print(f"--- {r['request_id']} ({r['user_id']}) [{all_ok}] ---")
            print(f"  affordability_status:           pred='{r['pred_status']}' | exp='{r['exp_status']}'")
            print(f"  recommended_payment_method:     pred='{r['pred_method']}' | exp='{r['exp_method']}'")
            print(f"  amount_safe_to_pay:             pred={r['pred_safe']} | exp={r['exp_safe']}")
            print(f"  payment_plan:                   pred='{r['pred_plan']}' | exp='{r['exp_plan']}'")
            print(f"  earliest_date_for_full_payment: pred='{r['pred_earliest']}' | exp='{r['exp_earliest']}'")
            print(f"  spending_changes_needed:        pred='{r['pred_changes']}' | exp='{r['exp_changes']}'")

    # Print mismatch diagnostics if any
    mismatches = [r for r in results if not r["all_match"]]
    if mismatches:
        print(f"\nDIAGNOSTIC DETAILS FOR ALL {len(mismatches)} MISMATCHED REQUESTS:")
        for r in mismatches:
            print(f"\n--- {r['request_id']} ({r['user_id']}) ---")
            if not r["status_match"]:
                print(f"  Status:   pred='{r['pred_status']}' vs exp='{r['exp_status']}'")
            if not r["method_match"]:
                print(f"  Method:   pred='{r['pred_method']}' vs exp='{r['exp_method']}'")
            if not r["safe_match"]:
                print(f"  SafeAmt:  pred={r['pred_safe']} vs exp={r['exp_safe']}")
            if not r["plan_match"]:
                print(f"  Plan:     pred='{r['pred_plan']}' vs exp='{r['exp_plan']}'")
            if not r["earliest_match"]:
                print(f"  Earliest: pred='{r['pred_earliest']}' vs exp='{r['exp_earliest']}'")
            if not r["changes_match"]:
                print(f"  Changes:  pred='{r['pred_changes']}' vs exp='{r['exp_changes']}'")

    accuracies = {k: counts[k] / total_samples * 100.0 for k in counts}
    return (counts["all_match"], total_samples, accuracies)


if __name__ == "__main__":
    run_benchmark()
