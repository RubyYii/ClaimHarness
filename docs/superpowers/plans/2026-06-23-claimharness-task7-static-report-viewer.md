# ClaimHarness Task 7 Static Report Viewer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a local static HTML viewer for an existing ClaimHarness audit package.

**Architecture:** `claim_harness.report_viewer` will parse the generated audit package and render a single self-contained HTML file with embedded CSS. The Typer CLI will gain a `view` command that writes `index.html` by default. The viewer is read-only, offline, and does not change deterministic audit behavior.

**Tech Stack:** Python 3.10+, Typer, Pytest, standard-library `csv`, `json`, `html`, and `pathlib`.

---

## File Structure

- Create `claim_harness/report_viewer.py`: read audit package files, validate required outputs, compute summaries, escape text, and render HTML.
- Modify `claim_harness/cli.py`: add `view` command with `--run` and optional `--out`.
- Create `tests/test_report_viewer.py`: unit tests for missing files, HTML rendering, escaping, optional LLM review display, and CLI output.
- Modify `README.md`: document the viewer command and `index.html`.
- Modify `docs/architecture.md`: add the static viewer module.
- Modify `docs/demo_walkthrough.md`: add the viewer as a demo step after running the audit.
- Modify `tests/test_release_readiness.py`: require README mention of `view` and `index.html`.

### Task 1: Report Viewer Tests

**Files:**
- Create: `tests/test_report_viewer.py`
- Create: `claim_harness/report_viewer.py`

- [ ] **Step 1: Write failing report viewer tests**

Create `tests/test_report_viewer.py`:

```python
import json
from pathlib import Path

from typer.testing import CliRunner

from claim_harness.cli import app
from claim_harness.report_viewer import MissingAuditOutput, render_report_viewer


def write_sample_audit_package(path: Path, include_llm_review: bool = False) -> None:
    path.mkdir(parents=True)
    (path / "claim_table.csv").write_text(
        "\n".join(
            [
                "claim_id,text,source_section,claim_type,strength,status,risk_level,reason,suggested_revision",
                "C001,Escaped <claim>,Results,performance_claim,strong,supported,low,Table evidence,No revision needed",
                "C002,Clinically ready claim,Discussion,clinical_claim,high,overclaimed,high,No validation,Narrow the claim",
            ]
        ),
        encoding="utf-8",
    )
    (path / "evidence_map.json").write_text(
        json.dumps(
            {
                "claims": [
                    {"claim_id": "C001", "text": "Escaped <claim>", "evidence_ids": ["E001"]},
                    {"claim_id": "C002", "text": "Clinically ready claim", "evidence_ids": []},
                ],
                "evidence": [
                    {
                        "evidence_id": "E001",
                        "source": "table1_metrics.csv",
                        "evidence_type": "quantitative_result",
                        "text": "Dice improved to 0.91",
                        "linked_claim_ids": ["C001"],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (path / "audit_report.md").write_text("# Audit Report\n\nSummary text", encoding="utf-8")
    (path / "revision_suggestions.md").write_text("# Revision Suggestions\n\nNarrow the claim", encoding="utf-8")
    (path / "agent_trace.jsonl").write_text(
        "\n".join(
            [
                json.dumps({"step": 1, "module": "loader", "message": "Loaded inputs", "data": {"sections": 3}}),
                json.dumps({"step": 2, "module": "verifier", "message": "Verified claims", "data": {"supported": 1}}),
            ]
        ),
        encoding="utf-8",
    )
    if include_llm_review:
        (path / "llm_review.json").write_text(
            json.dumps(
                {
                    "summary": "Advisory review",
                    "highest_risk_claims": ["C002"],
                    "recommended_next_actions": ["Human review"],
                    "limitations": ["Synthetic demo only"],
                }
            ),
            encoding="utf-8",
        )


def test_render_report_viewer_writes_static_html(tmp_path):
    run_dir = tmp_path / "audit"
    write_sample_audit_package(run_dir, include_llm_review=True)

    output = render_report_viewer(run_dir)
    html = output.read_text(encoding="utf-8")

    assert output == run_dir / "index.html"
    assert "ClaimHarness Report Viewer" in html
    assert "Claims audited" in html
    assert "supported" in html
    assert "overclaimed" in html
    assert "C001" in html
    assert "E001" in html
    assert "Audit trace" in html
    assert "Advisory LLM review" in html
    assert "Escaped &lt;claim&gt;" in html
    assert "<claim>" not in html


def test_render_report_viewer_reports_missing_required_outputs(tmp_path):
    run_dir = tmp_path / "audit"
    run_dir.mkdir()

    try:
        render_report_viewer(run_dir)
    except MissingAuditOutput as exc:
        message = str(exc)
    else:
        raise AssertionError("Expected MissingAuditOutput")

    assert "claim_table.csv" in message
    assert "agent_trace.jsonl" in message


def test_view_cli_writes_index_html(tmp_path):
    run_dir = tmp_path / "audit"
    write_sample_audit_package(run_dir)
    runner = CliRunner()

    result = runner.invoke(app, ["view", "--run", str(run_dir)])

    assert result.exit_code == 0, result.output
    assert (run_dir / "index.html").exists()
    assert "index.html" in result.output
```

- [ ] **Step 2: Run viewer tests to verify they fail**

Run:

```bash
.venv\Scripts\python.exe -m pytest tests/test_report_viewer.py -v
```

Expected: FAIL because `claim_harness.report_viewer` and CLI `view` do not exist.

### Task 2: Implement Static HTML Renderer

**Files:**
- Create: `claim_harness/report_viewer.py`

