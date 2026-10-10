# Examples

- `evaluation/samples/sample-review.json`: illustrative scoring input; intentionally low coverage and an unverified technical gate.
- `approved-memory-proposal.json`: **not approved**. Replace with a genuine project decision and supporting record before using `memory-cli.mjs approve`.
- `npm run selftest` at the Skill root: validates core deterministic modules without an API key or running app.

## Integration prompt

"Use apple-inspired-design v4 to audit this React/Next.js app. Preserve current product brand and business logic. Run technical QA and screenshot capture; grade only evidence-backed criteria with the rubric, include confidence and coverage, output score.json/issues.json/report.md, and provide a plan-only prioritized repair list. Do not send screenshots to any external API without asking me, do not update baselines or design memory, and do not modify the app until the initial report is reviewed."
