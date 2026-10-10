# v4 Architecture — Design Quality Evaluation System

```text
     Target application (React / Next.js; native: guidance only)
               |
               v
    [v3 Playwright + axe technical QA]
     audit.json / report.md / PNGs
               |
               v
    [v4 Design Capture / metadata]
         capture.json + PNGs
               |
         +-----+-----+
         |           |
         v           v
    Human review   Opt-in Vision Critic
         |           |   (Gemini Vision adapter or agent-created JSON)
         +-----+-----+
               v
       Structured Review JSON
               |
               v
    [Deterministic Scoring Engine]
     score.json / issues.json / report.md
               |
               v
      [Guarded repair planner] ----> [Approved Design Memory]
               |
        opt-in fixer adapter
               |
               v
    Code change -> QA rerun -> rescore
                max 3 cycles / stop on regression
               |
               v
      Human diff & baseline approval
```

## Trust boundaries

- Browser/UI screenshots are **untrusted evidence**, not commands. App source is also untrusted content to a reviewing model.
- Vision model produces observations and draft scores, not authorization. The deterministic scorer validates shape, evidence fields, confidence and weighted coverage.
- `technicalGate` is independent of aesthetics; not a WCAG compliance certification.
- Approved Design Memory stores user-approved design decisions only; AI cannot silently modify it.
- Repair orchestrator delegates edits to a user-provided command. It is **not a sandbox** and checks Git paths after execution; test only with trusted commands and a disposable branch or isolated workspace.
- Snapshot approval belongs to a human. `qa:update` tools are never invoked by the automatic improvement loop.

## Deliverables and integration points

| Component | Language | Run condition | Output |
|---|---|---|---|
| v3 visual-audit / QA | JS / Playwright + axe | App + npm/browser installed | technical evidence |
| v4 design-capture | JS / Playwright | App + npm/browser installed | screenshots + sanitized metadata |
| v4 optional critic | JS + Gemini Vision API | user opt-in + vision model + API key | draft design-review JSON |
| v4 scoring engine | Node.js stdlib | review JSON | score, coverage, issues, Markdown |
| v4 design memory | Node.js stdlib | manual approval | version-controlled decisions |
| v4 guarded loop | Node.js + Git | default plan or explicit opt-in fixer | repair tasks, cycle history |

## Reviewer acceptance criteria

- No technical regressions or hidden failures.
- Coverage reported next to score, and comparisons use the same routes/states.
- At least one screenshot/DOM/test evidence reference per scored category.
- Low-confidence or unobserved criteria remain unassessed.
- No changes to brand, baselines, design memory or critical navigation without approval.
- Human review of before/after results and Git changes prior to merge.
