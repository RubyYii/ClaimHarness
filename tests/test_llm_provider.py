from io import BytesIO
import json
from urllib.error import HTTPError

import pytest

import claim_harness.llm as llm_module
from claim_harness.llm import (
    LLMProviderConfig,
    LLMProviderError,
    MAX_PROVIDER_ERROR_BYTES,
    MAX_PROVIDER_RESPONSE_BYTES,
    MissingProviderConfig,
    build_anthropic_messages_request,
    build_gemini_request,
    build_openai_compatible_request,
    build_openai_responses_request,
    call_provider_json,
    load_prompt,
    parse_openai_compatible_json,
    parse_openai_responses_json,
    parse_anthropic_json,
    parse_gemini_json,
    resolve_provider_config,
    validate_provider,
)


def test_validate_provider_accepts_common_provider_presets():
    assert validate_provider("mock") == "mock"
    assert validate_provider(" OpenAI-Compatible ") == "openai-compatible"
    assert validate_provider("DeepSeek") == "deepseek"
    assert validate_provider("groq") == "groq"
    assert validate_provider("mistral") == "mistral"
    assert validate_provider("openrouter") == "openrouter"
    assert validate_provider("xai") == "xai"
    assert validate_provider("ollama") == "ollama"
    assert validate_provider("Qwen") == "qwen"
    assert validate_provider("gemini") == "gemini"
    assert validate_provider("anthropic") == "anthropic"


def test_validate_provider_rejects_unknown_provider():
    with pytest.raises(ValueError, match="Supported providers:"):
        validate_provider("other")


def test_resolve_provider_config_uses_env_and_defaults(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)

    config = resolve_provider_config("openai-compatible")

    assert config.provider == "openai-compatible"
    assert config.api_key == "test-key"
    assert config.base_url == "https://api.openai.com/v1"
    assert config.model == "gpt-5.4-mini"


def test_resolve_openai_provider_uses_gpt56_responses_api(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)

    config = resolve_provider_config("openai")

    assert config.api_style == "openai-responses"
    assert config.model == "gpt-5.6"


def test_build_openai_responses_request_uses_strict_text_format():
    config = LLMProviderConfig(
        provider="openai",
        api_key="test-key",
        base_url="https://api.openai.com/v1",
        model="gpt-5.6",
        api_style="openai-responses",
    )

    built = build_openai_responses_request(config, "System", "User")
    payload = json.loads(built.data.decode("utf-8"))

    assert built.full_url == "https://api.openai.com/v1/responses"
    assert payload["model"] == "gpt-5.6"
    assert payload["instructions"] == "System"
    assert payload["input"] == "User"
    assert payload["text"]["format"]["type"] == "json_schema"
    assert payload["text"]["format"]["strict"] is True


def test_parse_openai_responses_json_reads_typed_output_and_metadata():
    review = {
        "summary": "Review summary",
        "highest_risk_claims": ["C004"],
        "recommended_next_actions": ["Human review"],
        "limitations": ["Synthetic demo only"],
    }
    response = {
        "id": "resp_test",
        "model": "gpt-5.6-sol",
        "output": [
            {
                "type": "message",
                "content": [{"type": "output_text", "text": json.dumps(review)}],
            }
        ],
    }

    parsed = parse_openai_responses_json(json.dumps(response).encode("utf-8"))

    assert parsed.payload == review
    assert parsed.response_id == "resp_test"
    assert parsed.model == "gpt-5.6-sol"


def test_parse_openai_responses_json_rejects_incomplete_response():
    response = {
        "id": "resp_incomplete",
        "status": "incomplete",
        "output": [
            {
                "type": "message",
                "content": [{"type": "output_text", "text": "{}"}],
            }
        ],
    }

    with pytest.raises(LLMProviderError, match="did not complete"):
        parse_openai_responses_json(json.dumps(response).encode("utf-8"))


def test_resolve_provider_config_uses_deepseek_preset(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "deepseek-key")
    monkeypatch.delenv("DEEPSEEK_BASE_URL", raising=False)
    monkeypatch.delenv("DEEPSEEK_MODEL", raising=False)

    config = resolve_provider_config("deepseek")

    assert config.provider == "deepseek"
    assert config.api_style == "openai-chat"
    assert config.api_key == "deepseek-key"
    assert config.base_url == "https://api.deepseek.com"
    assert config.model == "deepseek-v4-flash"
    assert config.json_mode == "json_object"


