# Problem Card

## Project

Quality Inspection Review Alignment

## Alignment Profile

`quality_inspection`

## Source Problem

# Quality Inspection Review Alignment

I want to build an AI-assisted quality inspection workflow, but I do not want the model to directly decide whether an item passes or fails. The useful goal is to help reviewers inspect input quality, candidate defect visibility, uncertainty, supporting notes, and conservative summary wording.

The risk is that an AI engineer may formulate the project as a pure detection or classification problem. In practice, a missing or faint visual mark can reflect capture quality, sampling, acceptable variation, or unclear criteria rather than a final quality failure. The system should produce evidence sidecars, uncertainty statements, and human review flags rather than autonomous pass/fail decisions.

## Domain Goal

Support reviewable inspection by preserving material quality, defect visibility, uncertainty, reviewer notes, and final human judgement.

## Not Allowed Goal

autonomous pass/fail decision

## Meaningful Outputs

- Evidence sidecar for reviewer inspection
- Conservative inspection summary draft
- Human review flag for low-confidence or high-impact findings

## Non-Meaningful Outputs

- A standalone pass/fail decision from a visual mark
- A deployment-ready quality gate without validation
