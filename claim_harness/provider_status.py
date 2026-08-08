"""Offline provider inventory plus an explicit synthetic probe helper.

The inspector is deliberately passive: it reads environment-variable presence,
validates configured URLs through the normal provider resolver, and locates
known executable names with ``shutil.which``. It never opens a network socket,
runs a discovered executable, reads client credential files, or returns secret
values and absolute executable paths. The separate probe function uses fixed
synthetic prompts and returns only sanitized state.
"""

from __future__ import annotations

import os
import shutil
from dataclasses import asdict, dataclass, replace
from typing import Any, Callable, Literal

from .llm import (
    LLMProviderError,
    MissingProviderConfig,
    PROVIDER_PRESETS,
    call_provider_json,
    resolve_provider_config,
    validate_provider,
)
from .local_agent_cli import (
    LocalAgentCLIError,
    resolve_local_agent_executable,
    validate_local_agent_model,
)


ProviderMode = Literal[
    "deterministic-local",
    "direct-api",
    "local-endpoint",
    "installed-client",
    "candidate-client",
]
ProviderState = Literal[
    "ready",
    "configured",
    "missing_config",
    "invalid_config",
    "installed",
    "not_installed",
    "detected_only",
]
ProviderProbeState = Literal["ready", "failed", "not_attempted"]

PROBE_SYSTEM_PROMPT = (
    "This is a synthetic ClaimHarness provider availability probe. Return only a "
    "JSON object matching the supplied schema. Do not use tools or claim that any "
    "real manuscript, evidence, account quota, or future request was validated."
)
PROBE_USER_PROMPT = (
    "Synthetic probe data only. Return summary='Synthetic provider probe completed', "
    "with empty highest_risk_claims, recommended_next_actions, and limitations arrays."
)


@dataclass(frozen=True)
class ProviderAvailability:
    """Sanitized, non-secret availability result for one provider option."""

    provider: str
    mode: ProviderMode
    selectable: bool
    state: ProviderState
    detail: str
    model: str | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class ProviderProbeResult:
    """Sanitized result from one explicitly confirmed synthetic provider call."""

    provider: str
    state: ProviderProbeState
    attempted: bool
    timeout_seconds: int
    detail: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class CandidateClient:
    provider: str
    command_names: tuple[str, ...]
    detail: str


CANDIDATE_CLIENTS: tuple[CandidateClient, ...] = (
    CandidateClient(
        provider="kimi-cli",
        command_names=("kimi",),
        detail=(
            "official client detection only; a safe stdin plus strict-schema "
            "ClaimHarness adapter is not enabled"
        ),
    ),
    CandidateClient(
        provider="deepcode-cli",
        command_names=("deepcode",),
        detail="third-party DeepSeek client detection only; no ClaimHarness adapter",
    ),
    CandidateClient(
        provider="deepseek-tui",
        command_names=("deepseek",),
        detail="third-party DeepSeek client detection only; no ClaimHarness adapter",
    ),
)


def inspect_provider_availability() -> list[ProviderAvailability]:
    """Inspect all selectable presets plus explicitly labelled client candidates."""

    results = [_inspect_selectable(name) for name in PROVIDER_PRESETS]
    results.extend(_inspect_candidate(candidate) for candidate in CANDIDATE_CLIENTS)
    return results


def probe_provider_availability(
    provider: str,
    *,
    timeout_seconds: int = 60,
    provider_caller: Callable[..., dict[str, Any]] | None = None,
) -> ProviderProbeResult:
    """Send one synthetic structured-output call after CLI-level confirmation."""

    normalized = validate_provider(provider)
    if normalized == "mock":
        return ProviderProbeResult(
            provider="mock",
            state="ready",
            attempted=False,
            timeout_seconds=timeout_seconds,
            detail="mock is deterministic and already available without a provider call",
        )
    if not 1 <= timeout_seconds <= 600:
        raise ValueError("Provider probe timeout must be between 1 and 600 seconds.")

    try:
        config = resolve_provider_config(normalized)
    except MissingProviderConfig:
        return ProviderProbeResult(
            provider=normalized,
            state="not_attempted",
            attempted=False,
            timeout_seconds=timeout_seconds,
            detail=(
                "required local configuration is missing or invalid; no provider call "
                "was sent"
            ),
        )

    caller = provider_caller or call_provider_json
    try:
        caller(
            replace(config, timeout_seconds=timeout_seconds),
            PROBE_SYSTEM_PROMPT,
            PROBE_USER_PROMPT,
        )
    except LLMProviderError:
        return ProviderProbeResult(
            provider=normalized,
            state="failed",
            attempted=True,
            timeout_seconds=timeout_seconds,
            detail=(
                "synthetic structured-output probe failed; check login, endpoint, "
                "model access, quota, and timeout"
            ),
        )

    return ProviderProbeResult(
        provider=normalized,
        state="ready",
        attempted=True,
        timeout_seconds=timeout_seconds,
        detail=(
            "one synthetic structured-output probe succeeded; this does not guarantee "
            "future availability"
        ),
    )


