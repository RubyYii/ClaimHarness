import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable
from urllib import request
from urllib.error import HTTPError, URLError

from .schemas import Claim, VerificationResult


SUPPORTED_PROVIDERS = {"mock", "openai-compatible"}
DEFAULT_OPENAI_BASE_URL = "https://api.openai.com/v1"
DEFAULT_OPENAI_MODEL = "gpt-5.4-mini"

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


def validate_provider(provider: str) -> str:
    normalized = provider.strip().lower()
    if normalized not in SUPPORTED_PROVIDERS:
        supported = ", ".join(sorted(SUPPORTED_PROVIDERS))
        raise ValueError(f"Unsupported LLM provider '{provider}'. Supported providers: {supported}.")
    return normalized


def resolve_provider_config(provider: str) -> LLMProviderConfig:
    normalized = validate_provider(provider)
    if normalized == "mock":
        return LLMProviderConfig(provider="mock")

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise MissingProviderConfig(
            "OPENAI_API_KEY is required when --llm openai-compatible is selected."
        )

    base_url = os.getenv("OPENAI_BASE_URL") or DEFAULT_OPENAI_BASE_URL
    model = os.getenv("OPENAI_MODEL") or DEFAULT_OPENAI_MODEL
    return LLMProviderConfig(
        provider=normalized,
        api_key=api_key,
        base_url=base_url.rstrip("/"),
        model=model,
    )


def load_prompt(name: str) -> str:
    prompt_name = f"{name}.md"
    candidates = [
        Path.cwd() / "prompts" / prompt_name,
        Path(__file__).resolve().parents[1] / "prompts" / prompt_name,
    ]
    for path in candidates:
        if path.exists():
            return path.read_text(encoding="utf-8")
    raise FileNotFoundError(f"Prompt not found: {prompt_name}")


def build_openai_compatible_request(
    config: LLMProviderConfig,
    system_prompt: str,
    user_prompt: str,
) -> request.Request:
    if not config.api_key or not config.base_url or not config.model:
        raise MissingProviderConfig("OpenAI-compatible provider config is incomplete.")

    payload = {
        "model": config.model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0,
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "claimharness_audit_review",
                "strict": True,
                "schema": AUDIT_REVIEW_SCHEMA,
            },
        },
    }
    return request.Request(
        f"{config.base_url.rstrip('/')}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {config.api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )


def parse_openai_compatible_json(response_body: bytes) -> dict[str, Any]:
    try:
        response_payload = json.loads(response_body.decode("utf-8"))
        content = response_payload["choices"][0]["message"]["content"]
        parsed = json.loads(content)
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
        raise LLMProviderError("OpenAI-compatible provider returned invalid JSON content.") from exc

    if not isinstance(parsed, dict):
        raise LLMProviderError("OpenAI-compatible provider returned non-object JSON content.")
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


def summarize_audit_with_llm(
    config: LLMProviderConfig,
    claims: list[Claim],
    results: list[VerificationResult],
) -> dict[str, Any]:
    system_prompt = load_prompt("audit_summary")
    user_prompt = json.dumps(
        {
            "claims": [claim.model_dump() for claim in claims],
            "verification_results": [result.model_dump() for result in results],
        },
        indent=2,
        ensure_ascii=False,
    )
    return call_openai_compatible_json(config, system_prompt, user_prompt)
