from typer.testing import CliRunner

import claim_harness
from claim_harness.cli import app


def test_package_imports():
    assert claim_harness.__version__


def test_run_help_command():
    runner = CliRunner()
    result = runner.invoke(app, ["run", "--help"])

    assert result.exit_code == 0
    assert "Run a ClaimHarness audit" in result.output
    assert "--manuscript" in result.output
    assert "--llm" in result.output


def test_run_help_documents_openai_compatible_provider():
    runner = CliRunner()
    result = runner.invoke(app, ["run", "--help"])

    assert result.exit_code == 0
    assert "openai-compatible" in result.output


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
