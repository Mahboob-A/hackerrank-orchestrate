# System Architecture: Buy or Wait?

This document defines the official 4-layer system architecture for the "Buy or Wait?" AI financial decision engine. It establishes strict module boundaries, data contracts, and data flows between components.

```
+-------------------------------------------------------------------------+
| Layer 1: Ingestion & Normalization                                      |
| (data_loader.py, multimodal.py, models.py)                              |
+------------------------------------+------------------------------------+
                                     | Strongly Typed Domain Objects
                                     v
+-------------------------------------------------------------------------+
| Layer 2: 90-Day Cashflow Engine                                         |
| (forecaster.py)                                                         |
+------------------------------------+------------------------------------+
                                     | Daily Cash Balances B(t) & Headroom
                                     v
+-------------------------------------------------------------------------+
| Layer 3: Decision & Plan Evaluator                                      |
| (evaluator.py)                                                          |
+------------------------------------+------------------------------------+
                                     | Evaluated DecisionOutput & Plans
                                     v
+-------------------------------------------------------------------------+
| Layer 4: Compliance & Output Formatter                                  |
| (formatter.py, main.py)                                                 |
+-------------------------------------------------------------------------+
```

---

## 1. Layer 1: Ingestion and Normalization

Layer 1 ingests raw inputs from `dataset/`, standardizes currency denominations, extracts missing amounts, processes contextual messages, and constructs immutable, strongly typed domain objects.

### 1.1 `models.py` (Domain Data Models)
Defines strongly typed dataclasses representing core entities:

- `UserProfile`:
  - `user_id`: str
  - `home_currency`: str (e.g., INR, ZAR, IDR, USD, EUR)
  - `current_available_balance`: float
  - `minimum_balance_to_keep`: float
  - `financial_priorities`: tuple[str, ...]
  - `expense_categories_to_protect`: frozenset[str]
  - `expense_categories_user_is_willing_to_reduce`: frozenset[str]
  - `expense_categories_user_is_willing_to_stop`: frozenset[str]
  - `payment_methods_user_will_consider`: frozenset[str]
  - `max_installment_months`: int | None

