# v2 Visual & accessibility QA workflow

1. Identify entry route(s), app start command, backend prerequisites and stable fixture data.
2. Run typecheck and framework build; fix compile errors first.
3. Start app separately and run `qa/` Playwright suite with `UI_BASE_URL` and `UI_ROUTES`.
4. Use axe findings for high-impact violations; also audit keyboard focus, screen readers, visible focus, zoom, reduced motion, and meaningful empty/loading/error states manually.
5. Set `UI_VISUAL=1` to compare reviewed screenshots against committed snapshots. On first run, generate with `npm run qa:update`, then review images visually before committing.
6. Report passes/failures with command, viewport, route, and screenshots. Never claim tests passed without execution.

Do not remove tests to silence defects. Avoid fragile screenshots of dynamic content.
