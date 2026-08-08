import json
import os
import socket
import subprocess

from click.utils import strip_ansi
from typer.testing import CliRunner

import claim_harness.cli as cli_module
import claim_harness.provider_status as provider_status
from claim_harness.cli import app
from claim_harness.llm import LLMProviderConfig, LLMProviderError, MissingProviderConfig


def _by_name(statuses):
    return {status.provider: status for status in statuses}


def test_provider_status_is_offline_and_never_executes_discovered_clients(monkeypatch):
    def fail_network(*args, **kwargs):
        raise AssertionError("provider inspection must not open a network socket")

    def fail_process(*args, **kwargs):
        raise AssertionError("provider inspection must not execute a client")

    monkeypatch.setattr(socket, "socket", fail_network)
    monkeypatch.setattr(socket, "create_connection", fail_network)
    monkeypatch.setattr(subprocess, "Popen", fail_process)
    monkeypatch.setattr(subprocess, "run", fail_process)

    statuses = provider_status.inspect_provider_availability()

    assert statuses
    assert _by_name(statuses)["mock"].state == "ready"


def test_provider_status_reports_selectable_and_detection_only_options(monkeypatch):
    monkeypatch.setattr(
        provider_status,
        "resolve_local_agent_executable",
        lambda selected: f"C:/private/{selected}.cmd",
    )
    monkeypatch.setattr(
        provider_status.shutil,
        "which",
        lambda command: (
            "C:/private/kimi.cmd" if command in {"kimi", "kimi.cmd"} else None
        ),
    )

    statuses = _by_name(provider_status.inspect_provider_availability())

    assert statuses["codex"].selectable is True
    assert statuses["codex"].state == "installed"
    assert statuses["kimi-cli"].selectable is False
    assert statuses["kimi-cli"].state == "detected_only"
    assert statuses["deepcode-cli"].selectable is False


def test_provider_status_distinguishes_invalid_executable_override(monkeypatch):
    monkeypatch.setenv("CLAIMHARNESS_CODEX_BIN", "C:/invalid/not-a-client.txt")
    monkeypatch.setattr(
        provider_status,
        "resolve_local_agent_executable",
        lambda selected: (_ for _ in ()).throw(
            provider_status.LocalAgentCLIError("invalid executable")
        )
        if selected == "codex"
        else f"C:/tools/{selected}.cmd",
    )

    status = _by_name(provider_status.inspect_provider_availability())["codex"]

    assert status.state == "invalid_config"
    assert "CLAIMHARNESS_CODEX_BIN" in status.detail
    assert "not-a-client" not in status.detail


