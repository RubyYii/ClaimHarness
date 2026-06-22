# AGENTS.md

## Project goal

Build ClaimHarness: a lightweight Agent Harness for scientific claim-evidence auditing.

The system should take a manuscript, result tables, and optional references as input, then produce an auditable episode package:

- `claim_table.csv`
- `evidence_map.json`
- `audit_report.md`
- `revision_suggestions.md`
- `agent_trace.jsonl`

The goal is not to replace peer reviewers. The goal is to make scientific claims more traceable, reviewable, and evidence-aware.

## Engineering rules

- Use Python 3.10+.
- Keep the first version simple and reproducible.
- Do not use LangChain, AutoGen, CrewAI, or other heavy agent frameworks in v1.
- Use a small modular architecture.
- Support a deterministic mock LLM provider so the demo works without API keys.
- Add optional OpenAI-compatible API support only after the mock pipeline works.
- Do not use private medical data, real patient data, or unpublished confidential manuscripts.
- Do not hardcode absolute local paths.
- Every command should run from the repository root.
- Prefer clear JSON, CSV, and Markdown outputs over complex UI.
- Each implementation task should update README or docs when behavior changes.

## Required repository structure

```text
claim-harness/
  claim_harness/
    __init__.py
    __main__.py
    cli.py
    schemas.py
    loader.py
    context_manager.py
    claim_extractor.py
    evidence_retriever.py
    verifier.py
    report_generator.py
    audit_logger.py
    llm.py
  examples/
    oocyte_demo/
      manuscript.md
      references.md
      tables/
        table1_metrics.csv
        table2_ablation.csv
    general_demo/
      manuscript.md
      references.md
      tables/
        results.csv
  outputs/
  tests/
  docs/
    architecture.md
    demo_walkthrough.md
    limitations.md
  README.md
  pyproject.toml
```

## Done criteria

A task is complete only if:

1. The command below runs successfully:

   ```bash
   python -m claim_harness run --manuscript examples/oocyte_demo/manuscript.md --tables examples/oocyte_demo/tables --references examples/oocyte_demo/references.md --out outputs/oocyte_demo_run --llm mock
   ```

2. The output folder contains:

   - `claim_table.csv`
   - `evidence_map.json`
   - `audit_report.md`
   - `revision_suggestions.md`
   - `agent_trace.jsonl`

3. `pytest` passes.

4. README includes the current command and expected outputs.

## Design principles

- The pipeline should expose intermediate states.
- Every claim must have a `claim_id`.
- Every evidence item must have an `evidence_id`.
- The verifier must classify each claim as one of:
  - `supported`
  - `weakly_supported`
  - `unsupported`
  - `overclaimed`
  - `needs_human_review`
- High-risk biomedical or clinical claims should default to `needs_human_review` or `overclaimed` unless strong evidence is present.
- The audit log should record each pipeline step in JSONL format.

## Scope guardrails

Do not turn v1 into a general agent platform, medical reviewer, submission-quality review system, or multi-project integration. Keep each task narrow: loader, mock verifier, tests, docs, sample outputs, or one bounded provider integration at a time.
