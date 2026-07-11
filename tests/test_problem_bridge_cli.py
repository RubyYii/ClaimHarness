from pathlib import Path

from typer.testing import CliRunner

import problem_bridge
from problem_bridge.cli import app


EXPECTED_FILES = {
    "problem_card.md",
    "workflow_map.md",
    "painpoint_opportunity_matrix.csv",
    "concept_alignment_table.csv",
    "ai_task_spec.yaml",
    "evidence_contract.yaml",
    "evaluation_protocol.md",
    "misalignment_risk_report.md",
    "human_in_loop_plan.md",
    "implementation_routes.md",
    "alignment_trace.jsonl",
    "project_record.json",
    "project_summary_log.md",
}


def test_problem_bridge_package_imports():
    assert problem_bridge.__version__


def test_align_help_documents_problem_alignment_cli():
    runner = CliRunner()
    result = runner.invoke(app, ["align", "--help"])

    assert result.exit_code == 0
    assert "Generate a Problem Alignment Package" in result.output
    assert "--brief" in result.output
    assert "--llm" in result.output


def test_align_rejects_unknown_provider(tmp_path):
    brief = tmp_path / "problem.md"
    brief.write_text("I want to build an AI model for quality inspection support.", encoding="utf-8")
    runner = CliRunner()

    result = runner.invoke(
        app,
        ["align", "--brief", str(brief), "--out", str(tmp_path / "out"), "--llm", "remote"],
    )

    assert result.exit_code != 0
    assert "mock" in result.output


def test_demo_writes_problem_alignment_package_outside_repository_cwd(tmp_path, monkeypatch):
    runner = CliRunner()
    out = tmp_path / "demo_alignment"
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["demo", "--out", str(out)])

    assert result.exit_code == 0
    assert "ProblemBridge demo complete" in result.output
    assert EXPECTED_FILES == {path.name for path in out.iterdir()}


def test_align_writes_deterministic_quality_inspection_package(tmp_path):
    runner = CliRunner()
    out = tmp_path / "quality_inspection_alignment"

    result = runner.invoke(
        app,
        [
            "align",
            "--brief",
            "examples/problem_bridge/quality_inspection/problem.md",
            "--out",
            str(out),
            "--llm",
            "mock",
        ],
    )

    assert result.exit_code == 0
    task_spec = (out / "ai_task_spec.yaml").read_text(encoding="utf-8")
    risk_report = (out / "misalignment_risk_report.md").read_text(encoding="utf-8")

    assert "quality_inspection_review_alignment" in task_spec
    assert "not_allowed_goal: autonomous pass/fail decision" in task_spec
    assert "pass/fail decision" in risk_report
