# Improvement Agent

Read `improvement/README.md` and `workflows/design-improvement.md`. Default plan only. Do not auto-execute high-severity, low-confidence, structural, brand or security-sensitive changes. For approved low-risk changes, make the smallest edits, verify via screenshot/technical checks, compare same rubric coverage and stop after at most 3 cycles. Abort on new accessibility/runtime errors or non-improving scores. Always submit Git diff and unresolved risks for human review. An external coding agent is not a trusted sandbox.
