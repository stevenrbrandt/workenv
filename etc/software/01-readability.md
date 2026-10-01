# 01 — Readability: Write for Humans

> Provenance: Martin *Clean Code* Ch.2–5 (Names, Functions, Formatting, Comments); Google Go Style Guide (Clarity > Simplicity > Concision); Google "What to look for in a code review" (Names, Comments).

Readability is the highest-leverage quality. Misread code gets changed incorrectly — readability failures are reliability failures.

## 1.1 Naming — MUST

- Names MUST reveal intent and domain language. Function names SHOULD be verbs; class/type names SHOULD be nouns; booleans SHOULD read as assertions (`isActive`, `hasPermission`, `canRetry`).
- Good: `calculateInvoiceTotal(items)`, `isEligibleForDiscount(user)`, `ORDER_SHIPPED`
- Bad: `doIt()`, `handleStuff()`, `data`, `info`, `temp`, `flag`, `calc(d1,d2)`
- MUST use pronounceable, searchable names. MUST NOT use encodings (`str_`, `i_`) or disinformation (`accountList` when it's not a list).
- MUST make meaningful distinctions: `get` vs `fetch` vs `load` must mean one thing per codebase — pick and stay consistent.
- Magic numbers/strings MUST be named constants, except idiomatic `0`, `1`, `-1` in trivial contexts.
- Scope rule: the smaller the scope, the shorter the name MAY be (`i` in a 3-line loop is fine; module-level `i` is not).

## 1.2 Functions — SHOULD be small and single-purpose

- Functions SHOULD do one thing, at one level of abstraction, in ~4–20 lines. Test: describe it in one sentence without "and".
- If a function mixes high-level orchestration with low-level details, extract the low level:
  ```
  // good
  function getPreviousDayOfWeek(weekday, from) {
    checkWeekdayArgument(weekday);
    return addDays(-daysBefore(weekday, from), from);
  }
  ```
- Parameters SHOULD be ≤2–3. More than that → introduce a parameter object.
- MUST follow Command-Query Separation: a function either *does* something (command) or *answers* something (query), not both. `save()` should not also return the saved entity's validation errors via side channel — either return a Result or throw.
- MUST NOT have hidden side effects. If the name says `getUser()`, it MUST NOT also write to disk.
- MUST prefer guard clauses over nesting:
  ```
  // prefer
  if (!user) return null;
  if (!user.isActive) return null;
  return process(user);
  // over nested if-if-if
  ```

## 1.3 Formatting & structure

- MUST follow the repo's formatter/linter (gofmt, prettier, black, etc.). Never debate formatting in review — automate it.
- MUST organize top-down: high-level concepts first, details below. Caller SHOULD appear above callee when reading top-to-bottom.
- MUST use vertical whitespace to separate logical sections; keep line length reasonable; prefer refactoring over aggressive line-splitting.
- Indentation SHOULD NOT exceed 3 levels. Deeper → extract function or invert condition.
- Related variables/functions that change together MUST live near each other (cohesion).

## 1.4 Comments — explain WHY, not WHAT

- Code MUST be self-documenting via names + structure first. Comments MUST NOT restate code (`i++ // increment i`).
- Comments SHOULD explain: why a non-obvious decision was made, business context code cannot express, warnings/consequences, references to specs/ADRs.
- Exceptions where *what*-comments are OK: complex regex/algorithms, performance-critical trickery, workarounds with link to issue.
- MUST delete commented-out code. Version control is history.
- Public APIs MUST have doc comments describing contract: purpose, params, return, errors thrown, usage example if non-trivial.

## AI checklist before emitting code

- [ ] Could a competent dev unfamiliar with this file understand it in one read?
- [ ] Are all names full words from the domain?
- [ ] Is any function >20 lines or >3 params? Split it.
- [ ] Is nesting >2 deep? Flatten it.
- [ ] Does every comment answer "why"?
