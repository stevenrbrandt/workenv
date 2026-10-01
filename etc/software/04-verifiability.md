# 04 — Verifiability: Tests + Explicit Failures

> Provenance: Martin *Clean Code* Ch.9–10,14 (Tests, Error Handling, TDD); Beck Simple Design ("runs all the tests"); Google eng-practices (tests in same CL, tests are maintained code); DORA (speed + stability together via discipline).

Untested code is incomplete code. Tests are the safety net that makes refactoring and readability improvements safe.

## 4.1 Testing discipline

- Behavior changes MUST ship with tests in the same change (unit + integration as appropriate). Pure refactorings SHOULD be covered by pre-existing tests; if none exist, add characterization tests first.
- Follow the pyramid: many fast unit tests, fewer integration tests, very few E2E (critical journeys only). MUST NOT rely solely on brittle E2E or manual verification for risky logic.
- Good tests are FIRST: Fast, Independent, Repeatable, Self-validating, Timely. Structure as Arrange–Act–Assert (Given–When–Then). One logical assertion focus per test; descriptive names (`rejects_expired_token` not `test1`).
- MUST ensure tests actually fail when code is broken (check by mutation/negation mentally). MUST NOT accept tautological or over-mocked tests that can't fail.
- Coverage is a signal, not a target. 80%+ branch coverage is a useful health bar (Google practice); 100% pursued blindly creates gaming. Untested branches in critical paths MUST be justified.
- Tests are maintained code: MUST apply readability rules to tests (clear names, helpers, no logic/complexity in tests). Flaky tests MUST be quarantined/fixed immediately.

## 4.2 Error handling — fail fast, fail loudly

- MUST prefer exceptions/Result types over error codes or `null` returns. Error codes are easily ignored.
- MUST NOT return `null` from functions to signal absence/failure — use Option/Maybe, empty collection, Result, or throw. MUST NOT pass `null` as control flow — use overloads, defaults, or Null Object.
- MUST NOT swallow exceptions (`catch {}` / `except: pass`). Catch specifically, at the layer that can act; add context; rethrow if not handled. Log once at the boundary, not at every layer.
- MUST validate at boundaries (public API, I/O, parsing) and fail fast with useful messages. Internal invariants SHOULD be asserted explicitly.
- Error messages + test failures MUST be actionable: what happened, what was expected, how to reproduce/fix.
- Concurrency / I/O MUST handle: timeouts on everything, retries with backoff+jitter only if idempotent, no unbounded retries.

## 4.3 Observability for maintainability

- SHOULD use structured logging (context fields, levels); log decisions/inputs at boundaries, not noise in hot loops.
- SHOULD expose golden signals for services (latency, traffic, errors, saturation) — percentiles, not averages.
- Production debugging order: mitigate first, root-cause second, blameless post-mortem after. Every bug fix SHOULD add a regression test.

## AI checklist

- [ ] Did I add/update tests with the behavior? Do they fail without the fix?
- [ ] Is there any swallowed error, null return, or error code? Replace it.
- [ ] Can a future dev diagnose a failure from message + test name alone?
