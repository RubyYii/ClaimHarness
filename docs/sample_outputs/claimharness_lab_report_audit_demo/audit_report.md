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
- Source kind: manuscript
- Risk level: low
- Reason: Required evidence is missing: table.
- Required evidence: table
- Missing evidence: table
- Supporting evidence IDs: E001, S005, S006, S007
- Supporting evidence locations: E001 @ table1_metrics.csv, data row 1, cells model=baseline_rules (A2), macro_f1=0.79 (B2), recall=0.74 (D2), notes=synthetic benchmark baseline without review routing (E2); S005 @ manuscript.md, line 17; S006 @ manuscript.md, line 17; S007 @ manuscript.md, line 17
- Contradicting evidence IDs: none
- Contradicting evidence locations: none

### C002: weakly_supported

It enables auditable review by recording intermediate evidence, low-confidence statements, and replayable trace notes.

- Source section: Abstract
- Source line: 5
- Source kind: manuscript
- Risk level: low
- Reason: Only narrative or topically related evidence is available; no strong relation was verified.
- Required evidence: trace
- Missing evidence: none
- Supporting evidence IDs: S001, S002, S003
- Supporting evidence locations: S001 @ manuscript.md, line 13; S002 @ manuscript.md, line 13; S003 @ manuscript.md, line 13
- Contradicting evidence IDs: none
- Contradicting evidence locations: none

### C003: overclaimed

The workflow is ready for real-world operational deployment.

- Source section: Abstract
- Source line: 5
- Source kind: manuscript
- Risk level: high
- Reason: High-risk readiness or deployment language is missing required evidence: external_validation, human_review.
- Required evidence: external_validation, human_review
- Missing evidence: external_validation, human_review
- Supporting evidence IDs: S011
- Supporting evidence locations: S011 @ manuscript.md, line 21
- Contradicting evidence IDs: none
- Contradicting evidence locations: none

### C004: weakly_supported

Report review requires reliable boundaries around what a measurement table supports, what a method note explains, and what still needs reviewer judgement.

- Source section: Introduction
- Source line: 9
- Source kind: manuscript
- Risk level: low
- Reason: Required evidence is missing: robustness_test.
- Required evidence: robustness_test
- Missing evidence: robustness_test
- Supporting evidence IDs: S008
- Supporting evidence locations: S008 @ manuscript.md, line 17
- Contradicting evidence IDs: none
- Contradicting evidence locations: none

### C005: needs_human_review

A lightweight harness reduces the risk of opaque model output by separating the task specification, selected context, evidence table, and review decision.

- Source section: Introduction
- Source line: 9
- Source kind: manuscript
- Risk level: low
- Reason: Provided evidence conflicts with the claim: S012.
- Required evidence: trace
- Missing evidence: trace
- Supporting evidence IDs: none
- Supporting evidence locations: none
- Contradicting evidence IDs: S012
- Contradicting evidence locations: S012 @ manuscript.md, line 21

### C006: unsupported

The first design goal is to make every report claim traceable to a table row, a text passage, or a limitation statement.

- Source section: Introduction
- Source line: 9
- Source kind: manuscript
- Risk level: low
- Reason: Required evidence is missing: citation.
- Required evidence: citation
- Missing evidence: citation
- Supporting evidence IDs: none
- Supporting evidence locations: none
- Contradicting evidence IDs: none
- Contradicting evidence locations: none

### C007: weakly_supported

The workflow uses an explainable evidence summary, a confidence note, and a structured trace replay for each synthetic report section.

- Source section: Methods
- Source line: 13
- Source kind: manuscript
- Risk level: low
- Reason: Required evidence is missing: trace.
- Required evidence: trace
- Missing evidence: trace
- Supporting evidence IDs: S003, S007
- Supporting evidence locations: S003 @ manuscript.md, line 13; S007 @ manuscript.md, line 17
- Contradicting evidence IDs: none
- Contradicting evidence locations: none

### C008: weakly_supported

The human review gate supports manual inspection when evidence confidence is low or when the model highlights an ambiguous claim.

- Source section: Methods
- Source line: 13
- Source kind: manuscript
- Risk level: low
- Reason: Required evidence is missing: trace.
- Required evidence: trace
- Missing evidence: trace
- Supporting evidence IDs: none
- Supporting evidence locations: none
- Contradicting evidence IDs: none
- Contradicting evidence locations: none

### C009: weakly_supported

Trace replay enables reviewers to see which table metrics, ablation rows, and limitation notes were available before a claim was labeled.

- Source section: Methods
- Source line: 13
- Source kind: manuscript
- Risk level: low
- Reason: Only narrative or topically related evidence is available; no strong relation was verified.
- Required evidence: trace
- Missing evidence: none
- Supporting evidence IDs: S001, S007, S009, S010
- Supporting evidence locations: S001 @ manuscript.md, line 13; S007 @ manuscript.md, line 17; S009 @ manuscript.md, line 21; S010 @ manuscript.md, line 21
- Contradicting evidence IDs: none
- Contradicting evidence locations: none

### C010: supported

The evidence_guided_reviewer_v1 model outperforms the baseline_rules model on macro F1, precision, and recall in the synthetic metric table.

