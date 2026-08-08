import json
import os
from pathlib import Path
import sys
import time

import pytest

import claim_harness.llm as llm_module
import claim_harness.local_agent_cli as local_cli
from claim_harness.llm import (
    LLMProviderConfig,
    LLMProviderError,
    MissingProviderConfig,
    call_provider_json,
    resolve_provider_config,
)
from claim_harness.local_agent_cli import (
    LocalAgentCLIError,
    LocalAgentProcessResult,
    resolve_local_agent_executable,
    run_local_agent_cli,
)


AUDIT_REVIEW = {
    "summary": "Review summary",
    "highest_risk_claims": ["C004"],
    "recommended_next_actions": ["Request human review"],
    "limitations": ["Advisory model output"],
}
SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "highest_risk_claims": {"type": "array", "items": {"type": "string"}},
        "recommended_next_actions": {
            "type": "array",
            "items": {"type": "string"},
        },
        "limitations": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "summary",
        "highest_risk_claims",
        "recommended_next_actions",
        "limitations",
    ],
    "additionalProperties": False,
}


def _option_value(command: list[str], option: str) -> str:
    return command[command.index(option) + 1]


def test_resolve_local_agent_executable_accepts_explicit_file(monkeypatch, tmp_path):
    executable = tmp_path / "codex.cmd"
    executable.write_text("@echo off\n", encoding="utf-8")
    executable.chmod(0o755)
    monkeypatch.setenv("CLAIMHARNESS_CODEX_BIN", str(executable))

    assert resolve_local_agent_executable("codex") == str(executable.resolve())


def test_resolve_local_agent_executable_rejects_missing_override(monkeypatch, tmp_path):
    missing = tmp_path / "missing-qwen"
    monkeypatch.setenv("CLAIMHARNESS_QWEN_BIN", str(missing))
    monkeypatch.setattr(local_cli.shutil, "which", lambda command: None)

    with pytest.raises(LocalAgentCLIError, match="CLAIMHARNESS_QWEN_BIN"):
        resolve_local_agent_executable("qwen-cli")


def test_resolve_local_agent_executable_rejects_non_executable_file(
    monkeypatch, tmp_path
):
    invalid = tmp_path / "codex.txt"
    invalid.write_text("not an executable", encoding="utf-8")
    invalid.chmod(0o644)
    monkeypatch.setenv("CLAIMHARNESS_CODEX_BIN", str(invalid))

    with pytest.raises(LocalAgentCLIError, match="executable|Windows"):
        resolve_local_agent_executable("codex")


@pytest.mark.parametrize(
    ("provider", "model_env", "model"),
    [
        ("codex", "CLAIMHARNESS_CODEX_MODEL", "gpt-test"),
        ("claude-cli", "CLAIMHARNESS_CLAUDE_MODEL", "claude-test"),
        ("qwen-cli", "CLAIMHARNESS_QWEN_MODEL", "qwen-test"),
    ],
)
def test_resolve_local_provider_config_uses_cli_and_optional_model(
    monkeypatch, provider, model_env, model
):
    monkeypatch.setattr(
        llm_module,
        "resolve_local_agent_executable",
        lambda selected: f"C:/tools/{selected}.cmd",
    )
    monkeypatch.setenv(model_env, model)

    config = resolve_provider_config(provider)

    assert config.provider == provider
    assert config.api_style == "local-agent-cli"
    assert config.api_key is None
    assert config.base_url is None
    assert config.model == model
    assert config.executable == f"C:/tools/{provider}.cmd"


def test_resolve_local_provider_config_reports_missing_cli(monkeypatch):
    def missing_cli(provider):
        raise LocalAgentCLIError(f"{provider} is missing")

    monkeypatch.setattr(llm_module, "resolve_local_agent_executable", missing_cli)

    with pytest.raises(MissingProviderConfig, match="codex is missing"):
        resolve_provider_config("codex")


def test_resolve_local_provider_config_rejects_unsafe_model_override(monkeypatch):
    monkeypatch.setattr(
        llm_module,
        "resolve_local_agent_executable",
        lambda selected: f"C:/tools/{selected}.cmd",
    )
    monkeypatch.setenv("CLAIMHARNESS_CODEX_MODEL", "gpt-test & whoami")

    with pytest.raises(MissingProviderConfig, match="model overrides"):
        resolve_provider_config("codex")


