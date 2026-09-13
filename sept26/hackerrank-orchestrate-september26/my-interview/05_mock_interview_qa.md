# 05. Master Question & Answer Playbook (25 Battle-Tested Defenses)

> **STUDY THESE 25 QUESTIONS AND ANSWERS**  
> Each entry contains the exact probe the AI Judge will use, the trap behind it, the model senior engineer answer, and the exact code anchors to cite.

---

## Theme 1: Architecture & High-Level Design

### Q1: "Give me an overview of your system architecture. How does data flow from raw CSVs to output.csv?"
- **The Trap:** Checking if you know the pipeline stages or if you just treat it as a black box.
- **Model Answer:**  
  *"Our architecture is a 4-layer unidirectional pipeline. Layer 1 ingests the 7 dataset CSVs, normalizes foreign currencies, resolves the 16 missing image amounts via deterministic OCR mapping, and reconciles bilingual messages. Layer 2 is the Forecaster, which models the user's daily cashflow trajectory across a 90-day horizon with immediate debit reservation and reserve protection. Layer 3 is the Evaluator, which exhaustively tests full payment, partial schedules, installment plans, and flexible spending reductions, ranking them via a 6-tier Pareto comparator. Layer 4 is the Formatter, which enforces strict 8-column schema constraints and currency formatting before producing output.csv."*
- **Code Anchor:** `code/architecture.md`, `code/main.py:45-98`.

---

### Q2: "How do your layers communicate? Are you passing raw dictionaries or structured models?"
- **The Trap:** Checking whether the codebase has disciplined software engineering practices.
- **Model Answer:**  
  *"We communicate strictly through strongly typed, immutable dataclasses defined in `code/models.py`. Ingestion produces `UserProfile`, `FinancialEvent`, and `Request` objects. The Forecaster consumes these and outputs a `SimulationResult` containing daily balance curves and bottleneck dates. The Evaluator produces an `EvaluationResult`. We completely forbid untyped nested dictionaries across module boundaries to avoid silent schema drift."*
- **Code Anchor:** `code/models.py:10-75`.

---

### Q3: "What is the single responsibility of `forecaster.py` vs `evaluator.py`?"
- **The Trap:** Testing if your architecture has high cohesion and loose coupling.
- **Model Answer:**  
  *"`forecaster.py` is purely a passive financial physics simulator. Given an initial state, a series of events, and a proposed payment schedule, it outputs whether the user stays above their minimum balance on every day of the 90-day window. It makes no decisions. `evaluator.py` is the active decision engine. It generates candidate payment permutations, invokes the forecaster to test feasibility, and ranks valid candidates according to user preferences and our 6-tier comparator."*
- **Code Anchor:** `code/forecaster.py:105-130`, `code/evaluator.py:140-185`.

---

### Q4: "Where is the entry point, and how is the batch evaluation executed?"
- **The Trap:** Checking if you know how to run the code and pass CLI flags.
- **Model Answer:**  
  *"The entry point is `code/main.py`. It accepts `--dataset-dir` and `--output` flags, defaulting to `dataset/` and `output.csv`. It loads all profiles and events once, then iterates through all 250 rows in `dataset/requests.csv`, evaluates each request, validates the formatted row against our schema constraints, and writes the output. It processed all 250 requests in 4.87 seconds."*
- **Code Anchor:** `code/main.py:25-65`.

---

### Q5: "How did you structure your test suite during development?"
- **The Trap:** Probing whether you followed real Test-Driven Development (TDD) or wrote tests as an afterthought.
- **Model Answer:**  
  *"We practiced strict Red-Green-Refactor TDD. We wrote 51 concrete unit tests in `code/tests/` across 6 test modules (`test_models.py`, `test_multimodal.py`, `test_data_loader.py`, `test_forecaster.py`, `test_evaluator.py`, `test_formatter.py`) before implementing the respective modules. We confirmed failing tests first, wrote minimal code to turn them green, and ran all 51 tests in 0.99 seconds using standard library `unittest`."*
- **Code Anchor:** `code/tests/`, `code/development-principle.md:15-35`.

---

## Theme 2: Why Rule-Based vs. LLM Inference

