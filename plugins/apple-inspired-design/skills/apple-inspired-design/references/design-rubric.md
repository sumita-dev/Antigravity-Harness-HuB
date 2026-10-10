# Independent Design Evaluation Rubric

This is **not** an Apple standard, certification or a numerical interpretation of Apple HIG. It is an engineering aid aligned with HIG concepts such as purpose, simplicity, craft, hierarchy, adaptability and platform context.

## Criteria and weights

| Criterion | Weight | Required evidence |
| --- | ---: | --- |
| Visual hierarchy | 20 | Visual screenshot with identifiable primary content/action |
| Layout and spacing | 15 | Screenshot + DOM/CSS alignment and spacing measurements |
| Typography | 15 | Screenshot with font sizes, weights, line height, reading order |
| Color and contrast | 10 | Screenshot plus actual computed colors/automated contrast checks as available |
| Component consistency | 15 | Comparison of repeated components, tokens and variants |
| Interaction and UX | 10 | Recorded states: hover, focus, form validation, loading/error/empty flows |
| Responsive design | 10 | Comparable screenshots across at least two or more target viewports |
| Motion and polish | 5 | Motion/state evidence and reduced-motion behavior |

### Rating anchors (0..5)

0 observed severe failure (not missing evidence); 1 major failure; 2 substantial issues; 3 usable but inconsistent; 4 clear/cohesive with minor deficiencies; 5 exceptional evidence-backed execution **for this user task and viewport**. Use decimal ratings sparingly. Unobserved or ambiguous criteria: `null` with a reason. A score is not a substitute for a user study.

### Reliability policy

- A metric needs evidence `type`, `ref` and a precise observation. Confidence must be >=0.55 for inclusion; below it the evaluator must mark it unassessed.
- Score must list assessed **coverage** and `technicalGate` separately. Require human review regardless of score.
- Visual analysis is not a code audit: do not claim contrast/WCAG compliance, keyboard behavior or animation performance from screenshot alone.
- Compare equivalent viewports, test fixtures, datasets and application states. Do not optimize the weighted score at the expense of actual user intent.
- Keep raw artifacts local/private unless user approves external analysis.

## Apple source reading

Official Apple design principles: https://developer.apple.com/design/human-interface-guidelines/design-principles

Layout and visual hierarchy: https://developer.apple.com/design/human-interface-guidelines/layout

Accessibility: https://developer.apple.com/design/human-interface-guidelines/accessibility

Playwright accessibility test limitations: https://playwright.dev/docs/accessibility-testing