- Source section: Results
- Source line: 17
- Source kind: manuscript
- Risk level: low
- Reason: All evidence requirements are met with 3 independently verifiable strong evidence item(s).
- Required evidence: table
- Missing evidence: none
- Supporting evidence IDs: E001, E002, E003, S006
- Supporting evidence locations: E001 @ table1_metrics.csv, data row 1, cells model=baseline_rules (A2), macro_f1=0.79 (B2), precision=0.84 (C2), recall=0.74 (D2), notes=synthetic benchmark baseline without review routing (E2); E002 @ table1_metrics.csv, data row 2, cells model=evidence_guided_reviewer_v1 (A3), macro_f1=0.86 (B3), precision=0.9 (C3), recall=0.83 (D3); E003 @ table1_metrics.csv, data row 3, cells model=evidence_guided_reviewer_v1_with_review (A4), macro_f1=0.88 (B4), precision=0.91 (C4), recall=0.85 (D4); S006 @ manuscript.md, line 17
- Contradicting evidence IDs: none
- Contradicting evidence locations: none

### C011: supported

Adding the human review gate increases macro F1 from 0.86 to 0.88 and recall from 0.83 to 0.85 in the controlled benchmark.

- Source section: Results
- Source line: 17
- Source kind: manuscript
- Risk level: low
- Reason: All evidence requirements are met with 2 independently verifiable strong evidence item(s).
- Required evidence: table
- Missing evidence: none
- Supporting evidence IDs: E002, E003, S005
- Supporting evidence locations: E002 @ table1_metrics.csv, data row 2, cells macro_f1=0.86 (B3), recall=0.83 (D3); E003 @ table1_metrics.csv, data row 3, cells macro_f1=0.88 (B4), recall=0.85 (D4), notes=adds human review gate for low-confidence claims (E4); S005 @ manuscript.md, line 17
- Contradicting evidence IDs: none
- Contradicting evidence locations: none

### C012: supported

The full harness improves workflow success rate from 0.70 in the answer-only setting to 0.86 when evidence logging, human review, and trace replay are all enabled.

- Source section: Results
- Source line: 17
- Source kind: manuscript
- Risk level: low
- Reason: All evidence requirements are met with 4 independently verifiable strong evidence item(s).
- Required evidence: table
- Missing evidence: none
- Supporting evidence IDs: E005, E006, E007, E008, S001, S003
- Supporting evidence locations: E005 @ table2_ablation.csv, data row 1, cells setting=answer_only (A2), evidence_logging=disabled (B2), trace_replay=disabled (D2), success_rate=0.7 (E2), notes=no claim trace and no explicit review routing (F2); E006 @ table2_ablation.csv, data row 2, cells setting=logging_only (A3), evidence_logging=enabled (B3), trace_replay=enabled (D3), success_rate=0.78 (E3); E007 @ table2_ablation.csv, data row 3, cells setting=review_gate_only (A4), evidence_logging=disabled (B4), human_review_gate=enabled (C4), trace_replay=disabled (D4), success_rate=0.8 (E4), notes=routes uncertain cases but cannot replay evidence chain (F4); E008 @ table2_ablation.csv, data row 4, cells setting=full_harness (A5), evidence_logging=enabled (B5), human_review_gate=enabled (C5), trace_replay=enabled (D5), success_rate=0.86 (E5), notes=combines evidence logging human review and replayable trace (F5); S001 @ manuscript.md, line 13; S003 @ manuscript.md, line 13
- Contradicting evidence IDs: none
- Contradicting evidence locations: none

### C013: weakly_supported

The compact reviewer is less reliable around ambiguous limitation statements despite being faster in informal synthetic checks.

- Source section: Results
- Source line: 17
- Source kind: manuscript
- Risk level: low
- Reason: Required evidence is missing: robustness_test.
- Required evidence: robustness_test
- Missing evidence: robustness_test
- Supporting evidence IDs: none
- Supporting evidence locations: none
- Contradicting evidence IDs: none
- Contradicting evidence locations: none

### C014: weakly_supported

The table evidence supports claims about review metrics and workflow ablation under the synthetic benchmark.

- Source section: Discussion
- Source line: 21
- Source kind: manuscript
- Risk level: low
- Reason: Required evidence is missing: trace.
- Required evidence: trace
- Missing evidence: trace
- Supporting evidence IDs: S003
- Supporting evidence locations: S003 @ manuscript.md, line 13
- Contradicting evidence IDs: none
- Contradicting evidence locations: none

### C015: weakly_supported

The workflow is robust to missing trace commentary only in the narrow sense that CSV metrics can still be inspected manually.

- Source section: Discussion
- Source line: 21
- Source kind: manuscript
- Risk level: low
- Reason: Required evidence is missing: robustness_test.
- Required evidence: robustness_test
- Missing evidence: robustness_test
- Supporting evidence IDs: S003
- Supporting evidence locations: S003 @ manuscript.md, line 13
- Contradicting evidence IDs: none
- Contradicting evidence locations: none

### C016: weakly_supported

ClaimHarness enables a compact demonstration of claim extraction, evidence linking, conservative verification, human-review routing, and trace logging for technical or scientific writing.

- Source section: Conclusion
- Source line: 25
- Source kind: manuscript
- Risk level: low
- Reason: Only narrative or topically related evidence is available; no strong relation was verified.
- Required evidence: trace
- Missing evidence: none
- Supporting evidence IDs: S001, S003, S007
- Supporting evidence locations: S001 @ manuscript.md, line 13; S003 @ manuscript.md, line 13; S007 @ manuscript.md, line 17
- Contradicting evidence IDs: none
- Contradicting evidence locations: none
