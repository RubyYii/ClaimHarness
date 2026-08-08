# Model Provider Guide

ProblemBridge and ClaimHarness remain local-first and default to:

```text
mock
```

`mock` does not require an API key, does not call an external model, and is the recommended mode for first-round usability testing.

Non-mock providers are advisory only. ClaimHarness audit runs can write
`llm_review.json`; Evidence-Gated Build can use GPT-5.6 to create a strict
structured proposal. Neither path replaces deterministic evidence checks,
verification statuses, or human review.

The Evidence-Gated Build page offers a `mock` / `openai` runtime choice but has
no API-key input. OpenAI credentials and model overrides are read from the
launch environment and are never stored in workspace memory or output files.

Do not send private patient data, confidential manuscripts, API keys, passwords, tokens, sensitive unpublished project materials, or data that you do not have permission to share with a third-party model provider. An installed CLI is still usually a cloud client: selecting it may transmit the audit inputs under that client's account and billing rules.

## Supported provider names

Before selecting anything, run the offline inventory:

```powershell
.venv\Scripts\python.exe -m claim_harness providers
```

Add `--json` for machine-readable output. This check reads only environment-variable
presence and executable locations. It does not execute a discovered client, inspect
client credential files, validate an account, contact an endpoint, or print secret
values and absolute executable paths. Therefore `installed` does not mean signed in,
and `configured` does not mean that a key, endpoint, model, quota, or subscription is
currently usable.

When a real usability check is needed, probe exactly one provider with synthetic data:

```powershell
.venv\Scripts\python.exe -m claim_harness providers `
  --probe codex `
  --confirm-call `
  --probe-timeout 60
```

`--probe` is default-off and refuses to run without `--confirm-call`. A probe
can contact a cloud service, consume account quota or billing, or use local compute;
it never sends a manuscript or evidence package. The sanitized result reports only
whether one strict structured-output request succeeded. It does not expose provider
diagnostics and does not guarantee that a later request will succeed. Use `--json` if
the result is consumed by automation.

Every non-mock run defaults to a 60-second advisory-provider timeout. Slow local
models can opt into a bounded longer wait with `--llm-timeout SECONDS` (1-600).
The selected value is written to sanitized provider provenance and the run-specification
hash. Raising it changes how long ClaimHarness waits; it does not prove provider health.

Use these values with:

```powershell
.venv\Scripts\python.exe -m claim_harness run `
  --manuscript examples/lab_report_audit_demo/manuscript.md `
  --tables examples/lab_report_audit_demo/tables `
  --references examples/lab_report_audit_demo/references.md `
  --out outputs/lab_report_audit_demo_remote `
  --llm PROVIDER_NAME
```