def test_providers_json_omits_secrets_urls_and_executable_paths(monkeypatch, tmp_path):
    secret = "do-not-print-this-kimi-key"
    executable_name = "codex.cmd" if os.name == "nt" else "codex"
    private_executable = tmp_path / "private-codex-location" / executable_name
    private_executable.parent.mkdir()
    private_executable.write_text("@echo off\n", encoding="utf-8")
    if os.name != "nt":
        private_executable.chmod(0o700)
    monkeypatch.setenv("KIMI_API_KEY", secret)
    monkeypatch.setenv("KIMI_BASE_URL", "https://private.example.test/v1")
    monkeypatch.setenv("CLAIMHARNESS_CODEX_BIN", str(private_executable))

    result = CliRunner().invoke(app, ["providers", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    serialized = json.dumps(payload)
    assert payload["offline_check"] is True
    assert payload["inventory_offline"] is True
    assert payload["provider_call_performed"] is False
    assert secret not in serialized
    assert "private.example.test" not in serialized
    assert str(private_executable) not in serialized
    statuses = {item["provider"]: item for item in payload["providers"]}
    assert statuses["kimi"]["state"] == "configured"
    assert statuses["codex"]["state"] == "installed"


def test_invalid_kimi_endpoint_is_reported_without_echoing_sensitive_url(monkeypatch):
    monkeypatch.setenv("KIMI_API_KEY", "configured-but-not-verified")
    monkeypatch.setenv(
        "KIMI_BASE_URL",
        "https://user:password@private.example.test/v1?token=hidden",
    )

    status = _by_name(provider_status.inspect_provider_availability())["kimi"]
    serialized = json.dumps(status.to_dict())

    assert status.state == "invalid_config"
    assert "password" not in serialized
    assert "private.example.test" not in serialized
    assert "hidden" not in serialized


def test_providers_table_explains_that_check_is_offline():
    result = CliRunner().invoke(app, ["providers"])

    assert result.exit_code == 0
    assert "offline check" in result.output.lower()
    assert "no client was executed" in result.output.lower()
    assert "kimi" in result.output.lower()
    assert "deepseek" in result.output.lower()


def test_provider_probe_requires_explicit_confirmation(monkeypatch):
    def must_not_probe(*args, **kwargs):
        raise AssertionError("probe must not run without confirmation")

    monkeypatch.setattr(cli_module, "probe_provider_availability", must_not_probe)

    result = CliRunner().invoke(app, ["providers", "--probe", "codex"])

    assert result.exit_code != 0
    assert "confirm-call" in strip_ansi(result.output)


def test_provider_probe_rejects_confirmation_without_selected_provider(monkeypatch):
    def must_not_probe(*args, **kwargs):
        raise AssertionError("probe must not run without a selected provider")

    monkeypatch.setattr(cli_module, "probe_provider_availability", must_not_probe)

    result = CliRunner().invoke(app, ["providers", "--confirm-call"])

    assert result.exit_code != 0


def test_confirmed_provider_probe_reports_sanitized_json(monkeypatch):
    observed = {}

    def fake_probe(provider, *, timeout_seconds):
        observed.update(provider=provider, timeout_seconds=timeout_seconds)
        return provider_status.ProviderProbeResult(
            provider=provider,
            state="ready",
            attempted=True,
            timeout_seconds=timeout_seconds,
            detail=(
                "one synthetic structured-output probe succeeded; this does not "
                "guarantee future availability"
            ),
        )

    monkeypatch.setattr(cli_module, "probe_provider_availability", fake_probe)

    result = CliRunner().invoke(
        app,
        [
            "providers",
            "--json",
            "--probe",
            "codex",
            "--confirm-call",
            "--probe-timeout",
            "17",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["offline_check"] is False
    assert payload["inventory_offline"] is True
    assert payload["provider_call_performed"] is True
    assert payload["probe"]["state"] == "ready"
    assert observed == {"provider": "codex", "timeout_seconds": 17}


def test_failed_provider_probe_uses_generic_error_and_nonzero_exit(monkeypatch):
    secret = "provider-secret-must-not-appear"

    def fake_probe(provider, *, timeout_seconds):
        return provider_status.ProviderProbeResult(
            provider=provider,
            state="failed",
            attempted=True,
            timeout_seconds=timeout_seconds,
            detail="synthetic structured-output probe failed; check provider settings",
        )

    monkeypatch.setattr(cli_module, "probe_provider_availability", fake_probe)
    monkeypatch.setenv("OPENAI_API_KEY", secret)

    result = CliRunner().invoke(
        app,
        [
            "providers",
            "--json",
            "--probe",
            "openai",
            "--confirm-call",
        ],
    )

    assert result.exit_code == 1
    assert secret not in result.output
    assert json.loads(result.output)["probe"]["state"] == "failed"


def test_probe_helper_does_not_call_provider_when_config_is_missing(monkeypatch):
    monkeypatch.setattr(
        provider_status,
        "resolve_provider_config",
        lambda provider: (_ for _ in ()).throw(MissingProviderConfig("missing secret")),
    )

    def must_not_call(*args, **kwargs):
        raise AssertionError("missing configuration must prevent provider calls")

    result = provider_status.probe_provider_availability(
        "codex", provider_caller=must_not_call
    )

    assert result.state == "not_attempted"
    assert result.attempted is False
    assert "missing secret" not in result.detail


def test_probe_helper_uses_synthetic_prompts_and_bounded_timeout(monkeypatch):
    config = LLMProviderConfig(
        provider="codex",
        api_style="local-agent-cli",
        executable="codex.cmd",
    )
    monkeypatch.setattr(provider_status, "resolve_provider_config", lambda provider: config)
    observed = {}

    def fake_call(resolved, system_prompt, user_prompt):
        observed.update(
            timeout=resolved.timeout_seconds,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )
        return {
            "summary": "Synthetic provider probe completed",
            "highest_risk_claims": [],
            "recommended_next_actions": [],
            "limitations": [],
        }

    result = provider_status.probe_provider_availability(
        "codex", timeout_seconds=23, provider_caller=fake_call
    )

    assert result.state == "ready"
    assert result.attempted is True
    assert observed["timeout"] == 23
    assert "synthetic" in observed["system_prompt"].lower()
    assert "synthetic" in observed["user_prompt"].lower()


def test_probe_helper_redacts_provider_failure_detail(monkeypatch):
    config = LLMProviderConfig(
        provider="codex",
        api_style="local-agent-cli",
        executable="codex.cmd",
    )
    monkeypatch.setattr(provider_status, "resolve_provider_config", lambda provider: config)

    def fail(*args, **kwargs):
        raise LLMProviderError("secret diagnostic from provider")

    result = provider_status.probe_provider_availability(
        "codex", provider_caller=fail
    )

    assert result.state == "failed"
    assert "secret diagnostic" not in result.detail
