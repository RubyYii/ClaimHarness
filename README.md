# ClaimHarness

A lightweight Agent Harness for scientific claim-evidence auditing.

ClaimHarness is being built as a small, reproducible Python demo. It will take a Markdown manuscript, CSV result tables, and references, then produce an auditable claim-evidence package.

## Expected Input

- `manuscript.md`
- `tables/*.csv`
- `references.md`

## Demo Input Structure

The first synthetic demo lives under `examples/oocyte_demo/`:

```text
examples/oocyte_demo/
  manuscript.md
  references.md
  tables/
    table1_metrics.csv
    table2_ablation.csv
```

The manuscript is fully synthetic and describes a human-in-the-loop, explainable workflow for oocyte injection guidance. The tables are toy result tables designed to exercise future claim extraction, evidence retrieval, and verification logic.

## Expected Output

- `claim_table.csv`
- `evidence_map.json`
- `audit_report.md`
- `revision_suggestions.md`
- `agent_trace.jsonl`

## Current Status

The repository currently contains the initial deterministic mock audit pipeline. Mock mode runs without API keys.

## Development Commands

```bash
python -m claim_harness run --help
pytest
```

## Mock Demo Command

```bash
python -m claim_harness run \
  --manuscript examples/oocyte_demo/manuscript.md \
  --tables examples/oocyte_demo/tables \
  --references examples/oocyte_demo/references.md \
  --out outputs/oocyte_demo_run \
  --llm mock
```

The command writes:

- `claim_table.csv`
- `evidence_map.json`
- `audit_report.md`
- `revision_suggestions.md`
- `agent_trace.jsonl`
