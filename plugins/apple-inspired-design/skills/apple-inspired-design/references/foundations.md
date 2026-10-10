# Foundations

Source of inspiration: https://developer.apple.com/design/human-interface-guidelines/

## Purpose and hierarchy
- Prioritize the single most important user goal on each screen. Make primary and secondary actions distinguishable.
- Group related information through spacing, alignment, and surfaces rather than borders everywhere.
- Do not hide critical information behind aesthetics.

## Layout
- Use a consistent spacing scale and purposeful content width; do not treat all surfaces as full width.
- Accommodate resized windows, narrow mobile screens, long labels, localization, zoom, and dynamic text.
- Avoid horizontal scrolling except where intentional and accessible.
- Respect device safe areas on native devices.

## Typography
- Prefer platform system fonts in native applications. For websites, use legal system font stacks or a properly licensed font.
- Keep a clear scale for headings, body, captions and metadata; do not shrink key information to fit.
- Use real semantic headings on web, not just visual font sizes.

## Color
- Use semantic tokens (background, surface, foreground, secondary, accent, border, danger, success).
- Ensure light/dark variants and readable contrast. Never use color alone to indicate status.
- Avoid hard-coded Apple system color values; system native APIs are preferable in native apps.

## Motion and materials
- Animate transitions only when they clarify state or relationships.
- Keep motion subtle and respect prefers-reduced-motion / OS reduced-motion settings.
- Translucency and blur should preserve content contrast; do not default to imitation Liquid Glass.

## Accessibility
- Keyboard and screen reader support; visible focus; sufficiently sized interactive controls.
- Web: aim for WCAG 2.2 AA where applicable; check text contrast 4.5:1 for normal text and 3:1 for large text, with applicable exceptions.
- Test at zoom, large text, narrow viewports, and screen readers where available.

Apple guides are principles, not a universal fixed spacing or radius specification for the web.
