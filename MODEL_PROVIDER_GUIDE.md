# Model Provider Guide

ClaimHarness and ProblemBridge remain local-first. The default provider is:

```text
mock
```

`mock` does not require an API key, does not call an external model, and is the recommended mode for first-round usability testing.

Remote providers are advisory only. They can write `llm_review.json`, but they do not replace deterministic claim extraction, evidence matching, verification statuses, or human review.

Do not send private patient data, confidential manuscripts, API keys, passwords, tokens, sensitive unpublished project materials, or data that you do not have permission to share with a third-party model provider.

## Supported provider names

Use these values with:

```powershell
.venv\Scripts\python.exe -m claim_harness run `
  --manuscript examples/oocyte_demo/manuscript.md `
  --tables examples/oocyte_demo/tables `
  --references examples/oocyte_demo/references.md `
  --out outputs/oocyte_demo_remote `
  --llm PROVIDER_NAME
```

| Provider | API style | Required key | Optional overrides | Default base URL | Default model |
| --- | --- | --- | --- | --- | --- |
| `mock` | local deterministic | none | none | none | none |
| `openai` | OpenAI chat completions | `OPENAI_API_KEY` | `OPENAI_BASE_URL`, `OPENAI_MODEL` | `https://api.openai.com/v1` | `gpt-5.4-mini` |
| `openai-compatible` | OpenAI-compatible chat completions | `OPENAI_API_KEY` | `OPENAI_BASE_URL`, `OPENAI_MODEL` | `https://api.openai.com/v1` | `gpt-5.4-mini` |
| `deepseek` | OpenAI-compatible chat completions | `DEEPSEEK_API_KEY` | `DEEPSEEK_BASE_URL`, `DEEPSEEK_MODEL` | `https://api.deepseek.com` | `deepseek-v4-flash` |
| `groq` | OpenAI-compatible chat completions | `GROQ_API_KEY` | `GROQ_BASE_URL`, `GROQ_MODEL` | `https://api.groq.com/openai/v1` | `llama-3.3-70b-versatile` |
| `mistral` | OpenAI-compatible chat completions | `MISTRAL_API_KEY` | `MISTRAL_BASE_URL`, `MISTRAL_MODEL` | `https://api.mistral.ai/v1` | `mistral-large-latest` |
| `openrouter` | OpenAI-compatible chat completions | `OPENROUTER_API_KEY` | `OPENROUTER_BASE_URL`, `OPENROUTER_MODEL` | `https://openrouter.ai/api/v1` | `openai/gpt-5.4-mini` |
| `xai` | OpenAI-compatible chat completions | `XAI_API_KEY` | `XAI_BASE_URL`, `XAI_MODEL` | `https://api.x.ai/v1` | `grok-4.3` |
| `ollama` | local OpenAI-compatible chat completions | none | `OLLAMA_BASE_URL`, `OLLAMA_MODEL`, `OLLAMA_API_KEY` | `http://localhost:11434/v1` | `llama3.2` |
| `gemini` | Gemini native generateContent | `GEMINI_API_KEY` | `GEMINI_BASE_URL`, `GEMINI_MODEL` | `https://generativelanguage.googleapis.com/v1beta` | `gemini-3.5-flash` |
| `anthropic` | Anthropic Messages API | `ANTHROPIC_API_KEY` | `ANTHROPIC_BASE_URL`, `ANTHROPIC_MODEL` | `https://api.anthropic.com/v1` | `claude-sonnet-4-5` |

## DeepSeek example

```powershell
$env:DEEPSEEK_API_KEY = Read-Host "DEEPSEEK_API_KEY"
$env:DEEPSEEK_MODEL="deepseek-v4-flash"

.venv\Scripts\python.exe -m claim_harness run `
  --manuscript examples/oocyte_demo/manuscript.md `
  --tables examples/oocyte_demo/tables `
  --references examples/oocyte_demo/references.md `
  --out outputs/oocyte_demo_deepseek `
  --llm deepseek
```

## Gemini example

```powershell
$env:GEMINI_API_KEY = Read-Host "GEMINI_API_KEY"
$env:GEMINI_MODEL="gemini-3.5-flash"

.venv\Scripts\python.exe -m claim_harness run `
  --manuscript examples/oocyte_demo/manuscript.md `
  --tables examples/oocyte_demo/tables `
  --references examples/oocyte_demo/references.md `
  --out outputs/oocyte_demo_gemini `
  --llm gemini
```

## Anthropic example

```powershell
$env:ANTHROPIC_API_KEY = Read-Host "ANTHROPIC_API_KEY"
$env:ANTHROPIC_MODEL="claude-sonnet-4-5"

.venv\Scripts\python.exe -m claim_harness run `
  --manuscript examples/oocyte_demo/manuscript.md `
  --tables examples/oocyte_demo/tables `
  --references examples/oocyte_demo/references.md `
  --out outputs/oocyte_demo_anthropic `
  --llm anthropic
```

## Local Ollama example

Start Ollama locally and pull a model first, then run:

```powershell
$env:OLLAMA_MODEL="llama3.2"

.venv\Scripts\python.exe -m claim_harness run `
  --manuscript examples/oocyte_demo/manuscript.md `
  --tables examples/oocyte_demo/tables `
  --references examples/oocyte_demo/references.md `
  --out outputs/oocyte_demo_ollama `
  --llm ollama
```

## Notes

- Use `mock` for first-time testing and non-AI user workflow validation.
- Use remote providers only when you are comfortable sending the current inputs to that provider.
- Provider model names change. Override the default model with the provider-specific `*_MODEL` environment variable when needed.
- The remote review is advisory only and should be read as an additional reviewer note.
