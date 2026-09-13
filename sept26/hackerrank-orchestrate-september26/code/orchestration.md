# Master Orchestration Guide: Buy or Wait?

This is the central operating manual for any agent or developer executing tasks inside `code/`. Every coding task must follow this orchestration guide without deviation.

---

## 1. The First-Read Rule

Whenever an agent or developer initiates or resumes work in `code/`, this file (`code/orchestration.md`) must be consulted first. It establishes the execution sequence, documentation references, and non-negotiable verification gates.

---

## 2. Documentation Map and Trigger Conditions

Consult the appropriate documents based on the task lifecycle:

| Document | When to Read | Purpose and Scope |
|---|---|---|
| [`code/rulebook.md`](./rulebook.md) | At start of session or task | Non-negotiable operating rules: mandatory `log.txt` updates, zero fake tests, TDD culture, KISS, no em-dashes, concise facts. |
| [`code/development-principle.md`](./development-principle.md) | Before writing any code or tests | Core engineering principles: Red-Green-Refactor, fail loudly with explicit domain errors, 100% offline Python 3.12 standard library, financial math precision. |
| [`code/architecture.md`](./architecture.md) | Before creating or modifying classes/modules | System design: 4-layer architecture (Ingestion -> Cashflow -> Evaluator -> Formatter), dataclass models, and cross-layer data contracts. |
| [`code/decisions.md`](./decisions.md) | When handling messages, images, cashflow math, or plan ranking | Architectural Decision Records: ADR-001 (offline regex), ADR-002 (image lookup/fallback), ADR-003 (analytical 90-day bottleneck), ADR-004 (6-tier tie-breaker). |
| [`code/dos-dont.md`](./dos-dont.md) | As final review checklist before closing any task | Pre-completion quality gate: verify pending debit reservations, date bounds, format rules, and zero contract violations. |

---

## 3. Strict 5-Step Agent Execution Protocol

Every single coding or refactoring task must execute through these five sequential steps:

### Step 1: Check Architecture and ADRs
- Review [`code/architecture.md`](./architecture.md) to locate the target layer and verify input/output dataclass contracts.
- Review [`code/decisions.md`](./decisions.md) if the task involves message parsing, image resolution, cashflow simulation, or plan ranking.
- Ensure the proposed change maintains module size under 300 lines and introduces zero external dependencies.

### Step 2: Write Tests in `code/tests/` First
- Define concrete test cases in the appropriate test file under `code/tests/`.
- Cover typical paths, numerical boundaries (e.g., balance exactly equal to minimum balance), and edge cases (e.g., zero amounts, boundary dates, foreign currencies).
- Enforce meaningful assertions on computed numbers, dates, and enums. Never write trivial checks (`assert True`).

### Step 3: Run Tests and Verify Legitimate Failure (Red)
- Execute the test suite using Python's standard `unittest` runner:
  ```bash
  python3 -m unittest code/tests/test_<module_name>.py -v
  ```
- Confirm that the tests fail specifically due to missing implementation, not due to syntax or test harness defects.

### Step 4: Write Minimal Implementation to Pass (Green)
- Write the minimal, cleanest code necessary to make the failing tests pass.
- Maintain pure Python 3.12 standard library compliance.
- Run the test suite again and confirm 100% green assertions.
- Refactor for clarity and simplicity while keeping tests green.

### Step 5: Run DOs and DONTs Checklist
- Perform an explicit audit against [`code/dos-dont.md`](./dos-dont.md):
  - Pending debits reserved immediately?
  - Confirmed salary credited strictly on settlement date?
  - Pending credits, bonuses, and speculative inflows completely ignored?
  - Safe amount bounded by `[0, requested_amount]`?
  - `earliest_date_for_full_payment == request_date` if `affordable_now`?
  - Partial payment formatted as exactly 2 payments totaling `requested_amount`?
  - No single event both stopped and reduced?
  - Zero unicode em-dashes (`\u2014`) or en-dashes (`\u2013`) used?
  - `log.txt` updated per AGENTS.md Section 5.2?
