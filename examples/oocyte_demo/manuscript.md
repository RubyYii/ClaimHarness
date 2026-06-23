# Human-in-the-loop and Explainable Workflow for Oocyte Injection Guidance

## Abstract

This synthetic manuscript describes a human-in-the-loop and explainable workflow for oocyte injection guidance in a controlled microscopy benchmark. The proposed harness improves segmentation Dice and IoU over a baseline visual model in the accompanying synthetic table. It enables auditable review by recording intermediate evidence, low-confidence regions, and replayable trace notes. We intentionally include claims that vary in support level so the future verifier can exercise supported, weakly supported, unsupported, and overclaimed cases. Although the prototype is not clinically validated, one intentionally overclaimed sentence says the workflow is clinically ready for deployment so the audit pipeline can flag it later.

## Introduction

Micromanipulation guidance requires reliable visual boundaries around the oocyte membrane, zona pellucida, and injection region. A lightweight harness reduces the risk of opaque model output by separating the task specification, selected context, evidence table, and review decision. The first design goal is to make every guidance claim traceable to a table row, a text passage, or a limitation statement. The second design goal is to keep the demo reproducible with synthetic files rather than private laboratory material.

## Methods

The workflow uses an explainable segmentation summary, a confidence note, and a structured trace replay for each synthetic microscopy frame. The human review gate supports manual inspection when boundary confidence is low or when the model highlights an ambiguous injection region. Trace replay enables reviewers to see which table metrics, ablation rows, and limitation notes were available before a claim was labeled. The synthetic benchmark is intentionally small and does not measure live laboratory performance.

## Results

The explainable_guidance_v1 model outperforms the baseline_unet model on Dice, IoU, precision, and recall in the synthetic metric table. Adding the human review gate increases Dice from 0.88 to 0.89 and IoU from 0.78 to 0.80 in the controlled benchmark. The full harness improves workflow success rate from 0.71 in the vision-only setting to 0.86 when evidence logging, human review, and trace replay are all enabled. The compact detector is less reliable around faint zona boundaries despite being faster in informal synthetic checks.

## Discussion

The table evidence supports claims about segmentation metrics and workflow ablation under the synthetic benchmark. The workflow is robust to missing trace commentary only in the narrow sense that CSV metrics can still be inspected manually. The manuscript overclaims if it says the system is ready for real-world clinical deployment because no external validation, operator study, or safety review is included. The system should not be considered a decision-making device; it is a reproducible audit harness for studying claim-evidence traceability.

## Conclusion

ClaimHarness enables a compact demonstration of claim extraction, evidence linking, conservative verification, human-review routing, and trace logging for scientific writing. It remains a synthetic engineering demo whose value is showing how an Agent Harness can make model-assisted review more reviewable before any high-risk use.
