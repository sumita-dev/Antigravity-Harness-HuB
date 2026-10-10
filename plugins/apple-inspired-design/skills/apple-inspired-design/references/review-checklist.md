# Design review checklist

Report findings as BLOCKER, MAJOR, MINOR. Include file/route, observation, proposed fix, and whether verified.

## Blockers
- Critical workflow fails or action cannot be completed.
- Keyboard interaction absent for essential action, misleading semantics, inaccessible critical content.
- Serious viewport overflow preventing use or lost data / destructive action without appropriate safeguards.

## Major
- Missing error/empty/loading states, confusing navigation, unacceptable contrast, focus obscured, poor mobile behavior.
- Inconsistent primary actions, illegible type at zoom / dynamic type, reduced-motion preference ignored.

## Minor
- Inconsistent spacing/radii, weak alignment, unnecessary visual complexity, excessive decoration.

## Test matrix
- Mobile small viewport, tablet, desktop / resizable window
- Light/dark and increased contrast where supported
- 200% browser zoom, larger native text
- Keyboard-only and focus visibility
- Screen reader smoke test where available
- Loading, empty, error, disabled, success states
- Long translated strings and data-heavy screens
- Reduced motion and low-performance hardware

## Output template
1. Overall assessment (not a made-up numeric score)
2. Blockers
3. Major concerns
4. Minor improvements
5. Proposed changes and what was actually tested
