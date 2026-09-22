# Workbench layout polish · 22 September 2026

This pass preserves the accepted journey: describe a real task, confirm the wording, then take a collaborator brief and a language-model task. Optional evidence checking stays available after the handoff.

## Layout changes

- A compact brand and language bar replaces the tall language control; the main introduction uses a smaller heading and less space.
- The current question, progress indicator, input and primary action share one white card. Desktop shows a short explanation of the two outputs beside it; narrow screens put that explanation below the question.
- The review form groups the work and difficulty alongside the expected result and materials. It stacks on mobile.
- Handoffs have separate tabs, green download actions and readable scrollable previews. The confirmed need remains available in an expander above them.
- A bundled `.streamlit/config.toml` supplies the light theme and teal native controls. Scoped CSS handles spacing, focus indicators and responsive layouts without external fonts or image services.

## Verification

Browser checks use an isolated workspace under `outputs/layout_polish_20260922/preview` and invented art-research needs. No private project data is needed for the checks.

- The novice route was completed in the browser, including an unknown material list, review, confirmation, both handoff tabs and both downloads.
- Downloaded Markdown files exactly matched the saved generated files, byte for byte.
- Switching between Chinese and English retained the user's wording. The inspected views showed no Streamlit exceptions or horizontal page overflow.
- Existing targeted workflow and readiness checks: **77 passed, 4 deselected**. The deselected release ZIP tests are included in the full suite.
- Final full repository suite: **531 passed in 245.38 seconds**, including the release ZIP checks. Log: `outputs/layout_polish_20260922/full_suite.log`.
- The required mock CLI demo completed in a fresh output folder with all five required artifacts. Its 16 extracted claims include 3 supported, 13 requiring attention and 3 requiring human review; these are synthetic software checks.
- Final desktop captures use 1440 × 1000; mobile checks use 390 × 844, with an additional English view at 320 × 740. No horizontal page overflow was observed. On the 390-pixel Chinese first screen, both the answer field and Continue action are visible. Tabbing from the answer field reaches Continue with a visible focus outline.
- The final review card, resumed handoff, native theme, language switching and preserved wording were inspected after restarting the app. Local visual smoke checks passed for the screenshots; they did not call Gemini.

Screenshot and command-log evidence is kept locally in `outputs/layout_polish_20260922/`. The README includes [English](figures/workbench-start-en.png) and [Chinese](figures/workbench-start-zh.png) captures of the empty starting screen. Project settings are collapsed; no saved user drafts are shown.

## Review limits

The abstract Gemini design-draft request returned HTTP 503. A bounded UI source review returned HTTP 429 after narrowing an oversized input; no independent Gemini review was obtained. Screenshots are inspected locally. A local visual smoke gate checks image validity and dimensions only and is not an independent aesthetic review. This work does not establish usability improvements with real novice users or cross-disciplinary collaborators.

The Git update includes the previously accepted shared workbench, handoff modules and the audit-core dependencies needed by this runnable version. Local research drafts, submission materials, release records and runtime outputs are outside this source update.
