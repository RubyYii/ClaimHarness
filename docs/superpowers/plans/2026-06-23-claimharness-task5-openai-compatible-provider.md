# ClaimHarness Task 5 OpenAI-Compatible Provider Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an optional `--llm openai-compatible` provider without changing the deterministic default mock demo.

**Architecture:** The CLI will keep `--llm mock` as the default and validate provider configuration before loading inputs. `claim_harness.llm` will own environment-based provider config, prompt loading, JSON schema request construction, response parsing, and a small HTTP client built on the Python standard library. Real provider output will be written as an additional `llm_review.json` artifact and logged in `agent_trace.jsonl`; the core claim extraction, evidence retrieval, verification, and five required mock outputs remain deterministic.

**Tech Stack:** Python 3.10+, Pydantic, Typer, Pytest, standard-library `urllib.request`.

---

## File Structure

- Modify `claim_harness/llm.py`: add provider config, missing-key error, prompt loader, OpenAI-compatible JSON request builder, HTTP call, response parser, and `summarize_audit_with_llm`.
- Modify `claim_harness/cli.py`: accept `mock` and `openai-compatible`, validate config, call optional LLM review after deterministic verification, and write `llm_review.json`.
- Create `prompts/audit_summary.md`: prompt template for a compact, conservative JSON review.
- Create `tests/test_llm_provider.py`: unit tests for provider validation, config loading, prompt loading, request body shape, response parsing, and no-network missing-key CLI behavior.
- Modify `tests/test_cli.py`: assert `run --help` documents `openai-compatible`.
- Modify `README.md`: document optional provider usage and environment variables.
- Modify `docs/architecture.md`: mention optional provider sits after deterministic verification.
- Modify `docs/limitations.md`: clarify that LLM review is advisory and does not change conservative verification.
- Modify `tests/test_release_readiness.py`: include `llm_review.json` in optional-provider README checks while preserving mock-output expectations.

### Task 1: Provider Config and Prompt Loading Tests

**Files:**
- Create: `tests/test_llm_provider.py`
- Modify: `claim_harness/llm.py`
- Create: `prompts/audit_summary.md`

- [ ] **Step 1: Write failing tests for provider config and prompt loading**

Create `tests/test_llm_provider.py` with:

```python
import json
from pathlib import Path

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

    assert request.url == "https://example.test/v1/chat/completions"
    assert request.headers["Authorization"] == "Bearer test-key"
    assert request.headers["Content-Type"] == "application/json"
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
```

- [ ] **Step 2: Run provider tests to verify they fail**

Run:

```bash
.venv\Scripts\python.exe -m pytest tests/test_llm_provider.py -v
```

Expected: FAIL because provider config, prompt loading, request building, and response parsing do not exist yet.

- [ ] **Step 3: Create prompt and minimal provider implementation**

Create `prompts/audit_summary.md`:

```markdown
You are reviewing a ClaimHarness audit package.

Return conservative JSON only. Do not claim clinical validity, publication readiness, diagnostic safety, or factual certainty.

Summarize:
- the overall audit result
- the highest-risk claim IDs
- the next human-review actions
- limitations that should be shown to a reviewer
```

Replace `claim_harness/llm.py` with an implementation that defines:

```python
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib import request


SUPPORTED_PROVIDERS = {"mock", "openai-compatible"}
DEFAULT_OPENAI_BASE_URL = "https://api.openai.com/v1"
DEFAULT_OPENAI_MODEL = "gpt-5.4-mini"


class MissingProviderConfig(ValueError):
    pass


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
```

Then add the config, prompt, request, parse, and call helpers needed by the tests.

- [ ] **Step 4: Run provider tests to verify they pass**

Run:

```bash
.venv\Scripts\python.exe -m pytest tests/test_llm_provider.py -v
```

Expected: PASS.

### Task 2: CLI Integration and No-Key Behavior

**Files:**
- Modify: `tests/test_cli.py`
- Modify: `claim_harness/cli.py`

- [ ] **Step 5: Write failing CLI tests**

Add these tests to `tests/test_cli.py`:

```python
def test_run_help_documents_openai_compatible_provider():
    runner = CliRunner()
    result = runner.invoke(app, ["run", "--help"])

    assert result.exit_code == 0
    assert "openai-compatible" in result.output


def test_openai_compatible_provider_requires_api_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    runner = CliRunner()

    result = runner.invoke(app, ["run", "--llm", "openai-compatible"])

    assert result.exit_code != 0
    assert "OPENAI_API_KEY" in result.output
```

- [ ] **Step 6: Run CLI tests to verify they fail**

Run:

```bash
.venv\Scripts\python.exe -m pytest tests/test_cli.py -v
```

Expected: FAIL because help does not document `openai-compatible` and CLI does not yet resolve provider config.

- [ ] **Step 7: Wire config validation into CLI**

