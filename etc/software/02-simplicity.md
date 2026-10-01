# 02 — Simplicity: KISS, YAGNI, DRY (Done Right)

> Provenance: Hunt & Thomas *Pragmatic Programmer* (DRY = knowledge, not text); Beck Simple Design (runs tested, no duplication, expresses intent, minimal entities); Martin Ch.18 (YAGNI, minimize duplication); Sandi Metz ("duplication is cheaper than the wrong abstraction"); Google "complexity" + "over-engineering" review checks.

## 2.1 KISS — Keep It Simple

- MUST choose the simplest design that solves the *actual* problem. Fewer moving parts, fewer layers, straightforward control flow.
- SHOULD NOT introduce a design pattern, framework, or abstraction until plain code has proven insufficient. A function + data beats a class hierarchy + plugin registry for one case.
- Cleverness is a cost. Nested ternaries, bit tricks, metaprogramming MUST have a comment + test proving the need (e.g., profiled bottleneck).
- Complexity MUST be added deliberately, with docs + tests + examples showing correct use.

## 2.2 YAGNI — You Aren't Gonna Need It

- MUST NOT build for imagined futures: no speculative multi-DB layers, plugin registries, config flags, or generic frameworks for one concrete case.
- Rule: implement when actually needed, not when foreseen. Cost of adding later (with real requirements) is almost always lower than carrying wrong guesses.
- Signals you are violating YAGNI:
  - unused parameters / options "for later"
  - interfaces with a single implementation and no second case in sight
  - `else` branches / features with no test or caller
  - "we might need..." in a commit message without a ticket
- Exception: building ahead is allowed ONLY when change-later cost is provably high (e.g., public API, data migration, safety-critical) — document the tradeoff in an ADR/comment.

## 2.3 DRY — Don't Repeat Knowledge, Not Characters

- DRY = every piece of *knowledge* (business rule, validation, calculation, schema) has one authoritative home.
- MUST deduplicate when the same rule would require multi-place edits to stay correct.
- MUST NOT merge code that merely *looks* alike but represents different facts. Coincidental similarity is not duplication.
- Rule of Three: 1st time write it, 2nd time copy it, 3rd time — only when you understand what varies — extract it.
- Wrong-abstraction smell: shared helper sprouting boolean flags / switch-on-caller / special cases → inline it back into separate copies.
- Deduplication MUST NOT increase coupling more than the duplication costs. Two 3-line blocks left apart are better than a flag-heavy helper used in two places.

## 2.4 Conflict resolution

- DRY vs KISS: KISS wins. If removing duplication adds more complexity than the duplication, leave the duplication.
- DRY vs YAGNI: YAGNI wins. Don't build a generic helper for a predicted third use.
- OCP vs YAGNI: YAGNI wins until a real second case arrives (see `03-design.md`).

## 2.5 Boy Scout Rule — relentless micro-improvement

- SHOULD leave every touched file slightly cleaner: rename one confusing var, extract one long function, delete one dead branch.
- MUST keep behavior changes and cleanups reviewable: prefer separate commits/CLs for pure refactoring vs feature/fix. Never mix a large reformat with logic changes.
- Continuous small cleanups beat rare big-bang rewrites.

## AI checklist

- [ ] Am I adding anything no current caller/test needs? Delete it.
- [ ] Am I abstracting on first or second duplication? Wait.
- [ ] Is there a flag/switch in my helper that only one caller uses? Inline it.
- [ ] Can I delete code and all tests still pass? Delete it.
