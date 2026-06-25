# ClaimHarness Audit Report

## Summary

- Claims audited: 18
- Evidence items collected: 26
- overclaimed: 2
- supported: 15
- weakly_supported: 1

## Claim Results

### C001: supported

This synthetic manuscript describes a human-in-the-loop and explainable workflow for oocyte injection guidance in a controlled microscopy benchmark.

- Source section: Abstract
- Source line: 4
- Risk level: high
- Reason: Linked to 2 structured table or results evidence item(s).

### C002: supported

The proposed harness improves segmentation Dice and IoU over a baseline visual model in the accompanying synthetic table.

- Source section: Abstract
- Source line: 4
- Risk level: low
- Reason: Linked to 6 structured table or results evidence item(s).

### C003: supported

It enables auditable review by recording intermediate evidence, low-confidence regions, and replayable trace notes.

- Source section: Abstract
- Source line: 4
- Risk level: low
- Reason: Linked to 8 structured table or results evidence item(s).

### C004: overclaimed

Although the prototype is not clinically validated, one intentionally overclaimed sentence says the workflow is clinically ready for deployment so the audit pipeline can flag it later.

- Source section: Abstract
- Source line: 4
- Risk level: high
- Reason: Clinical deployment language appears without external validation or safety evidence.

### C005: supported

Micromanipulation guidance requires reliable visual boundaries around the oocyte membrane, zona pellucida, and injection region.

- Source section: Introduction
- Source line: 8
- Risk level: high
- Reason: Linked to 2 structured table or results evidence item(s).

### C006: supported

A lightweight harness reduces the risk of opaque model output by separating the task specification, selected context, evidence table, and review decision.

- Source section: Introduction
- Source line: 8
- Risk level: low
- Reason: Linked to 5 structured table or results evidence item(s).

### C007: weakly_supported

The first design goal is to make every guidance claim traceable to a table row, a text passage, or a limitation statement.

- Source section: Introduction
- Source line: 8
- Risk level: low
- Reason: Linked only to narrative, citation, trace, or limitation evidence (1 item(s)).

### C008: supported

The workflow uses an explainable segmentation summary, a confidence note, and a structured trace replay for each synthetic microscopy frame.

- Source section: Methods
- Source line: 12
- Risk level: low
- Reason: Linked to 2 structured table or results evidence item(s).

### C009: supported

The human review gate supports manual inspection when boundary confidence is low or when the model highlights an ambiguous injection region.

- Source section: Methods
- Source line: 12
- Risk level: low
- Reason: Linked to 6 structured table or results evidence item(s).

### C010: supported

Trace replay enables reviewers to see which table metrics, ablation rows, and limitation notes were available before a claim was labeled.

- Source section: Methods
- Source line: 12
- Risk level: low
- Reason: Linked to 4 structured table or results evidence item(s).

### C011: supported

The explainable_guidance_v1 model outperforms the baseline_unet model on Dice, IoU, precision, and recall in the synthetic metric table.

- Source section: Results
- Source line: 16
- Risk level: low
- Reason: Linked to 5 structured table or results evidence item(s).

### C012: supported

Adding the human review gate increases Dice from 0.88 to 0.89 and IoU from 0.78 to 0.80 in the controlled benchmark.

- Source section: Results
- Source line: 16
- Risk level: low
- Reason: Linked to 5 structured table or results evidence item(s).

### C013: supported

The full harness improves workflow success rate from 0.71 in the vision-only setting to 0.86 when evidence logging, human review, and trace replay are all enabled.

- Source section: Results
- Source line: 16
- Risk level: low
- Reason: Linked to 7 structured table or results evidence item(s).

### C014: supported

The compact detector is less reliable around faint zona boundaries despite being faster in informal synthetic checks.

- Source section: Results
- Source line: 16
- Risk level: low
- Reason: Linked to 2 structured table or results evidence item(s).

### C015: supported

The table evidence supports claims about segmentation metrics and workflow ablation under the synthetic benchmark.

- Source section: Discussion
- Source line: 20
- Risk level: low
- Reason: Linked to 2 structured table or results evidence item(s).

### C016: supported

The workflow is robust to missing trace commentary only in the narrow sense that CSV metrics can still be inspected manually.

- Source section: Discussion
- Source line: 20
- Risk level: low
- Reason: Linked to 1 structured table or results evidence item(s).

### C017: overclaimed

The manuscript overclaims if it says the system is ready for real-world clinical deployment because no external validation, operator study, or safety review is included.

- Source section: Discussion
- Source line: 20
- Risk level: high
- Reason: Clinical deployment language appears without external validation or safety evidence.

### C018: supported

ClaimHarness enables a compact demonstration of claim extraction, evidence linking, conservative verification, human-review routing, and trace logging for scientific writing.

- Source section: Conclusion
- Source line: 24
- Risk level: low
- Reason: Linked to 6 structured table or results evidence item(s).
