# Design improvement workflow — agent procedure

1. Review `workflows/design-audit.md` output and approved `design-system/design-memory.json`. Respect existing brand, functionality, scope and architectural boundaries.
2. Build plan-only tasks with `node improvement/guarded-loop.mjs --repo ... --issues ... --score ...`.
3. Separate low/medium evidence-backed cosmetic/component issues from architecture/branding/high-severity issues requiring approval.
4. Implement smallest authorized changes in a feature branch; never update snapshot baselines or approved Design Memory as an automatic way to pass scoring.
5. Rerun technical QA, all three viewports and AI/human evaluation **on changed UI**, checking score, coverage and technical gate.
6. Stop after <=3 cycles, immediately on any regression, reduced coverage or no meaningful improvement. Do not equate a higher score with user success.
7. Present before/after screenshots, Git diff, issues fixed, tests run, remaining risks and human-review checklist.