| Provider | Transport | Authentication source | Optional overrides | Default endpoint | Default model |
| --- | --- | --- | --- | --- | --- |
| `mock` | local deterministic | none | none | none | none |
| `codex` | installed Codex CLI | current Codex CLI authentication | `CLAIMHARNESS_CODEX_BIN`, `CLAIMHARNESS_CODEX_MODEL` | selected by Codex | selected by Codex |
| `claude-cli` | installed Claude Code CLI | current Claude Code authentication | `CLAIMHARNESS_CLAUDE_BIN`, `CLAIMHARNESS_CLAUDE_MODEL` | selected by Claude Code | selected by Claude Code |
| `qwen-cli` | installed Qwen Code CLI | current Qwen Code provider configuration | `CLAIMHARNESS_QWEN_BIN`, `CLAIMHARNESS_QWEN_MODEL` | selected by Qwen Code | selected by Qwen Code |
| `openai` | OpenAI Responses API + strict Structured Outputs | `OPENAI_API_KEY` | `OPENAI_BASE_URL`, `OPENAI_MODEL` | `https://api.openai.com/v1` | `gpt-5.6` |
| `openai-compatible` | OpenAI-compatible chat completions | `OPENAI_API_KEY` | `OPENAI_BASE_URL`, `OPENAI_MODEL` | `https://api.openai.com/v1` | `gpt-5.4-mini` |
| `qwen` | DashScope Qwen OpenAI-compatible chat completions | `DASHSCOPE_API_KEY` | `QWEN_BASE_URL`, `QWEN_MODEL` | `https://dashscope.aliyuncs.com/compatible-mode/v1` | `qwen-plus` |
| `kimi` | Kimi OpenAI-compatible chat completions + JSON mode | `KIMI_API_KEY` | `KIMI_BASE_URL`, `KIMI_MODEL_NAME` | `https://api.moonshot.ai/v1` | `kimi-k3` |
| `deepseek` | OpenAI-compatible chat completions | `DEEPSEEK_API_KEY` | `DEEPSEEK_BASE_URL`, `DEEPSEEK_MODEL` | `https://api.deepseek.com` | `deepseek-v4-flash` |
| `groq` | OpenAI-compatible chat completions | `GROQ_API_KEY` | `GROQ_BASE_URL`, `GROQ_MODEL` | `https://api.groq.com/openai/v1` | `llama-3.3-70b-versatile` |
| `mistral` | OpenAI-compatible chat completions | `MISTRAL_API_KEY` | `MISTRAL_BASE_URL`, `MISTRAL_MODEL` | `https://api.mistral.ai/v1` | `mistral-large-latest` |
| `openrouter` | OpenAI-compatible chat completions | `OPENROUTER_API_KEY` | `OPENROUTER_BASE_URL`, `OPENROUTER_MODEL` | `https://openrouter.ai/api/v1` | `openai/gpt-5.4-mini` |
| `xai` | OpenAI-compatible chat completions | `XAI_API_KEY` | `XAI_BASE_URL`, `XAI_MODEL` | `https://api.x.ai/v1` | `grok-4.3` |
| `ollama` | local OpenAI-compatible chat completions | none | `OLLAMA_BASE_URL`, `OLLAMA_MODEL`, `OLLAMA_API_KEY` | `http://localhost:11434/v1` | `llama3.2` |
| `gemini` | Gemini native generateContent | `GEMINI_API_KEY` | `GEMINI_BASE_URL`, `GEMINI_MODEL` | `https://generativelanguage.googleapis.com/v1beta` | `gemini-3.5-flash` |
| `anthropic` | Anthropic Messages API | `ANTHROPIC_API_KEY` | `ANTHROPIC_BASE_URL`, `ANTHROPIC_MODEL` | `https://api.anthropic.com/v1` | `claude-sonnet-4-5` |

## Supported installed Codex, Claude Code, and Qwen Code clients

The `codex`, `claude-cli`, and `qwen-cli` presets let ClaimHarness invoke an
already installed command-line client. ClaimHarness does not ask for or persist
an API key for these presets. First make sure the chosen command works and is
authenticated when run directly, then select it normally:

```powershell
.venv\Scripts\python.exe -m claim_harness run `
  --manuscript examples/lab_report_audit_demo/manuscript.md `
  --tables examples/lab_report_audit_demo/tables `
  --references examples/lab_report_audit_demo/references.md `
  --out outputs/lab_report_audit_demo_codex `
  --llm codex
