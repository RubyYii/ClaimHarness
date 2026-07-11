# Project Summary Log

## Run

- Run ID: `44ab3e7074c14fcea5c0865ceda67595`
- Started: 2026-07-11T01:33:36+00:00
- Completed: 2026-07-11T01:33:36+00:00
- ClaimHarness version: 0.3.3
- Provider: mock (not_requested)
- Manuscript: manuscript.md
- References: references.md
- Tables: table1_metrics.csv, table2_ablation.csv

## Audit Snapshot

- Claims audited: 16
- supported: 3
- weakly_supported: 10
- unsupported: 1
- overclaimed: 1
- needs_human_review: 1

## Claims Requiring Follow-up

- C001 [weakly_supported; low risk] Abstract, line 5: The proposed harness improves macro F1 and recall over a baseline rules-only workflow in the accompanying synthetic table.
- C002 [weakly_supported; low risk] Abstract, line 5: It enables auditable review by recording intermediate evidence, low-confidence statements, and replayable trace notes.
- C003 [overclaimed; high risk] Abstract, line 5: The workflow is ready for real-world operational deployment.
- C004 [weakly_supported; low risk] Introduction, line 9: Report review requires reliable boundaries around what a measurement table supports, what a method note explains, and what still needs reviewer judgement.
- C005 [needs_human_review; low risk] Introduction, line 9: A lightweight harness reduces the risk of opaque model output by separating the task specification, selected context, evidence table, and review decision.
- C006 [unsupported; low risk] Introduction, line 9: The first design goal is to make every report claim traceable to a table row, a text passage, or a limitation statement.
- C007 [weakly_supported; low risk] Methods, line 13: The workflow uses an explainable evidence summary, a confidence note, and a structured trace replay for each synthetic report section.
- C008 [weakly_supported; low risk] Methods, line 13: The human review gate supports manual inspection when evidence confidence is low or when the model highlights an ambiguous claim.
- C009 [weakly_supported; low risk] Methods, line 13: Trace replay enables reviewers to see which table metrics, ablation rows, and limitation notes were available before a claim was labeled.
- C013 [weakly_supported; low risk] Results, line 17: The compact reviewer is less reliable around ambiguous limitation statements despite being faster in informal synthetic checks.
- C014 [weakly_supported; low risk] Discussion, line 21: The table evidence supports claims about review metrics and workflow ablation under the synthetic benchmark.
- C015 [weakly_supported; low risk] Discussion, line 21: The workflow is robust to missing trace commentary only in the narrow sense that CSV metrics can still be inspected manually.
- C016 [weakly_supported; low risk] Conclusion, line 25: ClaimHarness enables a compact demonstration of claim extraction, evidence linking, conservative verification, human-review routing, and trace logging for technical or scientific writing.

## Artifact Index

- `claim_table.csv`
- `evidence_map.json`
- `audit_report.md`
- `revision_suggestions.md`
- `agent_trace.jsonl`
- `run_manifest.json`
- `project_summary_log.md`

## Revision Guardrail

- Use at most 3 revision rounds for one stable target.
- After round 3, accept the result or escalate the specification, evidence, or structure; do not apply a fourth patch to the same target.
- Record what changed and how it was verified before starting the next round.

## Interpretation Boundary

This log is a navigation and provenance aid. It is not scientific evidence, a peer review, or a clinical decision.
