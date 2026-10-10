# Evidence-led Design Evaluation (v4)

## Rubric and evaluation contract

Weights: visualHierarchy=20, layoutSpacing=15, typography=15, colorContrast=10, componentConsistency=15, interactionUX=10, responsive=10, motionPolish=5. See `rubric.json` and `references/design-rubric.md`.

Each review is for exactly one route and viewport. `metrics` is an object keyed by rubric ID. A rated item needs score 0..5, confidence >= 0.55, a written summary and at least one evidence object `{type,ref,observation}`. Types: `screenshot`, `dom`, `test`, `interaction`, `token`, `manual`. An unassessed item has `score:null` and `reason`. Score 0 indicates observed severe failure; missing evidence is **never scored as zero**.

```json
{
  "source": "human-review",
  "technicalGate": "pass",
  "reviews": [{"route":"/dashboard","viewport":"desktop-1440","metrics": {
    "visualHierarchy": {"score":4,"confidence":0.85,"summary":"Main CTA is clearly distinguished.","recommendation":"Minor refinement only.","evidence":[{"type":"screenshot","ref":"capture/example.png","observation":"Primary CTA in top-right dominates secondary buttons."}]},
    "motionPolish": {"score":null,"reason":"No motion sample was collected."}
  }}]
}
```

Other metrics can be omitted (reported unassessed). `technicalGate` must be one of `pass`, `fail`, `unverified`; `pass` should be based on actual QA, not a model guess.

```bash
node evaluation/scoring-engine.mjs --input review.json --out artifacts/design-quality
node evaluation/scoring-engine.mjs --input review.json --out artifacts/design-quality --strict
```

Generated files: `score.json`, `issues.json`, `report.md`. `--strict` exits code 2 if score is not trustworthy; trustworthiness requires technical gate pass, average evaluated weight >=75%, and at least one rated item. Passing does **not** mean a good score or design approval. Score is weighted average over **assessed** metrics only; every report shows coverage to prevent misleading comparisons. Compare two scores only with similar coverage and matching routes/states.

## AI visual critic — opt-in

1. Run `cd qa && npm run qa:design:capture`. It produces images and metadata.
2. Review screenshots for secrets, personal data, licensed/private UI or tokens before sending to an API. The capture script avoids collecting text content in metadata, but screenshots **may contain sensitive data**.
3. Set `GEMINI_API_KEY`, `UI_CRITIC_MODEL` (`gemini-2.5-flash` or `gemini-2.5-pro`), `UI_ALLOW_EXTERNAL_IMAGES=1`.
4. Run `node evaluation/critic-gemini.mjs --capture qa/artifacts/design-capture/capture.json --out qa/artifacts/design-quality/ai-review.json` from the skill root.
5. Optionally add `--technical-audit qa/artifacts/visual-qa/audit.json` to ground the gate. Without it gate is unverified.
6. Inspect the generated review before running scoring. The model can misread screenshot details, and cannot validate UX flows or disabled-motion states just by looking at static imagery.

The adapter sends each PNG plus sanitized DOM metadata to Google Gemini Vision API and requires structured output. It does not send files to any service unless explicitly enabled; the API call can incur cost. The design critic does **not** approve/commit code and is **not** part of default CI.

## Model-agnostic option

Any AI agent (Claude, Codex, Antigravity etc.) may produce the same JSON review by inspecting the supplied screenshots and rubric. Pass the output through the local deterministic scoring engine. This avoids binding the scoring pipeline to one provider. Never instruct the AI to fabricate missing scores or interaction evidence.

### Responsive comparison mode

By default the model receives one screenshot per review, so `responsive` is **unassessed**. Set `UI_COMPARE_VIEWPORTS=1` to explicitly include the other collected viewport images of the same route (up to two additional screenshots per review). This costs additional image tokens and reveals more visual content to the model. Responsive scoring still requires evidence-backed commentary and a human check.
