# Comparative Landscape and Bounded Adoption

This note records which adjacent-project ideas ClaimHarness adopted and which it deliberately left outside the local-first v1 scope. It is a design trace, not a claim of feature parity or benchmark superiority.

## Projects reviewed

| Project or guidance | Relevant idea | Adopted in ClaimHarness | Deliberately not adopted |
| --- | --- | --- | --- |
| [ValSci](https://github.com/bricee98/Valsci) | Batch scientific-claim checking, self-hosting, literature retrieval, and structured reports | Claim-level records and auditable outputs | Semantic Scholar retrieval, bibliometric credibility scoring, background jobs, and a database-backed web service; these would expand v1 into a networked literature platform |
| [Amazon RefChecker](https://www.amazon.science/code-and-datasets/refchecker-reference-based-fine-grained-hallucination-checker-and-benchmark-for-large-language-models) | Fine-grained, claim-level checking against references | Claim-specific evidence locations rather than one undifferentiated row locator | LLM-based hallucination labels and benchmark claims; ClaimHarness keeps the deterministic mock path and does not have gold reference labels in a normal run |
| [RAGChecker](https://github.com/amazon-science/RAGChecker) | Separate diagnostic signals to make failures actionable | `audit_diagnostics.json` separates any-link coverage, support relations, missing requirements, contradictions, high-risk routing, and unused evidence | Its RAG retriever/generator metrics and names such as faithfulness or hallucination, because a ClaimHarness audit run has neither a RAG ground-truth answer nor equivalent model-based entailment evaluation |
| [Microsoft HAX Toolkit](https://www.microsoft.com/en-us/haxtoolkit/) | Make system limits visible, support recovery when AI is wrong, and define human responsibilities | Explicit diagnostic boundaries and a pending claim-role human-review queue | Browser-local approval buttons or silent status overrides; a queue item cannot be interpreted as a decision, verified identity, or evidence |

## Resulting bounded increment within v0.4

The adopted changes remain deterministic and offline:

1. A table evidence item keeps its full base row, while each claim link records only the matched cells, their columns, values, and A1 coordinates.
2. A single-run diagnostic artifact reports counts and ratios with numerators and denominators, without a composite health score.
3. A human-review queue records only immutable `pending` work items. Formal reviewer decisions would require a separately governed, hash-bound sidecar workflow and are intentionally future work.

## Interpretation boundary

These changes improve traceability and review navigation. They do not establish factual correctness, scientific validity, clinical safety, reviewer competence, or superiority over the referenced projects. No code was copied from these projects; the links above document design inspiration and scope comparisons.
