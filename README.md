# ProblemBridge + ClaimHarness

<p align="center">
  <strong>A two-stage harness for interdisciplinary AI projects.</strong><br>
  ProblemBridge aligns domain problems before AI work begins. ClaimHarness audits evidence after claims exist.
</p>

<p align="center">
  <img alt="Local first" src="https://img.shields.io/badge/local--first-yes-0f766e">
  <img alt="Default API requirement" src="https://img.shields.io/badge/default-no%20API%20key-2563eb">
  <img alt="ProblemBridge" src="https://img.shields.io/badge/ProblemBridge-problem%20alignment-c2410c">
  <img alt="ClaimHarness" src="https://img.shields.io/badge/ClaimHarness-evidence%20audit-374151">
</p>

**Language:** [English](README.md) | [简体中文](README.zh-CN.md)
**Showcase:** [English static showcase](docs/static_showcase/en.html) | [中文静态展示](docs/static_showcase/zh-CN.html)

## Overview

ProblemBridge + ClaimHarness is a local-first portfolio prototype for interdisciplinary AI projects. It is not a writing assistant, STORM clone, generic RAG demo, or report generator. It focuses on a practical alignment workflow:

1. **Before AI work begins:** ProblemBridge helps teams turn a domain workflow into an aligned AI task specification, evidence contract, evaluation protocol, and human-review plan.
2. **After outputs exist:** ClaimHarness audits whether written or generated scientific claims are supported by the available manuscript, tables, and reference context.

The default path is deterministic mock mode. It does not require an API key, does not call external services, and uses synthetic examples only.

## Document Intake Layer

The Document Intake Layer lets users bring local files into the workflow before problem discovery or claim auditing. It converts supported files into auditable extraction outputs without calling an external API.

Supported input types:

- `.docx` Word documents
- `.pdf` text-based PDF files
- `.txt`
- `.md`
- `.csv`

It writes:

- `extracted_text.md`
- `extracted_tables/`
- `source_manifest.json`
- `extraction_warnings.md`
- `problem_seed.md`

The boundary is deliberate: text-based PDF only, no OCR, no scanned PDF understanding, no image understanding, and no figure interpretation. Document intake extracts text and tables; it does not validate professional claims or replace domain review.
## Question Discovery Layer

ProblemBridge does not assume the user already knows the right problem. The Question Discovery Layer helps non-AI users discover what to ask, who to ask, and what unknowns must be validated before anyone proposes an AI solution.

Use it when the user only has a vague concern such as "this workflow is slow" or "we may need AI, but I do not know what to ask yet." It writes a small expert-handoff package:

- `question_brief.md`
- `stakeholder_map.md`
- `expert_interview_guide.md`
- `unknowns_to_validate.md`
- `discussion_plan.md`

The boundary is intentional: **Do not propose a solution yet.** First identify the right questions and the people who can answer them. After that, use the guided interview or alignment generator to turn validated answers into a ProblemBridge package.

## Guided Interview Engine

ProblemBridge is designed to ask better questions before it generates artifacts. The Guided Interview Engine uses local rule-based question routing to ask one question at a time, track what it understands, show missing information, and confirm whether the workflow is clear enough to generate an alignment package.

This is the main difference from a generic chatbot. The goal is not to answer immediately; the goal is to reconstruct the user's real workflow, judgement materials, pain points, and human-review boundaries before translating anything into an AI task.

## Why This Exists

Many interdisciplinary AI projects fail before modeling starts. The original domain problem is compressed into the wrong AI task, evaluated with the wrong metric, or deployed without clear evidence boundaries. This repository explores a lightweight harness around that risk: align the problem first, then audit the claims.

```mermaid
flowchart LR
    A["Domain workflow"] --> B["ProblemBridge"]
    B --> C["AI / researcher / team work"]
    C --> D["ClaimHarness"]
    B --> E["Task spec + evidence contract + evaluation protocol"]
    D --> F["Claim table + audit report + trace log"]
```

## Who It Is For

- **Domain practitioners** who can describe daily work, judgement materials, pain points, and review boundaries but do not want to write an AI task from scratch.
- **AI and research users** who need to translate domain problems into task specifications, evidence standards, evaluation protocols, and review routes.
- **External testers** who want a local prototype they can run without API keys, private data, or online deployment.

## What It Produces

ProblemBridge writes a Problem Alignment Package:

- workflow map
- pain point and opportunity matrix
- concept alignment table
- AI task specification
- evidence contract
- evaluation protocol
- misalignment risk report
- human-in-the-loop plan
- implementation routes
- alignment trace

ClaimHarness writes an audit package:

