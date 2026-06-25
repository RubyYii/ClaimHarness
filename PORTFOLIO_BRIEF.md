# ProblemBridge + ClaimHarness Portfolio Brief

## One-Sentence Summary

ProblemBridge and ClaimHarness form a lightweight two-stage harness for interdisciplinary AI projects: pre-model problem alignment and post-output evidence auditing.

## Motivation

Many interdisciplinary AI projects fail not because the model is weak, but because the domain problem is translated into the wrong AI task, evaluated with the wrong metrics, or deployed without evidence boundaries.

This repository demonstrates a small, reproducible workflow for keeping domain meaning, evidence standards, evaluation protocols, and human-review boundaries visible.

## Stage 1: ProblemBridge

ProblemBridge helps reconstruct domain workflows, identify pain points, map domain concepts to AI representations, define AI task specifications, establish evidence contracts, and design evaluation protocols.

It is used before model building, when the team still needs to decide what the AI task should be and what must remain human-reviewed.

## Stage 2: ClaimHarness

ClaimHarness audits generated or human-written scientific claims against available manuscript, table, and reference evidence. It flags weakly supported or overclaimed statements and produces traceable audit packages.

It is used after writing, system output, or report drafting, when the team needs to check whether claims are supported by evidence.

## Why This Is Not STORM

STORM focuses on multi-perspective knowledge curation and article or outline generation.

ProblemBridge focuses on problem alignment: making sure the AI task formulation remains faithful to the source-domain workflow, evidence standards, evaluation needs, and human-review boundaries.

## Why This Matters

The system helps:

- domain practitioners discover where AI can meaningfully support their workflow
- AI practitioners understand domain goals, evidence requirements, evaluation protocols, and deployment boundaries
- interdisciplinary teams avoid false task formulations and overclaiming

## Current Synthetic Examples

- HSG evidence-ready support
- Chinese painting / VULCA cultural interpretation alignment
- Political education risk evaluation
- Oocyte ClaimHarness claim-evidence audit

## Limitations

- Synthetic examples only.
- No clinical, legal, educational, or cultural authority is claimed.
- No private data, real patient data, or confidential manuscripts should be used.
- Mock mode is deterministic and demonstrates structure, not semantic completeness.
- Optional LLM review is advisory only and does not replace domain expert review.
