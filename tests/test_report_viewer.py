import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from claim_harness.cli import app
from claim_harness.report_viewer import MissingAuditOutput, render_report_viewer
from problem_bridge.project_lifecycle import prepare_run_directory


def write_sample_audit_package(path: Path, include_llm_review: bool = False) -> None:
    path.mkdir(parents=True, exist_ok=True)
    (path / "claim_table.csv").write_text(
        "\n".join(
            [
                "claim_id,text,source_section,claim_type,strength,status,risk_level,reason,suggested_revision",
                "C001,Escaped <claim>,Results,performance_claim,strong,supported,low,Table evidence,No revision needed",
                "C002,Deployment-ready claim,Discussion,deployment_claim,high,overclaimed,high,No validation,Narrow the claim",
            ]
        ),
        encoding="utf-8",
    )
    (path / "evidence_map.json").write_text(
        json.dumps(
            {
                "claims": [
                    {"claim_id": "C001", "text": "Escaped <claim>", "evidence_ids": ["E001"]},
                    {"claim_id": "C002", "text": "Deployment-ready claim", "evidence_ids": []},
                ],
                "evidence": [
                    {
                        "evidence_id": "E001",
                        "source": "table1_metrics.csv",
                        "evidence_type": "quantitative_result",
                        "text": "Dice improved to 0.91",
                        "linked_claim_ids": ["C001"],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (path / "audit_report.md").write_text("# Audit Report\n\nSummary text", encoding="utf-8")
    (path / "revision_suggestions.md").write_text(
        "# Revision Suggestions\n\nNarrow the claim",
        encoding="utf-8",
    )
    (path / "agent_trace.jsonl").write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "step": 1,
                        "module": "loader",
                        "message": "Loaded inputs",
                        "data": {"sections": 3},
                    }
                ),
                json.dumps(
                    {
                        "step": 2,
                        "module": "verifier",
                        "message": "Verified claims",
                        "data": {"supported": 1},
                    }
                ),
            ]
        ),
        encoding="utf-8",
    )
    (path / "project_summary_log.md").write_text(
        "# Project Summary Log\n\nRun ID: example-run\n",
        encoding="utf-8",
    )
    if include_llm_review:
        (path / "llm_review.json").write_text(
            json.dumps(
                {
                    "summary": "Advisory review",
                    "highest_risk_claims": ["C002"],
                    "recommended_next_actions": ["Human review"],
                    "limitations": ["Synthetic demo only"],
                }
            ),
            encoding="utf-8",
        )


def test_render_report_viewer_writes_static_html(tmp_path):
    run_dir = tmp_path / "audit"
    write_sample_audit_package(run_dir, include_llm_review=True)

    output = render_report_viewer(run_dir)
    html = output.read_text(encoding="utf-8")

    assert output == run_dir / "index.html"
    assert "ClaimHarness Report Viewer" in html
    assert "Claims audited" in html
    assert "supported" in html
    assert "overclaimed" in html
    assert "C001" in html
    assert "E001" in html
    assert "Audit trace" in html
    assert "Advisory LLM review" in html
    assert "Project summary log" in html
    assert "example-run" in html
    assert str(run_dir.parent) not in html
    assert "data-filter=\"weak-or-worse\"" in html
    assert "data-status=\"supported\"" in html
    assert "data-risk=\"high\"" in html
    assert "Match reason" in html
    assert "Escaped &lt;claim&gt;" in html
    assert "<claim>" not in html
    assert "Unverified legacy package" in html


def test_render_report_viewer_reports_missing_required_outputs(tmp_path):
    run_dir = tmp_path / "audit"
    run_dir.mkdir()

    try:
        render_report_viewer(run_dir)
    except MissingAuditOutput as exc:
        message = str(exc)
    else:
        raise AssertionError("Expected MissingAuditOutput")

    assert "claim_table.csv" in message
    assert "agent_trace.jsonl" in message


def test_view_cli_writes_index_html(tmp_path):
    run_dir = tmp_path / "audit"
    write_sample_audit_package(run_dir)
    runner = CliRunner()

    result = runner.invoke(app, ["view", "--run", str(run_dir)])

    assert result.exit_code == 0, result.output
    assert (run_dir / "index.html").exists()
    assert "index.html" in result.output


def test_governed_viewer_rejects_tampered_or_incomplete_artifacts(tmp_path):
    run_dir = tmp_path / "governed"
    context = prepare_run_directory(
        run_dir,
        project_id="project-viewer",
        owned_artifacts=(
            "claim_table.csv",
            "evidence_map.json",
            "audit_report.md",
            "revision_suggestions.md",
            "agent_trace.jsonl",
        ),
        required_artifacts=(
            "claim_table.csv",
            "evidence_map.json",
            "audit_report.md",
            "revision_suggestions.md",
            "agent_trace.jsonl",
            "project_summary_log.md",
        ),
    )
    with context.transaction():
        write_sample_audit_package(run_dir)

    html_path = render_report_viewer(run_dir)
    assert "Verified governed run" in html_path.read_text(encoding="utf-8")
    (run_dir / "claim_table.csv").write_text("tampered", encoding="utf-8")
    with pytest.raises(MissingAuditOutput, match="integrity"):
        render_report_viewer(run_dir)


def test_viewer_refuses_to_overwrite_package_artifact(tmp_path):
    run_dir = tmp_path / "audit"
    write_sample_audit_package(run_dir)

    with pytest.raises(MissingAuditOutput, match="Refusing to overwrite"):
        render_report_viewer(run_dir, run_dir / "audit_report.md")
