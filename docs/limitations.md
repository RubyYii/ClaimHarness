# Limitations

ClaimHarness is a small engineering demo, not a scientific review authority.

## Current Limits

- ClaimHarness does not guarantee factual correctness.
- It only checks the manuscript, tables, and references passed to the command.
- High-risk biomedical claims require human review unless the required strong external evidence is present; clinical claims follow the same conservative default.
- Mock mode is deterministic and not semantically complete.
- Keyword claim extraction can miss claims or over-detect explanatory sentences.
- Evidence linking remains deterministic and heuristic. Results prose is candidate context and cannot automatically provide strong evidence for the same claim; table support requires a verifiable metric/value relationship.
- Source lines and evidence locators support navigation, but they are not formal citation anchors.
- Evidence match reasons explain retrieval heuristics; they are not proof that the evidence scientifically supports the claim.
- The verifier is conservative but rule-based.
- Optional LLM review output may be wrong and is advisory only.
- Remote providers are available only through the ClaimHarness CLI. The local Streamlit UI is mock-only and does not accept, collect, or store API keys.
- `run_manifest.json` and `project_summary_log.md` provide provenance and navigation; they are not scientific evidence, peer review, or approval records.
- ProblemBridge revision governance limits one stable target to three rounds. The limit prevents repeated local patching, but it cannot determine whether a revised specification is scientifically correct.
- PDF and figure understanding are future work.

## What The Demo Can Show

The demo shows how to turn a manuscript review task into an auditable episode package. It is useful for explaining task decomposition, evidence traceability, intermediate state, and inspectable ordered logs.

## What The Demo Should Not Claim

The demo should not be presented as a medical device, clinical review tool, diagnostic system, or publication-quality scientific reviewer. Any biomedical or clinical claim should be routed to human review unless supported by strong external evidence.

If a remote `--llm` provider is used through the ClaimHarness CLI, `llm_review.json` should be treated as an extra reviewer note. It does not override deterministic claim statuses, evidence links, or the need for human scientific review. Remote provider calls may send the current audit inputs to the selected third-party service, so they should not be used with private or confidential material.
