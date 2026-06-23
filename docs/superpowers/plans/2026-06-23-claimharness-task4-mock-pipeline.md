# ClaimHarness Task 4 Mock Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `--llm mock` run end-to-end and generate the five required audit package files.

**Architecture:** The CLI loads inputs, builds context, extracts deterministic keyword claims, retrieves evidence from CSV rows and manuscript text, verifies claims with conservative rules, writes reports, and records a JSONL trace. Each pipeline module remains small and framework-free.

**Tech Stack:** Python 3.10+, Typer, Rich, Pydantic v2, Pandas, Pytest.

---

## File Structure

- Modify `claim_harness/cli.py`: wire the mock pipeline behind `python -m claim_harness run`.
- Modify `claim_harness/context_manager.py`: add a typed `AuditContext` container and `build_context`.
- Modify `claim_harness/claim_extractor.py`: add deterministic keyword claim extraction.
- Modify `claim_harness/evidence_retriever.py`: add table/text/reference evidence extraction and keyword linking.
- Modify `claim_harness/verifier.py`: add conservative verification rules.
- Modify `claim_harness/audit_logger.py`: add JSONL trace writer.
- Modify `claim_harness/report_generator.py`: write `claim_table.csv`, `evidence_map.json`, `audit_report.md`, and `revision_suggestions.md`.
- Modify `claim_harness/llm.py`: expose supported provider validation for `mock`.
- Create `tests/test_mock_pipeline.py`: module and end-to-end CLI tests.
- Modify `README.md`: add the current mock run command and expected output files.

### Task 1: Add End-To-End Mock Pipeline Tests

**Files:**
- Create: `tests/test_mock_pipeline.py`

- [ ] **Step 1: Write failing mock pipeline tests**

Create `tests/test_mock_pipeline.py`:

```python
import csv
import json
from pathlib import Path

from typer.testing import CliRunner

from claim_harness.claim_extractor import extract_claims
from claim_harness.cli import app
from claim_harness.evidence_retriever import retrieve_evidence
from claim_harness.loader import load_manuscript, load_references, load_tables
from claim_harness.verifier import verify_claims


DEMO_MANUSCRIPT = Path("examples/oocyte_demo/manuscript.md")
DEMO_TABLES = Path("examples/oocyte_demo/tables")
DEMO_REFERENCES = Path("examples/oocyte_demo/references.md")
EXPECTED_OUTPUTS = [
    "claim_table.csv",
    "evidence_map.json",
    "audit_report.md",
    "revision_suggestions.md",
    "agent_trace.jsonl",
]


def test_deterministic_modules_produce_claims_evidence_and_statuses():
    sections = load_manuscript(DEMO_MANUSCRIPT)
    tables = load_tables(DEMO_TABLES)
    references = load_references(DEMO_REFERENCES)

    claims = extract_claims(sections)
    evidence = retrieve_evidence(claims, sections, tables, references)
    results = verify_claims(claims, evidence)
    statuses = {result.status for result in results}

    assert len(claims) >= 10
    assert claims[0].claim_id == "C001"
    assert any(claim.claim_type == "performance_claim" for claim in claims)
    assert any(item.evidence_type == "quantitative_result" for item in evidence)
    assert any(item.linked_claim_ids for item in evidence)
    assert {"supported", "weakly_supported", "overclaimed"}.issubset(statuses)


def test_mock_cli_run_writes_required_outputs(tmp_path):
    output_dir = tmp_path / "oocyte_demo_run"
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "run",
            "--manuscript",
            str(DEMO_MANUSCRIPT),
            "--tables",
            str(DEMO_TABLES),
            "--references",
            str(DEMO_REFERENCES),
            "--out",
            str(output_dir),
            "--llm",
            "mock",
        ],
    )

    assert result.exit_code == 0, result.output
    for filename in EXPECTED_OUTPUTS:
        assert (output_dir / filename).exists(), filename

    with (output_dir / "claim_table.csv").open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    statuses = {row["status"] for row in rows}

    assert len(rows) >= 10
    assert {"supported", "weakly_supported", "overclaimed"}.issubset(statuses)

    evidence_map = json.loads((output_dir / "evidence_map.json").read_text(encoding="utf-8"))
    trace_lines = (output_dir / "agent_trace.jsonl").read_text(encoding="utf-8").strip().splitlines()

    assert evidence_map["claims"]
    assert len(trace_lines) >= 5
    assert "claims" in result.output.lower()
    assert str(output_dir) in result.output
```

