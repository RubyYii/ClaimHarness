# Main integration and homepage update — 2026-10-18

The two-way handoff and compatibility fixes from development commit `ee7424718dc68bf50c68d1e48d6d3438f1e0dd3e` were integrated with main commit `dd4ac188f22b1f0bab39647eaae4164548bf8e9c`. The containing Git commit is the final identity of this update.

## Scope

- Application modules under `apps/`, `problem_bridge/` and `claim_harness/` match the already verified development commit byte for byte. The merge retains main's existing compatibility records, portable agent skills and problem/evidence exports.
- English and Chinese READMEs now lead with the two-way handoff, an editable SVG flow, and an actual screenshot of B reviewing A's response.
- The three static showcase files describe the current handoff and keep advanced tools, examples, local setup and evidence-audit boundaries. They are read-only HTML files; this change does not enable GitHub Pages or host the Streamlit app.
- [First individual test](first_round_single_participant.md) is an exploratory proposal. Its quantities and timing are planning choices, not completed participant results. The concrete domain remains subject to formative work.

## Verification

- `python -m pytest -q`: **630 passed in 212.10 seconds** on the merged Windows checkout, including the existing release checks. Subsequent wording and step-number edits affect documentation only; the affected homepage checks were repeated.
- The required lab-report command with `--llm mock` completed and produced `claim_table.csv`, `evidence_map.json`, `audit_report.md`, `revision_suggestions.md` and `agent_trace.jsonl`.
- Local links in both READMEs, all three showcase pages and the individual-test guide resolve. English/Chinese showcase checks at 1365 px and 390 px found no document-level horizontal overflow or missing screenshot images.
- A bounded Gemini 3.5 Flash review of the public homepage diff returned `pass`. No local research drafts or participant records were sent.
- Gemini visual review returned `caution`, not a visual pass. The mobile sequence gained explicit 1–2–3 labels. Other suggestions concerned small link/header text and secondary contrast. The SVG secondary color has a calculated 7.50:1 contrast on white and 6.96:1 on its pale background; this calculation is not a complete accessibility audit. Language links retain standard README styling. Actual-user readability remains to be tested.

## Figure provenance

`figures/two-way-handoff-en.svg` and `figures/two-way-handoff-zh.svg` are editable vector diagrams. `figures/handoff-review-en.png` and `figures/handoff-review-zh.png` are unaltered 1365 × 1050 browser screenshots of the real Streamlit app. Synthetic registration messages were prepared through the application's own confirmation and response APIs, then opened at revision 2 for B's pending review. The screenshots show the before/after wording, an unresolved date and B's review form. They are demonstration states, not evidence of a human study or completed mutual understanding.

Historical published research files were retained unchanged from the development branch. Uncommitted files in the user's original checkout were not included.
