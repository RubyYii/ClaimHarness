# OpenAI Build Week 2026 Submission and Judge Guide

## Submission identity

- **Project:** ProblemBridge: From Fuzzy Workflows to Evidence-Gated AI Build Contracts
- **Track:** Work and Productivity
- **Entrant:** complete in Devpost
- **Repository:** complete in Devpost
- **Demo URL:** complete before submission
- **Public YouTube video:** complete before submission
- **Primary Codex `/feedback` Session ID:** complete from the main Build Week task

## One-sentence pitch

ProblemBridge turns an expert's informal workflow into a testable AI build
contract, while ClaimHarness prevents unsupported capability claims from
entering implementation.

## What was built during Build Week

The repository existed before the competition. Only the following extension is
presented as Build Week work:

1. GPT-5.6 interprets a completed workflow-alignment package and returns a
   strict structured proposal containing candidate capability claims.
2. ClaimHarness checks every candidate against an allow-list of auditable
   workflow evidence and explicit human-review boundaries.
3. Every claim receives one of the required evidence statuses plus a build
   action: retain, downgrade, remove, or abstain.
4. The system exports a Codex Handoff Pack and a replayable, hash-linked record
   without storing prompts, credentials, or private inputs in model metadata.
5. The Streamlit workbench exposes this as a visible step between task
   alignment and final package review.

See [BUILD_WEEK_DELTA.md](BUILD_WEEK_DELTA.md) and Git tag
`pre-build-week-2026` for the exact baseline.

## Judge quickstart: no API key

From the repository root:

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -c requirements\constraints.txt -e ".[dev,ui]"
.venv\Scripts\python.exe -m problem_bridge build-week-demo `
  --out outputs/build_week_quality_inspection_demo `
  --llm mock
```

Open:

- `outputs/build_week_quality_inspection_demo/build_contract.md`
- `outputs/build_week_quality_inspection_demo/claim_decisions.csv`
- `outputs/build_week_quality_inspection_demo/build_record.jsonl`
- `outputs/build_week_quality_inspection_demo/codex_handoff/`

The mock run is deterministic and exercises the complete product path. Its
runtime record truthfully says that GPT-5.6 was not called.

## GPT-5.6 competition runtime

Use only synthetic or non-sensitive material:

```powershell
$env:OPENAI_API_KEY = Read-Host "OPENAI_API_KEY"
$env:OPENAI_MODEL = "gpt-5.6"
.venv\Scripts\python.exe -m problem_bridge build-week-demo `
  --out outputs/build_week_gpt56_demo `
  --llm openai
```

The competition command locks the remote path to
`https://api.openai.com/v1/responses`, rejects endpoint overrides and
non-GPT-5.6 model names, and uses a strict JSON schema. A successful run records:

- provider and requested/returned model;
- OpenAI response ID;
- hashes of the structured input and validated output;
- `gpt_5_6_used: true` only for a returned GPT-5.6-family response;
- `contains_api_key: false`.

The API key itself is never written to disk. The GPT-5.6 output remains
advisory and must pass deterministic Pydantic validation plus the ClaimHarness
gate before it enters the final contract.

## Run the local workbench

```powershell
.\RUN_PROBLEMBRIDGE_WINDOWS.bat
```

The judge-visible route is:

```text
Explore examples
  -> Domain practitioner wizard
  -> AI practitioner wizard
  -> Evidence-gated build
  -> View generated outputs
```

Choose deterministic mock for a no-key walkthrough, or choose OpenAI GPT-5.6
after setting `OPENAI_API_KEY` in the launch environment. The UI contains no API
key field and saves no credentials.

## Verification

```powershell
.venv\Scripts\python.exe -m claim_harness run `
  --manuscript examples/lab_report_audit_demo/manuscript.md `
  --tables examples/lab_report_audit_demo/tables `
  --references examples/lab_report_audit_demo/references.md `
  --out outputs/lab_report_audit_demo_run `
  --llm mock

.venv\Scripts\python.exe -m pytest -q
```

The first command must produce the five original required files:

- `claim_table.csv`
- `evidence_map.json`
- `audit_report.md`
- `revision_suggestions.md`
- `agent_trace.jsonl`

## Judging criteria map

| Criterion | Evidence |
| --- | --- |
| Technological Implementation | GPT-5.6 Responses API, strict structured output, deterministic gate, lifecycle hashes, CLI/UI/tests |
| Design | Continuous bilingual workflow with a visible evidence-gate step and downloadable handoff |
| Potential Impact | Prevents unsupported AI capability promises from reaching implementation in expert workflows |
| Quality of the Idea | Connects problem alignment before building to claim-evidence governance before implementation |

## Safety and truth boundary

- Workflow evidence supports design intent, not empirical performance.
- The tool does not replace clinicians, lawyers, teachers, policy owners,
  cultural experts, supervisors, or peer reviewers.
- No real patient data, confidential manuscripts, credentials, or unpublished
  private project material should be used in the demo.
- OCR and document intake are extraction features, not image understanding or
  professional judgement.
- A mock run must never be described as a GPT-5.6 API run.

## Owner checklist before Devpost submission

- [ ] Choose and add the repository licence appropriate to the owner's intent.
- [ ] Run the GPT-5.6 path once with synthetic data and retain its runtime record.
- [ ] Confirm the public or judge-shared repository matches the video.
- [ ] Record and publish the under-three-minute YouTube demo with audio.
- [ ] Run `/feedback` in the primary Codex Build Week task and copy the Session ID.
- [ ] Add repository, demo, video, and Session ID to Devpost.
- [ ] Submit before 21 July 2026 at 17:00 PT.