- `claim_table.csv`
- `evidence_map.json`
- `audit_report.md`
- `revision_suggestions.md`
- `agent_trace.jsonl`
- optional static `index.html` report viewer

## Run Locally

For non-AI users, start with the local guided app:

```powershell
.\RUN_PROBLEMBRIDGE_WINDOWS.bat
```

If you are cloning from GitHub manually:

```powershell
git clone https://github.com/RubyYii/ClaimHarness.git
cd ClaimHarness
.\scripts\run_problembridge_ui_powershell.ps1
```

For CLI users:

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -e ".[dev,ui]"
.venv\Scripts\python.exe -m problem_bridge demo
.venv\Scripts\python.exe -m claim_harness demo
```

## Safety Boundary

Do not enter real patient data, confidential manuscripts, API keys, unpublished project materials, or sensitive personal information. Remote model providers are optional and advisory only. Use the default mock mode for first-round testing.

## Downloadable Local Web App Package

For external testing, share the generated local package:

```text
ProblemBridge-ClaimHarness-v0.3.2-local-webapp.zip
```

After downloading, unzip it and double-click:

```text
RUN_PROBLEMBRIDGE_WINDOWS.bat
```

The first run creates `.venv`, installs dependencies, and opens a local browser UI. This is not an online service and not a standalone `.exe`.
## Technical Overview

ClaimHarness: A Lightweight Agent Harness for Scientific Claim-Evidence Auditing

ClaimHarness turns a scientific manuscript into an auditable claim-evidence package. Given a Markdown manuscript, CSV result tables, and references, it extracts scientific claims, retrieves possible evidence, verifies support levels, routes risky claims for human review, and writes a replayable audit trace.

This is not a prompt-only reviewer. It decomposes the task into task specification, context selection, claim extraction, evidence retrieval, verification, human-review routing, and trace logging.

ProblemBridge is the upstream sister module: a workflow discovery and problem alignment harness for interdisciplinary AI projects. It turns a domain problem brief into a Problem Alignment Package: workflow map, pain point matrix, concept alignment table, AI task spec, evidence contract, evaluation protocol, misalignment risk report, human-in-the-loop plan, implementation routes, and trace log.

ProblemBridge aligns the problem before AI work begins; ClaimHarness audits the claims after AI or human work produces outputs.

The relationship is:

```text
ProblemBridge: domain workflow -> aligned AI task specification
ClaimHarness: scientific claim -> evidence audit
```

ProblemBridge is not STORM, RAG, or a writing assistant. STORM-like systems help explore what a topic should cover; ProblemBridge asks whether the proposed AI task remains faithful to the source-domain workflow, evidence standards, evaluation goals, and human decision boundaries.

Run the bundled synthetic demo and generate the browser report in one command:

```bash
.venv\Scripts\python.exe -m claim_harness demo
```

Run the bundled ProblemBridge HSG alignment demo:

```bash
.venv\Scripts\python.exe -m problem_bridge demo
```

The project is checked by GitHub Actions CI on push and pull request.

## Architecture

```mermaid
flowchart LR
    A["Task Spec"] --> B["Context Manager"]
    B --> C["Claim Extractor"]
    C --> D["Evidence Retriever"]
    D --> E["Verifier"]
    E --> F["Audit Package"]
```

The mock pipeline is deterministic and local-first. It does not require an API key.

## Quickstart

Create and install the development environment:

```bash
python -m venv .venv
.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

Run the synthetic oocyte demo manually:

```bash
.venv\Scripts\python.exe -m claim_harness run \
  --manuscript examples/oocyte_demo/manuscript.md \
  --tables examples/oocyte_demo/tables \
  --references examples/oocyte_demo/references.md \
  --out outputs/oocyte_demo_run \
  --llm mock
```

Run tests:

```bash
.venv\Scripts\python.exe -m pytest
```

Or use the one-command demo path:

```bash
.venv\Scripts\python.exe -m claim_harness demo --out outputs/oocyte_demo_run
```

## For non-AI users

If you mainly want to test whether ProblemBridge can help describe a workflow, start with the guided UI instead of the CLI.

Clone the repository and enter the project folder:

```powershell
git clone https://github.com/RubyYii/ClaimHarness.git
cd ClaimHarness
```

Run the Windows helper script:

```powershell
.\scripts\run_problembridge_ui_powershell.ps1
```

Or double-click:

```text
scripts/run_problembridge_ui_windows.bat
```

When the browser opens:

1. Start with `Explore examples`.
2. Use `Question discovery` if you do not yet know what to ask or who to ask.
3. Generate one synthetic example.
4. Read the friendly summary before opening the technical files.
5. Use `Domain practitioner wizard` to describe a repeated workflow, not an AI task.
6. Download the package for an AI engineer only after checking that it contains no private material.

Start with synthetic examples. Do not upload private patient data, confidential manuscripts, API keys, or sensitive unpublished materials.

## Downloadable local web app package

For external testing, the repository can be shared as a local web app package:

```text
ProblemBridge-ClaimHarness-v0.3.2-local-webapp.zip
```

After downloading:

1. Unzip the package.
2. Double-click `RUN_PROBLEMBRIDGE_WINDOWS.bat`.
3. Wait while the first run creates `.venv` and installs dependencies.
4. Use the browser UI that opens locally.
5. Start with `Explore examples`.
6. Then try `Domain practitioner wizard` with a non-sensitive workflow.

This is not an online service and not a standalone `.exe`. It runs locally through Python and Streamlit. Do not upload sensitive data, private patient data, confidential manuscripts, API keys, or unpublished project materials.

If the Windows launcher does not load:

1. Make sure Python 3.10 or newer is installed.
2. Re-run from a terminal so the error remains visible:

```powershell
.\RUN_PROBLEMBRIDGE_WINDOWS.bat
```

3. If the browser does not open automatically, visit:

```text
http://127.0.0.1:8501
```

Static HTML is best for viewing examples only. It does not run the workflow wizard, generate new alignment packages, or run ClaimHarness.

To build the package from a checked-out repository:

```powershell
.\scripts\build_release_zip_powershell.ps1
```

If PowerShell blocks local scripts, use:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build_release_zip_powershell.ps1
```

To test the zip before sharing:

```powershell
.\scripts\test_release_zip_powershell.ps1
```

Or:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\test_release_zip_powershell.ps1
```

## ProblemBridge Quickstart

Run the synthetic HSG alignment demo:

```bash
.venv\Scripts\python.exe -m problem_bridge demo --out outputs/problem_bridge_hsg_demo
```

Run a specific problem brief:

```bash
.venv\Scripts\python.exe -m problem_bridge align `
  --brief examples/problem_bridge/hsg/problem.md `
  --out outputs/hsg_alignment `
  --llm mock
```

The mock alignment package writes:

```text
outputs/hsg_alignment/
  problem_card.md
  workflow_map.md
  painpoint_opportunity_matrix.csv
  concept_alignment_table.csv
  ai_task_spec.yaml
  evidence_contract.yaml
  evaluation_protocol.md
  misalignment_risk_report.md
  human_in_loop_plan.md
  implementation_routes.md
  alignment_trace.jsonl
```

Bundled synthetic ProblemBridge examples:

```text
examples/problem_bridge/
  hsg/problem.md
  chinese_painting/problem.md
  political_education/problem.md
```

ProblemBridge should be used before model building, when the key question is whether a domain workflow has been turned into the right AI task. ClaimHarness should be used after claims or reports exist, when the key question is whether those claims are supported by evidence.

## Guided UI for non-AI users

ProblemBridge also includes an optional local guided UI for people who do not already know how to describe an AI task. It starts from repeated work, workflow steps, judgement materials, pain points, human-review boundaries, and useful assistant outputs. The UI then generates the same Problem Alignment Package used by the CLI.

Install the optional UI dependencies:

```powershell
.venv\Scripts\python.exe -m pip install -e ".[dev,ui]"
```

Run the local Streamlit wizard:

```powershell
.venv\Scripts\python.exe -m streamlit run apps/problem_bridge_wizard.py
```

The wizard includes:

- Explore examples
- Question discovery
- Document intake
- Domain practitioner wizard
- AI practitioner wizard
- Friendly output cards
- Advanced technical file view
- Downloadable alignment package

Do not upload private patient data, confidential manuscripts, API keys, or sensitive unpublished materials.

## Optional OpenAI-Compatible Provider

The default demo uses `--llm mock` and never needs an API key. Remote providers are optional and advisory only. Supported provider names include:

```text
mock
openai
openai-compatible
qwen
deepseek
groq
mistral
openrouter
xai
ollama
gemini
anthropic
```

Use `mock` for first-round usability testing. Use remote providers only when you are comfortable sending the current inputs to that external service.

For OpenAI or a generic OpenAI-compatible endpoint, set environment variables and choose `openai-compatible`:

```powershell
$env:OPENAI_API_KEY = Read-Host "OPENAI_API_KEY"
$env:OPENAI_MODEL="gpt-5.4-mini"
.venv\Scripts\python.exe -m claim_harness run `
  --manuscript examples/oocyte_demo/manuscript.md `
  --tables examples/oocyte_demo/tables `
  --references examples/oocyte_demo/references.md `
  --out outputs/oocyte_demo_openai `
  --llm openai-compatible
```

