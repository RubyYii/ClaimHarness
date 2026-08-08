import ipaddress
import json
import os
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Any, Callable, Literal
from urllib import parse, request
from urllib.error import HTTPError, URLError

from pydantic import ValidationError

from .local_agent_cli import (
    LocalAgentCLIError,
    resolve_local_agent_executable,
    run_local_agent_cli,
    validate_local_agent_model,
)
from .schemas import Claim, LLMAuditReview, VerificationResult


ApiStyle = Literal[
    "mock",
    "openai-responses",
    "openai-chat",
    "gemini",
    "anthropic",
    "local-agent-cli",
]
JsonMode = Literal["json_schema", "json_object", "prompted_json"]


DEFAULT_OPENAI_BASE_URL = "https://api.openai.com/v1"
DEFAULT_OPENAI_MODEL = "gpt-5.6"
DEFAULT_OPENAI_COMPATIBLE_MODEL = "gpt-5.4-mini"
MAX_PROVIDER_RESPONSE_BYTES = 2 * 1024 * 1024
MAX_PROVIDER_ERROR_BYTES = 4 * 1024


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
    temperature: float | None = 0.0


PROVIDER_PRESETS: dict[str, ProviderPreset] = {
    "mock": ProviderPreset(
        provider="mock",
        api_style="mock",
        requires_api_key=False,
        temperature=None,
    ),
    "openai": ProviderPreset(
        provider="openai",
        api_style="openai-responses",
        api_key_env="OPENAI_API_KEY",
        base_url_env="OPENAI_BASE_URL",
        model_env="OPENAI_MODEL",
        default_base_url=DEFAULT_OPENAI_BASE_URL,
        default_model=DEFAULT_OPENAI_MODEL,
        json_mode="json_schema",
        temperature=None,
    ),
    "openai-compatible": ProviderPreset(
        provider="openai-compatible",
        api_style="openai-chat",
        api_key_env="OPENAI_API_KEY",
        base_url_env="OPENAI_BASE_URL",
        model_env="OPENAI_MODEL",
        default_base_url=DEFAULT_OPENAI_BASE_URL,
        default_model=DEFAULT_OPENAI_COMPATIBLE_MODEL,
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
    "qwen": ProviderPreset(
        provider="qwen",
        api_style="openai-chat",
        api_key_env="DASHSCOPE_API_KEY",
        base_url_env="QWEN_BASE_URL",
        model_env="QWEN_MODEL",
        default_base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        default_model="qwen-plus",
        json_mode="json_object",
    ),
    "kimi": ProviderPreset(
        provider="kimi",
        api_style="openai-chat",
        api_key_env="KIMI_API_KEY",
        base_url_env="KIMI_BASE_URL",
        model_env="KIMI_MODEL_NAME",
        default_base_url="https://api.moonshot.ai/v1",
        default_model="kimi-k3",
        json_mode="json_object",
        temperature=None,
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
    "codex": ProviderPreset(
        provider="codex",
        api_style="local-agent-cli",
        model_env="CLAIMHARNESS_CODEX_MODEL",
        requires_api_key=False,
        temperature=None,
    ),
    "claude-cli": ProviderPreset(
        provider="claude-cli",
        api_style="local-agent-cli",
        model_env="CLAIMHARNESS_CLAUDE_MODEL",
        requires_api_key=False,
        temperature=None,
    ),
    "qwen-cli": ProviderPreset(
        provider="qwen-cli",
        api_style="local-agent-cli",
        model_env="CLAIMHARNESS_QWEN_MODEL",
        requires_api_key=False,
        temperature=None,
    ),
}
SUPPORTED_PROVIDERS = set(PROVIDER_PRESETS)

AUDIT_REVIEW_SCHEMA: dict[str, Any] = LLMAuditReview.model_json_schema()


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
    executable: str | None = None
    temperature: float | None = 0.0
    timeout_seconds: int | None = 60


@dataclass(frozen=True)
class StructuredProviderResult:
    payload: dict[str, Any]
    provider: str
    api_style: ApiStyle
    model: str | None
    response_id: str | None = None


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
        return LLMProviderConfig(
            provider="mock",
            api_style="mock",
            temperature=None,
            timeout_seconds=None,
        )
    if preset.api_style == "local-agent-cli":
        try:
            executable = resolve_local_agent_executable(normalized)
            model = _read_optional_env(preset.model_env)
            validate_local_agent_model(model)
        except LocalAgentCLIError as exc:
            raise MissingProviderConfig(str(exc)) from exc
        return LLMProviderConfig(
            provider=normalized,
            model=model or None,
            api_style="local-agent-cli",
            json_mode="json_schema",
            executable=executable,
            temperature=None,
            timeout_seconds=60,
        )

    api_key = _read_optional_env(preset.api_key_env)
    if preset.requires_api_key and not api_key:
        raise MissingProviderConfig(
            f"{preset.api_key_env} is required when --llm {normalized} is selected."
        )

    base_url = _read_optional_env(preset.base_url_env)
    model = _read_optional_env(preset.model_env)
    config = LLMProviderConfig(
        provider=normalized,
        api_key=api_key,
        base_url=(base_url or preset.default_base_url or "").rstrip("/"),
        model=model or preset.default_model,
        api_style=preset.api_style,
        json_mode=preset.json_mode,
        temperature=preset.temperature,
        timeout_seconds=60,
    )
    _validate_provider_endpoint(config)
    return config


def _read_optional_env(name: str | None) -> str | None:
    """Return a trimmed, non-empty environment value without logging it."""

    if not name:
        return None
    value = os.getenv(name)
    if value is None:
        return None
    return value.strip() or None


def _validate_provider_endpoint(config: LLMProviderConfig) -> None:
    if config.api_style in {"mock", "local-agent-cli"}:
        return
    if not config.base_url:
        raise MissingProviderConfig(f"{config.provider} provider base URL is missing.")

    try:
        parsed = parse.urlsplit(config.base_url)
        port = parsed.port
    except ValueError as exc:
        raise MissingProviderConfig(f"{config.provider} provider base URL is invalid.") from exc

    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise MissingProviderConfig(
            f"{config.provider} provider base URL must be an http(s) URL."
        )
    if parsed.username is not None or parsed.password is not None:
        raise MissingProviderConfig(
            f"{config.provider} provider base URL must not contain credentials."
        )
    if parsed.query or parsed.fragment:
        raise MissingProviderConfig(
            f"{config.provider} provider base URL must not contain a query or fragment."
        )
    if port is not None and not 1 <= port <= 65535:
        raise MissingProviderConfig(f"{config.provider} provider base URL has an invalid port.")
    if parsed.scheme == "http" and not _is_loopback_host(parsed.hostname):
        raise MissingProviderConfig(
            f"{config.provider} provider base URL must use HTTPS unless it targets loopback."
        )


def _is_loopback_host(hostname: str) -> bool:
    normalized = hostname.rstrip(".").lower()
    if normalized == "localhost":
        return True
    try:
        return ipaddress.ip_address(normalized).is_loopback
    except ValueError:
        return False


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
    _validate_provider_endpoint(config)

    payload = {
        "model": config.model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }
    if config.temperature is not None:
        payload["temperature"] = config.temperature
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


def build_openai_responses_request(
    config: LLMProviderConfig,
    system_prompt: str,
    user_prompt: str,
    *,
    json_schema: dict[str, Any] = AUDIT_REVIEW_SCHEMA,
    schema_name: str = "claimharness_audit_review",
) -> request.Request:
    """Build an OpenAI Responses API request with strict structured output."""

    if not config.api_key or not config.base_url or not config.model:
        raise MissingProviderConfig("OpenAI Responses provider config is incomplete.")
    if config.provider != "openai" or config.api_style != "openai-responses":
        raise MissingProviderConfig(
            "The OpenAI Responses request builder requires the openai provider."
        )
    _validate_provider_endpoint(config)

    payload = {
        "model": config.model,
        "instructions": system_prompt,
        "input": user_prompt,
        "text": {
            "format": {
                "type": "json_schema",
                "name": schema_name,
                "strict": True,
                "schema": json_schema,
            }
        },
    }
    return request.Request(
        f"{config.base_url.rstrip('/')}/responses",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {config.api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )


def build_gemini_request(
    config: LLMProviderConfig,
    system_prompt: str,
    user_prompt: str,
) -> request.Request:
    if not config.api_key or not config.base_url or not config.model:
        raise MissingProviderConfig("Gemini provider config is incomplete.")
    _validate_provider_endpoint(config)

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
    _validate_provider_endpoint(config)

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
    except (KeyError, IndexError, TypeError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise LLMProviderError("OpenAI-compatible provider returned invalid JSON content.") from exc

    return validate_audit_review(
        _parse_json_object_text(content, "OpenAI-compatible provider")
    )


def parse_openai_responses_json(response_body: bytes) -> StructuredProviderResult:
    """Read strict JSON text from the typed Responses API output array."""

    try:
        response_payload = json.loads(response_body.decode("utf-8"))
        output = response_payload["output"]
        response_id = response_payload.get("id")
        model = response_payload.get("model")
    except (KeyError, TypeError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise LLMProviderError("OpenAI Responses API returned invalid JSON content.") from exc

    if not isinstance(output, list):
        raise LLMProviderError("OpenAI Responses API returned an invalid output array.")
    status = response_payload.get("status")
    if status is not None and status != "completed":
        raise LLMProviderError(
            f"OpenAI Responses API did not complete the structured request (status={status})."
        )

    text_content: str | None = None
    for item in output:
        if not isinstance(item, dict) or item.get("type") != "message":
            continue
        content = item.get("content")
        if not isinstance(content, list):
            continue
        for part in content:
            if not isinstance(part, dict):
                continue
            if part.get("type") == "refusal":
                raise LLMProviderError("OpenAI Responses API refused the structured request.")
            if part.get("type") == "output_text" and isinstance(part.get("text"), str):
                text_content = part["text"]
                break
        if text_content is not None:
            break

    if text_content is None:
        raise LLMProviderError("OpenAI Responses API returned no structured output text.")

    return StructuredProviderResult(
        payload=_parse_json_object_text(text_content, "OpenAI Responses API"),
        provider="openai",
        api_style="openai-responses",
        model=model if isinstance(model, str) else None,
        response_id=response_id if isinstance(response_id, str) else None,
    )


def parse_gemini_json(response_body: bytes) -> dict[str, Any]:
    try:
        response_payload = json.loads(response_body.decode("utf-8"))
        content = response_payload["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError, TypeError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise LLMProviderError("Gemini provider returned invalid JSON content.") from exc

    return validate_audit_review(_parse_json_object_text(content, "Gemini provider"))


def parse_anthropic_json(response_body: bytes) -> dict[str, Any]:
    try:
        response_payload = json.loads(response_body.decode("utf-8"))
        content = next(
            block["text"]
            for block in response_payload["content"]
            if block.get("type") == "text"
        )
    except (
        KeyError,
        IndexError,
        TypeError,
        StopIteration,
        UnicodeDecodeError,
        json.JSONDecodeError,
    ) as exc:
        raise LLMProviderError("Anthropic provider returned invalid JSON content.") from exc

    return validate_audit_review(_parse_json_object_text(content, "Anthropic provider"))


def _parse_json_object_text(content: str, provider_name: str) -> dict[str, Any]:
    try:
        parsed = json.loads(content)
    except (TypeError, json.JSONDecodeError) as exc:
        raise LLMProviderError(f"{provider_name} returned non-JSON text.") from exc

    if not isinstance(parsed, dict):
        raise LLMProviderError(f"{provider_name} returned non-object JSON content.")
    return parsed


def validate_audit_review(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        review = LLMAuditReview.model_validate(payload)
    except ValidationError as exc:
        raise LLMProviderError("Provider returned an invalid audit review schema.") from exc
    return review.model_dump()


class _RejectRedirectHandler(request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        return None


def _open_provider_request(api_request: request.Request, timeout: int):
    opener = request.build_opener(_RejectRedirectHandler())
    return opener.open(api_request, timeout=timeout)


def _read_provider_response(response: Any) -> bytes:
    headers = getattr(response, "headers", None)
    content_length = headers.get("Content-Length") if headers is not None else None
    if content_length:
        try:
            if int(content_length) > MAX_PROVIDER_RESPONSE_BYTES:
                raise LLMProviderError(
                    f"Provider response exceeds the {MAX_PROVIDER_RESPONSE_BYTES}-byte limit."
                )
        except ValueError:
            pass

    body = response.read(MAX_PROVIDER_RESPONSE_BYTES + 1)
    if len(body) > MAX_PROVIDER_RESPONSE_BYTES:
        raise LLMProviderError(
            f"Provider response exceeds the {MAX_PROVIDER_RESPONSE_BYTES}-byte limit."
        )
    return body


def _read_provider_error(exc: HTTPError) -> str:
    raw = exc.read(MAX_PROVIDER_ERROR_BYTES + 1)
    truncated = len(raw) > MAX_PROVIDER_ERROR_BYTES
    text = raw[:MAX_PROVIDER_ERROR_BYTES].decode("utf-8", errors="replace")
    compact = " ".join(text.split())
    if truncated:
        compact += " ...[truncated]"
    return compact or "no response body"


def call_openai_compatible_json(
    config: LLMProviderConfig,
    system_prompt: str,
    user_prompt: str,
    urlopen: Callable[..., Any] | None = None,
    timeout: int = 60,
) -> dict[str, Any]:
    api_request = build_openai_compatible_request(config, system_prompt, user_prompt)
    open_request = urlopen or _open_provider_request
    try:
        with open_request(api_request, timeout=timeout) as response:
            response_body = _read_provider_response(response)
    except HTTPError as exc:
        detail = _read_provider_error(exc)
        raise LLMProviderError(f"OpenAI-compatible provider HTTP {exc.code}: {detail}") from exc
    except URLError as exc:
        raise LLMProviderError(f"OpenAI-compatible provider request failed: {exc.reason}") from exc
    except TimeoutError as exc:
        raise LLMProviderError("OpenAI-compatible provider request timed out.") from exc

    return parse_openai_compatible_json(response_body)


def call_provider_json(
    config: LLMProviderConfig,
    system_prompt: str,
    user_prompt: str,
    urlopen: Callable[..., Any] | None = None,
    timeout: int | None = None,
) -> dict[str, Any]:
    effective_timeout = timeout if timeout is not None else config.timeout_seconds
    if effective_timeout is None:
        effective_timeout = 60
    if effective_timeout <= 0:
        raise LLMProviderError("Provider timeout must be greater than zero.")

    if config.api_style == "local-agent-cli":
        if not config.executable:
            raise LLMProviderError(
                f"{config.provider} local agent CLI configuration is incomplete."
            )
        try:
            payload = run_local_agent_cli(
                config.provider,
                executable=config.executable,
                model=config.model,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                json_schema=AUDIT_REVIEW_SCHEMA,
                timeout=effective_timeout,
            )
        except LocalAgentCLIError as exc:
            raise LLMProviderError(str(exc)) from exc
        return validate_audit_review(payload)

    if config.api_style == "openai-responses":
        api_request = build_openai_responses_request(
            config,
            system_prompt,
            user_prompt,
        )
        parser = parse_openai_responses_json
    elif config.api_style == "openai-chat":
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

    open_request = urlopen or _open_provider_request
    try:
        with open_request(api_request, timeout=effective_timeout) as response:
            response_body = _read_provider_response(response)
    except HTTPError as exc:
        detail = _read_provider_error(exc)
        raise LLMProviderError(f"{config.provider} provider HTTP {exc.code}: {detail}") from exc
    except URLError as exc:
        raise LLMProviderError(f"{config.provider} provider request failed: {exc.reason}") from exc
    except TimeoutError as exc:
        raise LLMProviderError(f"{config.provider} provider request timed out.") from exc

    parsed = parser(response_body)
    if isinstance(parsed, StructuredProviderResult):
        return validate_audit_review(parsed.payload)
    return parsed


def call_structured_provider_json(
    config: LLMProviderConfig,
    system_prompt: str,
    user_prompt: str,
    *,
    json_schema: dict[str, Any],
    schema_name: str,
    urlopen: Callable[..., Any] | None = None,
    timeout: int = 60,
) -> StructuredProviderResult:
    """Call GPT-5.6 through Responses API for a caller-defined JSON schema."""

    if config.api_style != "openai-responses":
        raise LLMProviderError(
            "Caller-defined structured output currently requires the openai provider."
        )
    api_request = build_openai_responses_request(
        config,
        system_prompt,
        user_prompt,
        json_schema=json_schema,
        schema_name=schema_name,
    )
    open_request = urlopen or _open_provider_request
    try:
        with open_request(api_request, timeout=timeout) as response:
            response_body = _read_provider_response(response)
    except HTTPError as exc:
        detail = _read_provider_error(exc)
        raise LLMProviderError(f"openai provider HTTP {exc.code}: {detail}") from exc
    except URLError as exc:
        raise LLMProviderError(f"openai provider request failed: {exc.reason}") from exc
    except TimeoutError as exc:
        raise LLMProviderError("openai provider request timed out.") from exc
    return parse_openai_responses_json(response_body)


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
