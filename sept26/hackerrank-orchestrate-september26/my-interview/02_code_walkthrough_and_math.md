# 02. Codebase Walkthrough, File Ownership & Algorithmic Math

## Executive Overview
When the HackerRank AI Judge asks you:
> *"Take any file in your codebase and explain what it does, how it works internally, and what invariants it guarantees."*

You need to demonstrate that you know every single line of code and the exact formulas driving the engine. This guide breaks down each file, its key functions, and the core mathematical formulas.

---

## 1. File-by-File Ownership & Responsibilities

### `code/models.py` (Data Contracts)
- **Role:** The foundational type system. Defines strongly typed, immutable dataclasses representing the financial domain.
- **Key Dataclasses:**
  - `UserProfile`: `user_id`, `current_balance`, `minimum_balance_to_keep`, `currency`, `risk_tolerance`, `priorities`, `payment_preference`.
  - `FinancialEvent`: `event_id`, `user_id`, `date`, `amount`, `category`, `is_recurring`, `frequency`, `status` (`confirmed`, `pending`), `is_flexible`.
  - `Request`: `request_id`, `user_id`, `requested_amount`, `request_date`, `desired_completion_date`, `is_partial_allowed`.
  - `PaymentOption`: `option_id`, `request_id`, `method` (`installments`, `full_payment`), `num_installments`, `frequency`, `installment_amount`, `total_amount`.
  - `SimulationResult`: `is_safe`, `min_balance_reached`, `bottleneck_date`, `daily_balances`.
  - `EvaluationResult`: Holds the 8 final output fields.
- **Invariant:** Zero mutable global state. All domain entities are strongly typed; no naked dictionaries are passed across layers.

---

### `code/exceptions.py` (Domain Error Hierarchy)
- **Role:** Enforces our "Fail Loudly, Never Mask Errors" development principle.
- **Key Classes:**
  - `MissingAmountError`: Raised when an event has a blank amount that cannot be resolved via linked images. Never defaults to 0.
  - `ExchangeRateNotFoundError`: Raised when a currency pair is missing on a transaction date. Never guesses rates.
  - `SchemaValidationError`: Raised when output columns or enums violate challenge constraints.
  - `UnresolvableEventError`: Raised when an event conflict cannot be reconciled.

---

### `code/multimodal.py` (Perception & Offline NLP)
- **Role:** Handles unstructured inputs (images and multilingual messages) deterministically.
- **Key Functions:**
  - `resolve_image_amount(image_id: str) -> float`: Deterministically maps image IDs to extracted monetary values for the 16 missing event amounts.
  - `parse_message(content: str) -> dict`: Bilingual regex extractor. Handles Indonesian syntax (`gaji dibayarkan`, `potongan`, `pengurangan`) and English syntax (`bonus credited`, `salary settled`, `subscription cancelled`). Extracts amount, event type, and date overrides.

---

### `code/data_loader.py` (Ingestion & Normalization)
- **Role:** Ingests the 7 CSV files from `dataset/`, resolves image amounts, normalizes foreign currencies, and applies message overrides.
- **Key Functions:**
  - `load_profiles()`, `load_events()`, `load_requests()`, `load_options()`, `load_rates()`, `load_messages()`: Standard library CSV ingestion.
  - `convert_currency(amount, from_curr, to_curr, date, rates) -> float`: Uses exact date-matched exchange rates to convert all transactions to the user's `home_currency`.
  - Message Reconciliation: If a confirmed message states a salary was settled on an earlier date or an event was cancelled, `data_loader.py` modifies the corresponding `FinancialEvent` before simulation begins.

---

### `code/forecaster.py` (Core Financial Simulation Engine)
- **Role:** Simulates the user's daily account balance across a 90-day forward horizon starting from `request_date`.
- **Key Functions:**
  - `simulate_cashflow(user, events, candidate_payments, spending_changes, horizon_days=90) -> SimulationResult`:
    - **Step 1:** Reserves all `pending` debits immediately on `request_date` (money already committed).
    - **Step 2:** Excludes speculative `pending` credits (money not in the bank).
    - **Step 3:** Identifies recurring salary cadence (excluding one-off bonuses, gig income, arrears) and projects future salary settlements.
    - **Step 4 (Pre-Payday Cadence Injection):** If `request_date` falls in the interval before the next salary settlement, injects a baseline cadence for necessities (`groceries`, `transport`) if none existed in that window, preventing an artificially inflated initial safe balance.
    - **Step 5 (Spending Adjustments):** Applies `stop` (zeros the expense) or `reduce_to` (caps the expense) to flexible recurring events.
    - **Step 6 (Daily Trajectory):** Steps through day `t = 0 ... 90`. At each day:
      ```text
      balance(t) = balance(t-1) + inflows(t) - outflows(t) - payments(t)
      ```
      Checks the safety condition:
      ```text
      balance(t) >= user.minimum_balance_to_keep
      ```
    - Returns `SimulationResult` with boolean `is_safe`, `min_balance_reached`, and `bottleneck_date`.

---

