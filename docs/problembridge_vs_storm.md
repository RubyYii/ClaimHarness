# ProblemBridge vs STORM

## Core Difference

STORM asks:

```text
What should we know about a topic, and how can we organize it into an article?
```

ProblemBridge asks:

```text
Is the AI task formulation faithful to the original domain problem?
```

## STORM

STORM focuses on multi-perspective knowledge curation and Wikipedia-like article or outline generation. It is useful when a user needs to explore a topic, gather perspectives, and organize knowledge before writing.

STORM-style outputs include:

- perspective-guided questions
- retrieved knowledge
- outline
- long-form article or report

## ProblemBridge

ProblemBridge focuses on interdisciplinary problem alignment. It is useful before model building, when a team needs to preserve the source-domain workflow, evidence standards, evaluation goals, and human-review boundaries.

ProblemBridge outputs:

- workflow map
- painpoint-opportunity matrix
- concept alignment table
- AI task specification
- evidence contract
- evaluation protocol
- misalignment risk report
- human-in-the-loop plan

## Why This Is Not A Long-Form Report Generator

ProblemBridge does not try to write a general report about a topic. It tries to prevent problem-formulation drift.

Examples:

- HSG: segmentation quality is not the same as diagnostic reliability.
- Chinese painting: object recognition is not the same as cultural interpretation.
- Political education: fluent answers are not the same as value-sensitive conceptual alignment.

The purpose is not to make AI sound knowledgeable about a domain. The purpose is to make the AI task safer, clearer, and more faithful to the domain problem before implementation begins.
