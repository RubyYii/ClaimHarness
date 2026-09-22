# Cross-disciplinary entry verification · 22 September 2026

The primary workbench now prepares a user-confirmed need for a collaborator or a language model. Evidence checking remains optional. The implementation uses local predefined questions and document rendering; it does not contact recipients, call a model or perform specialist interpretation.

## Verified behavior

- A novice can describe one real task, answer or skip three subsequent questions, go back, and edit before saving. No manuscript, CSV or file upload is required for either handoff.
- Professional background, desired collaborator contribution, term meanings and examples/counterexamples, acceptance checks and human boundaries persist with the same problem. Unknown meanings remain questions. Draft edits are distinguished from the last confirmed handoffs.
- Both recipients receive the same confirmed wording and framing fingerprint. English and Chinese document labels are available; user wording is not automatically translated. Browser downloads were byte-for-byte identical to the saved Chinese collaborator and model-task files.
- The optional audit carries the need context forward. A changed need clears its current audit association and retains prior snapshots. An actual pre-change schema-1 audit record with no handoff files was successfully loaded without modification.
- UI tests cover multiple terms, corrections, skip/back actions, language switching, reopening, manually saved unfinished drafts, project isolation, old interview entry points and the audit workflow.

## Tests

- Initial targeted regression after fixes: **33 passed in 40.45 s**.
- Complete repository suite: **531 passed in 210.06 s**. Log: `outputs/cross_disciplinary_20260922/full_suite.log`.
- After reducing document-preview heading sizes: **26 passed in 27.72 s** for the new handoff and unified audit journeys.
- After correcting the mobile hero-title CSS specificity: **7 passed in 10.49 s** for handoff journeys and the workbench shell.
- `git diff --check` passed.
- The required synthetic lab-report inputs ran with `--llm mock` in a fresh output directory, preserving prior runs: `outputs/cross_disciplinary_20260922/lab_report_audit_demo_run`. All five required artifacts and completion integrity were verified. The synthetic audit extracted 16 claims: 3 supported, 13 requiring attention and 3 requiring human review. These counts are software checks, not empirical product validation.

The first test attempt could not create its sandboxed temporary directory; the isolated tests subsequently ran with approved filesystem access. Early regression failures caught a Streamlit button accidentally included in draft preservation and inconsistent Windows newline handling in handoff bytes; both were fixed before the passing runs above.

## Browser evidence

An isolated preview under `outputs/cross_disciplinary_20260922/preview` was exercised at 1440 × 1000 and 390 × 844. A synthetic archive researcher described a task for a software colleague, skipped unknown materials, supplied a term and counterexample, confirmed both briefs, downloaded both, reopened the app and switched interface languages. No document-level horizontal overflow was observed. Native sidebar collapse was used for mobile content inspection.

Screenshot evidence is in `outputs/cross_disciplinary_20260922/`:

- `final-start-desktop.png` and `final-start-mobile.png`: new-user entry.
- `final-model-desktop.png` and `final-model-mobile.png`: compact model-task preview and download controls.
- `browser-collaboration.md` and `browser-model-task.md`: files downloaded through the actual browser.

Screenshots were inspected locally. The abstract Gemini design request returned HTTP 429 (daily request quota). The local `gemini-agent visual gate --smoke-only` checks passed file readability, format, size and dimensions; they do not constitute an independent Gemini visual judgement. No screenshot content was sent to an external model during this change.

No external novice study or cross-disciplinary collaboration trial was performed. Passing tests and screenshots do not establish reduced learning time, correct domain interpretations, agreement between participants or successful downstream model execution.