def test_resolve_provider_config_uses_qwen_preset(monkeypatch):
    monkeypatch.setenv("DASHSCOPE_API_KEY", "qwen-key")
    monkeypatch.delenv("QWEN_BASE_URL", raising=False)
    monkeypatch.delenv("QWEN_MODEL", raising=False)

    config = resolve_provider_config("qwen")

    assert config.provider == "qwen"
    assert config.api_style == "openai-chat"
    assert config.api_key == "qwen-key"
    assert config.base_url == "https://dashscope.aliyuncs.com/compatible-mode/v1"
    assert config.model == "qwen-plus"
    assert config.json_mode == "json_object"


def test_resolve_provider_config_allows_ollama_without_api_key(monkeypatch):
    monkeypatch.delenv("OLLAMA_API_KEY", raising=False)
    monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)
    monkeypatch.delenv("OLLAMA_MODEL", raising=False)

    config = resolve_provider_config("ollama")

    assert config.provider == "ollama"
    assert config.api_key is None
    assert config.base_url == "http://localhost:11434/v1"
    assert config.model == "llama3.2"


def test_resolve_provider_config_uses_gemini_native_preset(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "gemini-key")
    monkeypatch.delenv("GEMINI_BASE_URL", raising=False)
    monkeypatch.delenv("GEMINI_MODEL", raising=False)

    config = resolve_provider_config("gemini")

    assert config.provider == "gemini"
    assert config.api_style == "gemini"
    assert config.api_key == "gemini-key"
    assert config.base_url == "https://generativelanguage.googleapis.com/v1beta"
    assert config.model == "gemini-3.5-flash"


def test_resolve_provider_config_uses_anthropic_native_preset(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "anthropic-key")
    monkeypatch.delenv("ANTHROPIC_BASE_URL", raising=False)
    monkeypatch.delenv("ANTHROPIC_MODEL", raising=False)

    config = resolve_provider_config("anthropic")

    assert config.provider == "anthropic"
    assert config.api_style == "anthropic"
    assert config.api_key == "anthropic-key"
    assert config.base_url == "https://api.anthropic.com/v1"
    assert config.model == "claude-sonnet-4-5"


