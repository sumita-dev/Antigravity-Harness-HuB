---
name: domain-modeling
description: Build and sharpen a project's domain model and Ubiquitous Language (Eric Evans DDD). Use when discussing codebase terminology, creating or editing CONTEXT.md, or recording ADRs.
---

# Domain Modeling & Ubiquitous Language

Actively build and sharpen the project's domain model as you design (derived from Eric Evans' *Domain-Driven Design*). 

This is the **active discipline**: challenging ambiguous terms, exploring concrete edge-case scenarios, and maintaining a canonical glossary in `CONTEXT.md` so developers and AI agents communicate with 100% precision without wasting tokens.

## 1. File Structure

Most repositories have a single bounded context:

```text
/
├── CONTEXT.md                  # Project-wide canonical glossary & forbidden terms
├── docs/
│   └── adr/                    # Architectural Decision Records
│       ├── 0001-record-name.md
│       └── 0002-another-record.md
└── src/
```

If multiple subdomains or microservices exist, map them in `CONTEXT-MAP.md` at root pointing to their respective subdirectories.

Create files lazily: only when terms are defined. If no `CONTEXT.md` exists, create it when the first domain concept is resolved.

---

## 2. Active Discipline During Sessions

1. **Challenge against the Glossary:**
   When a user or prompt uses a term that conflicts with `CONTEXT.md`, call it out immediately:
   > *"Your glossary defines 'booking' as a confirmed court reservation, but here you seem to mean 'inquiry'. Which should we use?"*

2. **Sharpen Fuzzy or Overloaded Terms:**
   When terms are vague, propose a precise canonical term:
   > *"You said 'user profile': do you mean the Court Owner or the Player? They have distinct lifecycles and schemas."*

3. **Discuss Concrete Scenarios:**
   Stress-test domain relationships with edge cases:
   > *"If a Player cancels 10 minutes before match time, does the Court Slot return to 'Available' or 'Late-Cancellation'?"*

4. **Cross-Reference with Code:**
   Ensure database tables, schemas, and API payloads use the exact terms defined in `CONTEXT.md`. Never let variable names drift into generic synonyms.

5. **Update `CONTEXT.md` Inline:**
   When a term is resolved, update `CONTEXT.md` immediately. Do not batch them. Format strictly according to `references/CONTEXT-FORMAT.md`.

---

## 3. The Three Tests for an ADR (Architectural Decision Record)

Offer to create an ADR in `docs/adr/` ONLY when all three criteria are satisfied:
1. **Hard to reverse:** The cost of changing your mind later is significant (e.g. database choice, event-sourcing vs CRUD).
2. **Surprising without context:** A future developer or agent will ask *"Why did they do it this way?"*.
3. **Result of a real trade-off:** Genuine alternatives existed, and one was selected for explicit, documented reasons.