- `FinancialEvent`:
  - `event_id`: str
  - `user_id`: str
  - `event_type`: str (income, expense, debt_payment, etc.)
  - `description`: str
  - `category`: str
  - `direction`: str ("debit" or "credit")
  - `amount`: float (normalized into user's home_currency)
  - `currency`: str
  - `event_date`: datetime.date
  - `settlement_date`: datetime.date
  - `status`: str (settled, pending, scheduled, unrealized, etc.)
  - `linked_event_id`: str | None
  - `flexibility`: str ("fixed" or "flexible")
  - `minimum_allowed_amount`: float | None

- `PaymentOption`:
  - `payment_option_id`: str
  - `request_id`: str
  - `option_name`: str
  - `provider`: str
  - `down_payment_amount`: float
  - `installment_amount`: float
  - `number_of_installments`: int
  - `interval_days`: int
  - `start_date_offset_days`: int
  - `total_amount_payable`: float
  - `financing_fee`: float
  - `apr_percent`: float | None

- `EvaluationRequest`:
  - `request_id`: str
  - `user_id`: str
  - `request_date`: datetime.date
  - `request_type`: str
  - `requested_amount`: float
  - `desired_completion_date`: datetime.date
  - `allows_partial_payment`: bool
  - `request_text`: str

- `CandidatePlan`:
  - `method`: str ("full_payment", "partial_payment", "installments", "wait", "not_recommended")
  - `schedule`: tuple[tuple[datetime.date, float], ...]
  - `spending_changes`: tuple[str, ...] (e.g., ("stop:event_476",))
  - `total_cost`: float
  - `first_payment_date`: datetime.date | None
  - `completion_date`: datetime.date | None
  - `num_payments`: int
  - `payment_option_id`: str | None
  - `is_safe`: bool

- `DecisionOutput`:
  - `request_id`: str
  - `amount_safe_to_pay`: float
  - `affordability_status`: str
  - `recommended_payment_method`: str
  - `payment_plan`: str
  - `earliest_date_for_full_payment`: str
  - `spending_changes_needed`: str
  - `decision_explanation`: str

### 1.2 `data_loader.py` (Dataset Ingestion and Currency Normalization)
- Ingests all tables from `dataset/*.csv`.
- Currency Conversion:
  - For events where `currency != user.home_currency`, looks up exchange rates in `exchange_rates.csv` matching `settlement_date` and the exact `from_currency -> to_currency` direction.
  - Converts amounts strictly: `amount_in_home = amount * rate`.
  - Missing exchange rates raise `ExchangeRateNotFoundError`.
- Missing Field Validation: Blank critical fields trigger explicit domain exceptions.

### 1.3 `multimodal.py` (Multimodal and Contextual Resolution)
- Missing Image Amounts:
  - Resolves blank amounts for the 16 events linked in `images.csv` (payslips, utility bills, invoices, receipts).
  - Uses deterministic lookup and OCR text extraction mapped by `image_id` to establish ground truth amounts.
  - Unresolvable missing amounts raise `MissingAmountError`.
- Message Parsing (English & Indonesian):
  - Deterministic regex extractors parse `messages.csv` for payroll updates, rent increases, invoice settlements, and account transfers.
  - Handles Indonesian templates:
    - Salary raises: `Gaji bulanan Anda naik menjadi <CURRENCY> <AMOUNT>. Perubahan ini berlaku mulai <DATE>.`
    - Confirmed base pay: `Gaji pokok yang dikonfirmasi adalah <CURRENCY> <AMOUNT>.`
    - Approved invoices: `pembayaran faktur sebesar <CURRENCY> <AMOUNT>. Penyelesaian diperkirakan pada <DATE>.`
  - Handles English templates:
    - Temporary pay adjustments, unpaid leave deductions, rescheduled payroll dates, lease increases, and intra-account transfers.
  - Updates associated `FinancialEvent` records accordingly before passing downstream.

---

## 2. Layer 2: 90-Day Cashflow Engine

Layer 2 models the user's financial reality over a continuous 90-day simulation window.

### 2.1 `forecaster.py` (Daily Cashflow Simulator)
- Forecast Horizon:
  - Starts at `T0 = request_date` and projects daily through `T0 + 90 days`.
- Cash Balance Tracking `B(t)`:
  - Initial state: `B(T0) = current_available_balance`.
  - For each day `t` in `[T0, T0 + 90]`:
    - Apply confirmed settled inflows (e.g., confirmed salary on settlement date).
    - Deduct recurring fixed and flexible expenses falling on day `t`.
    - Apply spending adjustments (modified/cancelled expenses).
    - Deduct scheduled payments for candidate purchase plans.
- Invariants and Safety Constraints:
  - Strict Balance Invariant: `B(t) >= minimum_balance_to_keep` for all `t in [T0, T0 + 90]`.
  - Pending Debits: Deducted immediately on `T0` to protect against pending card authorizations and unposted transfers.
  - Speculative Inflows: Disregarded completely. Pending credits, unapproved invoices, bonuses awaiting review, and unrealized investment gains contribute 0 to cash flow.
- Simulation API:
  - `simulate_cashflow(profile, events, payment_schedule, spending_changes) -> SimulationResult`:
    - Returns `is_safe`: bool
    - Returns `min_headroom`: float (minimum value of `B(t) - minimum_balance_to_keep`)
    - Returns `bottleneck_date`: datetime.date

---

## 3. Layer 3: Decision & Plan Evaluator

Layer 3 generates, evaluates, optimizes, and ranks payment options to select the optimal recommendation.

### 3.1 `evaluator.py` (Decision Engine and Optimizer)
1. Calculate `amount_safe_to_pay`:
   - Evaluates the maximum amount payable on `request_date` without spending changes.
   - Constrained by minimum headroom over the 90-day forecast: `amount_safe_to_pay = max(0.0, min(requested_amount, min_headroom_today))`.
   - Guaranteed bounded: `0 <= amount_safe_to_pay <= requested_amount`.

2. Find `earliest_date_for_full_payment`:
   - Scans candidate dates `d` from `request_date` to `request_date + 90`.
   - Tests if paying `requested_amount` as a single payment on date `d` satisfies `B(t) >= minimum_balance_to_keep` for all `t`.
   - First date satisfying this is recorded.
   - If `amount_safe_to_pay == requested_amount`, `earliest_date_for_full_payment = request_date`.
   - If no safe date exists in the 90-day window, returns empty string `""`.

3. Candidate Plan Generation:
   - `full_payment`:
     - Feasible if safe on `request_date` and user considers `full_payment`.
   - `installments`:
     - Evaluates each option in `request_payment_options.csv`.
     - Validates `number_of_installments` fits within `max_installment_months`.
     - Tests installment payment dates and amounts against `forecaster.py`.
   - `partial_payment`:
     - Permitted only if `allows_partial_payment == true` and user considers `partial_payment`.
     - Requires `0 < amount_safe_to_pay < requested_amount` and `earliest_date_for_full_payment <= desired_completion_date`.
     - Exactly two payments: `amount_safe_to_pay` on `request_date`, remainder on `earliest_date_for_full_payment`.
   - `wait`:
     - Candidate if full payment becomes safe on `earliest_date_for_full_payment` and user considers `full_payment`.
   - `not_recommended`:
     - Fallback when no plan maintains the minimum balance.

4. Spending Changes Optimizer:
   - Invoked when plans fail baseline safety.
   - Identifies non-protected recurring expenses marked `flexible` in categories the user allows to reduce or stop.
   - Generates candidate combinations (up to 3 actions):
     - `stop:<event_id>`: Eliminates recurring outflow.
     - `reduce_to:<event_id>:<amount>`: Reduces recurring outflow down to `minimum_allowed_amount`.
     - Stop and reduce on the same event are mutually exclusive.
   - Finds minimal spending reduction that renders a plan safe.

5. Six-Tier Tie-Breaker Ranking Hierarchy:
   - Tier 1: Complete full payment on or before `desired_completion_date`.
   - Tier 2: Require no spending changes (0 changes preferred over 1, 2, 3).
   - Tier 3: Minimize total amount paid (including financing fees).
   - Tier 4: Start payment earlier (earliest first payment date).
   - Tier 5: Use fewer payments (single payment < 2 payments < installments).
   - Tier 6: Lowest `payment_option_id` as final tie-breaker.

6. Grounded Explanation Generation:
   - Formats a concise, factual explanation articulating the financial facts, balance headroom, dates, and spending modifications.

---

## 4. Layer 4: Compliance & Output Formatter

Layer 4 validates all output invariants and formats the final prediction files for submission.

### 4.1 `formatter.py` (Validation and Serialization)
- Verifies exact output schema (8 columns in required order):
  `request_id,amount_safe_to_pay,affordability_status,recommended_payment_method,payment_plan,earliest_date_for_full_payment,spending_changes_needed,decision_explanation`
- Hard Invariant Checks:
  - `0 <= amount_safe_to_pay <= requested_amount`.
  - `affordability_status` in `{"affordable_now", "affordable_with_plan", "affordable_later", "not_affordable"}`.
  - `recommended_payment_method` in `{"full_payment", "partial_payment", "installments", "wait", "not_recommended"}`.
  - For `affordable_now`, `earliest_date_for_full_payment == request_date`.
  - Partial payment has exactly 2 payments totaling `requested_amount`.
  - Installment schedule matches a supplied option.
  - Max 3 spending changes, non-empty only when valid.
  - Serializes dates and amounts without floating point artifacts.

### 4.2 `main.py` (Execution Orchestrator)
- CLI entry point:
  - Invokes Layer 1 to load profiles, events, options, rates, messages, and images.
  - Loops over requests in `dataset/requests.csv`.
  - Invokes Layer 2 and Layer 3 to evaluate safe options and rank optimal recommendations.
  - Invokes Layer 4 to validate invariants and emit `output.csv` at repository root.
  - Emits token usage and execution metrics to `evaluation/usage_report.md`.
