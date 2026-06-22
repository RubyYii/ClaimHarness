# ClaimHarness Task 1 Skeleton Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create the initial ClaimHarness Python repository skeleton with a working CLI help command and minimal tests.

**Architecture:** This task only establishes package shape and command wiring. The CLI delegates to a small Typer app, while domain modules remain placeholders until later tasks implement loaders and the mock pipeline.

**Tech Stack:** Python 3.10+, Typer, Rich, Pytest, Pydantic, Pandas.

---

## File Structure

- Create `pyproject.toml`: package metadata, dependencies, pytest configuration.
- Create `claim_harness/__init__.py`: package version.
- Create `claim_harness/__main__.py`: `python -m claim_harness` entry point.
- Create `claim_harness/cli.py`: Typer app with `run --help` available.
- Create placeholder modules: `schemas.py`, `loader.py`, `context_manager.py`, `claim_extractor.py`, `evidence_retriever.py`, `verifier.py`, `report_generator.py`, `audit_logger.py`, `llm.py`.
- Create example folders: `examples/oocyte_demo/tables`, `examples/general_demo/tables`.
- Create `outputs/.gitkeep`, `docs/.gitkeep`, and `tests/`.
- Create `README.md`: concise current status and expected future inputs/outputs.
- Create `tests/test_cli.py`: import and CLI help tests.

### Task 1: Create Package Skeleton

**Files:**
- Create: `pyproject.toml`
- Create: `claim_harness/__init__.py`
- Create: `claim_harness/__main__.py`
- Create: `claim_harness/cli.py`
- Create: placeholder modules under `claim_harness/`
- Create: `README.md`
- Create: `tests/test_cli.py`

- [ ] **Step 1: Write the failing CLI tests**

```python
from typer.testing import CliRunner

import claim_harness
from claim_harness.cli import app


def test_package_imports():
    assert claim_harness.__version__


def test_run_help_command():
    runner = CliRunner()
    result = runner.invoke(app, ["run", "--help"])

    assert result.exit_code == 0
    assert "Run a ClaimHarness audit" in result.output
    assert "--manuscript" in result.output
    assert "--llm" in result.output
```

- [ ] **Step 2: Run tests to verify they fail before implementation**

Run:

```bash
pytest tests/test_cli.py -v
```

Expected: FAIL because `claim_harness` does not exist yet.

- [ ] **Step 3: Add project metadata**

Create `pyproject.toml`:

```toml
[build-system]
requires = ["setuptools>=68", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "claim-harness"
version = "0.1.0"
description = "A lightweight Agent Harness for scientific claim-evidence auditing."
readme = "README.md"
requires-python = ">=3.10"
dependencies = [
  "pydantic>=2.0",
  "pandas>=2.0",
  "typer>=0.12",
  "rich>=13.0",
]

[project.optional-dependencies]
dev = [
  "pytest>=8.0",
]

[project.scripts]
claim-harness = "claim_harness.cli:main"

[tool.pytest.ini_options]
testpaths = ["tests"]
```

- [ ] **Step 4: Add package entry files**

Create `claim_harness/__init__.py`:

```python
"""ClaimHarness package."""

__version__ = "0.1.0"
```

Create `claim_harness/__main__.py`:

```python
from .cli import main


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Add the minimal Typer CLI**

Create `claim_harness/cli.py`:

```python
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console


app = typer.Typer(help="ClaimHarness command-line interface.")
console = Console()


@app.command()
def run(
    manuscript: Optional[Path] = typer.Option(None, help="Path to manuscript.md."),
    tables: Optional[Path] = typer.Option(None, help="Path to a folder of CSV tables."),
    references: Optional[Path] = typer.Option(None, help="Path to references.md."),
    out: Path = typer.Option(Path("outputs/run"), help="Output directory."),
    llm: str = typer.Option("mock", help="LLM provider to use. Currently only mock is supported."),
) -> None:
    """Run a ClaimHarness audit."""
    console.print("[yellow]ClaimHarness skeleton is installed.[/yellow]")
    console.print("The full audit pipeline will be implemented in a later task.")
    console.print(f"llm={llm}")
    console.print(f"out={out}")


def main() -> None:
    app()
```

- [ ] **Step 6: Add placeholder modules**

Create each placeholder file with this exact pattern, changing only the module docstring:

```python
"""Placeholder for future ClaimHarness implementation."""
```

Files:

- `claim_harness/schemas.py`
- `claim_harness/loader.py`
- `claim_harness/context_manager.py`
- `claim_harness/claim_extractor.py`
- `claim_harness/evidence_retriever.py`
- `claim_harness/verifier.py`
- `claim_harness/report_generator.py`
- `claim_harness/audit_logger.py`
- `claim_harness/llm.py`

- [ ] **Step 7: Add directories and keep files**

Create:

```text
examples/oocyte_demo/tables/.gitkeep
examples/general_demo/tables/.gitkeep
outputs/.gitkeep
docs/.gitkeep
```

- [ ] **Step 8: Add README**

Create `README.md`:

```markdown
# ClaimHarness

A lightweight Agent Harness for scientific claim-evidence auditing.

ClaimHarness is being built as a small, reproducible Python demo. It will take a Markdown manuscript, CSV result tables, and references, then produce an auditable claim-evidence package.

## Expected Input

- `manuscript.md`
- `tables/*.csv`
- `references.md`

## Expected Output

- `claim_table.csv`
- `evidence_map.json`
- `audit_report.md`
- `revision_suggestions.md`
- `agent_trace.jsonl`

## Current Status

The repository currently contains the initial package skeleton and CLI entry point. The deterministic mock audit pipeline will be implemented in later tasks.

## Development Commands

```bash
python -m claim_harness run --help
pytest
```
```

- [ ] **Step 9: Run CLI help verification**

Run:

```bash
python -m claim_harness run --help
```

Expected: exit code 0 and help output containing `Run a ClaimHarness audit`.

- [ ] **Step 10: Run tests**

Run:

```bash
pytest
```

Expected: all tests pass.

- [ ] **Step 11: Inspect file tree**

Run:

```bash
rg --files
```

Expected: output includes `pyproject.toml`, `README.md`, `claim_harness/cli.py`, and `tests/test_cli.py`.

- [ ] **Step 12: Commit Task 1**

```bash
git add .
git commit -m "Initialize ClaimHarness project skeleton"
```

## Self-Review

- Spec coverage: implements the initial repository skeleton, CLI help, README, folder structure, placeholder modules, and minimal tests.
- Placeholder scan: placeholder modules are intentional for Task 1; no implementation TODOs are left in executable code.
- Type consistency: CLI options use `Path | None` behavior through `Optional[Path]`, compatible with Python 3.10.
