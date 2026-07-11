# ClaimHarness Audit Report

## Summary

- Claims audited: 16
- Evidence items collected: 26
- needs_human_review: 1
- overclaimed: 1
- supported: 3
- unsupported: 1
- weakly_supported: 10

## Claim Results

### C001: weakly_supported

The proposed harness improves macro F1 and recall over a baseline rules-only workflow in the accompanying synthetic table.

- Source section: Abstract
- Source line: 5
- Risk level: low
- Reason: Required evidence is missing: table.
- Required evidence: table
- Missing evidence: table
- Supporting evidence IDs: E001, S005, S006, S007
- Contradicting evidence IDs: none

### C002: weakly_supported

It enables auditable review by recording intermediate evidence, low-confidence statements, and replayable trace notes.

- Source section: Abstract
- Source line: 5
- Risk level: low
- Reason: Only narrative or topically related evidence is available; no strong relation was verified.
- Required evidence: trace
- Missing evidence: none
- Supporting evidence IDs: S001, S002, S003
- Contradicting evidence IDs: none

### C003: overclaimed

The workflow is ready for real-world operational deployment.

- Source section: Abstract
- Source line: 5
- Risk level: high
- Reason: High-risk readiness or deployment language is missing required evidence: external_validation, human_review.
- Required evidence: external_validation, human_review
- Missing evidence: external_validation, human_review
- Supporting evidence IDs: S011
- Contradicting evidence IDs: none

### C004: weakly_supported

Report review requires reliable boundaries around what a measurement table supports, what a method note explains, and what still needs reviewer judgement.

- Source section: Introduction
- Source line: 9
- Risk level: low
- Reason: Required evidence is missing: robustness_test.
- Required evidence: robustness_test
- Missing evidence: robustness_test
- Supporting evidence IDs: S008
- Contradicting evidence IDs: none

### C005: needs_human_review

A lightweight harness reduces the risk of opaque model output by separating the task specification, selected context, evidence table, and review decision.

- Source section: Introduction
- Source line: 9
- Risk level: low
- Reason: Provided evidence conflicts with the claim: S012.
- Required evidence: trace
- Missing evidence: trace
- Supporting evidence IDs: none
- Contradicting evidence IDs: S012

### C006: unsupported

The first design goal is to make every report claim traceable to a table row, a text passage, or a limitation statement.

- Source section: Introduction
- Source line: 9
- Risk level: low
- Reason: Required evidence is missing: citation.
- Required evidence: citation
- Missing evidence: citation
- Supporting evidence IDs: none
- Contradicting evidence IDs: none

### C007: weakly_supported

The workflow uses an explainable evidence summary, a confidence note, and a structured trace replay for each synthetic report section.

- Source section: Methods
- Source line: 13
- Risk level: low
- Reason: Required evidence is missing: trace.
- Required evidence: trace
- Missing evidence: trace
- Supporting evidence IDs: S003, S007
- Contradicting evidence IDs: none

### C008: weakly_supported

The human review gate supports manual inspection when evidence confidence is low or when the model highlights an ambiguous claim.

- Source section: Methods
- Source line: 13
- Risk level: low
- Reason: Required evidence is missing: trace.
- Required evidence: trace
- Missing evidence: trace
- Supporting evidence IDs: none
- Contradicting evidence IDs: none

### C009: weakly_supported

Trace replay enables reviewers to see which table metrics, ablation rows, and limitation notes were available before a claim was labeled.

- Source section: Methods
- Source line: 13
- Risk level: low
- Reason: Only narrative or topically related evidence is available; no strong relation was verified.
- Required evidence: trace
- Missing evidence: none
- Supporting evidence IDs: S001, S007, S009, S010
- Contradicting evidence IDs: none

### C010: supported

The evidence_guided_reviewer_v1 model outperforms the baseline_rules model on macro F1, precision, and recall in the synthetic metric table.

- Source section: Results
- Source line: 17
- Risk level: low
- Reason: All evidence requirements are met with 3 independently verifiable strong evidence item(s).
- Required evidence: table
- Missing evidence: none
- Supporting evidence IDs: E001, E002, E003, S006
- Contradicting evidence IDs: none

### C011: supported

Adding the human review gate increases macro F1 from 0.86 to 0.88 and recall from 0.83 to 0.85 in the controlled benchmark.

- Source section: Results
- Source line: 17
- Risk level: low
- Reason: All evidence requirements are met with 2 independently verifiable strong evidence item(s).
- Required evidence: table
- Missing evidence: none
- Supporting evidence IDs: E002, E003, S005
- Contradicting evidence IDs: none

### C012: supported

The full harness improves workflow success rate from 0.70 in the answer-only setting to 0.86 when evidence logging, human review, and trace replay are all enabled.

- Source section: Results
- Source line: 17
- Risk level: low
- Reason: All evidence requirements are met with 4 independently verifiable strong evidence item(s).
- Required evidence: table
- Missing evidence: none
- Supporting evidence IDs: E005, E006, E007, E008, S001, S003
- Contradicting evidence IDs: none

### C013: weakly_supported

The compact reviewer is less reliable around ambiguous limitation statements despite being faster in informal synthetic checks.

- Source section: Results
- Source line: 17
- Risk level: low
- Reason: Required evidence is missing: robustness_test.
- Required evidence: robustness_test
- Missing evidence: robustness_test
- Supporting evidence IDs: none
- Contradicting evidence IDs: none

### C014: weakly_supported

The table evidence supports claims about review metrics and workflow ablation under the synthetic benchmark.

- Source section: Discussion
- Source line: 21
- Risk level: low
- Reason: Required evidence is missing: trace.
- Required evidence: trace
- Missing evidence: trace
- Supporting evidence IDs: S003
- Contradicting evidence IDs: none

### C015: weakly_supported

The workflow is robust to missing trace commentary only in the narrow sense that CSV metrics can still be inspected manually.

- Source section: Discussion
- Source line: 21
- Risk level: low
- Reason: Required evidence is missing: robustness_test.
- Required evidence: robustness_test
- Missing evidence: robustness_test
- Supporting evidence IDs: S003
- Contradicting evidence IDs: none

### C016: weakly_supported

ClaimHarness enables a compact demonstration of claim extraction, evidence linking, conservative verification, human-review routing, and trace logging for technical or scientific writing.

- Source section: Conclusion
- Source line: 25
- Risk level: low
- Reason: Only narrative or topically related evidence is available; no strong relation was verified.
- Required evidence: trace
- Missing evidence: none
- Supporting evidence IDs: S001, S003, S007
- Contradicting evidence IDs: none
