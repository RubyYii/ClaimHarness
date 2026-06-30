import json

import pytest

from claim_harness.llm import (
    LLMProviderConfig,
    MissingProviderConfig,
    build_anthropic_messages_request,
    build_gemini_request,
    build_openai_compatible_request,
    load_prompt,
    parse_openai_compatible_json,
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
