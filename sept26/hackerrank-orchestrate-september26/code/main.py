"""Main production pipeline and CLI entrypoint for Buy or Wait financial agent."""

import argparse
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import sys
import time
from typing import Dict, List, Sequence

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
from formatter import serialize_output_rows, validate_output_row
from models import DecisionOutput, EvaluationRequest, FinancialEvent, PaymentOption, UserProfile

REPO_ROOT = Path(__file__).resolve().parent.parent


def generate_usage_report(
    output_path: Path,
    num_requests: int,
    start_time: float,
    end_time: float,
) -> None:
    """Generate evaluation/usage_report.md required by competition rules."""
    elapsed_seconds = max(0.001, end_time - start_time)
    throughput = num_requests / elapsed_seconds if elapsed_seconds > 0 else 0.0

    report_content = f"""# Model and Token Usage Report

## Final Full-Dataset Run Summary

- **Timestamp:** {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}
- **Dataset Evaluated:** `dataset/requests.csv` ({num_requests} requests)
- **Execution Time:** {elapsed_seconds:.2f} seconds ({throughput:.1f} requests/sec)
- **Execution Mode:** Offline Rule-Based Mathematical Simulation Engine

## Model Providers and Architecture

- **Model Providers:** None (100% Offline Rule-Based Financial Reasoning)
- **Model Names:** Deterministic Cashflow and Multi-Tier Ranking Engine
- **Network / API Calls:** 0
- **External Dependencies:** Python Standard Library Only (100% Offline)

## Token Consumption and Cost Breakdown

| Metric | Value |
|---|---|
| Total Model Calls | 0 |
| Total Input Tokens | 0 |
| Total Output Tokens | 0 |
| Total Tokens | 0 |
| Average Tokens per Request | 0.0 |
| Estimated Total Cost (USD) | $0.00 |
| Estimated Cost per Request (USD) | $0.00 |

## Methodological Rationale

The "Buy or Wait?" challenge requires strict mathematical invariants:
1. Day-by-day cashflow balance tracking over a 90-day forward simulation window.
2. Hard conservation of minimum protected reserves across all projected essential expenses.
3. Strict lexicographical ranking across 6 domain criteria (on-time completion, minimal spending changes, lowest total financing cost, earliest start date, fewest payment transactions, and deterministic tie-breaking).

Employing an offline, deterministic evaluation engine eliminates non-deterministic hallucinations, prevents float drift, provides microsecond latency per request, and requires zero external API expenditure ($0.00 cost).
"""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, mode="w", encoding="utf-8") as f:
        f.write(report_content)


def run_pipeline(
    dataset_dir: Path,
    output_csv_path: Path,
    is_sample: bool = False,
) -> List[DecisionOutput]:
    """Execute end-to-end evaluation pipeline over requests and write output.csv."""
    t0 = time.time()
    print("=" * 80)
    print(" BUY OR WAIT? FINANCIAL DECISION AGENT")
    print(f" Dataset Directory: {dataset_dir}")
    print(f" Target Output:    {output_csv_path}")
    print(f" Mode:             {'Sample Benchmark' if is_sample else 'Full Production Evaluation'}")
    print("=" * 80)

    # 1. Ingest dataset tables
    print("[1/4] Ingesting financial profiles, events, rates, and contextual data...")
    profiles: Dict[str, UserProfile] = load_financial_profiles(dataset_dir / "financial_profiles.csv")
    rates = load_exchange_rates(dataset_dir / "exchange_rates.csv")
    events: List[FinancialEvent] = load_financial_events(dataset_dir / "financial_events.csv", profiles, rates)
    messages = load_messages(dataset_dir / "messages.csv")
    options: Dict[str, List[PaymentOption]] = load_payment_options(dataset_dir / "request_payment_options.csv")

    requests_file = dataset_dir / ("sample_requests.csv" if is_sample else "requests.csv")
    requests: List[EvaluationRequest] = load_evaluation_requests(requests_file)

    # 2. Multimodal contextual resolution
    print("[2/4] Resolving untrusted messages and contextual financial overrides...")
    updated_events, user_overrides = apply_message_overrides(events, messages)
    print(f"      Loaded {len(profiles)} profiles, {len(updated_events)} events, {len(requests)} evaluation requests.")

    # 3. Evaluate each request through the 4-layer decision pipeline
    print(f"[3/4] Evaluating {len(requests)} requests through 4-layer simulation and ranking engine...")
    decisions: List[DecisionOutput] = []
    status_counter: Counter[str] = Counter()
    method_counter: Counter[str] = Counter()

    for idx, req in enumerate(requests, start=1):
        prof = profiles[req.user_id]
        u_events = [e for e in updated_events if e.user_id == req.user_id]
        u_options = options.get(req.request_id, [])
        u_overrides = user_overrides.get(req.user_id, {})

        decision = evaluate_request(
            request=req,
            profile=prof,
            events=u_events,
            payment_options=u_options,
            user_overrides=u_overrides,
        )

        # Hard schema validation per competition invariants
        validate_output_row(decision, req)

        decisions.append(decision)
        status_counter[decision.affordability_status] += 1
        method_counter[decision.recommended_payment_method] += 1

        if idx % 50 == 0 or idx == len(requests):
            print(f"      Processed {idx:3d}/{len(requests)} requests...")

    # 4. Serialize to output.csv and generate usage report
    print(f"[4/4] Serializing {len(decisions)} decision records to {output_csv_path}...")
    serialize_output_rows(decisions, output_csv_path)

    t1 = time.time()
    usage_report_path = REPO_ROOT / "evaluation" / "usage_report.md"
    generate_usage_report(usage_report_path, len(requests), t0, t1)

    # Print summary statistics
    print("\n" + "=" * 80)
    print(" EXECUTION SUMMARY")
    print("=" * 80)
    print(f" Total Requests Processed: {len(decisions)}")
    print(f" Wall Clock Elapsed:       {t1 - t0:.2f} seconds")
    print(f" Output File:              {output_csv_path} (exists={output_csv_path.exists()})")
    print(f" Usage Report:             {usage_report_path} (exists={usage_report_path.exists()})")
    print("\n Affordability Status Breakdown:")
    for status, cnt in sorted(status_counter.items()):
        pct = (cnt / len(decisions)) * 100
        print(f"   {status:24s}: {cnt:3d} ({pct:5.1f}%)")
    print("\n Recommended Payment Method Breakdown:")
    for method, cnt in sorted(method_counter.items()):
        pct = (cnt / len(decisions)) * 100
        print(f"   {method:24s}: {cnt:3d} ({pct:5.1f}%)")
    print("=" * 80)

    return decisions


def main() -> None:
    """CLI entrypoint."""
    parser = argparse.ArgumentParser(description="Buy or Wait Financial Decision Agent Runner")
    parser.add_argument(
        "--dataset-dir",
        type=Path,
        default=REPO_ROOT / "dataset",
        help="Path to dataset directory containing CSV files",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=REPO_ROOT / "output.csv",
        help="Path to write output CSV file",
    )
    parser.add_argument(
        "--sample",
        action="store_true",
        help="Run against dataset/sample_requests.csv instead of requests.csv",
    )
    args = parser.parse_args()

    run_pipeline(
        dataset_dir=args.dataset_dir,
        output_csv_path=args.output,
        is_sample=args.sample,
    )


if __name__ == "__main__":
    main()
