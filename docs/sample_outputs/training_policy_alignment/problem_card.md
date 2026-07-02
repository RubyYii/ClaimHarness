# Problem Card

## Project

Training Policy Response Alignment

## Alignment Profile

`training_policy`

## Source Problem

# Training Policy Response Alignment

I want to evaluate LLM answers used around training or policy-support materials. The problem is not ordinary factual QA. The model must stay source-grounded, preserve concept relations, avoid unsupported procedural claims, and avoid unstable scope or framing.

The risk is that an AI practitioner evaluates only answer fluency or factual accuracy. A fluent answer can still misstate source guidance, frame a procedure too broadly, or omit uncertainty and source grounding. Human reviewer approval must remain part of the workflow.

## Domain Goal

Evaluate whether generated training or policy-support answers remain source-grounded, conceptually aligned, and appropriately bounded for review.

## Not Allowed Goal

fluent answer generation as policy compliance

## Meaningful Outputs

- Source-grounded answer audit
- Concept framing consistency checks
- Reviewer correction burden estimate

## Non-Meaningful Outputs

- Fluency-only answer scores
- Generic factual QA accuracy without policy or training-context review
