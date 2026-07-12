# External Review Closure Verification — v0.4.0

- Date: 2026-07-11
- Revision target: `external-review-closure-v0.4.0`
- Diagnosis: `version_contamination`
- Round: 1 of at most 3
- Decision: accepted

## Scope

The attached external review described a mixture of older and current repository states. This round reconciled all 14 issue classes against the current v0.4.0 source before changing code. Findings that were already fixed were recorded as such; remaining work was limited to core decision boundaries, URL intake provenance/MIME safety, viewer interaction consistency, and capability-truth documentation.

## Accepted changes

- Separated deterministic verification status and risk from `human_review_required` and `release_allowed` across CSV, Markdown, diagnostics, review queue, run manifest, trace, CLI, and the static viewer.
- Added model-level fail-closed invariants so high-risk, overclaimed, contradictory, or review-required results cannot be release-allowed when constructed outside the main verifier path.
- Upgraded diagnostics and review-queue artifact semantics to schema 2; split the gold-input schema (`1.0`) from the evaluation-report schema (`2.0`).
- Projected the review/release gates into gold evaluation and required both explicit human-review routing and release blocking for a safe high-risk decision.
- Replaced duplicated self-evidence rules with one canonical predicate: exact duplicates and same-span near-duplicates are blocked, while independent sentences sharing a source line remain eligible candidates.
- Added bounded verdict reasons and revision guidance to the verifier trace.
- Limited share-safe URL provenance to the final validated origin, removed path/query/fragment leakage, retained final redirect attribution, checked the final response MIME, and updated the intake User-Agent to v0.4.0.
- Updated English and Chinese README/showcase wording, limitations, the 14-issue reconciliation matrix, generated sample outputs, and viewer filters/metrics.

## Verification evidence

- Full suite: `386 passed, 2 skipped`.
- Final focused CLI/viewer/intake/release regression: `112 passed, 2 skipped`; an earlier combined core/security/docs gate also passed `158` tests with `2` environment-dependent skips.
- Python compile check: `python -m compileall -q claim_harness problem_bridge apps` passed.
- Diff hygiene: `git diff --check` passed; only line-ending conversion warnings were reported.
- Offline gold evaluation: claim F1 `0.833333`, status macro-F1 `0.866667`, high-risk miss rate `0.333333`; these are synthetic English-first regression metrics, not real-world validity evidence.
- Fresh governed mock audit: 16 claims, 3 supported, 13 weak-or-worse, 2 human-review-required, 13 release-blocked, package release gate false, and 16 structured verdict decisions.
- Browser interaction gate at 1280×720: 16 claim rows, 2 priority-review rows, 2 human-review rows, 13 needs-action rows, no document-level horizontal overflow.
- Browser interaction gate at 390×844: no document-level horizontal overflow; navigation and the claim table retained their own horizontal scrolling; review/release summary cards remained visible.
- The regenerated tracked sample passed lifecycle identity/hash checks and was rendered successfully by the governed viewer.
- Three independent read-only reviews covered core semantics, URL/docs safety, and sample-package consistency. Their actionable findings were resolved before acceptance.

## Explicitly deferred boundaries

- Chinese claim extraction/retrieval/verification remains unvalidated until a versioned Chinese gold set reaches an explicit acceptance threshold.
- The Streamlit workbench still inspects existing audit packages; direct ClaimHarness execution remains a CLI boundary.
- The pending review queue does not verify reviewer identity, record approval, or grant release authority.
- General upload-size limits, DOCX decompression budgets, non-OCR PDF page budgets, and a whole-request URL deadline/IP fan-out cap remain incomplete.
- Complete executable replay, typed external reviewer packages, and real-world validity studies remain future work.

No repository content or screenshots were sent to an external Gemini service because external data sharing was not authorised. User-owned changes to `docs/figures/github-workflow.svg` and local `.tmp*` paths were preserved and excluded from this revision.
