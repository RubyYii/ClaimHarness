# UI Memory Restore Identity Verification

Target: `ui-memory-restore-identity-v0.4.0`

Status: accepted in round 1 of at most 3.

## Diagnosis

The submission review reproduced a project-identity split: after saving project A's drafts and starting project B, explicitly loading the saved memory restored A's drafts and output pointer while retaining B's active project ID.

## Fix

- Treat the active project ID as project-scoped state during an explicit memory replacement.
- Validate a restored project ID before applying it.
- Restore an output pointer only when it resolves to a safe, complete governed UI run whose `project_id` matches the restored active project.
- Do not auto-restore unbound legacy or cross-project output paths as the current project's previous result.

## Verification

- Full regression: `362 passed, 2 skipped`.
- Focused workbench memory, interaction, and archive regression: `40 passed`.
- Added an AppTest covering A save -> B start -> load -> A identity and draft recovery.
- Added a direct regression proving that a project-B workspace rejects a project-A output pointer.
- Python compilation passed for `apps/problem_bridge_wizard.py`.

This is a state-integrity change and does not make a visual-completion claim.