### `code/evaluator.py` (Decision Engine & Multi-Tier Optimizer)
- **Role:** Generates all feasible payment configurations and ranks them using our 6-tier Pareto comparator.
- **Key Functions:**
  - `calculate_amount_safe_to_pay(user, events, request_date, requested_amount) -> float`:
    - Computes the unassisted baseline cashflow over 90 days.
    - Finds the minimum headroom buffer:
      ```text
      headroom = min(balance(t) - user.minimum_balance_to_keep)  for t in [0, 90]
      ```
    - Returns:
      ```text
      amount_safe_to_pay = max(0.0, min(requested_amount, headroom))
      ```
  - `find_earliest_date_for_full_payment(user, events, request, skip_request_date=False) -> Optional[str]`:
    - Scans candidate dates: `request_date`, upcoming paydays, day after paydays, and scheduled credit dates up to 90 days out.
    - Tests paying `requested_amount` as a single lump sum on date `D`.
    - Returns the earliest date `D` that maintains the 90-day minimum balance invariant without requiring spending changes.
  - `evaluate_request(request, user, events, options) -> EvaluationResult`:
    - Tests Strategy 1: Full Payment on `request_date`.
    - Tests Strategy 2: Partial Payment (Pay `amount_safe_to_pay` on `request_date`, pay remainder on `earliest_date_for_full_payment` if within `desired_completion_date`).
    - Tests Strategy 3: Installment Options from `request_payment_options.csv`.
    - Tests Strategy 4: Wait / Later Payment on `earliest_date_for_full_payment`.
    - Tests Spending Changes: Permutes stopping or reducing up to 3 flexible expenses if baseline options are unaffordable.
    - Sorts all valid candidates using the 6-tier comparator and returns the #1 optimal result.

---

### `code/formatter.py` (Output Schema Compliance)
- **Role:** Converts the internal `EvaluationResult` into the exact 8-column CSV format expected by HackerRank.
- **Key Logic:**
  - Formats numbers cleanly: integer amounts (e.g., `5000`) formatted without decimal points, fractional amounts (e.g., `12.5`) formatted to 2 decimals.
  - Formats payment plan string: `YYYY-MM-DD:amount|YYYY-MM-DD:amount` or `none`.
  - Formats spending changes: `stop:event_id|reduce_to:event_id:amount` or `none`.
  - Validates schema bounds:
    - `0 <= amount_safe_to_pay <= requested_amount`
    - `earliest_date_for_full_payment == request_date` if `affordable_now`
    - Partial payment adds up to exactly `requested_amount`
    - No non-flexible event modified

---

## 2. Core Algorithmic Mathematics

Be ready to explain these formulas or write them on a virtual whiteboard:

### 1. Bottleneck Reserve Headroom
For a given candidate payment schedule `P`, the balance on day `t` is:
```text
balance(t) = balance_0 + SUM_{k=0}^{t} ( inflow(k) - outflow(k) - P(k) )
```
The minimum reserve headroom buffer over the 90-day horizon is:
```text
headroom = MIN_{t in [0, 90]} ( balance(t) - minimum_balance_to_keep )
```
A payment schedule is **safe** if and only if:
```text
headroom >= 0
```

---

### 2. Unassisted Safe Amount on Request Date
```text
amount_safe_to_pay = max(0.0, min(requested_amount, baseline_headroom))
```
Where `baseline_headroom` is computed with `P(t) = 0` for all `t` (no candidate purchases applied).

---

### 3. Strict 2-Payment Partial Plan
Partial payment is allowed if and only if:
1. `is_partial_allowed == True` on the request.
2. `0 < amount_safe_to_pay < requested_amount`.
3. `earliest_date_for_full_payment <= desired_completion_date`.

The payment plan is constructed as:
```text
Payment_1 = (request_date, amount_safe_to_pay)
Payment_2 = (earliest_date_for_full_payment, requested_amount - amount_safe_to_pay)
```
Sum invariant:
```text
Payment_1 + Payment_2 == requested_amount
```

---

### 4. The 6-Tier Pareto Ranking Comparator (Python Implementation)
In `code/evaluator.py`, candidate plans are ranked by this composite key:

```python
def rank_key(candidate):
    # Tier 1: On-Time Completion (0 = On-time, 1 = Late)
    on_time = 0 if candidate.completion_date <= desired_completion_date else 1
    
    # Tier 2: Number of Spending Changes (0, 1, 2, or 3)
    num_changes = len(candidate.spending_changes)
    
    # Tier 3: Total Cost to User (Principal + Interest/Fees)
    total_cost = candidate.total_amount_paid
    
    # Tier 4: Start Date (Days from request_date)
    start_delay = (candidate.start_date - request_date).days
    
    # Tier 5: Transaction Friction (Number of payments)
    num_payments = len(candidate.payment_schedule)
    
    # Tier 6: Method Preference Tie-Breaker
    method_order = {"full_payment": 0, "installments": 1, "partial_payment": 2, "wait": 3}
    method_priority = method_order.get(candidate.method, 4)
    
    return (on_time, num_changes, total_cost, start_delay, num_payments, method_priority)
```
*Why this matters:* Python's `sort()` evaluates tuples lexicographically. Any plan that finishes on time (Tier 1 = 0) strictly defeats any late plan (Tier 1 = 1), regardless of cost. Within on-time plans, a plan requiring 0 spending changes strictly defeats one requiring spending cuts.
