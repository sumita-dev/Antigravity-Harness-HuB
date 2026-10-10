# Web implementation (React, Next.js, Tailwind)

Apple does not publish a universal Apple.com web CSS design system. Treat the values below as **project defaults**, not Apple's mandatory numbers.

## Implementation sequence
1. Inspect component library, CSS architecture, routing, responsive breakpoints and brand palette.
2. Adopt existing semantic tokens first. If absent, consider `assets/tokens.css` and adapt per brand.
3. Use semantic HTML (`button`, `nav`, `main`, `label`, `fieldset`, `dialog` where appropriate), accessible names and keyboard interactions.
4. Use CSS Grid/Flexbox with fluid widths; responsive mobile-first layouts; test 320px up to desktop sizes and 200% zoom.
5. Build stateful components: hover/focus/active/disabled, empty/loading/error/success, validation and feedback.
6. Avoid excessive heavy animations, nested blur/filter, and hydration mistakes.

## Visual principles
- Use a restrained palette and strong text contrast.
- Keep typographic hierarchy more important than ornamental chrome.
- Prefer subtle dividers and restrained shadows; use grouping via spacing.
- Give primary actions prominence without repeating them everywhere.
- Use an 8px-oriented rhythm as a **suggestion**, allowing 4px half steps where needed.
- Typical rounded corners can range from 8px to 20px based on component and brand; these are **not official Apple specs**.

## Tailwind tips
- Centralize colors/radii/spacing in theme tokens, rather than repeated arbitrary classes.
- Use `focus-visible` styling, `motion-reduce`, and dark variants.
- Keep responsive behavior semantic; avoid fixed-width controls that overflow.
- For icons, use a properly licensed icon set; SF Symbols has platform restrictions, so do not assume it is suitable for web.

## React/Next.js tips
- Prefer server-rendered static content when appropriate, use client components for actual interaction.
- Use reusable composable components and avoid reinventing accessibility-heavy widgets if an established library is present.
- Support loading and errors for async data; avoid blank skeleton-only screens.
