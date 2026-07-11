from pathlib import Path

from typer.testing import CliRunner

import claim_harness
import claim_harness.cli as cli_module
from claim_harness.cli import app
from claim_harness.llm import LLMProviderError


DEMO_MANUSCRIPT = Path("examples/lab_report_audit_demo/manuscript.md")
DEMO_TABLES = Path("examples/lab_report_audit_demo/tables")
DEMO_REFERENCES = Path("examples/lab_report_audit_demo/references.md")


def test_package_imports():
    assert claim_harness.__version__


def test_run_help_command():
    runner = CliRunner()
    result = runner.invoke(app, ["run", "--help"])

    assert result.exit_code == 0
    assert "Run a ClaimHarness audit" in result.output
    assert "--manuscript" in result.output
    assert "--llm" in result.output


def test_run_help_documents_common_provider_presets():
    runner = CliRunner()
    result = runner.invoke(app, ["run", "--help"])

    assert result.exit_code == 0
    assert "openai-compatible" in result.output
    assert "deepseek" in result.output
    assert "gemini" in result.output
    assert "anthropic" in result.output


def test_run_subcommand_requires_inputs():
    runner = CliRunner()
    result = runner.invoke(app, ["run"])

    assert result.exit_code != 0
    assert "--manuscript" in result.output


def test_openai_compatible_provider_requires_api_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    runner = CliRunner()

    result = runner.invoke(app, ["run", "--llm", "openai-compatible"])

    assert result.exit_code != 0
    assert "OPENAI_API_KEY" in result.output


def test_deepseek_provider_requires_deepseek_api_key(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    runner = CliRunner()

    result = runner.invoke(app, ["run", "--llm", "deepseek"])

    assert result.exit_code != 0
    assert "DEEPSEEK_API_KEY" in result.output


def test_remote_provider_failure_is_reported_without_internal_traceback(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    def fail_review(*args, **kwargs):
        raise LLMProviderError("provider unavailable")

    monkeypatch.setattr(cli_module, "summarize_audit_with_llm", fail_review)
    output_dir = tmp_path / "remote_failure"
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
            "openai-compatible",
        ],
    )

    assert result.exit_code == 1
    assert "deterministic audit outputs were written" in result.output.lower()
    assert "provider unavailable" in result.output
    assert "AttributeError" not in result.output
    assert "Traceback" not in result.output
    assert (output_dir / "claim_table.csv").is_file()
    assert (output_dir / "agent_trace.jsonl").is_file()
    assert (output_dir / "run_manifest.json").is_file()
    assert (output_dir / "project_summary_log.md").is_file()
    manifest = __import__("json").loads(
        (output_dir / "run_manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["provider"]["status"] == "failed"
    assert not (output_dir / "llm_review.json").exists()
