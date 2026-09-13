# Core Development Principles: Buy or Wait?

This document governs the engineering standards, test practices, failure semantics, mathematical invariants, and system architecture for the "Buy or Wait?" financial decision engine.

---

## 1. Full-Mode Test-Driven Development (TDD)

Engineering financial software requires absolute correctness. We enforce a strict Red-Green-Refactor development cycle across every component:

### 1.1 Test-First Requirement
- Before any production code is written in a module, comprehensive unit and edge-case tests must be created in `code/tests/`.
- Every test suite must be executed immediately after creation to verify legitimate failure (Red). We verify that the test fails for the expected reason (e.g., missing class, function, or behavior), never due to a typo in the test itself.
- Production code is written solely to satisfy the failing test cases with the minimal clean implementation (Green).
- Refactoring (Green -> Refactor) proceeds only while all tests continuously pass.

### 1.2 Meaningful Assertions and Boundary Coverage
- Zero trivial or pampered tests: Assertions like `self.assertTrue(True)` or tests that merely verify code executes without throwing are strictly prohibited.
- Assertions must evaluate exact calculated numerical values, date boundaries, status strings, payment plan structures, and invariants.
- 100% boundary testing:
  - Exactly at `minimum_balance_to_keep` threshold.
  - Zero-balance and near-zero balance scenarios.
  - Boundary dates (e.g., event on `request_date`, event on `desired_completion_date`, day 90 cutoff).
  - Maximum allowable installment durations and fee calculations.
  - Conflicting events with identical timestamps.

---

## 2. Fail Loudly, Never Mask Errors

In financial calculations, silent fallbacks, implicit defaults, and swallowed exceptions are dangerous bugs. The engine must fail loudly and immediately whenever input data or system state violates contract assumptions.

### 2.1 Explicit Domain Exceptions
Define and raise explicit domain exceptions in `code/exceptions.py`:
- `MissingAmountError`: Raised when an event amount is blank and cannot be extracted from linked images or supporting records. Never default missing amounts to 0 or null.
- `ExchangeRateNotFoundError`: Raised when a cross-currency transaction lacks a conversion rate for the specified settlement date and currency pair. Never guess or apply 1:1 rates.
- `SchemaValidationError`: Raised when an input row violates expected schemas, enums, date formats, or numerical bounds (e.g., negative balances, unknown request types, or unmapped payment methods).
- `InfeasiblePlanError`: Raised internally during plan search when cash flow constraints are breached, driving the decision optimizer rather than producing corrupted plans.

### 2.2 Rejection of Soft Coercion
- Numerical fields must parse strictly. If a value is unparseable or corrupted, raise `ValueError` or `SchemaValidationError`.
- Unknown categories or directions must not fall into a silent `else` block.

---

## 3. 100% Offline Determinism and Zero Network Reliance

The submission must run in an isolated, offline evaluation container with zero external connectivity.

### 3.1 Standard Library Exclusivity
- The engine uses Python 3.12 standard library exclusively (`csv`, `datetime`, `math`, `re`, `json`, `dataclasses`, `pathlib`, `typing`, `unittest`).
- No dependencies on external packages (`requests`, `numpy`, `pandas`, `PIL`, etc.).
- No external APIs, live banking calls, LLM inference endpoints, or remote translation services.

### 3.2 Deterministic Multilingual Text Parsing
- Messages in `dataset/messages.csv` appear in both English and Indonesian.
- Both languages are processed locally using deterministic regular expressions and compiled pattern extractors.
- Regex rules capture canonical banking, payroll, and merchant templates:
  - English: "confirmed salary is now expected on <YYYY-MM-DD>", "temporary monthly pay is <CURRENCY> <AMOUNT>", "reduced to <CURRENCY> <AMOUNT>".
  - Indonesian: "Gaji bulanan Anda naik menjadi <CURRENCY> <AMOUNT>", "Gaji pokok yang dikonfirmasi adalah <CURRENCY> <AMOUNT>", "pembayaran faktur sebesar <CURRENCY> <AMOUNT>. Penyelesaian diperkirakan pada <YYYY-MM-DD>".
- Pattern matching yields identical output on every run across all platforms.

---

## 4. Financial Math and Invariants

### 4.1 Numerical Precision and Currency Formatting
- Currency amounts must avoid floating-point drift. Where appropriate, calculate using integer cents/minor units or round cleanly to 2 decimal places (or integer for currencies like IDR/ZAR where whole units are standard).
- Generated output amounts must match the exact string format in `dataset/sample_requests.csv` (e.g., `25256`, `17229139.2`, `620.40`).

### 4.2 Cash Flow and Balance Invariants
- 90-Day Safety Rule: `balance(t) >= minimum_balance_to_keep` for every day `t` from `request_date` to `request_date + 90 days`.
- Pending Debits: Always reserved immediately against available balance on or before settlement date.
- Pending Credits and Speculative Inflows: Disregarded entirely. Do not count pending credits, bonuses, commissions, tax refunds, lottery winnings, or unrealized investment gains until settled.
- Confirmed Salary: Credited strictly on its confirmed settlement date.
- Safe Amount Bound: `0 <= amount_safe_to_pay <= requested_amount`.

---

## 5. KISS and Modular Architecture

Complexity kills reliability. Keep the system clean, modular, and easy to maintain.

### 5.1 File Size and Single Responsibility
- Aim for under 300 lines of code per file.
- Single responsibility principle: each module handles one discrete stage of the pipeline.

### 5.2 Strict Layered Architecture
```
Layer 1: Ingestion & Parsing
  - code/models.py: Strongly typed dataclasses
  - code/exceptions.py: Domain-specific errors
  - code/data_loader.py: Deterministic CSV parsers and validation
  - code/multimodal.py: Pattern matchers for messages and image metadata

Layer 2: Core Financial Engine
  - code/forecaster.py: 90-day daily cash flow simulator and safety checks

Layer 3: Decision Optimizer
  - code/evaluator.py: Safe amount solver, payment plan evaluator, spending changes optimizer, plan ranker

Layer 4: Formatting & Compliance
  - code/formatter.py: Output string serialization and validation against competition schema
  - code/main.py: CLI entry point coordinating the batch run
```
