# Limitations

ClaimHarness is a small engineering demo, not a scientific review authority.

## Current Limits

- ClaimHarness does not guarantee factual correctness.
- It only checks the manuscript, tables, and references passed to the command.
- biomedical claims require human review.
- Mock mode is deterministic and not semantically complete.
- Keyword claim extraction can miss claims or over-detect explanatory sentences.
- Evidence linking uses simple lexical overlap.
- The verifier is conservative but rule-based.
- Optional LLM review output may be wrong and is advisory only.
- PDF and figure understanding are future work.

## What The Demo Can Show

The demo shows how to turn a manuscript review task into an auditable episode package. It is useful for explaining task decomposition, evidence traceability, intermediate state, and replayable logs.

## What The Demo Should Not Claim

The demo should not be presented as a medical device, clinical review tool, diagnostic system, or publication-quality scientific reviewer. Any biomedical or clinical claim should be routed to human review unless supported by strong external evidence.

If `--llm openai-compatible` is used, `llm_review.json` should be treated as an extra reviewer note. It does not override deterministic claim statuses, evidence links, or the need for human scientific review.
