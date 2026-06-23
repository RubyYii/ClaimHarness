# Demo Walkthrough

This walkthrough uses the synthetic oocyte demo. The inputs are intentionally toy data, not private manuscript material.

## Install

```bash
python -m venv .venv
.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

## Run

```bash
.venv\Scripts\python.exe -m claim_harness run \
  --manuscript examples/oocyte_demo/manuscript.md \
  --tables examples/oocyte_demo/tables \
  --references examples/oocyte_demo/references.md \
  --out outputs/oocyte_demo_run \
  --llm mock
```

Expected summary:

```text
ClaimHarness audit complete.
claims=18
supported=15
weak_or_worse=3
out=outputs\oocyte_demo_run
```

## Generate Viewer

```bash
.venv\Scripts\python.exe -m claim_harness view --run outputs/oocyte_demo_run
```

This writes `outputs/oocyte_demo_run/index.html`, a static report viewer for the audit package. It does not run a server or change the audit outputs.

## Inspect Outputs

Start with `claim_table.csv`. It shows each claim, source section, claim type, status, risk level, reason, and suggested revision.

Open `audit_report.md` next. It gives a compact review summary and claim-by-claim notes.

Open `evidence_map.json` when you want to see which evidence IDs were linked to each claim.

Open `revision_suggestions.md` to inspect the claims that need narrowing, support, or human review.

Open `agent_trace.jsonl` last. It records the run as a replayable sequence of steps.

Open `index.html` when you want a browser-friendly overview with status counts, high-risk claims, evidence links, revision suggestions, and trace events.

## Presentation Order

For a short demo, show:

1. README first screen.
2. Architecture diagram.
3. Run command.
4. `index.html`.
5. `claim_table.csv`.
6. `audit_report.md`.
7. `agent_trace.jsonl`.
8. `docs/limitations.md`.

The key sentence to emphasize is:

```text
This is not a prompt-only reviewer.
```

The harness decomposes the task into task specification, context selection, claim extraction, evidence retrieval, verification, human-review routing, and trace logging.
