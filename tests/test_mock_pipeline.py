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
    assert claims[0].source_line is not None
    assert claims[0].source_line > 0
    assert any(claim.claim_type == "performance_claim" for claim in claims)
    assert any(item.evidence_type == "quantitative_result" for item in evidence)
    assert any(item.linked_claim_ids for item in evidence)
    assert any(item.claim_link_reasons for item in evidence)
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
    assert "source_line" in rows[0]
    assert rows[0]["source_line"]
    assert {"supported", "weakly_supported", "overclaimed"}.issubset(statuses)

    evidence_map = json.loads((output_dir / "evidence_map.json").read_text(encoding="utf-8"))
    trace_lines = (output_dir / "agent_trace.jsonl").read_text(encoding="utf-8").strip().splitlines()

    assert evidence_map["claims"]
    assert any(item.get("claim_link_reasons") for item in evidence_map["evidence"])
    assert len(trace_lines) >= 5
    assert "claims" in result.output.lower()
    assert str(output_dir) in result.output


def test_demo_cli_command_generates_audit_and_viewer(tmp_path):
    output_dir = tmp_path / "demo_run"
    runner = CliRunner()

    result = runner.invoke(app, ["demo", "--out", str(output_dir)])

    assert result.exit_code == 0, result.output
    for filename in [*EXPECTED_OUTPUTS, "index.html"]:
        assert (output_dir / filename).exists(), filename
    assert "Demo audit complete" in result.output
