# Judge Start Here

## 60-second orientation

**Project:** ProblemBridge: From Fuzzy Workflows to Evidence-Gated AI Build
Contracts

**Track:** Work and Productivity

**Pitch:** ProblemBridge turns an expert's informal workflow into a bounded AI
build contract. ClaimHarness checks every proposed capability claim before it
enters a Codex implementation handoff.

The repository predates Build Week. The exact competition increment is listed
in `BUILD_WEEK_DELTA.md` and is separated from the baseline by:

```text
tag: pre-build-week-2026
baseline commit: b5e9960
Build Week branch: codex/build-week-2026
```

## Fastest no-key review

If this file is inside the judge bundle, open:

```text
mock_demo_output/build_contract.md
mock_demo_output/claim_decisions.csv
mock_demo_output/gpt_5_6_runtime.json
mock_demo_output/build_record.jsonl
mock_demo_output/codex_handoff/
```

The bundled mock output is deterministic and intentionally records:

```json
"gpt_5_6_used": false
```

It demonstrates the full product workflow without pretending that an API call
occurred.

## Run the product

Unzip the local application package under `release/`, then double-click:

```text
RUN_PROBLEMBRIDGE_WINDOWS.bat
```

If the browser does not open, visit:

```text
http://127.0.0.1:8501
```

The visible route is:

```text
Explore examples
  -> Domain practitioner wizard
  -> AI practitioner wizard
  -> Evidence-gated build
  -> View generated outputs
```

## Run the Build Week demo from source

From the extracted application directory:

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -c requirements\constraints.txt -e ".[dev,ui]"
.venv\Scripts\python.exe -m problem_bridge build-week-demo `
  --out outputs/build_week_quality_inspection_demo `
  --llm mock
```

For the real competition runtime, use synthetic or otherwise non-sensitive
material and provide the key only through the process environment:

```powershell
$env:OPENAI_API_KEY = Read-Host "OPENAI_API_KEY"
$env:OPENAI_MODEL = "gpt-5.6"
.venv\Scripts\python.exe -m problem_bridge build-week-demo `
  --out outputs/build_week_gpt56_demo `
  --llm openai
```

The competition command accepts only the official OpenAI Responses endpoint and
a GPT-5.6-family model. It never writes the API key.

## What to inspect

1. `claim_decisions.csv` shows retain, downgrade, remove, or abstain decisions.
2. `build_contract.md` distinguishes workflow-supported design intent from
   empirical performance.
3. `gpt_5_6_runtime.json` records the runtime truth boundary and non-secret
   hashes.
4. `build_record.jsonl` records proposal, gate, and handoff stages.
5. `codex_handoff/` contains bounded implementation instructions and acceptance
   tests.

If the bundle includes `gpt56_runtime_evidence/`, it contains a deliberately
small, non-secret evidence subset from a real synthetic GPT-5.6 run. Confirm
`gpt_5_6_used: true` before treating it as runtime evidence.

## Safety boundary

- No real patient data.
- No confidential or unpublished manuscripts.
- No credentials or private project materials.
- Workflow evidence supports design intent, not real-world accuracy.
- Professional decisions remain with qualified humans.
- Mock output must never be represented as a GPT-5.6 API run.

For the full submission narrative and verification commands, open
`BUILD_WEEK_SUBMISSION.md`.
