# ClaimHarness

A lightweight Agent Harness for scientific claim-evidence auditing.

ClaimHarness is being built as a small, reproducible Python demo. It will take a Markdown manuscript, CSV result tables, and references, then produce an auditable claim-evidence package.

## Expected Input

- `manuscript.md`
- `tables/*.csv`
- `references.md`

## Expected Output

- `claim_table.csv`
- `evidence_map.json`
- `audit_report.md`
- `revision_suggestions.md`
- `agent_trace.jsonl`

## Current Status

The repository currently contains the initial package skeleton and CLI entry point. The deterministic mock audit pipeline will be implemented in later tasks.

## Development Commands

```bash
python -m claim_harness run --help
pytest
```