def test_codex_adapter_uses_stdin_isolated_cwd_and_tool_restrictions():
    observed = {}

    def fake_runner(*, command, input_bytes, cwd, env, timeout):
        observed.update(
            command=command,
            input_bytes=input_bytes,
            cwd=cwd,
            env=env,
            timeout=timeout,
        )
        result_path = Path(_option_value(command, "--output-last-message"))
        result_path.write_text(json.dumps(AUDIT_REVIEW), encoding="utf-8")
        return LocalAgentProcessResult(0, b"progress output", b"")

    result = run_local_agent_cli(
        "codex",
        executable="codex.cmd",
        model="gpt-test",
        system_prompt="Follow the audit contract.",
        user_prompt='{"claim":"untrusted"}',
        json_schema=SCHEMA,
        timeout=17,
        process_runner=fake_runner,
    )

    command = observed["command"]
    assert result == AUDIT_REVIEW
    assert command[:2] == ["codex.cmd", "exec"]
    assert "--ephemeral" in command
    assert "--ignore-user-config" in command
    assert _option_value(command, "--sandbox") == "read-only"
    assert "features.shell_tool=false" in command
    assert 'web_search="disabled"' in command
    assert "agents.enabled=false" in command
    assert _option_value(command, "--model") == "gpt-test"
    assert command[-1] == "-"
    assert Path(_option_value(command, "--cd")) == observed["cwd"]
    prompt = observed["input_bytes"].decode("utf-8")
    assert "Follow the audit contract." in prompt
    assert '<untrusted_audit_data>\n{"claim":"untrusted"}' in prompt
    assert observed["env"]["NO_COLOR"] == "1"


def test_claude_adapter_disables_tools_and_reads_structured_wrapper():
    observed = {}

    def fake_runner(*, command, input_bytes, cwd, env, timeout):
        system_path = Path(_option_value(command, "--system-prompt-file"))
        observed.update(
            command=command,
            input_bytes=input_bytes,
            cwd=cwd,
            system_prompt=system_path.read_text(encoding="utf-8"),
        )
        wrapper = {
            "type": "result",
            "subtype": "success",
            "is_error": False,
            "structured_output": AUDIT_REVIEW,
        }
        raw = b"\x1b[32m" + json.dumps(wrapper).encode("utf-8") + b"\x1b[0m\n"
        return LocalAgentProcessResult(0, raw, b"")

    result = run_local_agent_cli(
        "claude-cli",
        executable="claude.cmd",
        model=None,
        system_prompt="System contract",
        user_prompt="Untrusted audit data",
        json_schema=SCHEMA,
        process_runner=fake_runner,
    )

    command = observed["command"]
    assert result == AUDIT_REVIEW
    assert command[:2] == ["claude.cmd", "-p"]
    assert "--safe-mode" in command
    assert _option_value(command, "--tools") == ""
    assert _option_value(command, "--disallowedTools") == "mcp__*"
    assert "--strict-mcp-config" in command
    assert "--no-session-persistence" in command
    assert _option_value(command, "--output-format") == "json"
    assert json.loads(_option_value(command, "--json-schema")) == SCHEMA
    assert observed["system_prompt"] == "System contract"
    assert observed["input_bytes"] == b"Untrusted audit data"


def test_qwen_adapter_disables_tools_and_uses_ephemeral_runtime():
    observed = {}

    def fake_runner(*, command, input_bytes, cwd, env, timeout):
        observed.update(
            command=command,
            input_bytes=input_bytes,
            cwd=cwd,
            env=env,
            runtime_existed=Path(env["QWEN_RUNTIME_DIR"]).is_dir(),
        )
        return LocalAgentProcessResult(0, json.dumps(AUDIT_REVIEW).encode("utf-8"), b"")

    result = run_local_agent_cli(
        "qwen-cli",
        executable="qwen.cmd",
        model="qwen-test",
        system_prompt="System contract",
        user_prompt="Untrusted audit data",
        json_schema=SCHEMA,
        timeout=23,
        process_runner=fake_runner,
    )

    command = observed["command"]
    runtime_dir = Path(observed["env"]["QWEN_RUNTIME_DIR"])
    assert result == AUDIT_REVIEW
    assert command[0] == "qwen.cmd"
    assert "--safe-mode" in command
    assert _option_value(command, "--max-tool-calls") == "0"
    assert _option_value(command, "--exclude-tools") == "agent,shell,write,edit"
    assert _option_value(command, "--max-session-turns") == "1"
    assert _option_value(command, "--max-wall-time") == "23s"
    assert _option_value(command, "--output-format") == "text"
    assert _option_value(command, "--json-schema").startswith("@")
    assert _option_value(command, "--system-prompt") == "System contract"
    assert _option_value(command, "--model") == "qwen-test"
    assert runtime_dir.parent == observed["cwd"]
    assert observed["runtime_existed"] is True
    assert not runtime_dir.exists()
    assert observed["input_bytes"] == b"Untrusted audit data"


def test_local_adapter_reports_nonzero_exit_without_ansi_or_temp_path():
    def fake_runner(*, command, input_bytes, cwd, env, timeout):
        diagnostic = f"\x1b[31mfailed in {cwd}\x1b[0m".encode("utf-8")
        return LocalAgentProcessResult(7, b"", diagnostic)

    with pytest.raises(LocalAgentCLIError) as caught:
        run_local_agent_cli(
            "qwen-cli",
            executable="qwen.cmd",
            model=None,
            system_prompt="System",
            user_prompt="User",
            json_schema=SCHEMA,
            process_runner=fake_runner,
        )

    message = str(caught.value)
    assert "exited with code 7" in message
    assert "<temporary directory>" in message
    assert "\x1b" not in message