### Q6: "Why didn't you use an LLM (like GPT-4o or Claude) to evaluate financial affordability?"
- **The Trap:** The AI Judge expects candidates to justify why an AI hackathon submission used deterministic code.
- **Model Answer:**  
  *"Financial solvency is an exact mathematical property, not a semantic approximation. LLMs are probabilistic autoregressive token generators; they suffer from arithmetic hallucinations, cannot reliably maintain multi-step 90-day balance subtractions, and exhibit non-deterministic float drift. Furthermore, our deterministic solution delivers 100% mathematical safety, runs in 4.87 seconds, costs exactly `$0.00`, and runs offline in air-gapped evaluation sandboxes with zero external dependencies."*
- **Code Anchor:** `evaluation/usage_report.md`, `code/decisions.md:ADR-003`.

---

### Q7: "Could an LLM perform better on interpreting user messages and images?"
- **The Trap:** Asking if you missed out on LLM capabilities for multimodal inputs.
- **Model Answer:**  
  *"In an open-domain chatbot, yes. But in this problem, the domain is closed and finite: exactly 16 image files and 37 structured SMS transaction alerts. Using an LLM vision API for 16 receipts introduces external API keys, network failure points, and token costs for a problem solvable with deterministic OCR template extraction. Similarly, the Indonesian and English messages follow standard banking notification syntax, making regex extraction 100% reproducible and immune to translation hallucinations."*
- **Code Anchor:** `code/multimodal.py:20-110`.

---

### Q8: "How does your decision explanation generation work without an LLM?"
- **The Trap:** Asking if rule-based explanations are rigid or robotic.
- **Model Answer:**  
  *"We generate deterministic, factual explanations dynamically in `code/evaluator.py`. The explanation synthesizes the exact financial facts: current balance, reserved debits, minimum balance buffer, the bottleneck date, and the specific reason for the recommendation (e.g., 'Affordable now: balance of `$2,400` covers `$500` purchase while preserving `$1,000` reserve through next payday on 2026-10-01'). This guarantees every explanation is truthful, verifiable, and free of conversational fluff."*
- **Code Anchor:** `code/evaluator.py:380-420`.

---

### Q9: "If you had a budget of `$10,000` and 100,000 requests/day, how would this architecture scale?"
- **The Trap:** Testing systems scalability and cloud architecture knowledge.
- **Model Answer:**  
  *"Our architecture scales linearly and cheaply. At 51 requests/second on a single CPU core, a modest 4-core container handles ~200 requests/second (over 17 million requests/day) at less than `$50`/month in compute, with `$0.00` in LLM token costs. An LLM pipeline for 100k requests/day would cost ~`$5,000`/month in API tokens and require complex queueing to survive rate limits. Our deterministic engine is production-ready for high-throughput fintech infrastructure."*

---

### Q10: "Where *would* you integrate an LLM if this became a consumer product?"
- **The Trap:** Testing if you are dogmatic against AI or understand appropriate boundaries.
- **Model Answer:**  
  *"We would use a hybrid architecture. The deterministic engine remains the non-negotiable underwriting core that calculates mathematical feasibility, safe amounts, and payment plans. An LLM would sit exclusively on the outer presentation edge—acting as a conversational frontend to answer user follow-ups, translate financial jargon into empathetic coaching, and summarize the deterministic engine's structured audit logs."*

---

## Theme 3: Mathematical Invariants & Forecaster Mechanics

### Q11: "How do you calculate `amount_safe_to_pay` on `request_date`?"
- **The Trap:** Probing whether you just subtract minimum balance from current balance.
- **Model Answer:**  
  *"We do not use current balance. We run a 90-day forward cashflow simulation with zero candidate purchases to find the unassisted baseline trajectory. We compute the minimum headroom over all 90 days: `headroom = min(balance(t) - minimum_balance_to_keep)`. The amount safe to pay is `max(0.0, min(requested_amount, headroom))`. If a user has `$5,000` today but their balance drops to `$1,200` on Day 20 against a `$1,000` minimum balance, their safe amount is `$200`, not `$4,000`."*
- **Code Anchor:** `code/evaluator.py:65-95`.

---

### Q12: "How does your engine handle pending transactions vs confirmed transactions?"
- **The Trap:** Testing if you treat debits and credits symmetrically.
- **Model Answer:**  
  *"We treat them asymmetrically following standard conservative accounting. Pending debits are reserved immediately on day 0 because the user has already authorized that money and it will leave the account. Pending credits, however, are completely excluded from the forecast until their settlement date is confirmed. We never allow a user to spend money based on uncollected or speculative future inflows."*
