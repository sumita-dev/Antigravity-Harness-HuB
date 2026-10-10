# Controlled Improvement Loop (v4)

## Overview

`guarded-loop.mjs` is a coordinator for **trusted external** coding-agent commands. It is not a secure sandbox. The default action is **plan only**; no code edits are made. It reads the evidence-backed `issues.json` and a scored `score.json` from the evaluation engine.

### Plan-only example (recommended starting point)

```bash
node improvement/guarded-loop.mjs \
  --repo /path/to/your-app \
  --issues artifacts/design-quality/issues.json \
  --score artifacts/design-quality/score.json \
  --out /tmp/apple-design-plan
```

It will emit `repair-plan.json`. Only low/medium severity items with confidence >=0.80, existing evidence, actionable recommendation and no human-approval flag are eligible. **High severity requires human review** regardless of model confidence.

### Opt-in execution

Use only on a clean Git branch with a known/trusted coding-agent adapter and a way to recover source changes. Do not use a command you haven't inspected. Execution is intentionally unavailable without:

- `--execute` **and** `UI_ENABLE_AUTO_FIX=1`.
- `UI_FIX_COMMAND_JSON='["node","scripts/your-trusted-fixer.mjs"]'`: trusted command run in the target repository. It receives `UI_REPAIR_PLAN` and `UI_REPAIR_CYCLE`. It may modify source code.
- `UI_VERIFY_COMMAND_JSON='["node","scripts/your-qa-and-scoring.mjs"]'`: command must rerun the technical QA AND produce an updated score JSON from inspected post-change screenshots.
- `UI_SCORE_RESULT='artifacts/design-quality/score.json'`: verification output location, resolved relative to app repository.
- `UI_ALLOWED_EDIT_PREFIXES='src/components,app/dashboard'`: conservative subdirectory allowlist. Do **not** allow the entire repository.
- `UI_MAX_CYCLES=3` (1..3), optional `UI_TARGET_SCORE=90`.

Baseline must be trustworthy (`technicalGate=pass`, adequate coverage); target repo must have a **clean Git working tree**. Each cycle checks modified paths, verified score improvement >0.1, unchanged/higher coverage and passing technical gate. On any failure it **stops** with files left for human review; it does NOT silently revert or commit. Updates to `.github`, `.env`, `design-memory.json`, snapshot directories, `tokens.css` and lockfiles are forbidden in the post-fix guard.

Caution: the filesystem check happens **after the external command executes**. This does NOT prevent a malicious/unreliable command from reading secrets, making network calls or changing files outside the repository. Use trusted tooling, reviewed permissions and workspace isolation as appropriate.

## Mandatory human approval

Approve before: changing product branding, navigation architecture, critical UX flows, color system, snapshot baselines, tokens, or approved design memory. Never automatically bump visual snapshots to make a failing test pass.

`loop-history.json` captures progress, including score, coverage, technical gate and modified files. Inspect `git diff` and rerun important manual flows before merging.

The verification command must not only rewrite a score JSON: it must actually rerun QA/capture/review with fresh evidence. For legitimate score comparisons, use matching routes and viewports with comparable test state; the orchestrator checks scope when both reports include `results`. The system is not a replacement for manual product UX validation.
