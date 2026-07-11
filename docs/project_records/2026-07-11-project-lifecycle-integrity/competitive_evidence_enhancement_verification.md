# Competitive Evidence Enhancement Verification

## Revision target

- Target: `competitive-evidence-enhancement-v0.4.0`
- Round: 1/3
- Final status: accepted
- Scope: absorb bounded traceability, diagnostic, and human-review-routing ideas without introducing network retrieval, a general RAG platform, or a mutable approval UI.

## Implemented

- Added claim-specific evidence locators with safe source basenames, optional page numbers, manuscript lines, one-based CSV data rows, and matched table cells with A1 coordinates.
- Kept each base table evidence item as the complete row while preventing unrelated cells from being presented as every linked claim's precise location.
- Added deterministic `audit_diagnostics.json` with numerator/denominator pairs for link coverage, support-relation coverage, requirement gaps, contradictions, high-risk routing, and unused evidence.
- Added deterministic `human_review_queue.json`; every entry is immutable `pending` work and cannot act as a reviewer decision, identity check, approval, or verification-status override.
- Added static-viewer sections for structural diagnostics, precise evidence locations, and pending review work while preserving legacy-package compatibility.
- Added both new artifacts to governed lifecycle ownership, manifests, replace cleanup, report export, release smoke checks, and legacy share archives.
- Documented the comparison with ValSci, Amazon RefChecker, RAGChecker, and Microsoft HAX, including the features deliberately left outside local-first v1.

## Verification evidence

- Full regression: `347 passed, 2 skipped`.
- Focused enhancement/viewer/archive/mock regression: `35 passed`.
- Release-readiness and sharing regression: `57 passed, 2 skipped`.
- Python bytecode compilation completed for `claim_harness`, `problem_bridge`, and `tests`.
- The documented deterministic demo completed with 16 claims, 26 evidence items, and 67 claim-evidence links.
- Structural demo diagnostics distinguish any-link coverage `15/16` from support-relation coverage `12/16`; the latter explicitly includes weakly supported claims whose requirements may remain unmet.
- The committed sample run was regenerated through governed `replace`; its manifest and completion record hash both new artifacts.
- Independent review found and the round closed two issues: unescaped legacy diagnostic values in HTML and an overstrong `accepted support` metric name. Regression tests now cover the HTML-injection case and the metric is named `support_relation_coverage`.

## Evidence gaps and boundaries

- The in-app browser security policy blocked navigation to the local `file:` viewer. No workaround was used, so this round does not claim screenshot-level visual verification. Static HTML behavior and escaping are covered by automated tests.
- A strict release ZIP build was not run because the user-owned untracked directory `.tmp_academic_writing_toolkit/` makes the repository intentionally dirty. It was preserved untouched. Release-readiness test coverage passed.
- No external Gemini review was run because sending the project diff or screenshots to an external API was not authorized under the available data policy.
- The diagnostics have no gold labels and are not accuracy, faithfulness, hallucination, scientific-validity, or safety scores.
- The pending review queue is not a formal review sidecar. A future reviewer-decision workflow would need its own immutable, hash-bound run and stale-decision checks.
