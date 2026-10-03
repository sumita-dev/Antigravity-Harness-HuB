# CONTEXT.md Format Reference

## Canonical Template

```markdown
# {Project Context Name}

{One or two sentence description of what this bounded context covers and why it exists.}

## Domain Language & Terminology

**{Term}**:
{A one or two sentence crisp definition of what the concept IS, not how it is implemented.}
_Avoid_: {Synonyms, overloaded terms, or vague colloquialisms that should not be used in code or prompts}

**Booking**:
A confirmed reservation of a specific court slot by a player, backed by an active deposit.
_Avoid_: Order, transaction, appointment

**Court**:
The physical playing surface allocated for a match session.
_Avoid_: Pitch, field, ground, room
```

## Rules of Engagement

1. **Be opinionated:** Pick the single best term. List confusing alternatives under `_Avoid_`.
2. **Keep definitions tight:** Maximum 1-2 sentences. Define *what it is*, never implementation details (no React hooks, SQL types, or API endpoints).
3. **Domain-only concepts:** Only list concepts unique to this business domain. General programming terms (`timeout`, `error_handler`, `fetcher`) do NOT belong in `CONTEXT.md`.