- [ ] **Step 3: Implement renderer**

Create `claim_harness/report_viewer.py` with:

```python
import csv
import html
import json
from collections import Counter
from pathlib import Path
from typing import Any


REQUIRED_OUTPUTS = [
    "claim_table.csv",
    "evidence_map.json",
    "audit_report.md",
    "revision_suggestions.md",
    "agent_trace.jsonl",
]


class MissingAuditOutput(FileNotFoundError):
    pass
```

Then add:

- `render_report_viewer(run_dir: str | Path, out_file: str | Path | None = None) -> Path`
- `_load_audit_package(run_dir: Path) -> dict[str, Any]`
- `_read_claim_rows(path: Path) -> list[dict[str, str]]`
- `_read_trace(path: Path) -> list[dict[str, Any]]`
- `_render_html(payload: dict[str, Any], run_dir: Path) -> str`
- small helpers for escaping, status classes, count summaries, and rendering tables

CSS should be embedded in the HTML and use a restrained review-dashboard layout with responsive tables.

- [ ] **Step 4: Run viewer tests to verify renderer-level behavior**

Run:

```bash
.venv\Scripts\python.exe -m pytest tests/test_report_viewer.py -v
```

Expected: still FAIL only because CLI `view` is not wired.

### Task 3: Wire CLI Command

**Files:**
- Modify: `claim_harness/cli.py`

- [ ] **Step 5: Add `view` command**

Add imports:

```python
from .report_viewer import MissingAuditOutput, render_report_viewer
```

Add command:

```python
@app.command()
def view(
    run: Path = typer.Option(..., help="Audit output directory containing ClaimHarness files."),
    out: Optional[Path] = typer.Option(None, help="HTML file to write. Defaults to <run>/index.html."),
) -> None:
    """Generate a static HTML viewer for an audit package."""
    try:
        html_path = render_report_viewer(run, out)
    except MissingAuditOutput as exc:
        raise typer.BadParameter(str(exc), param_hint="--run") from exc
    console.print(f"[green]Report viewer written:[/green] {html_path}")
```

- [ ] **Step 6: Run viewer tests to verify they pass**

Run:

```bash
.venv\Scripts\python.exe -m pytest tests/test_report_viewer.py -v
```

Expected: PASS.

### Task 4: Docs and Release Checks

**Files:**
- Modify: `README.md`
- Modify: `docs/architecture.md`
- Modify: `docs/demo_walkthrough.md`
- Modify: `tests/test_release_readiness.py`

- [ ] **Step 7: Add failing release check expectations**

Update `tests/test_release_readiness.py` so README must contain:

```python
"claim_harness view",
"index.html",
"Report viewer",
```

- [ ] **Step 8: Run release-readiness tests to verify they fail**

Run:

```bash
.venv\Scripts\python.exe -m pytest tests/test_release_readiness.py -v
```

Expected: FAIL until docs mention the viewer.

- [ ] **Step 9: Update docs**

In `README.md`, add a "Static Report Viewer" section:

```markdown
## Static Report Viewer

Generate a local HTML viewer for an existing audit package:

```bash
.venv\Scripts\python.exe -m claim_harness view --run outputs/oocyte_demo_run
```

This writes `outputs/oocyte_demo_run/index.html`, a static report viewer that can be opened directly in a browser. It does not run a server or change audit results.
```

Update `docs/architecture.md` to mention `claim_harness.report_viewer`.

Update `docs/demo_walkthrough.md` to add the viewer after the mock run command.

- [ ] **Step 10: Run release-readiness tests to verify they pass**

Run:

```bash
.venv\Scripts\python.exe -m pytest tests/test_release_readiness.py -v
```

Expected: PASS.

### Task 5: Full Verification, Browser Check, Commit

**Files:**
- Run: tests
- Run: mock demo and viewer command
- Inspect: generated HTML
- Commit: code, tests, docs

- [ ] **Step 11: Run full tests**

Run:

```bash
.venv\Scripts\python.exe -m pytest
```

Expected: PASS.

- [ ] **Step 12: Generate demo audit and viewer**

Run:

```bash
.venv\Scripts\python.exe -m claim_harness run --manuscript examples/oocyte_demo/manuscript.md --tables examples/oocyte_demo/tables --references examples/oocyte_demo/references.md --out outputs/oocyte_demo_run --llm mock
.venv\Scripts\python.exe -m claim_harness view --run outputs/oocyte_demo_run
```

Expected: exit code 0 and `outputs/oocyte_demo_run/index.html` exists.

- [ ] **Step 13: Verify in browser**

Open the generated HTML in the in-app browser using a `file:///` URL. Capture a screenshot and verify:

- page is not blank
- title and summary are visible
- claim table is visible
- no obvious overlap on desktop

- [ ] **Step 14: Commit Task 7**

Run:

```bash
git add docs/superpowers/specs/2026-06-23-claimharness-report-viewer-design.md docs/superpowers/plans/2026-06-23-claimharness-task7-static-report-viewer.md claim_harness/report_viewer.py claim_harness/cli.py tests/test_report_viewer.py tests/test_release_readiness.py README.md docs/architecture.md docs/demo_walkthrough.md
git commit -m "Add static report viewer"
```

## Self-Review

- Spec coverage: includes static HTML generation, CLI `view`, required file validation, optional `llm_review.json`, HTML escaping, docs, tests, and browser verification.
- Placeholder scan: no unresolved placeholder or incomplete implementation language remains.
- Type consistency: `render_report_viewer`, `MissingAuditOutput`, `--run`, `index.html`, and output file names match across tests, docs, and CLI.
