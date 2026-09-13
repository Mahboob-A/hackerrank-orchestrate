# Engineering Checklist: DOs and DONTs

A practical engineering checklist for building the "Buy or Wait?" financial decision engine. Review this list before writing or reviewing code.

---

## DOs

### Financial Math and Cashflow
- DO reserve pending debits immediately on `request_date` against available balance.
- DO credit confirmed salary strictly on its confirmed settlement date.
- DO enforce the safety invariant `B(t) >= minimum_balance_to_keep` for every single day in the 90-day window (`t in [T0, T0+90]`).
- DO enforce the bound `0 <= amount_safe_to_pay <= requested_amount` unconditionally.
- DO set `earliest_date_for_full_payment = request_date` whenever `affordability_status` is `affordable_now`.
- DO format `partial_payment` as exactly two payments summing to `requested_amount`: `amount_safe_to_pay` on `request_date` and `requested_amount - amount_safe_to_pay` on `earliest_date_for_full_payment`.
- DO verify that the second payment of `partial_payment` falls on or before `desired_completion_date`.
- DO respect `max_installment_months`: reject installment offers exceeding this duration, and reject all installments if `max_installment_months` is blank.
- DO ensure every recommended installment plan matches a valid offer in `request_payment_options.csv`.
- DO break ties strictly using the 6-tier hierarchy (deadline completion -> fewer spending changes -> lower total cost -> earlier start -> fewer payments -> lowest option ID).

### Data Ingestion and Normalization
- DO match the exact 8 output columns in exact order:
  `request_id,amount_safe_to_pay,affordability_status,recommended_payment_method,payment_plan,earliest_date_for_full_payment,spending_changes_needed,decision_explanation`.
- DO convert cross-currency transactions using the exact dated rate from `exchange_rates.csv`.
- DO extract missing amounts for the 16 linked events in `images.csv` using deterministic verification.
- DO parse English and Indonesian messages using local compiled regular expressions.

### Engineering and Quality
- DO follow full-mode TDD: write tests in `code/tests/` first, watch them fail legitimately, and only then write implementation code.
- DO assert exact numerical values, dates, and invariants in tests--never trivial checks.
- DO fail loudly with explicit domain exceptions (`MissingAmountError`, `ExchangeRateNotFoundError`, `SchemaValidationError`).
- DO append a Section 5.2 entry to `log.txt` on every single turn with `tool=Antigravity`.

---

## DONTs

### Financial Rules
- DONT count pending credits, bonuses, commissions, tax refunds, or lottery winnings until they actually settle.
- DONT count unrealized investment gains or portfolio market values as liquid cash.
- DONT default blank event amounts to 0; resolve via image evidence or raise `MissingAmountError`.
- DONT guess or default missing exchange rates to 1:1; raise `ExchangeRateNotFoundError`.
- DONT both stop and reduce the same financial event; stop and reduce are mutually exclusive per event ID.
- DONT touch fixed expenses or protected expense categories when proposing spending changes.
- DONT propose more than 3 spending changes for any request.
- DONT recommend payment methods that the user excluded from `payment_methods_user_will_consider`.
- DONT recommend `wait` if the user will not consider `full_payment`.

### Environment and Architecture
- DONT make external network calls, invoke remote LLMs, or query third-party translation APIs.
- DONT install or import third-party packages (`pandas`, `numpy`, `PIL`, `requests`); stick 100% to Python 3.12 standard library.
- DONT write bloated modules; keep files focused and aim for under 300 lines per module.
- DONT write fake, pampered, or always-passing tests.
- DONT use unicode em-dashes or en-dashes anywhere in documentation, code, strings, or logs; use standard single hyphens (-) or double dashes (--).
