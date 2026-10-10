# UI Visual QA (v3)
Run against a test instance of your own React/Next.js app. Requires Node.js 20+, reachable app, and Chromium install.

```bash
cd qa
npm install
npx playwright install chromium
UI_BASE_URL=http://127.0.0.1:3000 UI_ROUTES=/,/dashboard npm run qa:audit
npm run qa
UI_VISUAL=1 npm run qa:visual
```

Windows PowerShell:
```powershell
$env:UI_BASE_URL='http://127.0.0.1:3000'
$env:UI_ROUTES='/,/dashboard'
npm run qa:audit
```

Outputs: `qa/artifacts/visual-qa/{audit.json,report.md,*.png}`. Exit status 1 means high/blocker findings. Axe minor/moderate issues appear in report but do not independently fail the audit process. `npm run qa` tests serious/critical violations and horizontal overflow.

Set `UI_VISUAL=1` to compare screenshot snapshots. Only after reviewing expected changes, run `npm run qa:visual:update` locally, commit approved baselines, and compare on CI. Avoid auto-updating snapshots. Screenshots can contain private content; don't commit raw captures.

The audit takes 3 fixed viewports, intentionally suppresses motion, uses default unauthenticated state and light theme; extend tests for real auth flows, dark mode, keyboard UX and responsive behavior. Pixel comparison is platform/browser dependent. If your site redirects to external auth, configure a local test login; do not bypass the cross-origin protection.

## v4 design capture

```bash
# Run after starting your app and installing qa dependencies above
UI_BASE_URL=http://127.0.0.1:3000 UI_ROUTES=/,/dashboard npm run qa:design:capture
```

Generates `qa/artifacts/design-capture/capture.json` and one PNG for each route/viewport. Metadata contains computed styles, tag/role/type, bounding boxes and counts, but **not** UI textual content. Screenshots may nevertheless include sensitive or proprietary information. Design capture does **not** independently assess beauty or UX. Use the opt-in AI critic or human review plus `evaluation/scoring-engine.mjs`. Always inspect captures before sharing them externally.
