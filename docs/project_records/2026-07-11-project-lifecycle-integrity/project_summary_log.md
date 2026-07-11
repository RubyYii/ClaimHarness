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
