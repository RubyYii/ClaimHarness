# Unified workbench verification · 22 September 2026

Implemented the user-approved ProblemBridge + ClaimHarness merge as one saved problem: confirm its framing, supply materials for a local audit, then record a next action or return a finding to the framing. Existing interview and optional tools remain available.

## Verified behavior

- Interview answers seed an editable problem record; observations, their sources, hypotheses and human boundaries remain distinct.
- The web app runs the existing deterministic audit pipeline on pasted / uploaded text and CSV tables. It does not call a remote provider. Source inputs and generated findings share one governed completion snapshot.
- Evidence conflicts retain claim IDs, source rows/cells and the verifier's reasons. Saving a follow-up does not modify the original verdict. A new framing keeps the problem ID and historical record while clearing the current audit.
- Empty inputs give specific guidance; zero extraction retains a coverage question. Cross-project links, modified source files, invalid CSVs and incomplete runs fail validation.
- Text drafts and selected uploads survive step/tool switches within the session. Changed material drafts are explicitly distinguished from the last saved audit. Saved problem/audit/follow-up records restore after reopening. Unsaved upload bytes remain session-only.
- Share ZIPs include the problem and follow-up records but exclude original inputs by default; explicit source inclusion is tested.

## Tests and CLI demo

- Full suite before the final draft-preservation additions: **522 passed**.
- Final interaction suite: **39 passed**, including uploaded-text precedence, draft preservation, project isolation and the original onboarding/interview flows.
- A final browser check exposed a language-switch navigation issue. Widget labels are now fixed for each render and translated controls use separate UI keys while retaining the logical page, stage and selected finding. The expanded UI, memory and archive suite passed **58 tests**, including the new repeated-language-switch scenario. This adds one regression to the 524-test baseline below.
- Full suite including the two new draft/upload scenarios: **523 passed, 1 failed**. The failure was the isolated release ZIP demo encountering `MemoryError` while reading a temporary manuscript for hashing. After stopping the task's preview processes, the targeted retry **passed in 64.91 seconds**. All **524 tests** were verified across the full run and this retry; the log is `outputs/unified_workbench_20260922/release_retry.log`.
- Required CLI inputs succeeded with `--llm mock`, using the new output directory `outputs/unified_workbench_20260922/lab_report_audit_demo_run` to preserve the pre-existing completed run. All five required audit artifacts and the completion marker were generated: 16 extracted claims, 3 supported, 13 requiring attention. These counts describe the synthetic software check only.
- `git diff --check` passed.

## Actual browser evidence

The real Streamlit app was exercised at 1440 × 1000 and 390 × 844. The browser completed a synthetic audit, recorded an answer, returned it to the problem, reloaded the saved result, restored source materials and switched languages without changing the problem. Actual Markdown/CSV file uploads were retained across steps, produced the stale-result warning before rerunning, and completed a new audit without that warning. No document-level horizontal overflow was observed.

Screenshots are under `outputs/unified_workbench_20260922/`: `home-desktop.png`, `findings-desktop.png`, `final-desktop.png`, `final-mobile.png`, `materials-mobile.png` and `final-english.png`. Screenshots show different workflow stages; they are not measured usability evidence.

Gemini's abstract design-draft request returned HTTP 503. External screenshot submission had already been rejected by automatic approval review earlier in this session. Screenshots were inspected locally; `gemini-agent visual gate --smoke-only` passed readability, type, byte-size and dimension checks. It made no Gemini call and supplies no independent visual judgement.

## Remaining boundaries

The audit is still English-first and rule-based; extraction coverage is unknown. User-entered boundaries are recorded as context and do not compile into custom verifier rules. Follow-up prompts derive from finding categories and evidence locations; they are not an adaptive expert interview. Local tests and screenshot inspection do not establish scientific validity or a measured reduction in learning time.
