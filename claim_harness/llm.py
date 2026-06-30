import json
import os
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Any, Callable, Literal
from urllib import request
from urllib.error import HTTPError, URLError

from .schemas import Claim, VerificationResult


ApiStyle = Literal["mock", "openai-chat", "gemini", "anthropic"]
JsonMode = Literal["json_schema", "json_object", "prompted_json"]


DEFAULT_OPENAI_BASE_URL = "https://api.openai.com/v1"
DEFAULT_OPENAI_MODEL = "gpt-5.4-mini"


@dataclass(frozen=True)
class ProviderPreset:
    provider: str
    api_style: ApiStyle
    api_key_env: str | None = None
    base_url_env: str | None = None
    model_env: str | None = None
    default_base_url: str | None = None
    default_model: str | None = None
    json_mode: JsonMode = "json_schema"
    requires_api_key: bool = True


PROVIDER_PRESETS: dict[str, ProviderPreset] = {
    "mock": ProviderPreset(provider="mock", api_style="mock", requires_api_key=False),
    "openai": ProviderPreset(
        provider="openai",
        api_style="openai-chat",
        api_key_env="OPENAI_API_KEY",
        base_url_env="OPENAI_BASE_URL",
        model_env="OPENAI_MODEL",
        default_base_url=DEFAULT_OPENAI_BASE_URL,
        default_model=DEFAULT_OPENAI_MODEL,
        json_mode="json_schema",
    ),
    "openai-compatible": ProviderPreset(
        provider="openai-compatible",
        api_style="openai-chat",
        api_key_env="OPENAI_API_KEY",
        base_url_env="OPENAI_BASE_URL",
        model_env="OPENAI_MODEL",
        default_base_url=DEFAULT_OPENAI_BASE_URL,
        default_model=DEFAULT_OPENAI_MODEL,
        json_mode="json_schema",
    ),
    "deepseek": ProviderPreset(
        provider="deepseek",
        api_style="openai-chat",
        api_key_env="DEEPSEEK_API_KEY",
        base_url_env="DEEPSEEK_BASE_URL",
        model_env="DEEPSEEK_MODEL",
        default_base_url="https://api.deepseek.com",
        default_model="deepseek-v4-flash",
        json_mode="json_object",
    ),
    "groq": ProviderPreset(
        provider="groq",
        api_style="openai-chat",
        api_key_env="GROQ_API_KEY",
        base_url_env="GROQ_BASE_URL",
        model_env="GROQ_MODEL",
        default_base_url="https://api.groq.com/openai/v1",
        default_model="llama-3.3-70b-versatile",
        json_mode="json_object",
    ),
    "mistral": ProviderPreset(
        provider="mistral",
        api_style="openai-chat",
        api_key_env="MISTRAL_API_KEY",
        base_url_env="MISTRAL_BASE_URL",
        model_env="MISTRAL_MODEL",
        default_base_url="https://api.mistral.ai/v1",
        default_model="mistral-large-latest",
        json_mode="json_object",
    ),
    "openrouter": ProviderPreset(
        provider="openrouter",
        api_style="openai-chat",
        api_key_env="OPENROUTER_API_KEY",
        base_url_env="OPENROUTER_BASE_URL",
        model_env="OPENROUTER_MODEL",
        default_base_url="https://openrouter.ai/api/v1",
        default_model="openai/gpt-5.4-mini",
        json_mode="json_object",
    ),
    "xai": ProviderPreset(
        provider="xai",
        api_style="openai-chat",
        api_key_env="XAI_API_KEY",
        base_url_env="XAI_BASE_URL",
        model_env="XAI_MODEL",
        default_base_url="https://api.x.ai/v1",
        default_model="grok-4.3",
        json_mode="json_object",
    ),
    "ollama": ProviderPreset(
        provider="ollama",
        api_style="openai-chat",
        api_key_env="OLLAMA_API_KEY",
        base_url_env="OLLAMA_BASE_URL",
        model_env="OLLAMA_MODEL",
        default_base_url="http://localhost:11434/v1",
        default_model="llama3.2",
        json_mode="json_object",
        requires_api_key=False,
    ),
    "gemini": ProviderPreset(
        provider="gemini",
        api_style="gemini",
        api_key_env="GEMINI_API_KEY",
        base_url_env="GEMINI_BASE_URL",
        model_env="GEMINI_MODEL",
        default_base_url="https://generativelanguage.googleapis.com/v1beta",
        default_model="gemini-3.5-flash",
        json_mode="json_object",
    ),
    "anthropic": ProviderPreset(
        provider="anthropic",
        api_style="anthropic",
        api_key_env="ANTHROPIC_API_KEY",
        base_url_env="ANTHROPIC_BASE_URL",
        model_env="ANTHROPIC_MODEL",
        default_base_url="https://api.anthropic.com/v1",
        default_model="claude-sonnet-4-5",
        json_mode="prompted_json",
    ),
}
SUPPORTED_PROVIDERS = set(PROVIDER_PRESETS)