`OPENAI_BASE_URL` is optional and defaults to `https://api.openai.com/v1`. The provider writes `llm_review.json` as an advisory artifact; it does not replace deterministic verification or human review.

Qwen / DashScope has its own preset:

```powershell
$env:DASHSCOPE_API_KEY = Read-Host "DASHSCOPE_API_KEY"
$env:QWEN_MODEL="qwen-plus"
.venv\Scripts\python.exe -m claim_harness run `
  --manuscript examples/oocyte_demo/manuscript.md `
  --tables examples/oocyte_demo/tables `
  --references examples/oocyte_demo/references.md `
  --out outputs/oocyte_demo_qwen `
  --llm qwen
```

In the local Streamlit UI, the sidebar `Workspace Memory` and `API Settings` can remember provider, base URL, model, recent output path, and draft form fields in `outputs/ui_memory/workbench_memory.json`. Changing the provider auto-fills its default base URL and model; use `Use provider defaults` to restore those values after editing them. API keys are session-only: the password field can apply the key to the current Streamlit process, but it is not saved to memory. Clear local memory before sharing the folder or zip if the drafts include sensitive workflow details.

DeepSeek can use its own preset:

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

See [MODEL_PROVIDER_GUIDE.md](MODEL_PROVIDER_GUIDE.md) for `openai`, `qwen`, `deepseek`, `groq`, `mistral`, `openrouter`, `xai`, `ollama`, `gemini`, and `anthropic` setup.

## Static Report Viewer

Generate a local HTML viewer for an existing audit package:

```bash
.venv\Scripts\python.exe -m claim_harness view --run outputs/oocyte_demo_run
```

This writes `outputs/oocyte_demo_run/index.html`, a static report viewer that can be opened directly in a browser. It does not run a server or change audit results.

## Demo Input Structure

```text
examples/oocyte_demo/
  manuscript.md
  references.md
  tables/
    table1_metrics.csv
    table2_ablation.csv
```

The manuscript is fully synthetic and describes a human-in-the-loop, explainable workflow for oocyte injection guidance. The tables are toy result tables designed to exercise claim extraction, evidence retrieval, and verification logic.

## Expected Output

The mock demo writes five files:

```text
outputs/oocyte_demo_run/
  claim_table.csv
  evidence_map.json
  audit_report.md
  revision_suggestions.md
  agent_trace.jsonl
  index.html
```

`claim_table.csv` contains one row per claim:

```text
claim_id,source_line,status,claim_type,example
C002,4,supported,performance_claim,The proposed harness improves segmentation Dice and IoU...
C004,4,overclaimed,clinical_claim,Although the prototype is not clinically validated...
C007,8,weakly_supported,novelty_claim,The first design goal is to make every guidance claim traceable...
```

`source_line` points back to the approximate manuscript line. `evidence_map.json` links claim IDs to evidence IDs and includes a match reason for each link so reviewers can inspect why a claim was classified. `agent_trace.jsonl` records each pipeline step in order, including loading, extraction, retrieval, verification, and report generation.

## Why this is an Agent Harness

ClaimHarness is designed as a small harness around an AI-assisted scientific review task, not as a monolithic agent. It exposes:

- task specification
- context selection
- tool and data access
- intermediate state tracking
- verification
- human-review routing
- replayable audit log

The goal is not to replace reviewers. The goal is to make scientific claims more traceable, reviewable, and evidence-aware before they enter higher-risk workflows.

## Current Status

Implemented:

- CLI-first mock audit pipeline
- synthetic oocyte demo inputs
- Pydantic schemas
- Markdown and CSV loaders
- deterministic claim extraction
- deterministic evidence retrieval
- source_line and match reason traceability
- conservative mock verification
- optional OpenAI-compatible advisory review
- static report viewer
- GitHub Actions CI
- CSV, JSON, Markdown, and JSONL outputs

Planned or optional:

- richer prompt templates
- scanned PDF OCR and figure-aware evidence ingestion

## Limitations

- ClaimHarness does not guarantee factual correctness.
- It only checks evidence available in the provided files.
- Biomedical claims require human review.
- Mock mode is deterministic and not semantically complete.
- Scanned PDF OCR and figure understanding are future work.

See [docs/architecture.md](docs/architecture.md), [docs/demo_walkthrough.md](docs/demo_walkthrough.md), and [docs/limitations.md](docs/limitations.md) for more detail.
