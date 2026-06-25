# Problem Card

## Project

HSG Evidence-Ready Second-Reader Support

## Alignment Profile

`hsg`

## Source Problem

# HSG Evidence-Ready Support

I want to build an AI-assisted HSG workflow, but I do not want the model to directly diagnose tubal obstruction from images. The useful goal is to help clinicians review image quality, contrast passage, tube visibility, uncertainty, and conservative report wording.

The risk is that an AI engineer may formulate the project as a pure segmentation or obstruction classification problem. In practice, segmentation absence can reflect poor visibility, timing, or image quality, not a definitive clinical obstruction. The system should produce evidence sidecars, uncertainty statements, and human review flags rather than autonomous diagnosis.

## Domain Goal

Support reviewable HSG interpretation by preserving image quality, contrast passage, visibility, uncertainty, and clinician judgement.

## Not Allowed Goal

autonomous diagnosis

## Meaningful Outputs

- Evidence sidecar for clinician review
- Conservative structured report draft
- Human review flag for low-confidence or high-risk findings

## Non-Meaningful Outputs

- A standalone obstruction diagnosis from mask absence
- A deployment-ready clinical conclusion without validation
