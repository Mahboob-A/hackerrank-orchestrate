# Engineering Rulebook: Buy or Wait?

This document defines the non-negotiable engineering principles, operational standards, and technical contracts for building the "Buy or Wait?" financial decision engine for HackerRank Orchestrate.

---

## 1. Core Engineering Principles

### 1.1 Mandatory Session Logging
- Strict adherence to AGENTS.md logging specifications.
- Log file `log.txt` resides exclusively at the repository root next to `AGENTS.md`.
- `log.txt` must remain in `.gitignore` and never be committed to git.
- Session start entries must follow Section 5.1 of AGENTS.md.
- Every user turn must record a per-turn entry adhering to Section 5.2 of AGENTS.md.
- The `tool=` identifier must exactly match the runtime harness (`tool=Antigravity`).
- Never log secrets, API keys, tokens, or sensitive PII.

### 1.2 Absolutely ZERO Fake or Pampered Tests
- No mock tests designed solely to pass.
- No synthetic or fudged data created to turn assertions green.
- A failing test that exposes a real bug or incorrect domain assumption is 10x more valuable than a fake passing test.
- Every test must exercise genuine financial decision logic, safety checks, edge cases, and arithmetic invariants against real or representative scenario data.

### 1.3 Strict TDD Culture
- Red-Green-Refactor lifecycle is mandatory for all core modules.
- Phase 1 (Red): Write concrete tests specifying expected behavior and financial rules. Run them and verify that they fail legitimately.
- Phase 2 (Green): Write the minimal, cleanest code required to satisfy the failing tests.
- Phase 3 (Refactor): Clean up and optimize while preserving all passing assertions.
- Never write application code or modify `code/main.py` before test coverage exists.

### 1.4 KISS (Keep It Simple, Stupid)
- Zero bloated frameworks. No heavy third-party dependencies unless strictly required.
- Pure Python 3.12 standard library (`csv`, `datetime`, `math`, `re`, `json`, `dataclasses`, `pathlib`, `typing`, `unittest`).
- Evaluation runs in an isolated, offline environment. Everything must be deterministic, reproducible, and self-contained.
- Clear module boundaries with single responsibilities. No premature abstractions, convoluted meta-programming, or complex class hierarchies.

### 1.5 No Unicode Em-Dashes
- Do not use unicode em-dashes (U+2014) or en-dashes (U+2013) anywhere in documentation, code comments, strings, or logs.
- Use standard single hyphens (-) or double dashes (--) exclusively.

### 1.6 Honest, Concise Communication
- Direct, factual, engineering-first dialogue.
- Zero sycophantic filler, flattering statements, or speculative fluff.
- Always communicate what passed, what failed, why it failed, and what concrete technical decisions require resolution.

---

## 2. Challenge Contract and Domain Specifications

### 2.1 File and Path Contracts
- Input dataset directory: `dataset/`
  - `requests.csv`: 250 evaluation requests requiring predictions.
  - `sample_requests.csv`: 25 solved reference requests illustrating format and logic.
  - `financial_profiles.csv`: User profiles (currency, balances, priorities, preferences).
  - `financial_events.csv`: Transaction history, pending transactions, salary events.
  - `request_payment_options.csv`: Vendor financing options per request.
  - `exchange_rates.csv`: Fixed historical and settlement conversion rates.
  - `messages.csv`: Contextual messages modifying or clarifying transactions.
  - `images.csv` and `media/images/`: Images containing missing transaction amounts or payroll proofs.
- Output file: `output.csv` at repository root.
- Token and usage report: `evaluation/usage_report.md`.

### 2.2 Output Schema Contract
The output file `output.csv` must contain exactly these columns in this exact sequence:
1. `request_id`
2. `amount_safe_to_pay`
3. `affordability_status`
4. `recommended_payment_method`
5. `payment_plan`
6. `earliest_date_for_full_payment`
7. `spending_changes_needed`
8. `decision_explanation`

### 2.3 Value Domain Invariants
- `0 <= amount_safe_to_pay <= requested_amount` must hold for every request.
- `affordability_status` allowed values:
  - `affordable_now`
  - `affordable_with_plan`
  - `affordable_later`
  - `not_affordable`
- `recommended_payment_method` allowed values:
  - `full_payment`
  - `partial_payment`
  - `installments`
  - `wait`
  - `not_recommended`
- `payment_plan`:
  - Format: `<YYYY-MM-DD>:<amount>|<YYYY-MM-DD>:<amount>` or `none`.
  - For `partial_payment`: Exactly two payments adding up to `requested_amount`. First payment is `amount_safe_to_pay` on `request_date`, second payment is `requested_amount - amount_safe_to_pay` on `earliest_date_for_full_payment`. Both must complete on or before `desired_completion_date`.
  - For `installments`: Must strictly match an offer from `request_payment_options.csv`.
- `earliest_date_for_full_payment`:
  - For `affordable_now`: Must equal `request_date`.
  - If full payment never becomes safe within the 90-day forecast: empty string.
  - Measures underlying financial capacity independently of user payment preferences.
- `spending_changes_needed`:
  - Up to three changes separated by `|`, or `none`.
  - Format: `stop:<event_id>` or `reduce_to:<event_id>:<new_amount>`.
  - Only flexible, recurring, non-protected expenses permitted in user profile may be modified.
  - Stop and reduce on the same event are mutually exclusive.

### 2.4 Financial Decision Rules
- 90-Day Cash Flow Projection: Starting from `current_available_balance`, forecast daily balances for 90 days.
- Safety Threshold: Projected balance must never drop below `minimum_balance_to_keep` after essential spending and planned payments.
- Debits vs. Credits:
  - Reserve pending debits immediately.
  - Disregard pending credits, bonuses, commissions, refunds, or investment gains until settled.
  - Confirmed salary is counted on its settlement date.
- Multimodal Resolution:
  - Extract missing amounts in `financial_events.csv` from corresponding images in `images.csv`.
  - Apply message modifications (amendments, cancellations, delays) using explicit precedence rules.
- Plan Ranking Hierarchy:
  1. Complete by `desired_completion_date`.
  2. Require no spending changes.
  3. Minimize total amount paid.
  4. Start payment earlier.
  5. Use fewer payments.
  6. Final tie-breaker: lowest `payment_option_id`.
