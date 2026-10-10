# Design audit workflow — agent procedure

1. Determine framework and routes; record the primary user goal, supported devices, current brand, and critical interactions.
2. Technical baseline: run `cd qa && npm run qa:audit` with appropriate `UI_BASE_URL` and `UI_ROUTES`. Record blockers and high findings. Do not mark gate pass if tests fail or did not run.
3. Capture evidence: `cd qa && npm run qa:design:capture`. Inspect screenshots before any external sharing. For private apps, prefer offline review.
4. Read `evaluation/rubric.json` and `references/design-rubric.md`. Audit each route/viewport. Record 0..5 plus evidence only where supported; use null for missing observations.
5. Optionally call the opt-in visual model adapter (only after user approves sending screenshots). Otherwise author JSON reviews locally using the schema in `evaluation/README.md`.
6. Compute score with `node evaluation/scoring-engine.mjs --input ... --out ...`. Open `report.md`, `score.json`, `issues.json`.
7. Summarize technical state, rubric coverage, top 3 UX issues, confidence, screenshots, score limitations and issues requiring human validation.