AUDIT_REVIEW_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "highest_risk_claims": {
            "type": "array",
            "items": {"type": "string"},
        },
        "recommended_next_actions": {
            "type": "array",
            "items": {"type": "string"},
        },
        "limitations": {
            "type": "array",
            "items": {"type": "string"},
        },
    },
    "required": [
        "summary",
        "highest_risk_claims",
        "recommended_next_actions",
        "limitations",
    ],
    "additionalProperties": False,
}


class MissingProviderConfig(ValueError):
    """Raised when an optional provider is selected without required env config."""


class LLMProviderError(RuntimeError):
    """Raised when an optional LLM provider call fails or returns invalid data."""


@dataclass(frozen=True)
class LLMProviderConfig:
    provider: str
    api_key: str | None = None
    base_url: str | None = None
    model: str | None = None
    api_style: ApiStyle = "mock"
    json_mode: JsonMode = "json_schema"


def validate_provider(provider: str) -> str:
    normalized = provider.strip().lower()
    if normalized not in PROVIDER_PRESETS:
        supported = ", ".join(sorted(SUPPORTED_PROVIDERS))
        raise ValueError(f"Unsupported LLM provider '{provider}'. Supported providers: {supported}.")
    return normalized


def resolve_provider_config(provider: str) -> LLMProviderConfig:
    normalized = validate_provider(provider)
    preset = PROVIDER_PRESETS[normalized]
    if preset.api_style == "mock":
        return LLMProviderConfig(provider="mock", api_style="mock")

    api_key = os.getenv(preset.api_key_env or "") if preset.api_key_env else None
    if preset.requires_api_key and not api_key:
        raise MissingProviderConfig(
            f"{preset.api_key_env} is required when --llm {normalized} is selected."
        )

    base_url = os.getenv(preset.base_url_env or "") if preset.base_url_env else None
    model = os.getenv(preset.model_env or "") if preset.model_env else None
    return LLMProviderConfig(
        provider=normalized,
        api_key=api_key,
        base_url=(base_url or preset.default_base_url or "").rstrip("/"),
        model=model or preset.default_model,
        api_style=preset.api_style,
        json_mode=preset.json_mode,
    )


def load_prompt(name: str) -> str:
    prompt_name = f"{name}.md"
    candidates = [Path.cwd() / "prompts" / prompt_name]
    for path in candidates:
        if path.exists():
            return path.read_text(encoding="utf-8")
    package_prompt = resources.files("claim_harness").joinpath("prompts", prompt_name)
    if package_prompt.is_file():
        return package_prompt.read_text(encoding="utf-8")
    raise FileNotFoundError(f"Prompt not found: {prompt_name}")


def build_openai_compatible_request(
    config: LLMProviderConfig,
    system_prompt: str,
    user_prompt: str,
) -> request.Request:
    if not config.base_url or not config.model:
        raise MissingProviderConfig("OpenAI-compatible provider config is incomplete.")

    payload = {
        "model": config.model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0,
    }
    if config.json_mode == "json_schema":
        payload["response_format"] = {
            "type": "json_schema",
            "json_schema": {
                "name": "claimharness_audit_review",
                "strict": True,
                "schema": AUDIT_REVIEW_SCHEMA,
            },
        }
    elif config.json_mode == "json_object":
        payload["response_format"] = {"type": "json_object"}

    headers = {"Content-Type": "application/json"}
    if config.api_key:
        headers["Authorization"] = f"Bearer {config.api_key}"
    return request.Request(
        f"{config.base_url.rstrip('/')}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )


def build_gemini_request(
    config: LLMProviderConfig,
    system_prompt: str,
    user_prompt: str,
) -> request.Request:
    if not config.api_key or not config.base_url or not config.model:
        raise MissingProviderConfig("Gemini provider config is incomplete.")

    payload = {
        "system_instruction": {"parts": [{"text": system_prompt}]},
        "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
        "generation_config": {
            "temperature": 0,
            "response_mime_type": "application/json",
        },
    }
    return request.Request(
        f"{config.base_url.rstrip('/')}/models/{config.model}:generateContent",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "x-goog-api-key": config.api_key,
            "Content-Type": "application/json",
        },
        method="POST",
    )


