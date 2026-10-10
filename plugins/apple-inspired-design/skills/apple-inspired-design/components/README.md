# React components (independent implementation)

`src/ui.tsx` exports `Button`, `Card`, `TextField`, `Badge`, `Stack`, `Container`, and `Dialog`. Built for React 18/19 + Tailwind CSS, without Apple assets. For Next.js App Router, components using hooks/events need a client boundary (`'use client'` in the importing wrapper, or add it at the top of the copied `ui.tsx`).

1. Copy `src/ui.tsx` into your application's components directory (or integrate this folder as a workspace package).
2. Install `clsx`; ensure React and Tailwind are installed.
3. Import `../assets/tokens.css` into the global stylesheet (adjust path). Add the copied component source to the Tailwind `content` scan (Tailwind v3) / source discovery (v4).
4. Import the components into a page. Components use Tailwind arbitrary values bound to CSS variables.
5. Run typecheck, automated QA, and manual keyboard/screen-reader checks.

Example:

```tsx
import {Button,Card,TextField,Stack} from './components/ui';
export function Example(){return <Card><Stack><h2 className="text-xl font-semibold">Create project</h2><TextField label="Name" name="name" required/><Button>Continue</Button></Stack></Card>}
```

Warning: `Dialog` is a lightweight starter, not a substitute for a mature audited primitive in complex products (nested dialogs, i18n, inert background, screen reader support). Prefer Radix/Dialog or React Aria for production-critical cases.
