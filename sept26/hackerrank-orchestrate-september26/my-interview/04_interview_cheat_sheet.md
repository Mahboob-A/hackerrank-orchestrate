# 04. AI Judge Interview Quick-Glance Cheat Sheet

> **KEEP THIS OPEN DURING YOUR LIVE AI INTERVIEW**  
> Use these bullets for instant, bulletproof answers when probed on numbers, file paths, rules, or architectural decisions.

---

## 1. Key Metrics & Numbers to Quote Confidently

| Metric | Exact Value | Context / Meaning |
|---|---|---|
| **Production Runtime** | **4.87 seconds** | All 250 requests evaluated (~51.3 reqs/sec). |
| **Model Calls & Tokens** | **0 calls, 0 tokens** | 100% offline, deterministic rule-based engine. |
| **Total Incurred Cost** | **`$0.00`** | Zero external API bills, zero network latency. |
| **Unit Test Coverage** | **51 / 51 passing (100%)** | Full TDD across all 4 layers in 0.99s. |
| **Benchmark Accuracy** | **88%** Payment Method<br>**88%** Spending Changes<br>**84%** Payment Plan<br>**84%** Amount Safe to Pay<br>**80%** Affordability Status | Verified dynamically on 25 ground-truth requests (`code/evaluation/benchmark.py`). |
| **Forecast Horizon** | **90 days** | Daily cashflow simulation step-by-step. |
| **Resolved Images** | **16 images** | Deterministic OCR mapping for missing event amounts. |
| **Parsed Messages** | **37 messages** | Indonesian & English payroll, deduction & cancel notices. |

---

## 2. File Directory Map (Which File Does What)

- **`code/models.py`**: Immutable domain dataclasses (`UserProfile`, `FinancialEvent`, `Request`, `PaymentOption`, `SimulationResult`).
- **`code/exceptions.py`**: Domain errors (`MissingAmountError`, `ExchangeRateNotFoundError`, `SchemaValidationError`).
- **`code/multimodal.py`**: Deterministic resolution of 16 missing image amounts + bilingual regex message parsing (`gaji`, `potongan`, etc.).
- **`code/data_loader.py`**: Ingestion of 7 CSVs, dated exchange rate conversion, message reconciliation with events.
- **`code/forecaster.py`**: 90-day cashflow simulation loop, immediate pending debit reservation, speculative credit exclusion, pre-payday cadence protection, spending change application.
- **`code/evaluator.py`**: Candidate plan generation (full, partial, installments, wait), `calculate_amount_safe_to_pay`, `find_earliest_date_for_full_payment`, 6-tier Pareto comparator.
- **`code/formatter.py`**: Output schema serializer, integer/float formatting conventions, strict 8-column invariant validation.
- **`code/main.py`**: CLI batch runner coordinating ingestion -> evaluation -> formatting into `output.csv`.
- **`code/evaluation/benchmark.py`**: Golden evaluation harness against `dataset/sample_requests.csv`.

---

## 3. The Golden Financial Invariants (Non-Negotiable Rules)

1. **Pending Debits:** Subtracted **immediately on `request_date`** (money already committed).
2. **Pending Credits:** **Ignored completely** until settled (cannot buy goods with speculative income).
3. **Confirmed Salary:** Credited **strictly on exact settlement cadence** (monthly/bi-weekly). One-off bonuses/gig spikes are not projected forward.
4. **Pre-Payday Cadence Protection:** Injects baseline necessity reserve (`groceries`, `transport`) in the gap before next payday if historical data has a blind spot.
5. **Minimum Balance Floor:** `balance(t) >= minimum_balance_to_keep` on **every single day** in the 90-day horizon.
6. **Amount Safe to Pay:** Unassisted headroom on `request_date`, bounded by `[0, requested_amount]`.
7. **Earliest Full Payment Date:** First date full amount can be paid unassisted (without spending changes) while preserving the 90-day reserve.
8. **Partial Payment Rules:**
   - Exactly 2 payments: `P_1 = amount_safe_to_pay` on `request_date`, `P_2 = remainder` on `earliest_date_for_full_payment`.
   - `P_1 + P_2 == requested_amount`.
   - Allowed only if `0 < P_1 < requested_amount` and `earliest_date_for_full_payment <= desired_completion_date`.
9. **Spending Changes Rules:**
   - Maximum 3 changes.
   - Only flexible recurring expenses (`is_recurring=True` and `is_flexible=True`). Never rent, utilities, or loan payments.
   - Allowed operations: `stop:<event_id>` or `reduce_to:<event_id>:<amount>`.
   - Never both stop and reduce on the same event.
10. **Installments Matching:** Must exactly match an available option in `request_payment_options.csv`.

---

## 4. The 6-Tier Pareto Comparator (Ranking Hierarchy)

When choosing the best payment recommendation, plans are ranked lexicographically:
1. **Tier 1 — On-Time:** Completes on or before `desired_completion_date` (1st priority).
2. **Tier 2 — Minimal Lifestyle Disruption:** 0 spending changes > 1 change > 2 changes > 3 changes.
3. **Tier 3 — Lowest Financial Cost:** Minimal total money paid (principal + interest/fees).
4. **Tier 4 — Earliest Start Date:** User gets the item as early as safe.
5. **Tier 5 — Lowest Transaction Friction:** Fewer discrete payments preferred.
6. **Tier 6 — Deterministic Preference Tie-Breaker:** `full_payment` > `installments` > `partial_payment` > `wait`.

---

## 5. 30-Second Elevator Pitch (Memorize This)

> *"We built an offline, deterministic 4-layer financial decision agent. Rather than using an LLM—which is prone to arithmetic hallucination, latency, and high cost—we simulate the user's forward cashflow day-by-day over 90 days in pure Python standard library. We protect essentials and the user's minimum reserve, reserve pending debits immediately, and rank all viable payment paths using a 6-tier Pareto comparator. It runs 250 requests in under 5 seconds with `$0.00` API cost and zero network dependencies."*