- [ ] **Step 2: Run tests to verify they fail before implementation**

Run:

```bash
.venv\Scripts\python.exe -m pytest tests/test_mock_pipeline.py -v
```

Expected: FAIL because mock pipeline functions are not implemented yet.

### Task 2: Implement Deterministic Pipeline Modules

**Files:**
- Modify: `claim_harness/context_manager.py`
- Modify: `claim_harness/claim_extractor.py`
- Modify: `claim_harness/evidence_retriever.py`
- Modify: `claim_harness/verifier.py`
- Modify: `claim_harness/audit_logger.py`
- Modify: `claim_harness/report_generator.py`
- Modify: `claim_harness/llm.py`

- [ ] **Step 3: Implement context and provider helpers**

Implement a dataclass `AuditContext` with `manuscript_sections`, `tables`, and `references`, plus `build_context(...)`. In `llm.py`, implement `SUPPORTED_PROVIDERS = {"mock"}` and `validate_provider(provider)`.

- [ ] **Step 4: Implement deterministic claim extraction**

Implement `extract_claims(sections) -> list[Claim]` using keyword sentence matching for: `improves`, `outperforms`, `robust`, `reliable`, `clinically`, `ready`, `novel`, `first`, `supports`, `enables`, `reduces`, `increases`, `auditable`, `explainable`. Assign IDs `C001`, `C002`, etc. Classify into `performance_claim`, `novelty_claim`, `clinical_claim`, `robustness_claim`, `workflow_claim`, or `general_claim`.

- [ ] **Step 5: Implement deterministic evidence retrieval**

Implement `retrieve_evidence(claims, sections, tables, references) -> list[EvidenceItem]`. Convert CSV rows into table evidence, Results sentences into narrative evidence, reference lines into citation evidence, and limitation-like Discussion sentences into limitation evidence. Link evidence to claims using keyword overlap.

- [ ] **Step 6: Implement conservative verification**

Implement `verify_claims(claims, evidence) -> list[VerificationResult]`. Rules: clinical deployment or diagnosis language without strong table evidence is `overclaimed`; table evidence is `supported`; narrative/citation/limitation-only evidence is `weakly_supported`; no evidence is `unsupported`; biomedical or clinical claims raise risk.

- [ ] **Step 7: Implement audit logging and report generation**

Implement JSONL logging with `AuditLogger.log(module, message, data)`. Implement `write_outputs(out_dir, claims, evidence, results, trace_path)` to generate `claim_table.csv`, `evidence_map.json`, `audit_report.md`, and `revision_suggestions.md`.

### Task 3: Wire CLI

**Files:**
- Modify: `claim_harness/cli.py`
- Modify: `README.md`

- [ ] **Step 8: Wire `run` command to the mock pipeline**

Update `run` so it requires manuscript, tables, and references paths for the mock pipeline, validates `--llm mock`, creates the output directory, logs each module step, calls the pipeline modules, writes outputs, and prints a summary with claim counts and output path.

- [ ] **Step 9: Update README mock command**

Add the end-to-end mock command and list the five expected output files.

### Task 4: Verify And Commit

**Files:**
- Test: `tests/test_mock_pipeline.py`
- Run: full test suite

- [ ] **Step 10: Run focused mock pipeline tests**

Run:

```bash
.venv\Scripts\python.exe -m pytest tests/test_mock_pipeline.py -v
```

Expected: PASS.

- [ ] **Step 11: Run full test suite**

Run:

```bash
.venv\Scripts\python.exe -m pytest
```

Expected: PASS.

- [ ] **Step 12: Run actual demo command**

Run:

```bash
.venv\Scripts\python.exe -m claim_harness run --manuscript examples/oocyte_demo/manuscript.md --tables examples/oocyte_demo/tables --references examples/oocyte_demo/references.md --out outputs/oocyte_demo_run --llm mock
```

Expected: exit code 0 and `outputs/oocyte_demo_run` contains all five required output files.

- [ ] **Step 13: Commit Task 4**

```bash
git add claim_harness tests README.md
git commit -m "Implement deterministic mock audit pipeline"
```

## Self-Review

- Spec coverage: covers deterministic claim extraction, evidence retrieval, verification, JSONL audit trace, required reports, CLI wiring, and README command.
- Placeholder scan: removes placeholder contents from all Task 4 modules touched by the pipeline.
- Scope check: does not add OpenAI-compatible API support, Streamlit UI, PDF parsing, or heavy agent frameworks.
- Type consistency: functions consume and return the schema models from Task 3.
