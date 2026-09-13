# Model and Token Usage Report

## Final Full-Dataset Run Summary

- **Timestamp:** 2026-09-13T11:26:02Z
- **Dataset Evaluated:** `dataset/requests.csv` (250 requests)
- **Execution Time:** 4.87 seconds (51.3 requests/sec)
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
