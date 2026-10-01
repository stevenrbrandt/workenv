# 03 — Design: SOLID (Pragmatic), Cohesion, Coupling, Dependencies

> Provenance: Martin *Clean Code* Ch.6–12,19 (Classes, Objects, SOLID); ISO/IEC 25010 maintainability (modularity, reusability); Google Code Health (simplicity, local reasoning).

SOLID and patterns are heuristics for *cheap change*, not commandments. Apply to reduce friction; skip when cost exceeds benefit (throwaway prototype, <500-line script, stable 3-year-untouched utility).

## 3.1 SRP — Single Responsibility

- A module/class/function SHOULD have one reason to change = serves one actor / one concern.
- Smell: class handling parsing + calculation + persistence + notification. Split by actor.
- At service level SRP maps to bounded context: one service owns one domain capability.

## 3.2 OCP — Open for extension, closed for modification

- Evolve by *adding* new code, not editing working code, WHEN the extension point is real.
- Good: `PaymentProcessor` accepts `PaymentMethod` interface; new method = new class, zero edits to dispatcher.
- Bad: growing `if method==X else if method==Y` chain.
- MUST NOT apply OCP speculatively. No strategy interface until the second concrete case exists.

## 3.3 LSP — Substitutability is behavioral

- Subtypes MUST honor the base contract: accept at least as much (weaken preconditions), guarantee at least as much (strengthen postconditions). Never narrow promises.
- Classic violation: `Square extends Rectangle` breaking independent width/height setters.
- AI rule: if you override, MUST NOT surprise callers; run base-class tests against the subclass.

## 3.4 ISP — Small, role-specific interfaces

- Clients MUST NOT be forced to depend on methods they don't use.
- Prefer `Printer` + `Scanner` over fat `Machine(print,scan,fax)` forcing empty stubs.
- Avoid fragment hell (ten 1-method interfaces for one cohesive role) — split by client need, not dogma.

## 3.5 DIP — Depend on abstractions at volatile boundaries

- High-level policy MUST NOT construct low-level details directly (`new MySQLDatabase()` inside `OrderService`). Inject via interface/constructor.
- This enables test doubles and swapping infra without touching domain logic.
- MUST NOT add an interface for every class "just in case" — one implementation + no test need = YAGNI violation. Add the seam where volatility or testing demands it.

## 3.6 Cohesion, coupling, encapsulation

- MUST maximize cohesion (related things together) and minimize coupling (knowledge across boundaries).
- MUST expose only what consumers need; hide internals. Protect invariants via types/value objects (e.g., `Money`, `Email`) instead of scattered validation.
- MUST structure for local reasoning: a reader should understand a call site without opening the implementation (explicit ownership transfer, explicit error contracts, predictable names).
- Layering: domain/core MUST NOT depend on infra/framework details. Depend inward (Hexagonal / Clean Architecture dependency rule). Isolate technology so DB/framework/message bus can be replaced.
- SHOULD prefer composition over inheritance. Inheritance is the tightest coupling — use it only for true is-a + LSP-safe cases.
- SHOULD replace large conditionals/switches with polymorphism *when* cases grow and vary independently; otherwise a simple `if` is clearer (KISS wins).

## 3.7 When to skip SOLID

| Scenario | Guidance |
|---|---|
| Prototype / spike | Skip — will be rewritten |
| Single-file script | Skip — clarity > abstraction |
| Stable utility, no change in years | Skip OCP/DIP — YAGNI |
| Microservice boundary | Apply SRP + DIP strongly |
| Domain-rich, frequently changed | Apply all five |

## AI checklist

- [ ] Does each unit have one reason to change?
- [ ] Can I add the next likely variant without editing tested code? If not, is that variant real?
- [ ] Are dependencies injected at boundaries and minimal?
- [ ] Would composition be simpler than my inheritance?
