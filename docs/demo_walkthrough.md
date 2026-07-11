# Demo Walkthrough

This walkthrough uses the synthetic lab-report audit demo. The inputs are intentionally toy data, not private manuscript material.

## Install

```bash
python -m venv .venv
.venv\Scripts\python.exe -m pip install -c requirements\constraints.txt -e ".[dev]"
```

## Run

Fast path:

```bash
.venv\Scripts\python.exe -m claim_harness demo --out outputs/lab_report_audit_demo_run
```

This runs the mock audit and writes the static `index.html` report viewer. `new` is the default lifecycle mode, so the output directory must be empty or absent. Use a fresh output name for a separate run.

The local Streamlit workbench and this demo path both use deterministic mock rules. The UI does not accept or store API keys. Remote advisory providers are available only through the ClaimHarness CLI.

For a UI walkthrough, keep one active local project and follow Home -> Question discovery -> Domain practitioner wizard -> AI practitioner wizard -> View generated outputs. Empty required forms should show inline guidance without creating a run. Question discovery should seed the guided interview at partial completeness; the interview should remain editable before generation; and the AI form should receive separate concise fields rather than duplicated raw package files. Output history is current-project-only by default, with an explicit opt-in for all projects.

Manual path:

```bash
.venv\Scripts\python.exe -m claim_harness run \
  --manuscript examples/lab_report_audit_demo/manuscript.md \
  --tables examples/lab_report_audit_demo/tables \
  --references examples/lab_report_audit_demo/references.md \
  --out outputs/lab_report_audit_demo_run \
  --llm mock
```

Expected summary shape:

```text
ClaimHarness audit complete.
claims=<count>
supported=<count>
weak_or_worse=<count>
out=outputs\lab_report_audit_demo_run
```

For one fixed ClaimHarness version, identical inputs, provider configuration, and deterministic mock rules produce the same claim/evidence/status content. Lifecycle IDs and timestamps are intentionally unique, and output bytes can change when the tool version or deterministic rules change. Therefore reproducibility means “same declared run specification on the same version,” not “every file is byte-identical across versions.”

To replace an existing governed output directory, read its `project_id` and `run_id` from `run_identity.json`, then provide both values explicitly:

```powershell
.venv\Scripts\python.exe -m claim_harness demo `
  --out outputs\lab_report_audit_demo_run `
  --mode replace `
  --project-id PROJECT_ID_FROM_RUN_IDENTITY `
  --expected-run-id RUN_ID_FROM_RUN_IDENTITY
```

Replace both placeholder values with the exact fields from the existing run. `resume` uses the same two identity arguments, only accepts an incomplete run, and additionally requires the exact original workflow/run specification. A completed run cannot be resumed.

## Generate Viewer

```bash
.venv\Scripts\python.exe -m claim_harness view --run outputs/lab_report_audit_demo_run
```

This writes `outputs/lab_report_audit_demo_run/index.html`, a static report viewer for the audit package. It does not run a server or change the audit outputs.

## Inspect Outputs

Start with `claim_table.csv`. It shows each claim, source section, claim type, status, risk level, reason, and suggested revision.

Use the `source_line` column to jump back to the recorded manuscript line.

Open `audit_report.md` next. It gives a compact review summary and claim-by-claim notes.

Open `evidence_map.json` when you want to see which evidence IDs were linked to each claim and the match reason for each link.

Open `revision_suggestions.md` to inspect the claims that need narrowing, support, or human review.

Open `agent_trace.jsonl` last. It records an ordered, inspectable sequence of steps; it is not a complete execution replay without the original inputs and environment.

Open `run_manifest.json` to verify the run ID, tool version, timestamps, provider status, and SHA-256 records for inputs and outputs. It stores filenames rather than absolute local paths.

Open `run_identity.json` to check the project/run IDs, workflow type, and run-specification hash. Open `run_complete.json` to verify the identity hash and exact governed artifact snapshot. The completion record is published last; it is a filesystem integrity checkpoint, not a scientific approval or complete execution replay.

Open `project_summary_log.md` for a concise navigation summary and the three-round revision guardrail. This summary is not scientific evidence, peer review, or approval.

Open `index.html` when you want a browser-friendly overview with status counts, high-risk claims, evidence links, match reasons, revision suggestions, trace events, and local status filters.

When reading evidence, remember that a Results sentence does not automatically provide strong evidence for itself. Strong table support requires a verifiable metric/value relationship, and high-risk biomedical or clinical claims default to human review unless the required external evidence is present.

## Record A Bounded ProblemBridge Revision

ProblemBridge packages include `project_record.json` and `project_summary_log.md`. After a revision, run `problem-bridge record-revision` to append schema-v3 `revision_history.jsonl`. A stable target may use at most three rounds; round three must be accepted or escalated rather than followed by a fourth local patch. Legacy v1/v2 histories require the explicit migration command before they can be read or extended.

## Presentation Order

For a short demo, show:

1. README first screen.
2. Architecture diagram.
3. Run command.
4. `index.html`.
5. `claim_table.csv`.
6. `audit_report.md`.
7. `agent_trace.jsonl`.
8. `run_manifest.json` and `project_summary_log.md`.
9. `docs/limitations.md`.

The key sentence to emphasize is:

```text
This is not a prompt-only reviewer.
```

The harness decomposes the task into task specification, context selection, claim extraction, evidence retrieval, verification, human-review routing, and trace logging.
