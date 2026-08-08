# Human-in-the-loop Evidence Review for Synthetic Lab Reports

## Abstract

This synthetic manuscript describes a human-in-the-loop workflow for reviewing measurement claims in lab-style reports. The proposed harness improves macro F1 and recall over a baseline rules-only workflow in the accompanying synthetic table. It enables auditable review by recording intermediate evidence, low-confidence statements, and replayable trace notes. We intentionally include claims that vary in support level so the verifier can exercise supported, weakly supported, unsupported, overclaimed, and needs-human-review cases. The workflow is ready for real-world operational deployment.

## Introduction

Report review requires reliable boundaries around what a measurement table supports, what a method note explains, and what still needs reviewer judgement. A lightweight harness reduces the risk of opaque model output by separating the task specification, selected context, evidence table, and review decision. The first design goal is to make every report claim traceable to a table row, a text passage, or a limitation statement. The second design goal is to keep the demo reproducible with synthetic files rather than private laboratory material.

## Methods

The workflow uses an explainable evidence summary, a confidence note, and a structured trace replay for each synthetic report section. The human review gate supports manual inspection when evidence confidence is low or when the model highlights an ambiguous claim. Trace replay enables reviewers to see which table metrics, ablation rows, and limitation notes were available before a claim was labeled. The synthetic benchmark is intentionally small and does not measure live operational performance.

## Results

The evidence_guided_reviewer_v1 model outperforms the baseline_rules model on macro F1, precision, and recall in the synthetic metric table. Adding the human review gate increases macro F1 from 0.86 to 0.88 and recall from 0.83 to 0.85 in the controlled benchmark. The full harness improves workflow success rate from 0.70 in the answer-only setting to 0.86 when evidence logging, human review, and trace replay are all enabled. The compact reviewer is less reliable around ambiguous limitation statements despite being faster in informal synthetic checks.

## Discussion

The table evidence supports claims about review metrics and workflow ablation under the synthetic benchmark. The workflow is robust to missing trace commentary only in the narrow sense that CSV metrics can still be inspected manually. The manuscript overclaims if it says the system is deployment-ready for real-world operations because no external validation, user study, or safety review is included. The system should not be considered a decision-making device; it is a reproducible audit harness for studying claim-evidence traceability.

## Conclusion

ClaimHarness enables a compact demonstration of claim extraction, evidence linking, conservative verification, human-review routing, and trace logging for technical or scientific writing. It remains a synthetic engineering demo whose value is showing how an Agent Harness can make model-assisted review more reviewable before any high-risk use.
