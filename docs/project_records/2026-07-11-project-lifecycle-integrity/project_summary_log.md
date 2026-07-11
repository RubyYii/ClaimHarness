# Project Summary Log

## Project

- ID: claimharness-v040-lifecycle-integrity
- Name: ClaimHarness v0.4 lifecycle integrity upgrade
- Goal: Prevent project/run contamination, cap repeated revision at three rounds, and make evidence, OCR, sharing, evaluation, and release provenance auditable.
- Revision rule: maximum 3 rounds per target; no fourth patch.

## Boundaries

- Keep the local-first deterministic mock pipeline working without API keys.
- Do not treat OCR text or generated contracts as scientific validation.
- Do not modify unrelated user workspace content.

## Artifact Index

- revision_history.jsonl
- project_summary_log.md
- project_record.json
- round_1_verification.md
- round_2_verification.md
- round_3_verification.md
- windows_deep_path_release_verification.md

## Revision History

### project-lifecycle-integrity-v0.4.0 — round 1/3

- Revision ID: 47f00f2b-2c2a-4852-9d39-c7578e4d9fb3
- Parent revision: None
- Time: 2026-07-11T06:59:41.209285+00:00
- Diagnosis: version_contamination
- Status: needs_revision
- Change: Added project/run identities, workflow and run-spec binding, exact completion snapshots, safe new/resume/replace semantics, lock-protected writers, and privacy-preserving run/project deletion and sharing.
- Verification: Lifecycle, CLI, UI archive, concurrency, tamper, nested-artifact, and deletion recovery tests passed in targeted runs.
- Integrity SHA-256: de0d92d694a6f0cc9c2f2ad9dbf01e2a92b50ffa981932d61fccb82b41f70e82
- Changed files:
  - problem_bridge/project_lifecycle.py
  - claim_harness/cli.py
  - problem_bridge/cli.py
  - apps/problem_bridge_wizard.py

### project-lifecycle-integrity-v0.4.0 — round 2/3

- Revision ID: 66cc1a64-3153-4d11-8725-73b8aeb60509
- Parent revision: 47f00f2b-2c2a-4852-9d39-c7578e4d9fb3
- Time: 2026-07-11T06:59:41.219503+00:00
- Diagnosis: evidence_gap
- Status: needs_revision
- Change: Bound executable evidence contracts to project/content identity, blocked narrative evidence promotion, propagated OCR provenance, added OCR resource limits and mixed-PDF warnings, expanded evaluation risk metrics, and hardened reproducible release gates.
- Verification: Full suite reached 280 passing tests with only stale generated samples, a sidebar assertion, and network-dependent clean-install smoke remaining; all three were then addressed or isolated.
- Integrity SHA-256: 3f6e29251c1ffd80d08cbde7e9e641bf11f7fb6cf82bf3d360856ff300f056b9
- Changed files:
  - claim_harness/evidence_contract.py
  - claim_harness/verifier.py
  - problem_bridge/document_intake.py
  - claim_harness/evaluation.py
  - scripts/build_release_zip_powershell.ps1
  - scripts/test_release_zip_powershell.ps1

### project-lifecycle-integrity-v0.4.0 — round 3/3

- Revision ID: af24abad-5558-4b1a-a26b-ff2456c41206
- Parent revision: 66cc1a64-3153-4d11-8725-73b8aeb60509
- Time: 2026-07-11T08:03:47.294523+00:00
- Diagnosis: structural_mismatch
- Status: accepted
- Change: Closed crash recovery, snapshot replacement, deletion identity/TOCTOU, safe sharing, UI root boundaries, sample provenance, visual review, and release gates.
- Verification: Full regression: 315 passed, 2 skipped; Gemini diff review passed; independent review found no reproducible P0-P2 findings.
- Integrity SHA-256: 79a3f79f7cf9e22d4f2f11a77065ec81cc2ace78bbb0d05dcb8f10141d212689
- Changed files:
  - problem_bridge/project_lifecycle.py
  - problem_bridge/revision_governance.py
  - apps/problem_bridge_wizard.py
  - claim_harness/evidence_contract.py
  - claim_harness/verifier.py
  - problem_bridge/document_intake.py
  - tests/test_project_lifecycle.py
  - tests/test_revision_governance.py
  - tests/test_ui_archive.py

### windows-deep-path-release-gate — round 1/3

- Revision ID: 8bfa41c6-9dcb-4a39-a1b6-9013988c79fe
- Parent revision: None
- Time: 2026-07-11T09:29:22.118258+00:00
- Diagnosis: local_execution_problem
- Status: accepted
- Change: Closed Windows deep-path atomic-write, transaction staging, run-name, history ordering, and clean-clone interpreter portability findings.
- Verification: Main regression 329 passed/2 skipped; deep clean clone 331 passed; documented demo and strict tracked-HEAD release gate passed; Gemini and independent review found no remaining P0-P2 issue.
- Integrity SHA-256: a780ad9b2a5bda9b586c39caefd94566118dd7711be6665e93f775b4c626a61d
- Changed files:
  - problem_bridge/project_lifecycle.py
  - problem_bridge/revision_governance.py
  - claim_harness/run_records.py
  - claim_harness/report_viewer.py
  - apps/problem_bridge_wizard.py
  - scripts/test_release_zip_powershell.ps1
  - scripts/build_and_test_release_powershell.ps1
  - tests/test_atomic_write_safety.py
  - tests/test_project_lifecycle.py
  - tests/test_revision_governance.py
  - tests/test_ui_archive.py
  - tests/test_release_readiness.py
  - README.md
  - README.zh-CN.md
  - RELEASE_PACKAGE_GUIDE.md
  - docs/v0.4_upgrade.md

