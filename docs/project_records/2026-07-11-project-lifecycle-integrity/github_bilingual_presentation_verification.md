# GitHub Bilingual Presentation Verification

Target: `github-bilingual-presentation-v0.4.0`

Status: accepted in round 1 of at most 3.

Diagnosis: structural mismatch. The English and Chinese repository-facing surfaces described different workflow depth, interaction updates, audit records, and UI/CLI boundaries, so this work was recorded as a new target instead of extending an already accepted UI target.

## Scope

- Added matching three-step quick starts and explicit workbench-versus-CLI boundaries to both READMEs.
- Updated the English and Chinese static showcases to the same eight-section structure and exact five-step workflow.
- Documented the current navigation, result context, reset safeguards, project-bound memory, searchable report viewer, export behavior, diagnostics, human-review queue, trace files, and three-round revision records in both languages.
- Updated the shared language landing page with a read-only boundary, v0.4.0 marker, keyboard focus support, language metadata, and current feature summaries.
- Added regression assertions that require matching section identifiers, exactly five workflow steps, current audit records, and the same UI/CLI responsibility boundary in both languages.
- Preserved the unrelated in-progress `docs/figures/github-workflow.svg` change and temporary user files without editing or staging them.

## Verification

- Full regression: `362 passed, 2 skipped`.
- Release-readiness suite: `42 passed, 2 skipped`.
- `git diff --check` passed; the only output was the repository's existing CRLF-to-LF normalization warning for the edited test file.
- Python's standard HTML parser read `index.html`, `en.html`, and `zh-CN.html` successfully.
- Local desktop browser checks found eight matching section IDs, five workflow steps, five navigation links, and no page-level horizontal overflow in either language.
- Local 375-pixel browser checks found no page-level horizontal overflow; the five-step workflow correctly scrolls inside its own container in both languages.
- The bilingual landing page exposed two language choices, a valid `main-content` target, and separate block-level descriptions and action tags after the narrow-screen layout fix.
- A fresh governed deterministic mock audit completed with 16 claims and produced `claim_table.csv`, `evidence_map.json`, `audit_report.md`, `revision_suggestions.md`, and `agent_trace.jsonl` without overwriting the older legacy demo directory.

## External review boundary

Repository content and screenshots were not sent to the external Gemini API because this project session did not clearly authorize external transmission. Visual verification was completed locally in the in-app browser instead.