def test_local_adapters_fail_closed_on_invalid_structured_output():
    def malformed(*, command, input_bytes, cwd, env, timeout):
        return LocalAgentProcessResult(0, b"```json\n{}\n```", b"")

    with pytest.raises(LocalAgentCLIError, match="non-JSON"):
        run_local_agent_cli(
            "qwen-cli",
            executable="qwen.cmd",
            model=None,
            system_prompt="System",
            user_prompt="User",
            json_schema=SCHEMA,
            process_runner=malformed,
        )


def test_claude_adapter_requires_structured_output_object():
    def missing_structured(*, command, input_bytes, cwd, env, timeout):
        wrapper = {"type": "result", "subtype": "success", "is_error": False}
        return LocalAgentProcessResult(0, json.dumps(wrapper).encode("utf-8"), b"")

    with pytest.raises(LocalAgentCLIError, match="structured_output"):
        run_local_agent_cli(
            "claude-cli",
            executable="claude.cmd",
            model=None,
            system_prompt="System",
            user_prompt="User",
            json_schema=SCHEMA,
            process_runner=missing_structured,
        )


def test_call_provider_json_revalidates_local_cli_result(monkeypatch):
    monkeypatch.setattr(
        llm_module,
        "run_local_agent_cli",
        lambda *args, **kwargs: {"summary": "incomplete"},
    )
    config = LLMProviderConfig(
        provider="codex",
        api_style="local-agent-cli",
        executable="codex.cmd",
    )

    with pytest.raises(LLMProviderError, match="invalid audit review schema"):
        call_provider_json(config, "System", "User")


def test_call_provider_json_passes_configured_timeout_to_local_cli(monkeypatch):
    observed = {}

    def fake_local_agent(*args, **kwargs):
        observed["timeout"] = kwargs["timeout"]
        return AUDIT_REVIEW

    monkeypatch.setattr(llm_module, "run_local_agent_cli", fake_local_agent)
    config = LLMProviderConfig(
        provider="codex",
        api_style="local-agent-cli",
        executable="codex.cmd",
        timeout_seconds=177,
    )

    assert call_provider_json(config, "System", "User") == AUDIT_REVIEW
    assert observed["timeout"] == 177


def test_local_agent_model_override_rejects_shell_metacharacters_before_execution():
    def must_not_run(**kwargs):
        raise AssertionError("invalid model must fail before process execution")

    with pytest.raises(LocalAgentCLIError, match="model overrides"):
        run_local_agent_cli(
            "codex",
            executable="codex.cmd",
            model="gpt-test & whoami",
            system_prompt="System",
            user_prompt="User",
            json_schema=SCHEMA,
            process_runner=must_not_run,
        )


def test_process_runner_pipes_stdin_and_captures_exit_code(tmp_path):
    command = [
        sys.executable,
        "-B",
        "-c",
        "import sys; data=sys.stdin.buffer.read(); "
        "sys.stdout.buffer.write(data.upper()); sys.stderr.write('diagnostic')",
    ]

    result = local_cli._run_process(
        command=command,
        input_bytes=b"hello",
        cwd=tmp_path,
        env=os.environ,
        timeout=10,
    )

    assert result.returncode == 0
    assert result.stdout == b"HELLO"
    assert result.stderr == b"diagnostic"


def test_process_runner_terminates_on_timeout(tmp_path):
    started = time.monotonic()
    command = [sys.executable, "-B", "-c", "import time; time.sleep(30)"]

    with pytest.raises(LocalAgentCLIError, match="timed out after 1 seconds"):
        local_cli._run_process(
            command=command,
            input_bytes=b"",
            cwd=tmp_path,
            env=os.environ,
            timeout=1,
        )

    assert time.monotonic() - started < 10


def test_process_runner_terminates_immediately_when_output_limit_is_exceeded(
    monkeypatch, tmp_path
):
    monkeypatch.setattr(local_cli, "MAX_LOCAL_AGENT_OUTPUT_BYTES", 32)
    marker = tmp_path / "child_completed.txt"
    child_code = (
        "import pathlib,sys,time; "
        "sys.stdout.buffer.write(b'x' * 1024); sys.stdout.flush(); "
        "time.sleep(30); pathlib.Path('child_completed.txt').write_text('unsafe')"
    )
    started = time.monotonic()

    with pytest.raises(LocalAgentCLIError, match="output exceeds the 32-byte limit"):
        local_cli._run_process(
            command=[sys.executable, "-B", "-c", child_code],
            input_bytes=b"",
            cwd=tmp_path,
            env=os.environ,
            timeout=20,
        )

    assert time.monotonic() - started < 10
    assert not marker.exists()


def test_local_agent_input_is_bounded(monkeypatch):
    monkeypatch.setattr(local_cli, "MAX_LOCAL_AGENT_INPUT_BYTES", 3)

    with pytest.raises(LocalAgentCLIError, match="input exceeds"):
        run_local_agent_cli(
            "qwen-cli",
            executable="qwen.cmd",
            model=None,
            system_prompt="S",
            user_prompt="four",
            json_schema=SCHEMA,
        )
