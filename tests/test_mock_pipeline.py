import csv
import hashlib
import json
from pathlib import Path

from typer.testing import CliRunner

from claim_harness.claim_extractor import extract_claims
from claim_harness.cli import app
from claim_harness.evidence_retriever import retrieve_evidence
from claim_harness.loader import load_manuscript, load_references, load_tables
from claim_harness.schemas import Claim
from claim_harness.verifier import verify_claims


DEMO_MANUSCRIPT = Path("examples/lab_report_audit_demo/manuscript.md")
DEMO_TABLES = Path("examples/lab_report_audit_demo/tables")
DEMO_REFERENCES = Path("examples/lab_report_audit_demo/references.md")
EXPECTED_OUTPUTS = [
    "claim_table.csv",
    "evidence_map.json",
    "audit_report.md",
    "revision_suggestions.md",
    "agent_trace.jsonl",
]
RUN_RECORD_OUTPUTS = ["run_manifest.json", "project_summary_log.md"]


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
    assert {
        "supported",
        "weakly_supported",
        "unsupported",
        "overclaimed",
        "needs_human_review",
    }.issubset(statuses)


def test_mock_cli_run_writes_required_outputs(tmp_path):
    output_dir = tmp_path / "lab_report_audit_demo_run"
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
    for filename in [*EXPECTED_OUTPUTS, *RUN_RECORD_OUTPUTS]:
        assert (output_dir / filename).exists(), filename

    with (output_dir / "claim_table.csv").open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    statuses = {row["status"] for row in rows}

    assert len(rows) >= 10
    assert "source_line" in rows[0]
    assert rows[0]["source_line"]
    assert {
        "supported",
        "weakly_supported",
        "unsupported",
        "overclaimed",
        "needs_human_review",
    }.issubset(statuses)

    evidence_map = json.loads((output_dir / "evidence_map.json").read_text(encoding="utf-8"))
    trace_lines = (output_dir / "agent_trace.jsonl").read_text(encoding="utf-8").strip().splitlines()
    trace_events = [json.loads(line) for line in trace_lines]
    manifest = json.loads((output_dir / "run_manifest.json").read_text(encoding="utf-8"))
    summary_log = (output_dir / "project_summary_log.md").read_text(encoding="utf-8")

    assert evidence_map["claims"]
    assert any(item.get("claim_link_reasons") for item in evidence_map["evidence"])
    assert len(trace_lines) >= 5
    assert {event["run_id"] for event in trace_events} == {manifest["run_id"]}
    assert all(event["created_at"] for event in trace_events)
    assert manifest["inputs"]["manuscript"]["name"] == DEMO_MANUSCRIPT.name
    assert str(DEMO_MANUSCRIPT.resolve().parent) not in json.dumps(manifest)
    output_records = {item["name"]: item for item in manifest["outputs"]}
    assert output_records["audit_report.md"]["sha256"] == hashlib.sha256(
        (output_dir / "audit_report.md").read_bytes()
    ).hexdigest()
    assert "at most 3 revision rounds" in summary_log
    assert manifest["run_id"] in summary_log
    assert "claims" in result.output.lower()
    assert str(output_dir) in result.output


def test_demo_cli_command_generates_audit_and_viewer_outside_repository_cwd(tmp_path, monkeypatch):
    output_dir = tmp_path / "demo_run"
    runner = CliRunner()
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["demo", "--out", str(output_dir)])

    assert result.exit_code == 0, result.output
    for filename in [*EXPECTED_OUTPUTS, *RUN_RECORD_OUTPUTS, "index.html"]:
        assert (output_dir / filename).exists(), filename
    assert "Demo audit complete" in result.output


def test_mock_run_replaces_owned_outputs_and_preserves_unknown_files(tmp_path):
    output_dir = tmp_path / "reused_run"
    output_dir.mkdir()
    (output_dir / "llm_review.json").write_text('{"summary": "stale"}', encoding="utf-8")
    (output_dir / "index.html").write_text("stale viewer", encoding="utf-8")
    (output_dir / "audit_report.md").write_text("stale audit", encoding="utf-8")
    (output_dir / "project_summary_log.md").write_text("stale summary", encoding="utf-8")
    (output_dir / "keep.txt").write_text("user-owned", encoding="utf-8")
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
    assert not (output_dir / "llm_review.json").exists()
    assert not (output_dir / "index.html").exists()
    assert "stale audit" not in (output_dir / "audit_report.md").read_text(encoding="utf-8")
    assert "stale summary" not in (output_dir / "project_summary_log.md").read_text(encoding="utf-8")
    assert (output_dir / "keep.txt").read_text(encoding="utf-8") == "user-owned"


def test_references_are_optional_for_a_local_mock_run(tmp_path):
    output_dir = tmp_path / "without_references"
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "run",
            "--manuscript",
            str(DEMO_MANUSCRIPT),
            "--tables",
            str(DEMO_TABLES),
            "--out",
            str(output_dir),
            "--llm",
            "mock",
        ],
    )

    assert result.exit_code == 0, result.output
    manifest = json.loads((output_dir / "run_manifest.json").read_text(encoding="utf-8"))
    assert manifest["inputs"]["references"] is None
    assert "References: not supplied" in (
        output_dir / "project_summary_log.md"
    ).read_text(encoding="utf-8")


def test_verifier_flags_generic_deployment_overclaims():
    claim = Claim(
        claim_id="C999",
        text="The workflow is ready for real-world operational deployment.",
        source_section="Discussion",
        claim_type="deployment_claim",
        strength="high",
        requires_evidence=["external validation"],
    )

    result = verify_claims([claim], [])[0]

    assert result.status == "overclaimed"
    assert result.risk_level == "high"
    assert "deployment" in result.reason.lower()


def test_claim_extractor_uses_generic_deployment_claim_type():
    sections = load_manuscript(DEMO_MANUSCRIPT)
    claims = extract_claims(sections)

    assert any(claim.claim_type == "deployment_claim" for claim in claims)
    assert all(claim.claim_type != "clinical_claim" for claim in claims)
