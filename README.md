# ProblemBridge Workbench

[English](README.md) · [简体中文](README.zh-CN.md)

**Make your needs clear to a collaborator or an AI.**

Start with a real task, check the wording, then take away two briefs: one for someone from another discipline and one for a language model.

Local-first · Bilingual interface · No API key needed to start

![Illustration: turn an unclear need into shared understanding and two briefs, for a collaborator and an AI](docs/figures/github-hero-workbench-v2.png)

## Use it in three steps

1. **Describe your work.** Answer one short question at a time. Skip what you do not know yet.
2. **Confirm your meaning.** Correct the wording, explain specialist terms, and say what a useful result looks like.
3. **Take your briefs.** Copy or download both documents and choose who to share them with.

When results exist, optional **ClaimHarness** checks can compare recognized English numerical statements with CSV tables.

## Use in Codex or Claude Code

Already use a local coding assistant? Install the two portable Skills to clarify tasks, continue after feedback and check revisions directly in chat. They call the existing Python engine without a second model API key or the web UI. [Installation, update and examples](docs/agent_skills.md).

## Run locally

**Windows:** [download the source ZIP](https://github.com/RubyYii/ClaimHarness/archive/refs/heads/main.zip), unzip it, and double-click `RUN_PROBLEMBRIDGE_WINDOWS.bat`.

Use Python 3.10–3.13. The first launch installs dependencies and opens the local app at `http://127.0.0.1:8501`.

<details>
<summary>Install from a terminal</summary>

From the repository root, with your Python environment active:

```bash
python -m pip install -c requirements/constraints.txt -e ".[dev,ui]"
python -m streamlit run apps/problem_bridge_wizard.py
```

[Environment setup and troubleshooting](docs/reference.md#run-locally)

</details>

## Executable clarification example

Run `python -m problem_bridge clarify-demo --out outputs/clarification_demo --answer sensors` to follow one synthetic need through execution previews, a clarification answer, a versioned task handoff and a CSV result. Add `--correct-to observations` to demonstrate an explicit requirement correction. No model calls or real users are involved in this local demo.

[Mechanism, outputs and Python API](docs/clarification_mechanism.md)

## Continue after feedback or a revision

Bring collaborator/AI feedback back from a confirmed brief, discuss selected questions, and explicitly confirm the next version. After checking revised materials, compare two audit runs, annotate missed statements and keep user actions separate from program results.

Run the complete synthetic example with `python scripts/run_continuity_demo.py --out outputs/continuity_demo`. ClaimHarness can also run independently: `python -m streamlit run apps/claim_compare.py`. [Workflow, comparison CLI and record formats](docs/continuous_review.md)

## Export confirmed context and audit findings

Create a local, version-bound handoff from a confirmed ProblemBridge record or a single completed ClaimHarness audit. Exports retain conditions, source identities, evidence locations and separately labelled user records. [Commands and output contents](docs/local_handoffs.md).

## Scope and privacy

The guided web interface uses local, predefined questions. You confirm domain meanings; documents are not sent automatically. Evidence checks are limited and do not establish factual correctness or replace expert review.

Use public or synthetic materials. Do not upload private patient data or confidential manuscripts. Clear local memory before sharing a project folder.

## Documentation

- **Use the workbench:** [English guide](docs/reference.md) · [中文指南](docs/reference.zh-CN.md)
- **Understand its limits:** [Capabilities and limitations](docs/limitations.md)
- **Configure optional tools:** [Models](MODEL_PROVIDER_GUIDE.md) · [OCR](OCR_SETUP.md)
- **Develop or explore the project:** [Architecture](docs/architecture.md) · [Documentation index](docs/project_map.md)

<details>
<summary>Command-line evidence-checking demo</summary>

Run from the repository root after installation (PowerShell):

```powershell
.venv\Scripts\python.exe -m claim_harness run `
  --manuscript examples/lab_report_audit_demo/manuscript.md `
  --tables examples/lab_report_audit_demo/tables `
  --references examples/lab_report_audit_demo/references.md `
  --out outputs/lab_report_audit_demo_run `
  --llm mock
```

Required outputs: `claim_table.csv`, `evidence_map.json`, `audit_report.md`, `revision_suggestions.md`, and `agent_trace.jsonl`.

Use a fresh `--out` folder when repeating a run. [Audit walkthrough](docs/demo_walkthrough.md) · [Full output reference](docs/reference.md#expected-output)

</details>