def test_resolve_provider_config_requires_key_for_openai_compatible(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with pytest.raises(MissingProviderConfig, match="OPENAI_API_KEY"):
        resolve_provider_config("openai-compatible")


def test_resolve_provider_config_requires_provider_specific_key(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

    with pytest.raises(MissingProviderConfig, match="DEEPSEEK_API_KEY"):
        resolve_provider_config("deepseek")


def test_resolve_provider_config_requires_dashscope_key_for_qwen(monkeypatch):
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)

    with pytest.raises(MissingProviderConfig, match="DASHSCOPE_API_KEY"):
        resolve_provider_config("qwen")


def test_load_prompt_reads_packaged_prompt():
    prompt = load_prompt("audit_summary")

    assert "ClaimHarness" in prompt
    assert "JSON" in prompt


def test_build_openai_compatible_request_uses_json_schema():
    config = LLMProviderConfig(
        provider="openai-compatible",
        api_key="test-key",
        base_url="https://example.test/v1",
        model="demo-model",
    )

    request = build_openai_compatible_request(
        config,
        system_prompt="System text",
        user_prompt="User text",
    )

    assert request.full_url == "https://example.test/v1/chat/completions"
    assert request.headers["Authorization"] == "Bearer test-key"
    assert request.headers["Content-type"] == "application/json"
    payload = json.loads(request.data.decode("utf-8"))
    assert payload["model"] == "demo-model"
    assert payload["messages"][0]["role"] == "system"
    assert payload["messages"][1]["content"] == "User text"
    assert payload["response_format"]["type"] == "json_schema"
    assert payload["response_format"]["json_schema"]["name"] == "claimharness_audit_review"
    assert payload["temperature"] == 0


def test_build_openai_compatible_request_can_use_json_object():
    config = LLMProviderConfig(
        provider="deepseek",
        api_key="test-key",
        base_url="https://api.deepseek.com",
        model="deepseek-v4-flash",
        api_style="openai-chat",
        json_mode="json_object",
    )

    request = build_openai_compatible_request(
        config,
        system_prompt="System text",
        user_prompt="User text",
    )

    assert request.full_url == "https://api.deepseek.com/chat/completions"
    payload = json.loads(request.data.decode("utf-8"))
    assert payload["model"] == "deepseek-v4-flash"
    assert payload["response_format"] == {"type": "json_object"}


def test_build_openai_compatible_request_omits_authorization_when_key_absent():
    config = LLMProviderConfig(
        provider="ollama",
        api_key=None,
        base_url="http://localhost:11434/v1",
        model="llama3.2",
        api_style="openai-chat",
        json_mode="json_object",
    )

    request = build_openai_compatible_request(
        config,
        system_prompt="System text",
        user_prompt="User text",
    )

    assert request.full_url == "http://localhost:11434/v1/chat/completions"
    assert "Authorization" not in request.headers


@pytest.mark.parametrize(
    "base_url",
    [
        "http://api.example.test/v1",
        "ftp://api.example.test/v1",
        "https://user:secret@api.example.test/v1",
        "https://api.example.test/v1?tenant=demo",
        "https://api.example.test/v1#fragment",
    ],
)
def test_provider_endpoint_rejects_insecure_or_ambiguous_base_urls(base_url):
    config = LLMProviderConfig(
        provider="openai-compatible",
        api_key="test-key",
        base_url=base_url,
        model="demo-model",
        api_style="openai-chat",
    )

    with pytest.raises(MissingProviderConfig):
        build_openai_compatible_request(config, "System", "User")


@pytest.mark.parametrize(
    "base_url",
    ["http://localhost:11434/v1", "http://127.0.0.1:11434/v1", "http://[::1]:11434/v1"],
)
def test_provider_endpoint_allows_loopback_http(base_url):
    config = LLMProviderConfig(
        provider="ollama",
        api_key=None,
        base_url=base_url,
        model="llama3.2",
        api_style="openai-chat",
        json_mode="json_object",
    )

    built = build_openai_compatible_request(config, "System", "User")

    assert built.full_url.endswith("/chat/completions")


def test_build_gemini_request_uses_generate_content_shape():
    config = LLMProviderConfig(
        provider="gemini",
        api_key="gemini-key",
        base_url="https://generativelanguage.googleapis.com/v1beta",
        model="gemini-3.5-flash",
        api_style="gemini",
        json_mode="json_object",
    )

    request = build_gemini_request(config, "System text", "User text")

    assert request.full_url == "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash:generateContent"
    assert request.headers["X-goog-api-key"] == "gemini-key"
    payload = json.loads(request.data.decode("utf-8"))
    assert payload["system_instruction"]["parts"][0]["text"] == "System text"
    assert payload["contents"][0]["parts"][0]["text"] == "User text"
    assert payload["generation_config"]["response_mime_type"] == "application/json"


def test_build_anthropic_messages_request_uses_messages_shape():
    config = LLMProviderConfig(
        provider="anthropic",
        api_key="anthropic-key",
        base_url="https://api.anthropic.com/v1",
        model="claude-sonnet-4-5",
        api_style="anthropic",
        json_mode="prompted_json",
    )

    request = build_anthropic_messages_request(config, "System text", "User text")

    assert request.full_url == "https://api.anthropic.com/v1/messages"
    assert request.headers["X-api-key"] == "anthropic-key"
    assert request.headers["Anthropic-version"] == "2023-06-01"
    payload = json.loads(request.data.decode("utf-8"))
    assert payload["model"] == "claude-sonnet-4-5"
    assert payload["system"] == "System text"
    assert payload["messages"][0]["content"] == "User text"


def test_parse_openai_compatible_json_reads_chat_completion_content():
    response = {
        "choices": [
            {
                "message": {
                    "content": json.dumps(
                        {
                            "summary": "Review summary",
                            "highest_risk_claims": ["C004"],
                            "recommended_next_actions": ["Human review"],
                            "limitations": ["Synthetic demo only"],
                        }
                    )
                }
            }
        ]
    }

    parsed = parse_openai_compatible_json(json.dumps(response).encode("utf-8"))

    assert parsed["summary"] == "Review summary"
    assert parsed["highest_risk_claims"] == ["C004"]


def test_parse_gemini_json_reads_candidate_text():
    response = {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {
                            "text": json.dumps(
                                {
                                    "summary": "Gemini summary",
                                    "highest_risk_claims": [],
                                    "recommended_next_actions": [],
                                    "limitations": [],
                                }
                            )
                        }
                    ]
                }
            }
        ]
    }

    parsed = parse_gemini_json(json.dumps(response).encode("utf-8"))

    assert parsed["summary"] == "Gemini summary"


