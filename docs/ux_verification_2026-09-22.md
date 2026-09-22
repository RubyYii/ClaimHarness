# Workbench interaction verification

Verified locally on 22 September 2026 (Europe/London). This checks implementation and usability mechanics, not measured improvements in first-time users' learning time.

## Delivered behavior

- Home offers a working one-click synthetic example and three task-based entry routes. Advanced navigation, project settings and technical explanations are collapsed.
- The interview shows the number of saved answers, provides examples in each input, allows corrections before completion, and preserves later answers when an earlier one changes.
- Home resumes an interview or opens a validated completed result belonging to the active project. Explicitly saved workspace memory now includes interview answers and the original project identity.
- Success feedback describes the next action. Empty results provide a working Home button. Failures keep the current interview and show retry guidance.
- Unopened cleanup controls no longer inspect historical runs. Result history scopes by project before checking artifact hashes.
- The native sidebar expansion control remains available on narrow screens.

## Checks

- Full suite: **505 passed**, 149.44 seconds.
- After the final interview layout changes: **33 related UI/memory tests passed**. The subsequent CSS-only sidebar correction was checked directly in the browser.
- Seven new user-journey tests cover example generation, failure recovery, editing and completing an interview, resumption and language switching, persistence across reopening, lazy history inspection, and empty-state navigation.
- Mock audit demo completed with the five required output files and a valid completion snapshot. The existing demo output directory was retained; this run used `outputs/ux_review_20260921/lab_report_audit_demo_run`.
- Browser: Chinese and English Home, actual sample generation, result display, interview submission, resumption, keyboard focus/Enter navigation, and mobile sidebar navigation.
- At **1440 × 1000**, the old Home route buttons began at approximately **y = 2126 px**. The new sample action starts at **y = 409 px**, and all three route actions at **y = 713 px**.
- At **390 × 844**, the sample action starts at approximately **y = 645 px**. Document width remains 390 px, and the sidebar can be opened to navigate into the interview.
- `git diff --check` passed (existing CRLF normalization warnings only).

## Visual evidence

Screenshots are under `outputs/ux_review_20260921/`:

- `before-home.png`
- `after-home-zh.png`
- `after-home-en.png`
- `after-home-mobile.png`
- `after-home-resume.png`
- `after-interview-desktop.png`
- `after-mobile-interview.png`
- `after-result.png`

Local Gemini-agent `visual gate --smoke-only` checks passed for desktop and mobile screenshot files. These checks inspect the image files, not visual usability. Local browser screenshots were also inspected directly. The external Gemini design call returned HTTP 429, and automatic approval review rejected screenshot egress because of the project identifier and configuration text. No external visual review was completed.