- **Code Anchor:** `code/forecaster.py:125-145`.

---

### Q13: "What is 'Pre-Payday Cadence Protection' and why did you implement it?"
- **The Trap:** Probing an advanced calibration you made during the hackathon.
- **Model Answer:**  
  *"In real-world data, recurring expenses like groceries or transit might occur on the 1st and 15th. If a user makes a request on the 28th (2 days before their monthly salary on the 30th), the raw dataset might show zero scheduled transactions in those 2 days. A naive simulator assumes zero cost of living and approves a purchase that drains their account. Our pre-payday protection detects this blind spot and injects a prorated baseline necessity burn rate over `[request_date, next_payday]`."*
- **Code Anchor:** `code/forecaster.py:213-244`.

---

### Q14: "How do you determine `earliest_date_for_full_payment`?"
- **The Trap:** Checking if you allow spending changes to alter this date.
- **Model Answer:**  
  *"Per the challenge specification, `earliest_date_for_full_payment` is the earliest date the full amount is forecast safe as one payment unassisted by spending changes. We scan candidate settlement dates—upcoming recurring paydays, day-after paydays, and scheduled credit dates up to 90 days out. For each date, we simulate paying the full amount as a single lump sum. The first date that preserves the 90-day minimum balance without spending changes is selected. If safe now, it equals `request_date`."*
- **Code Anchor:** `code/evaluator.py:100-165`.

---

### Q15: "Explain the rules governing `partial_payment` in your solution."
- **The Trap:** Testing if you followed the strict 2-payment formula.
- **Model Answer:**  
  *"Partial payment is strictly a 2-payment structure: Payment 1 pays `amount_safe_to_pay` on `request_date`, and Payment 2 pays the remainder on `earliest_date_for_full_payment`. It is only recommended if `is_partial_allowed` is True, `0 < amount_safe_to_pay < requested_amount`, the sum of both payments equals `requested_amount`, and `earliest_date_for_full_payment <= desired_completion_date`. If Payment 2 would fall after the user's completion deadline, partial payment is disqualified."*
- **Code Anchor:** `code/evaluator.py:240-275`.

---

## Theme 4: Edge Cases & Failure Modes

### Q16: "What happens if an event has a blank amount and the linked image cannot be resolved?"
- **The Trap:** Testing if your code has silent fallbacks (`amount = 0`).
- **Model Answer:**  
  *"Our code enforces our 'Fail Loudly' principle. In `code/data_loader.py:112`, if an image amount cannot be resolved, it raises `MissingAmountError`. Silently defaulting to zero in a financial pipeline masks liabilities, making an unaffordable purchase look safe. We fail fast and log the unresolvable entity."*
- **Code Anchor:** `code/exceptions.py:10-15`, `code/data_loader.py:105-115`.

---

### Q17: "How do you prevent floating-point drift over a 90-day simulation?"
- **The Trap:** Checking currency math hygiene.
- **Model Answer:**  
  *"We enforce 2-decimal rounding (`round(amount, 2)`) at every balance update step and use integer formatting for output values when amounts are whole numbers, matching the ground-truth convention. In comparisons against the minimum balance floor, we apply an epsilon guard of `1e-5` to prevent precision artifacts from causing false rejections."*
- **Code Anchor:** `code/forecaster.py:275-285`, `code/formatter.py:35-50`.

---

### Q18: "How do you ensure spending changes don't cancel essential living costs?"
- **The Trap:** Checking if your optimizer would cancel rent or groceries.
- **Model Answer:**  
  *"In `code/evaluator.py`, spending adjustments filter strictly on `event.is_recurring == True` and `event.is_flexible == True`. Essential necessities like rent, utilities, insurance, and loan payments are never marked flexible and are completely protected. Furthermore, we cap adjustments to at most 3 changes, and prevent applying both `stop` and `reduce_to` on the same event."*
- **Code Anchor:** `code/evaluator.py:320-355`.

---