```

Replace `codex` with `claude-cli` or `qwen-cli` for the other clients. By
default, each client chooses its configured model. A bounded override can be
set without changing ClaimHarness source, for example:

```powershell
$env:CLAIMHARNESS_CODEX_MODEL="gpt-5.6"
$env:CLAIMHARNESS_CLAUDE_MODEL="your-configured-claude-model"
$env:CLAIMHARNESS_QWEN_MODEL="your-configured-qwen-model"
```

If the command is not on `PATH`, set only the corresponding executable path:
`CLAIMHARNESS_CODEX_BIN`, `CLAIMHARNESS_CLAUDE_BIN`, or
`CLAIMHARNESS_QWEN_BIN`. These are executable overrides, not arbitrary shell
command templates. Explicit paths must resolve to an executable file. Local model
overrides are limited to 1-256 model-ID characters and reject spaces, control
characters, and shell metacharacters before any process starts.

The adapter uses stdin for audit content and an isolated temporary working
directory. Codex runs ephemerally with user configuration/rules ignored,
read-only sandboxing, and shell, web-search, and multi-agent tools disabled.
Claude Code runs in safe mode with tools, MCP, Chrome, and session persistence
disabled. Qwen Code runs in safe mode with a zero tool-call budget, its built-in
agent tool denied, and an ephemeral runtime directory. Output and error streams are
read concurrently into fixed-size in-memory buffers; exceeding a limit immediately
terminates the process tree. Timed-out process trees are also terminated, ANSI control
sequences are removed, and the returned object is revalidated against ClaimHarness's
Pydantic schema.

This integration is not GUI automation and does not make a cloud model local or
free. Codex and Claude Code may use a subscription login or another credential
already selected by their clients. Qwen Code may use a Coding Plan, API key, or
custom provider; `qwen-cli` means that ClaimHarness reuses that configuration,
not that Qwen is inherently keyless. Check the client's own authentication and
usage status before a run. See the official [Codex CLI documentation](https://developers.openai.com/codex/cli),
[Claude Code CLI reference](https://code.claude.com/docs/en/cli-usage), and
[Qwen Code headless-mode documentation](https://qwenlm.github.io/qwen-code-docs/en/users/features/headless/), and
[Qwen Code authentication guide](https://qwenlm.github.io/qwen-code-docs/en/users/configuration/auth/).

## Kimi Code and DeepSeek client boundary

`providers` also detects `kimi`, `deepcode`, and `deepseek` executable names, but
reports them as non-selectable candidate clients. Detection never executes those
commands.

Kimi Code is an official client and supports OAuth login plus non-interactive
`-p` / `stream-json` output. Its current print-mode contract, however, accepts the
prompt as a command argument and automatically handles regular tools; the strict
tool-free custom-agent route remains experimental. ClaimHarness therefore does not
yet pass manuscript data to it. This avoids exposing long audit input through the
process command line or enabling an agent whose tool boundary is weaker than the
existing adapters. See the official [Kimi Code command reference](https://www.kimi.com/code/docs/en/kimi-code-cli/reference/kimi-command.html).

DeepSeek provides an API and official guides for configuring other coding agents,
but the listed Deep Code and DeepSeek TUI clients are third-party tools rather than
an official DeepSeek CLI contract. ClaimHarness detects their command names only and
does not execute them. Use `--llm deepseek`, configure a supported `claude-cli` or
`qwen-cli` client with a provider you trust, or use a local OpenAI-compatible model
through `--llm ollama`. DeepSeek's own integration guide explicitly labels Deep Code
as third-party: [DeepSeek coding-agent integrations](https://api-docs.deepseek.com/quick_start/agent_integrations/deepcode).

## GPT-5.6 Evidence-Gated Build example

```powershell
$env:OPENAI_API_KEY = Read-Host "OPENAI_API_KEY"
$env:OPENAI_MODEL = "gpt-5.6"

.venv\Scripts\python.exe -m problem_bridge build-week-demo `
  --out outputs/build_week_gpt56_demo `
  --llm openai
```

This competition path only accepts the official `openai` provider, the exact
`https://api.openai.com/v1` base endpoint, and a model name in the GPT-5.6
family; endpoint overrides are rejected for this path. It writes non-secret runtime evidence to
`gpt_5_6_runtime.json`. A mock run writes `gpt_5_6_used: false`.

## Qwen / DashScope example

```powershell
$env:DASHSCOPE_API_KEY = Read-Host "DASHSCOPE_API_KEY"
$env:QWEN_MODEL="qwen-plus"

.venv\Scripts\python.exe -m claim_harness run `
  --manuscript examples/lab_report_audit_demo/manuscript.md `
  --tables examples/lab_report_audit_demo/tables `
  --references examples/lab_report_audit_demo/references.md `
  --out outputs/lab_report_audit_demo_qwen `
  --llm qwen
```

`QWEN_BASE_URL` is optional and defaults to `https://dashscope.aliyuncs.com/compatible-mode/v1`. If your DashScope workspace uses a regional endpoint, set `QWEN_BASE_URL` before running.

## Kimi API example

```powershell
$env:KIMI_API_KEY = Read-Host "KIMI_API_KEY"
$env:KIMI_MODEL_NAME="kimi-k3"

.venv\Scripts\python.exe -m claim_harness run `
  --manuscript examples/lab_report_audit_demo/manuscript.md `
  --tables examples/lab_report_audit_demo/tables `
  --references examples/lab_report_audit_demo/references.md `
  --out outputs/lab_report_audit_demo_kimi `
  --llm kimi