def test_parse_anthropic_json_reads_text_block():
    response = {
        "content": [
            {
                "type": "text",
                "text": json.dumps(
                    {
                        "summary": "Anthropic summary",
                        "highest_risk_claims": [],
                        "recommended_next_actions": [],
                        "limitations": [],
                    }
                ),
            }
        ]
    }

    parsed = parse_anthropic_json(json.dumps(response).encode("utf-8"))

    assert parsed["summary"] == "Anthropic summary"


@pytest.mark.parametrize(
    "review",
    [
        {
            "highest_risk_claims": [],
            "recommended_next_actions": [],
            "limitations": [],
        },
        {
            "summary": "Review",
            "highest_risk_claims": [4],
            "recommended_next_actions": [],
            "limitations": [],
        },
        {
            "summary": "Review",
            "highest_risk_claims": [],
            "recommended_next_actions": [],
            "limitations": [],
            "unexpected": "field",
        },
    ],
)
def test_provider_response_requires_strict_audit_review_schema(review):
    response = {"choices": [{"message": {"content": json.dumps(review)}}]}

    with pytest.raises(LLMProviderError, match="schema"):
        parse_openai_compatible_json(json.dumps(response).encode("utf-8"))


def test_provider_response_rejects_invalid_utf8_without_leaking_decode_error():
    with pytest.raises(LLMProviderError, match="invalid JSON content"):
        parse_openai_compatible_json(b"\xff\xfe")


def test_provider_response_rejects_non_string_message_content():
    response = {"choices": [{"message": {"content": ["not", "a", "string"]}}]}

    with pytest.raises(LLMProviderError, match="non-JSON text"):
        parse_openai_compatible_json(json.dumps(response).encode("utf-8"))


class _FakeResponse:
    def __init__(self, body: bytes, headers: dict[str, str] | None = None):
        self.body = body
        self.headers = headers or {}

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self, size: int = -1) -> bytes:
        return self.body if size < 0 else self.body[:size]


def _remote_config() -> LLMProviderConfig:
    return LLMProviderConfig(
        provider="openai-compatible",
        api_key="test-key",
        base_url="https://api.example.test/v1",
        model="demo-model",
        api_style="openai-chat",
    )


def test_provider_response_body_is_bounded():
    response = _FakeResponse(b"x" * (MAX_PROVIDER_RESPONSE_BYTES + 1))

    with pytest.raises(LLMProviderError, match="exceeds"):
        call_provider_json(
            _remote_config(),
            "System",
            "User",
            urlopen=lambda *args, **kwargs: response,
        )


def test_provider_content_length_over_limit_is_rejected_before_parsing():
    response = _FakeResponse(
        b"{}",
        headers={"Content-Length": str(MAX_PROVIDER_RESPONSE_BYTES + 1)},
    )

    with pytest.raises(LLMProviderError, match="exceeds"):
        call_provider_json(
            _remote_config(),
            "System",
            "User",
            urlopen=lambda *args, **kwargs: response,
        )


def test_provider_http_error_summary_is_bounded():
    def fail(*args, **kwargs):
        raise HTTPError(
            "https://api.example.test/v1/chat/completions",
            500,
            "failure",
            {},
            BytesIO(b"x" * (MAX_PROVIDER_ERROR_BYTES + 100)),
        )

    with pytest.raises(LLMProviderError) as exc_info:
        call_provider_json(_remote_config(), "System", "User", urlopen=fail)

    assert "[truncated]" in str(exc_info.value)
    assert len(str(exc_info.value)) < MAX_PROVIDER_ERROR_BYTES + 200


def test_provider_timeout_is_reported_as_provider_error():
    def timeout(*args, **kwargs):
        raise TimeoutError("socket timed out")

    with pytest.raises(LLMProviderError, match="timed out"):
        call_provider_json(_remote_config(), "System", "User", urlopen=timeout)


def test_default_provider_transport_rejects_redirects(monkeypatch):
    captured_handlers = []

    class RedirectingOpener:
        def open(self, api_request, timeout):
            raise HTTPError(
                api_request.full_url,
                302,
                "redirect",
                {"Location": "https://other.example.test/v1"},
                BytesIO(b"redirect refused"),
            )

    def build_opener(*handlers):
        captured_handlers.extend(handlers)
        return RedirectingOpener()

    monkeypatch.setattr(llm_module.request, "build_opener", build_opener)

    with pytest.raises(LLMProviderError, match="HTTP 302"):
        call_provider_json(_remote_config(), "System", "User")

    assert any(
        isinstance(handler, llm_module._RejectRedirectHandler)
        for handler in captured_handlers
    )
