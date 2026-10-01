# Software Design Advice for AIs — Readability & Maintainability First

> **Audience:** AI coding assistants working in this repo / workspace.
> **Goal:** Produce code that is easy to read and cheap to change.
> **Prime directive:** Optimize for the reader, not the writer. Code is read 10x more than written.

This directory is a set of short, opinionated, proven-practice guides.
They synthesize: Robert C. Martin *Clean Code* (incl. 2nd ed.), Hunt & Thomas *The Pragmatic Programmer* (DRY), Beck's Simple Design, SOLID, and Google Engineering Practices / Code Health (readability, code review, small changes).

## How to use these files

1. **Default to all files.** If the task involves writing or editing code, follow `01`–`05`.
2. **Severity keywords** follow RFC 2119 throughout:
   - `MUST` / `MUST NOT` = always follow, no exception without explicit user approval.
   - `SHOULD` / `SHOULD NOT` = follow by default; break only with a code comment explaining *why*.
   - `MAY` = use judgment.
3. **When rules conflict**, priority order is: `01-readability` > `02-simplicity` > `03-design` > `04-verifiability` > `05-workflow`. Simpler + readable beats clever + abstract.
4. **Never sacrifice clarity for brevity.** A longer, obvious solution beats a short, clever one.

## File index

- `01-readability.md` — Naming, small functions, formatting, comments (why not what). Highest leverage.
- `02-simplicity.md` — KISS, YAGNI, DRY done right, Boy Scout Rule. Anti-over-engineering.
- `03-design.md` — SOLID pragmatically, cohesion/coupling, encapsulation, dependencies.
- `04-verifiability.md` — Testing as safety net, error handling, no silent failures.
- `05-workflow.md` — Small changes, code review mindset, consistency, docs.

## The 10-rule quick check (if you read nothing else)

1. Names MUST reveal intent. `calculateMonthlyInterestRate()`, not `calc()`. No `data`, `info`, `tmp`, `manager`, `helper` without qualification.
2. Functions SHOULD be small (roughly 4–20 lines), do one thing, one level of abstraction. If you need "and" to describe it, split it.
3. Nesting SHOULD NOT exceed 2–3 levels. Use guard clauses / early returns, extract helpers.
4. Parameters SHOULD be ≤3. Group related args into an object. MUST NOT pass/return `null` as control flow — use exceptions, Option/Result, or Null Object.
5. DRY applies to *knowledge*, not *text*. Duplication is cheaper than the wrong abstraction. Wait for 3rd occurrence before generalizing.
6. KISS + YAGNI: solve today's problem simply. MUST NOT add speculative generality, future hooks, or unused options.
7. Dependencies MUST point toward abstractions for volatile/domain boundaries; minimize coupling, maximize cohesion.
8. Comments SHOULD explain *why*, never restate *what*. Delete commented-out code — version control has history.
9. Changes MUST be verifiable: add/update tests with behavior changes, keep tests clean (FIRST, Arrange-Act-Assert).
10. Leave code cleaner than you found it (Boy Scout), but keep cleanup in a separate, small, reviewable change.

Sources & further reading: `AGENTS.md` companion files list full provenance; canonical refs are Clean Code Ch.2–8,17–19; Google `eng-practices` (What to look for in a review, Small CLs, Style); ISO/IEC 25010 maintainability (modularity, analysability, modifiability, testability).
