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
    brief.write_text("I want to build an AI model for HSG support.", encoding="utf-8")
    runner = CliRunner()

    result = runner.invoke(
        app,
        ["align", "--brief", str(brief), "--out", str(tmp_path / "out"), "--llm", "remote"],
    )

    assert result.exit_code != 0
    assert "mock" in result.output


def test_demo_writes_problem_alignment_package(tmp_path):
    runner = CliRunner()
    out = tmp_path / "demo_alignment"

    result = runner.invoke(app, ["demo", "--out", str(out)])

    assert result.exit_code == 0
    assert "ProblemBridge demo complete" in result.output
    assert EXPECTED_FILES == {path.name for path in out.iterdir()}


def test_align_writes_deterministic_hsg_package(tmp_path):
    runner = CliRunner()
    out = tmp_path / "hsg_alignment"

    result = runner.invoke(
        app,
        [
            "align",
            "--brief",
            "examples/problem_bridge/hsg/problem.md",
            "--out",
            str(out),
            "--llm",
            "mock",
        ],
    )

    assert result.exit_code == 0
    task_spec = (out / "ai_task_spec.yaml").read_text(encoding="utf-8")
    risk_report = (out / "misalignment_risk_report.md").read_text(encoding="utf-8")

    assert "evidence_ready_hsg_support" in task_spec
    assert "not_allowed_goal: autonomous diagnosis" in task_spec
    assert "segmentation absence" in risk_report
