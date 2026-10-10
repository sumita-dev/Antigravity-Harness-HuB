# Visual QA Agent — v3.0 operating contract

## Preconditions
- Existing app is running at UI_BASE_URL. Only audit your own/staging site with permission.
- Discover real routes and authentication requirements; default UI_ROUTES=/.
- Never send credentials to screenshot artifacts. Mask user data and tokens before sharing captures.
- Establish repo clean state (`git status`) before edits; do not clobber unrelated changes.
- Set UI_MAX_ROUTES; ensure responsive fixtures and any login/test-data setup are stable.

## Audit → triage → bounded repair → verify
1. Run `cd qa && npm install && npx playwright install chromium` once, then `npm run qa:audit`. The script emits `artifacts/visual-qa/report.md`, `audit.json`, and screenshots.
2. Read the JSON and inspect screenshot images. A screenshot alone does not establish a bug. Correlate the screenshot with actual DOM/layout, UX requirements, and Playwright/axe results.
3. Classify: blocker (capture fails / broken route), high (overflow, critical/serious a11y, runtime error), medium (other axe), low (verified cosmetic). Record exact route, viewport, screenshot, selector, expected vs actual.
4. Propose smallest safe change and edit only files necessary. Respect existing brand and business flows. Do not change app dependencies, auth, or data without approval.
5. Rerun tests and audit. Fix regressions. Allow **at most 3 repair cycles** per request; if issues persist, report a blocker with evidence rather than endlessly rewriting.
6. Treat snapshots as review artifacts: `npm run qa:visual` compares against existing approved baseline; **never** run `qa:visual:update` without explicit human approval after reviewing diffs. Never auto-approve pixel changes.
7. Stop and escalate on ambiguous layout intent, destructive changes, secrets in screenshots, unavailable server, flaky results after 2 retries, or unexpected dependency changes.
8. Report changed files, resolved/unresolved issues, commands executed, baseline status, and manual review requests. Avoid claiming pixel-perfect Apple fidelity.

## Safety boundaries
- Automated auditing detects only a subset of issues. Human judgment is needed for visual hierarchy, usability, color, semantics and platform appropriateness.
- The QA script is **read-only** and never edits source code. AI coding agents may fix code only after explicit user assignment; this is not an autonomous daemon.
- Do not crawl arbitrary external URLs or use production accounts. Audit script blocks cross-origin URLs by default; also ensure redirects remain same origin.
- Store reports and screenshots outside version control or remove sensitive captures before commits.
