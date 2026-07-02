# ClaimHarness Audit Report

## Summary

- Claims audited: 17
- Evidence items collected: 26
- overclaimed: 2
- supported: 14
- weakly_supported: 1

## Claim Results

### C001: supported

The proposed harness improves macro F1 and recall over a baseline rules-only workflow in the accompanying synthetic table.

- Source section: Abstract
- Source line: 4
- Risk level: low
- Reason: Linked to 4 structured table or results evidence item(s).

### C002: supported

It enables auditable review by recording intermediate evidence, low-confidence statements, and replayable trace notes.

- Source section: Abstract
- Source line: 4
- Risk level: low
- Reason: Linked to 9 structured table or results evidence item(s).

### C003: overclaimed

Although the prototype is not externally validated, one intentionally overclaimed sentence says the workflow is ready for real-world operational deployment so the audit pipeline can flag it later.

- Source section: Abstract
- Source line: 4
- Risk level: high
- Reason: Deployment or readiness language appears without external validation or safety evidence.

### C004: supported

Report review requires reliable boundaries around what a measurement table supports, what a method note explains, and what still needs reviewer judgement.

- Source section: Introduction
- Source line: 8
- Risk level: low
- Reason: Linked to 2 structured table or results evidence item(s).

### C005: supported

A lightweight harness reduces the risk of opaque model output by separating the task specification, selected context, evidence table, and review decision.

- Source section: Introduction
- Source line: 8
- Risk level: low
- Reason: Linked to 6 structured table or results evidence item(s).

### C006: weakly_supported

The first design goal is to make every report claim traceable to a table row, a text passage, or a limitation statement.

- Source section: Introduction
- Source line: 8
- Risk level: low
- Reason: Linked only to narrative, citation, trace, or limitation evidence (1 item(s)).

### C007: supported

The workflow uses an explainable evidence summary, a confidence note, and a structured trace replay for each synthetic report section.

- Source section: Methods
- Source line: 12
- Risk level: low
- Reason: Linked to 4 structured table or results evidence item(s).

### C008: supported

The human review gate supports manual inspection when evidence confidence is low or when the model highlights an ambiguous claim.

- Source section: Methods
- Source line: 12
- Risk level: low
- Reason: Linked to 7 structured table or results evidence item(s).

### C009: supported

Trace replay enables reviewers to see which table metrics, ablation rows, and limitation notes were available before a claim was labeled.

- Source section: Methods
- Source line: 12
- Risk level: low
- Reason: Linked to 5 structured table or results evidence item(s).

### C010: supported

The evidence_guided_reviewer_v1 model outperforms the baseline_rules model on macro F1, precision, and recall in the synthetic metric table.

- Source section: Results
- Source line: 16
- Risk level: low
- Reason: Linked to 6 structured table or results evidence item(s).

### C011: supported

Adding the human review gate increases macro F1 from 0.86 to 0.88 and recall from 0.83 to 0.85 in the controlled benchmark.

- Source section: Results
- Source line: 16
- Risk level: low
- Reason: Linked to 6 structured table or results evidence item(s).

### C012: supported

The full harness improves workflow success rate from 0.70 in the answer-only setting to 0.86 when evidence logging, human review, and trace replay are all enabled.

- Source section: Results
- Source line: 16
- Risk level: low
- Reason: Linked to 7 structured table or results evidence item(s).

### C013: supported

The compact reviewer is less reliable around ambiguous limitation statements despite being faster in informal synthetic checks.

- Source section: Results
- Source line: 16
- Risk level: low
- Reason: Linked to 2 structured table or results evidence item(s).

### C014: supported

The table evidence supports claims about review metrics and workflow ablation under the synthetic benchmark.

- Source section: Discussion
- Source line: 20
- Risk level: low
- Reason: Linked to 5 structured table or results evidence item(s).

### C015: supported

The workflow is robust to missing trace commentary only in the narrow sense that CSV metrics can still be inspected manually.

- Source section: Discussion
- Source line: 20
- Risk level: low
- Reason: Linked to 1 structured table or results evidence item(s).

### C016: overclaimed

The manuscript overclaims if it says the system is deployment-ready for real-world operations because no external validation, user study, or safety review is included.

- Source section: Discussion
- Source line: 20
- Risk level: high
- Reason: Deployment or readiness language appears without external validation or safety evidence.

### C017: supported

ClaimHarness enables a compact demonstration of claim extraction, evidence linking, conservative verification, human-review routing, and trace logging for technical or scientific writing.

- Source section: Conclusion
- Source line: 24
- Risk level: low
- Reason: Linked to 6 structured table or results evidence item(s).