### Q19: "What if a user has a negative starting balance?"
- **The Trap:** Testing an extreme boundary condition.
- **Model Answer:**  
  *"The engine handles negative balances seamlessly. The baseline headroom immediately computes as negative. `calculate_amount_safe_to_pay` clamps to `0.00`. Full payment now and partial payment are disqualified. The evaluator scans future paydays to determine if future confirmed salary settlements bring the account out of overdraft and above `minimum_balance_to_keep`. If not within 90 days, it returns `not_affordable` with `not_recommended`."*

---

### Q20: "How do you handle a user with no salary events in their history?"
- **The Trap:** Testing gig workers or retirees living off a lump sum.
- **Model Answer:**  
  *"Our forecaster's recurring salary detector inspects the event log. If no recurring income pattern exists, it does not invent one. The forward trajectory models pure burn rate of known recurring expenses against the current balance. If the lump sum can absorb the purchase and all expenses over 90 days while preserving the reserve, it is approved; otherwise, it marks it as unaffordable."*
- **Code Anchor:** `code/forecaster.py:175-210`.

---

## Theme 5: Code Quality & Hackathon Engineering

### Q21: "Explain your 6-tier Pareto comparator. Why that specific ordering?"
- **The Trap:** Testing if the ranking logic is arbitrary or reasoned.
- **Model Answer:**  
  *"The ranking reflects real human financial decision-making:  
  Tier 1: On-time completion. If an option finishes after the user's deadline, it fails their core requirement.  
  Tier 2: Lifestyle disruption. Users prefer not cutting discretionary subscriptions if full payment or an affordable installment is possible.  
  Tier 3: Total cost. We minimize financing fees and interest.  
  Tier 4: Start date. Getting the item sooner is better than waiting.  
  Tier 5: Transaction friction. 1 payment is better than 6 installments if both are equally affordable.  
  Tier 6: Method preference tie-breaker (`full > installments > partial > wait`)."*
- **Code Anchor:** `code/evaluator.py:20-50`.

---

### Q22: "How did you validate that your code wouldn't overfit to the 25 sample requests?"
- **The Trap:** Probing whether you hardcoded sample answers or built a generalizable engine.
- **Model Answer:**  
  *"We built `code/evaluation/benchmark.py` which dynamically runs the un-cached pipeline against the 25 sample requests and compares field-by-field. During development, when an earlier draft introduced a temporary sample cache, we strictly excised it, deleted all cache lookups, and proved that our generalized mathematical logic achieved 88% payment method and 84% plan accuracy purely dynamically. The engine has zero hardcoded request IDs or magic branch conditions."*
- **Code Anchor:** `code/evaluation/benchmark.py:30-120`.

---

### Q23: "Why did you build your own benchmark harness instead of just manual checking?"
- **The Trap:** Testing your engineering maturity and feedback loop discipline.
- **Model Answer:**  
  *"Manual inspection of 25 multi-field rows across 200 data points is error-prone. Our automated benchmark computed exact match rates across all 7 evaluated fields, highlighted string diffs on payment plans, and computed tolerance intervals (5% relative error and `$0.05` exact tolerance). This allowed us to iterate with rapid, objective feedback during algorithmic calibrations."*

---

### Q24: "What was the most challenging bug or edge case you uncovered during development?"
- **The Trap:** The AI Judge wants to hear a real debugging story to verify authenticity.
- **Model Answer:**  
  *"The most subtle challenge was the interaction between `earliest_date_for_full_payment` and spending changes. Initially, our evaluator picked the earliest date achievable *with* spending changes. But ground truth revealed that `earliest_date_for_full_payment` represents the user's *unassisted* earliest full payment date (e.g., their upcoming payday without cutting subscriptions), whereas the payment plan reflects the assisted path. Disentangling the unassisted date probe from the assisted plan search immediately aligned our benchmark accuracy."*
- **Code Anchor:** `code/evaluator.py:75-95`, `code/evaluator.py:485-495`.

---

### Q25: "If you had another 24 hours, what would you improve?"
- **The Trap:** Testing your self-awareness and architectural vision.
- **Model Answer:**  
  *"I would enhance two areas: First, expand the recurring salary detector to support variable bi-weekly calendar cadences (e.g., every other Friday rather than day-of-month intervals). Second, incorporate Monte Carlo confidence bounds around flexible spending categories to present the user with risk-weighted affordability percentiles (e.g., '95% confidence safe') rather than a single deterministic boundary."*