### interaction-usability-v0.4.0 — round 1/3

- Revision ID: 2a058bef-a709-45b1-b52f-c1f50162cae2
- Parent revision: None
- Time: 2026-07-11T10:35:30.131453+00:00
- Diagnosis: structural_mismatch
- Status: accepted
- Change: Reworked the local workbench into a validated, project-scoped, action-first guided flow with provisional handoffs, editable interview state, structured AI seeds, and accessible navigation.
- Verification: Full regression 338 passed and 2 skipped; focused interaction suite 28 passed; real browser walkthrough and three independent read-only reviews completed.
- Integrity SHA-256: 1a15bf2cd9857438e048a84b139ae64c684817c57bb0a885ba374e8758854e29
- Changed files:
  - apps/problem_bridge_wizard.py
  - tests/test_ui_smoke.py
  - tests/test_ui_archive.py
  - tests/test_release_readiness.py
  - README.md
  - README.zh-CN.md
  - docs/demo_walkthrough.md
  - docs/project_records/2026-07-11-project-lifecycle-integrity/interaction_usability_verification.md

### competitive-evidence-enhancement-v0.4.0 — round 1/3

- Revision ID: 6319a120-af87-4f11-bb70-a1775ecc89f8
- Parent revision: None
- Time: 2026-07-11T15:56:53.265731+00:00
- Diagnosis: evidence_gap
- Status: accepted
- Change: Added claim-specific evidence locators, structural diagnostics, pending human-review routing, viewer integration, lifecycle/share packaging, and a bounded competitor comparison.
- Verification: Full regression 347 passed and 2 skipped; focused enhancement suite 35 passed; release/share suite 57 passed and 2 skipped; independent review findings were fixed and covered by regression tests; local file screenshot was blocked by browser policy and is recorded as missing evidence.
- Integrity SHA-256: 99e7caaa50fac4a3193aecc70eb037cfdab6e5f9bb6679c513b941575b0f9870
- Changed files:
  - claim_harness/schemas.py
  - claim_harness/evidence_retriever.py
  - claim_harness/diagnostics.py
  - claim_harness/review_queue.py
  - claim_harness/report_generator.py
  - claim_harness/report_viewer.py
  - problem_bridge/project_lifecycle.py
  - apps/problem_bridge_wizard.py
  - tests/test_audit_enhancements.py
  - tests/test_report_viewer.py
  - tests/test_ui_archive.py
  - README.md
  - README.zh-CN.md
  - docs/comparative_landscape.md
  - docs/project_records/2026-07-11-project-lifecycle-integrity/competitive_evidence_enhancement_verification.md

### ui-flow-convenience-v0.4.0 — round 1/3

- Revision ID: cd187fe6-42f4-4a10-9688-837eb968edb8
- Parent revision: None
- Time: 2026-07-11T16:53:28.742708+00:00
- Diagnosis: structural_mismatch
- Status: accepted
- Change: Shortened the local UI path, prevented destructive-state loss, corrected output routing, bounded export caching, and made static claim review searchable, navigable, accessible, and honest about unavailable legacy diagnostics.
- Verification: Full regression 360 passed and 2 skipped; focused UI/viewer/archive/release checks passed; deterministic mock audit produced all required outputs; two independent reviews were resolved; post-change browser screenshot remained blocked and is recorded as missing evidence.
- Integrity SHA-256: 40935d4012f9d14dcfd87f2959aae211441c9c2149a2e7cd70abb1a374b83431
- Changed files:
  - apps/problem_bridge_wizard.py
  - claim_harness/report_viewer.py
  - tests/test_ui_flow_convenience.py
  - tests/test_ui_smoke.py
  - tests/test_report_viewer.py
  - README.md
  - README.zh-CN.md
  - docs/demo_walkthrough.md
  - docs/limitations.md
  - docs/sample_outputs/claimharness_lab_report_audit_demo/index.html
  - docs/project_records/2026-07-11-project-lifecycle-integrity/ui_flow_convenience_verification.md

### ui-memory-restore-identity-v0.4.0 — round 1/3

- Revision ID: f1018a64-ee5a-4fbc-a1ea-85fb96653e8a
- Parent revision: None
- Time: 2026-07-11T17:04:12.407729+00:00
- Diagnosis: version_contamination
- Status: accepted
- Change: Bound explicit workspace-memory recovery to its validated project identity and rejected cross-project, incomplete, or unbound output pointers.
- Verification: Full regression 362 passed and 2 skipped; focused memory, interaction, and archive suite 40 passed; independent review reproduction is covered by AppTest and direct project-output validation.
- Integrity SHA-256: a0db42153de503d9cae6b9c49cb4e5e9b4b190f3a803c7d8fba90601e3345a37
- Changed files:
  - apps/problem_bridge_wizard.py
  - tests/test_ui_smoke.py
  - tests/test_ui_flow_convenience.py
  - README.md
  - README.zh-CN.md
  - docs/demo_walkthrough.md
  - docs/project_records/2026-07-11-project-lifecycle-integrity/ui_memory_restore_identity_verification.md