def _inspect_selectable(provider: str) -> ProviderAvailability:
    preset = PROVIDER_PRESETS[provider]
    if preset.api_style == "mock":
        return ProviderAvailability(
            provider=provider,
            mode="deterministic-local",
            selectable=True,
            state="ready",
            detail="local deterministic provider; no credential or network required",
        )

    if preset.api_style == "local-agent-cli":
        try:
            resolve_local_agent_executable(provider)
        except LocalAgentCLIError:
            executable_env = _local_executable_env(provider)
            if _optional_env(executable_env):
                return ProviderAvailability(
                    provider=provider,
                    mode="installed-client",
                    selectable=True,
                    state="invalid_config",
                    detail=(
                        f"{executable_env} is set but does not resolve to a supported "
                        "executable file"
                    ),
                    model=_optional_env(preset.model_env),
                )
            return ProviderAvailability(
                provider=provider,
                mode="installed-client",
                selectable=True,
                state="not_installed",
                detail=(
                    f"executable not found; install the client or set "
                    f"{_local_executable_env(provider)}"
                ),
                model=_optional_env(preset.model_env),
            )
        model = _optional_env(preset.model_env)
        try:
            validate_local_agent_model(model)
        except LocalAgentCLIError:
            return ProviderAvailability(
                provider=provider,
                mode="installed-client",
                selectable=True,
                state="invalid_config",
                detail="executable found but the local model override is invalid",
                model=None,
            )
        return ProviderAvailability(
            provider=provider,
            mode="installed-client",
            selectable=True,
            state="installed",
            detail="executable found; authentication and model access were not tested",
            model=model,
        )

    mode: ProviderMode = "local-endpoint" if provider == "ollama" else "direct-api"
    if preset.requires_api_key and not _optional_env(preset.api_key_env):
        return ProviderAvailability(
            provider=provider,
            mode=mode,
            selectable=True,
            state="missing_config",
            detail=f"set {preset.api_key_env}; no request was sent",
            model=_optional_env(preset.model_env) or preset.default_model,
        )

    try:
        config = resolve_provider_config(provider)
    except MissingProviderConfig:
        return ProviderAvailability(
            provider=provider,
            mode=mode,
            selectable=True,
            state="invalid_config",
            detail="provider environment is present but fails local configuration validation",
            model=_optional_env(preset.model_env) or preset.default_model,
        )

    return ProviderAvailability(
        provider=provider,
        mode=mode,
        selectable=True,
        state="configured",
        detail=(
            "configuration present; credential validity, endpoint reachability, and "
            "model access were not tested"
        ),
        model=config.model,
    )


def _inspect_candidate(candidate: CandidateClient) -> ProviderAvailability:
    installed = any(_command_exists(command) for command in candidate.command_names)
    return ProviderAvailability(
        provider=candidate.provider,
        mode="candidate-client",
        selectable=False,
        state="detected_only" if installed else "not_installed",
        detail=candidate.detail,
    )


def _command_exists(command: str) -> bool:
    candidates = [command]
    if os.name == "nt":
        candidates = [f"{command}.cmd", f"{command}.exe", command]
    return any(shutil.which(candidate) is not None for candidate in candidates)


def _optional_env(name: str | None) -> str | None:
    if not name:
        return None
    value = os.getenv(name)
    if value is None:
        return None
    return value.strip() or None


def _local_executable_env(provider: str) -> str:
    return {
        "codex": "CLAIMHARNESS_CODEX_BIN",
        "claude-cli": "CLAIMHARNESS_CLAUDE_BIN",
        "qwen-cli": "CLAIMHARNESS_QWEN_BIN",
    }[provider]
