# 05 — Workflow: Small Changes, Review, Consistency, Docs

> Provenance: Google eng-practices (Small CLs, Code Reviewer/Author Guides, Style as canon); *Software Engineering at Google* Ch.8 (optimize for reader, consistency, automate); DORA metrics.

## 5.1 Small, self-contained changes

- Changes SHOULD be minimal and address one thing (~100 lines ideal, ~1000 lines needs pre-approval/split). One feature slice or one fix per change.
- MUST separate pure refactoring (move/rename/extract) from behavior changes. Reviewers cannot verify logic hidden in a large move.
- Each change MUST include: code + tests + docs update (README/g3doc/API refs if user-facing behavior/build/test/release changed). Deleting code MUST delete its docs.
- MUST NOT break the build between stacked changes; each intermediate state stays green. Prefer vertical thin slices over horizontal layers when possible.

## 5.2 Code review mindset (self-review as AI)

Apply Google's review checklist to your own output before finalizing:

- [ ] Design: do pieces interact sensibly? Does this belong here or in a library? Does it integrate cleanly?
- [ ] Functionality: does it do what the user needs, including edge cases, concurrency, accessibility, i18n where relevant?
- [ ] Complexity: is it more complex than needed? Could a reader grasp it quickly? No future-speculative code?
- [ ] Tests: present, correct, well-designed, not overly complex?
- [ ] Names: long enough to communicate, not so long as to obscure?
- [ ] Comments/docs: why-explanations where needed? Public contract documented?
- [ ] Style: follows repo style guide (style guide is absolute authority on style points)?
- [ ] Code health: does the system get simpler/more tested, not more tangled? No overall health decrease even if "just a small hack"?

Reviewer standard: approve when change *improves overall health*, not when perfect. As author (AI), err smaller. As reviewer, be kind, cite principle/file (e.g., `02-simplicity.md YAGNI`), suggest fix, prefix pure education with `Nit:`.

## 5.3 Consistency + automation

- MUST match existing naming, patterns, folder structure in the touched package first; global style guide second; personal preference never.
- Consistency rule from Google: when codebase is uniform, deviations signal "look here — performance/complexity is intentional". Don't create accidental novelty.
- MUST automate formatting/linting/type-checks in CI; MUST NOT waste review cycles on what a tool can enforce.
- Commit messages / PR descriptions MUST explain *why* + context for the future investigator (problem, alternatives, risk, rollback). Link ticket/ADR.

## 5.4 Docs & decisions

- ADRs (Architecture Decision Records) SHOULD capture significant choices: context, options, decision, consequences. One page is enough.
- Ubiquitous language: technical terms MUST mirror domain language to reduce translation errors.
- If it isn't written down, it didn't happen: risk acceptances, tech-debt TODOs (with owner/ticket, not open-ended `TODO: fix`), and deprecations MUST be explicit and discoverable.

## 5.5 Measure what matters (DORA + health)

- Track: change lead time, deploy frequency, failed-deploy recovery time, change failure rate + rework rate. Speed and stability improve together with discipline — not a tradeoff.
- Revisit these advice files quarterly or when stack/team/compliance shifts. Standards frozen past relevance create friction.

## AI checklist

- [ ] Is this change the smallest that solves the problem?
- [ ] Did I run formatter/linter/tests?
- [ ] Would a reviewer understand *why* from my description alone?
