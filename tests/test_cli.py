import json
from pathlib import Path

from click.utils import strip_ansi
from typer.testing import CliRunner

import claim_harness
import claim_harness.cli as cli_module
from claim_harness.cli import app
from claim_harness.llm import LLMProviderConfig, LLMProviderError


DEMO_MANUSCRIPT = Path("examples/lab_report_audit_demo/manuscript.md")
DEMO_TABLES = Path("examples/lab_report_audit_demo/tables")
DEMO_REFERENCES = Path("examples/lab_report_audit_demo/references.md")


def test_package_imports():
    assert claim_harness.__version__


def test_provider_public_provenance_strips_credentials_but_hash_spec_binds_full_endpoint():
    first = LLMProviderConfig(
        provider="openai-compatible",
        api_key="secret-key",
        base_url="https://user:token@example.test/v1?key=hidden",
        model="model-a",
        api_style="openai-chat",
    )
    second = LLMProviderConfig(
        provider="openai-compatible",
        api_key="secret-key",
        base_url="https://user:token@example.test/v2?key=hidden",
        model="model-a",
        api_style="openai-chat",
    )

    public = cli_module._provider_public_details(first)
    persisted = json.dumps(public)
    assert public["endpoint_origin"] == "https://example.test"
    assert "user" not in persisted and "token" not in persisted and "hidden" not in persisted
    assert cli_module._provider_hash_spec(first) != cli_module._provider_hash_spec(second)


def test_run_help_command():
    runner = CliRunner()
    result = runner.invoke(app, ["run", "--help"])
    output = strip_ansi(result.output)

    assert result.exit_code == 0
    assert "Run a ClaimHarness audit" in output
    assert "--manuscript" in output
    assert "--llm" in output
    assert "--llm-timeout" in output
    assert "--mode" in output
    assert "--project-id" in output


def test_run_help_documents_common_provider_presets():
    runner = CliRunner()
    result = runner.invoke(app, ["run", "--help"])

    assert result.exit_code == 0
    assert "openai-compatible" in result.output
    assert "codex" in result.output
    assert "claude-cli" in result.output
    assert "qwen-cli" in result.output
    assert "kimi" in result.output
    assert "deepseek" in result.output
    assert "gemini" in result.output
    assert "anthropic" in result.output


def test_providers_help_documents_explicit_probe_confirmation():
    result = CliRunner().invoke(app, ["providers", "--help"])
    compact_output = "".join(strip_ansi(result.output).split())

    assert result.exit_code == 0
    assert "--probe" in compact_output
    assert "--confirm-call" in compact_output
    assert "--probe-timeout" in compact_output


def test_run_subcommand_requires_inputs():
    runner = CliRunner()
    result = runner.invoke(app, ["run"])

    assert result.exit_code != 0
    assert "--manuscript" in strip_ansi(result.output)


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


def test_kimi_provider_requires_kimi_api_key(monkeypatch):
    monkeypatch.delenv("KIMI_API_KEY", raising=False)
    runner = CliRunner()

    result = runner.invoke(app, ["run", "--llm", "kimi"])

    assert result.exit_code != 0
    assert "KIMI_API_KEY" in result.output


def test_remote_provider_failure_is_reported_without_internal_traceback(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    observed = {}

    def fail_review(config, *args, **kwargs):
        observed["timeout_seconds"] = config.timeout_seconds
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
            "--llm-timeout",
            "123",
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
    manifest = json.loads(
        (output_dir / "run_manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["provider"]["status"] == "failed"
    assert manifest["provider"]["timeout_seconds"] == 123
    assert observed["timeout_seconds"] == 123
    assert manifest["project_id"]
    assert manifest["run_id"] == json.loads(
        (output_dir / "run_identity.json").read_text(encoding="utf-8")
    )["run_id"]
    assert (output_dir / "run_complete.json").is_file()
    assert not (output_dir / "llm_review.json").exists()


def test_run_rejects_provider_timeout_outside_bounded_range():
    result = CliRunner().invoke(app, ["run", "--llm-timeout", "601"])

    assert result.exit_code != 0
    assert "600" in result.output


def test_run_requires_explicit_identity_guard_before_replacing_outputs(tmp_path):
    output_dir = tmp_path / "governed_run"
    runner = CliRunner()
    command = [
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
        "--project-id",
        "project-claim-cli",
    ]

    first = runner.invoke(app, command)
    identity = json.loads((output_dir / "run_identity.json").read_text(encoding="utf-8"))
    second = runner.invoke(app, command)
    missing_guard = runner.invoke(app, [*command, "--mode", "replace"])
    wrong_guard = runner.invoke(
        app,
        [*command, "--mode", "replace", "--expected-run-id", "run-wrong"],
    )
    replaced = runner.invoke(
        app,
        [
            *command,
            "--mode",
            "replace",
            "--expected-run-id",
            identity["run_id"],
        ],
    )

    assert first.exit_code == 0, first.output
    assert second.exit_code != 0
    assert "new mode requires an empty directory" in second.output.lower()
    assert missing_guard.exit_code != 0
    assert "expected-run-id" in strip_ansi(missing_guard.output).lower()
    assert wrong_guard.exit_code != 0
    assert "mismatch" in wrong_guard.output.lower()
    assert replaced.exit_code == 0, replaced.output
    replacement_identity = json.loads(
        (output_dir / "run_identity.json").read_text(encoding="utf-8")
    )
    assert replacement_identity["project_id"] == "project-claim-cli"
    assert replacement_identity["run_id"] != identity["run_id"]
