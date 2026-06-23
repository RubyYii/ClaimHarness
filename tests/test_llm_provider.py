import json

import pytest

from claim_harness.llm import (
    LLMProviderConfig,
    MissingProviderConfig,
    build_openai_compatible_request,
    load_prompt,
    parse_openai_compatible_json,
    resolve_provider_config,
    validate_provider,
)


def test_validate_provider_accepts_mock_and_openai_compatible():
    assert validate_provider("mock") == "mock"
    assert validate_provider(" OpenAI-Compatible ") == "openai-compatible"


def test_validate_provider_rejects_unknown_provider():
    with pytest.raises(ValueError, match="Supported providers: mock, openai-compatible"):
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


def test_resolve_provider_config_requires_key_for_openai_compatible(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with pytest.raises(MissingProviderConfig, match="OPENAI_API_KEY"):
        resolve_provider_config("openai-compatible")


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