Modify `claim_harness/cli.py` so it imports `MissingProviderConfig`, `resolve_provider_config`, and `summarize_audit_with_llm`. The `llm` option help should read:

```python
llm: str = typer.Option(
    "mock",
    help="LLM provider to use: mock or openai-compatible. mock is deterministic and local.",
)
```

After `provider = validate_provider(llm)`, call:

```python
try:
    provider_config = resolve_provider_config(provider)
except MissingProviderConfig as exc:
    raise typer.BadParameter(str(exc), param_hint="--llm") from exc
```

After `results = verify_claims(claims, evidence)`, if `provider == "openai-compatible"`, call `summarize_audit_with_llm(provider_config, claims, results)`, write the returned JSON to `out / "llm_review.json"`, and log an `llm` step. The deterministic five output files should still be written by `write_outputs`.

- [ ] **Step 8: Run CLI tests to verify they pass**

Run:

```bash
.venv\Scripts\python.exe -m pytest tests/test_cli.py -v
```

Expected: PASS.

### Task 3: Documentation and Release Checks

**Files:**
- Modify: `README.md`
- Modify: `docs/architecture.md`
- Modify: `docs/limitations.md`
- Modify: `tests/test_release_readiness.py`

- [ ] **Step 9: Write failing docs/release assertions**

Update `tests/test_release_readiness.py` so `test_readme_documents_runnable_demo_and_required_outputs` requires:

```python
"openai-compatible",
"OPENAI_API_KEY",
"OPENAI_MODEL",
"llm_review.json",
```

- [ ] **Step 10: Run release-readiness tests to verify they fail**

Run:

```bash
.venv\Scripts\python.exe -m pytest tests/test_release_readiness.py -v
```

Expected: FAIL until the README documents optional provider usage.

- [ ] **Step 11: Update docs**

In `README.md`, add an "Optional OpenAI-Compatible Provider" section with:

```markdown
## Optional OpenAI-Compatible Provider

The default demo uses `--llm mock` and never needs an API key. To request an additional advisory LLM review, set environment variables and choose `openai-compatible`:

```powershell
$env:OPENAI_API_KEY="..."
$env:OPENAI_MODEL="gpt-5.4-mini"
.venv\Scripts\python.exe -m claim_harness run `
  --manuscript examples/oocyte_demo/manuscript.md `
  --tables examples/oocyte_demo/tables `
  --references examples/oocyte_demo/references.md `
  --out outputs/oocyte_demo_openai `
  --llm openai-compatible
```

`OPENAI_BASE_URL` is optional and defaults to `https://api.openai.com/v1`. The provider writes `llm_review.json` as an advisory artifact; it does not replace deterministic verification or human review.
```

In `docs/architecture.md`, state that the optional provider runs after deterministic verification and does not change claim statuses.

In `docs/limitations.md`, state that LLM output may be wrong and is advisory only.

- [ ] **Step 12: Run release-readiness tests to verify they pass**

Run:

```bash
.venv\Scripts\python.exe -m pytest tests/test_release_readiness.py -v
```

Expected: PASS.

### Task 4: Final Verification and Commit

**Files:**
- Run: full tests
- Run: mock demo command
- Commit: plan, tests, code, prompt, docs

- [ ] **Step 13: Run full tests**

Run:

```bash
.venv\Scripts\python.exe -m pytest
```

Expected: PASS.

- [ ] **Step 14: Run mock demo smoke test**

Run:

```bash
.venv\Scripts\python.exe -m claim_harness run --manuscript examples/oocyte_demo/manuscript.md --tables examples/oocyte_demo/tables --references examples/oocyte_demo/references.md --out outputs/oocyte_demo_run --llm mock
```

Expected: exit code 0 and the existing deterministic output summary. The mock run should not create `llm_review.json`.

- [ ] **Step 15: Run no-key provider smoke test**

Run:

```bash
.venv\Scripts\python.exe -m claim_harness run --llm openai-compatible
```

Expected: non-zero exit with an `OPENAI_API_KEY` message and no network call.

- [ ] **Step 16: Commit Task 5**

Run:

```bash
git add docs/superpowers/plans/2026-06-23-claimharness-task5-openai-compatible-provider.md prompts/audit_summary.md claim_harness/llm.py claim_harness/cli.py tests/test_llm_provider.py tests/test_cli.py tests/test_release_readiness.py README.md docs/architecture.md docs/limitations.md
git commit -m "Add optional OpenAI-compatible provider"
```

## Self-Review

- Spec coverage: covers default mock, optional `openai-compatible`, `OPENAI_API_KEY`, optional `OPENAI_BASE_URL`, optional `OPENAI_MODEL`, no hardcoded keys, structured JSON request, prompt file, graceful missing-key failure, docs, tests, and mock compatibility.
- Placeholder scan: no unresolved placeholder or incomplete implementation language remains.
- Type consistency: provider names, config fields, test function names, prompt name, output artifact name, and environment variables match across tasks.