```

`KIMI_BASE_URL` defaults to `https://api.moonshot.ai/v1`. ClaimHarness uses
Kimi JSON mode and validates the returned object again with Pydantic. It does not
send an explicit `temperature`; Kimi applies the selected model's fixed/default
sampling contract. The API key
must come from the Kimi/Moonshot developer platform; a consumer or Kimi Code
subscription is not automatically an API credential. Kimi's official API overview
documents the OpenAI-compatible endpoint and authentication header:
[Kimi API overview](https://platform.kimi.ai/docs/api/overview).

## Local UI boundary and memory

Most Streamlit steps use deterministic local workflows. Evidence-Gated Build can
explicitly select OpenAI GPT-5.6 after the key is configured in the environment.
The workbench does not accept, collect, display, or store API keys. `Save current
workspace` writes only draft fields and the most recent output path to
`outputs/ui_memory/workbench_memory.json`. Clear local memory before sharing the
folder or zip if drafts contain sensitive workflow details.

## DeepSeek example

```powershell
$env:DEEPSEEK_API_KEY = Read-Host "DEEPSEEK_API_KEY"
$env:DEEPSEEK_MODEL="deepseek-v4-flash"

.venv\Scripts\python.exe -m claim_harness run `
  --manuscript examples/lab_report_audit_demo/manuscript.md `
  --tables examples/lab_report_audit_demo/tables `
  --references examples/lab_report_audit_demo/references.md `
  --out outputs/lab_report_audit_demo_deepseek `
  --llm deepseek
```

This is the direct API path. A DeepSeek model can also be selected behind a
trusted supported client or an Ollama-compatible local endpoint, but that client's
own authentication and model configuration remain outside ClaimHarness. Finding a
third-party `deepcode` or `deepseek` executable does not make it selectable.

## Gemini example

```powershell
$env:GEMINI_API_KEY = Read-Host "GEMINI_API_KEY"
$env:GEMINI_MODEL="gemini-3.5-flash"

.venv\Scripts\python.exe -m claim_harness run `
  --manuscript examples/lab_report_audit_demo/manuscript.md `
  --tables examples/lab_report_audit_demo/tables `
  --references examples/lab_report_audit_demo/references.md `
  --out outputs/lab_report_audit_demo_gemini `
  --llm gemini
```

## Anthropic example

```powershell
$env:ANTHROPIC_API_KEY = Read-Host "ANTHROPIC_API_KEY"
$env:ANTHROPIC_MODEL="claude-sonnet-4-5"

.venv\Scripts\python.exe -m claim_harness run `
  --manuscript examples/lab_report_audit_demo/manuscript.md `
  --tables examples/lab_report_audit_demo/tables `
  --references examples/lab_report_audit_demo/references.md `
  --out outputs/lab_report_audit_demo_anthropic `
  --llm anthropic
```

## Local Ollama example

Start Ollama locally and pull a model first, then run:

```powershell
$env:OLLAMA_MODEL="llama3.2"

.venv\Scripts\python.exe -m claim_harness run `
  --manuscript examples/lab_report_audit_demo/manuscript.md `
  --tables examples/lab_report_audit_demo/tables `
  --references examples/lab_report_audit_demo/references.md `
  --out outputs/lab_report_audit_demo_ollama `
  --llm ollama `
  --llm-timeout 300
```

## Notes

- Use `mock` for first-time testing and non-AI user workflow validation.
- Use any cloud-backed provider or installed client only when you are comfortable sending the current inputs under that client's provider policy.
- Installed-client presets inherit the selected CLI's authentication environment and configuration. ClaimHarness does not attest whether that client used a subscription, an API key, a local model, or which account incurred usage.
- `providers` is an offline inventory unless one provider is explicitly selected with both `--probe PROVIDER` and `--confirm-call`.
- A successful synthetic probe validates only that one bounded request; it is not login, billing, quota, safety, or future-availability attestation.
- Use `--llm-timeout` only when a trusted slow provider needs more than the 60-second default; the accepted range is 1-600 seconds.
- Kimi Code, Deep Code, and DeepSeek TUI are detection-only until they expose a reviewed non-interactive input, tool-isolation, and strict-output contract suitable for ClaimHarness.
- Provider model names change. Override the default model with the provider-specific `*_MODEL` environment variable when needed.
- The local UI does not remember provider/model settings and never accepts API keys; OpenAI configuration remains environment-only.
- The remote review is advisory only and should be read as an additional reviewer note.
