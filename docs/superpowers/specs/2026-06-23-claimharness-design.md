# ClaimHarness Product Design

## Purpose

ClaimHarness is a lightweight Agent Harness for scientific claim-evidence auditing. It turns a Markdown manuscript, result tables, and references into an auditable episode package that exposes claims, evidence links, verification labels, revision suggestions, and a replayable trace log.

This is not a prompt-only reviewer and not a replacement for peer review. The product demonstrates an Agent Harness layer around a scientific review task: task specification, context selection, tool/data access, intermediate state tracking, verification, human-review routing, and trace logging.

## V1 Product Boundary

V1 is a command-line Python package. It must run locally, from the repository root, without API keys.

Required input:

- `manuscript.md`: Markdown manuscript text.
- `tables/*.csv`: result tables used as structured evidence.
- `references.md`: references or background notes.

Required output:

- `claim_table.csv`: one row per extracted claim with status and rationale.
- `evidence_map.json`: claim-to-evidence links.
- `audit_report.md`: human-readable summary of findings.
- `revision_suggestions.md`: suggested rewrites for weak, unsupported, overclaimed, or human-review claims.
- `agent_trace.jsonl`: step-by-step JSONL audit events.

The minimum command is:

```bash
python -m claim_harness run --manuscript examples/oocyte_demo/manuscript.md --tables examples/oocyte_demo/tables --references examples/oocyte_demo/references.md --out outputs/oocyte_demo_run --llm mock
```

## V1 Required Capabilities

1. Provide a Python package named `claim_harness`.
2. Provide a CLI entry point that supports `python -m claim_harness run --help`.
3. Include synthetic demo inputs for an oocyte injection guidance manuscript.
4. Parse Markdown manuscript sections and CSV result tables.
5. Extract claims deterministically in mock mode using transparent keyword rules.
6. Retrieve possible evidence from tables, Results text, references, and limitation statements.
7. Verify each claim as `supported`, `weakly_supported`, `unsupported`, `overclaimed`, or `needs_human_review`.
8. Generate the five required output files.
9. Log each major pipeline step to `agent_trace.jsonl`.
10. Provide tests for imports, CLI help, loaders, demo inputs, and the end-to-end mock run.
11. Document architecture, demo walkthrough, and limitations.

## V1.1 Optional Capability

After the mock pipeline is stable, add `--llm openai-compatible` as an optional provider. It must:

- Keep `--llm mock` as the default.
- Read `OPENAI_API_KEY`, optional `OPENAI_BASE_URL`, and optional `OPENAI_MODEL`.
- Never hardcode API keys.
- Request structured JSON.
- Fail gracefully if the API key is missing.
- Use prompt files under `prompts/`.

This provider is not required for the first runnable demo.

## Out Of Scope

V1 must not include:

- LangChain, AutoGen, CrewAI, or other heavy agent frameworks.
- Real patient data, private medical data, or unpublished confidential manuscripts.
- PDF parsing, figure understanding, or multimodal evidence review.
- Claims of clinical safety, diagnostic validity, or publication readiness.
- A broad DeepSeek-specific, Gemini-specific, HSG, VULCA, or submission-quality review system.
- A required UI. Streamlit may be added later, but CLI plus audit package is the core.

## Architecture

The pipeline is deliberately small and explicit:

```text
Task Spec
  -> Context Manager
  -> Claim Extractor
  -> Evidence Retriever
  -> Verifier
  -> Report Generator
  -> Audit Package
```

Module responsibilities:

- `cli.py`: parse command-line options and orchestrate the run.
- `loader.py`: load manuscript sections, CSV tables, and references.
- `schemas.py`: define shared Pydantic data models.
- `context_manager.py`: assemble loaded inputs into the context passed between steps.
- `claim_extractor.py`: extract claims and assign claim IDs.
- `evidence_retriever.py`: create evidence items and link them to claims.
- `verifier.py`: classify claim support and risk.
- `report_generator.py`: write CSV, JSON, and Markdown outputs.
- `audit_logger.py`: write JSONL trace events.
- `llm.py`: isolate provider selection, starting with deterministic mock behavior.

## Data Rules

Every claim must have:

- `claim_id`
- `text`
- `source_section`
- `claim_type`
- `strength`
- `requires_evidence`

Every evidence item must have:

- `evidence_id`
- `source`
- `evidence_type`
- `text`
- `linked_claim_ids`

Every verification result must have:

- `claim_id`
- `status`
- `reason`
- `risk_level`
- `suggested_revision`

## Verification Rules

The deterministic mock verifier should be conservative:

- Table evidence with matching performance or ablation language can support a claim.
- Narrative-only evidence should usually be `weakly_supported`.
- Claims without evidence should be `unsupported`.
- Claims containing clinical deployment, diagnosis, or clinically ready language should be `overclaimed` or `needs_human_review` unless strong evidence is present.
- Biomedical or high-risk claims should increase `risk_level`.

## Demo Story

The synthetic demo manuscript topic is:

```text
Human-in-the-loop and explainable workflow for oocyte injection guidance
```

The manuscript must be fully synthetic. It should contain 12 to 18 claims, including supported, weakly supported, unsupported, and intentionally overclaimed examples. It must not copy from private work or include real patient/clinical data.

## Success Criteria

The repository is application-ready when:

1. GitHub repo opens cleanly.
2. README clearly explains the product, command, outputs, and limitations.
3. One mock command runs end-to-end.
4. `outputs/oocyte_demo_run` contains all five required output files.
5. `claim_table.csv` contains 10 to 20 claims.
6. Results include at least `supported`, `weakly_supported`, and `overclaimed`.
7. `agent_trace.jsonl` shows each major step.
8. `docs/limitations.md` is conservative.
9. `pytest` passes.

## Presentation Script

Use this framing:

```text
I built a small ClaimHarness demo to show how I think about Agent Harness design.
```

Show in this order:

1. README first screen.
2. Architecture diagram.
3. Run command.
4. `claim_table.csv`.
5. `audit_report.md`.
6. `agent_trace.jsonl`.
7. `docs/limitations.md`.

Emphasize:

```text
This is not a prompt-only reviewer. It decomposes the task into task specification, context selection, claim extraction, evidence retrieval, verification, human-review routing, and trace logging.
```