def build_anthropic_messages_request(
    config: LLMProviderConfig,
    system_prompt: str,
    user_prompt: str,
) -> request.Request:
    if not config.api_key or not config.base_url or not config.model:
        raise MissingProviderConfig("Anthropic provider config is incomplete.")

    payload = {
        "model": config.model,
        "max_tokens": 1200,
        "temperature": 0,
        "system": system_prompt,
        "messages": [{"role": "user", "content": user_prompt}],
    }
    return request.Request(
        f"{config.base_url.rstrip('/')}/messages",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "x-api-key": config.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        },
        method="POST",
    )


def parse_openai_compatible_json(response_body: bytes) -> dict[str, Any]:
    try:
        response_payload = json.loads(response_body.decode("utf-8"))
        content = response_payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
        raise LLMProviderError("OpenAI-compatible provider returned invalid JSON content.") from exc

    return _parse_json_object_text(content, "OpenAI-compatible provider")


def parse_gemini_json(response_body: bytes) -> dict[str, Any]:
    try:
        response_payload = json.loads(response_body.decode("utf-8"))
        content = response_payload["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
        raise LLMProviderError("Gemini provider returned invalid JSON content.") from exc

    return _parse_json_object_text(content, "Gemini provider")


def parse_anthropic_json(response_body: bytes) -> dict[str, Any]:
    try:
        response_payload = json.loads(response_body.decode("utf-8"))
        content = next(
            block["text"]
            for block in response_payload["content"]
            if block.get("type") == "text"
        )
    except (KeyError, IndexError, TypeError, StopIteration, json.JSONDecodeError) as exc:
        raise LLMProviderError("Anthropic provider returned invalid JSON content.") from exc

    return _parse_json_object_text(content, "Anthropic provider")


def _parse_json_object_text(content: str, provider_name: str) -> dict[str, Any]:
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as exc:
        raise LLMProviderError(f"{provider_name} returned non-JSON text.") from exc

    if not isinstance(parsed, dict):
        raise LLMProviderError(f"{provider_name} returned non-object JSON content.")
    return parsed


def call_openai_compatible_json(
    config: LLMProviderConfig,
    system_prompt: str,
    user_prompt: str,
    urlopen: Callable[..., Any] = request.urlopen,
    timeout: int = 60,
) -> dict[str, Any]:
    api_request = build_openai_compatible_request(config, system_prompt, user_prompt)
    try:
        with urlopen(api_request, timeout=timeout) as response:
            response_body = response.read()
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise LLMProviderError(f"OpenAI-compatible provider HTTP {exc.code}: {detail}") from exc
    except URLError as exc:
        raise LLMProviderError(f"OpenAI-compatible provider request failed: {exc.reason}") from exc

    return parse_openai_compatible_json(response_body)


def call_provider_json(
    config: LLMProviderConfig,
    system_prompt: str,
    user_prompt: str,
    urlopen: Callable[..., Any] = request.urlopen,
    timeout: int = 60,
) -> dict[str, Any]:
    if config.api_style == "openai-chat":
        api_request = build_openai_compatible_request(config, system_prompt, user_prompt)
        parser = parse_openai_compatible_json
    elif config.api_style == "gemini":
        api_request = build_gemini_request(config, system_prompt, user_prompt)
        parser = parse_gemini_json
    elif config.api_style == "anthropic":
        api_request = build_anthropic_messages_request(config, system_prompt, user_prompt)
        parser = parse_anthropic_json
    else:
        raise LLMProviderError(f"Provider '{config.provider}' does not support remote JSON calls.")

    try:
        with urlopen(api_request, timeout=timeout) as response:
            response_body = response.read()
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise LLMProviderError(f"{config.provider} provider HTTP {exc.code}: {detail}") from exc
    except URLError as exc:
        raise LLMProviderError(f"{config.provider} provider request failed: {exc.reason}") from exc

    return parser(response_body)


def summarize_audit_with_llm(
    config: LLMProviderConfig,
    claims: list[Claim],
    results: list[VerificationResult],
    evidence: list[Any] | None = None,
) -> dict[str, Any]:
    system_prompt = load_prompt("audit_summary")
    user_prompt = json.dumps(
        {
            "claims": [claim.model_dump() for claim in claims],
            "verification_results": [result.model_dump() for result in results],
            "evidence": [
                item.model_dump() if hasattr(item, "model_dump") else item
                for item in (evidence or [])
            ],
        },
        indent=2,
        ensure_ascii=False,
    )
    return call_provider_json(config, system_prompt, user_prompt)
