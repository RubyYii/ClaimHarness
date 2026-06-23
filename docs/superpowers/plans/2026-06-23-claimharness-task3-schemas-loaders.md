# ClaimHarness Task 3 Schemas And Loaders Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement shared Pydantic data models and deterministic input-loading helpers for manuscripts, CSV tables, and references.

**Architecture:** `schemas.py` owns the typed records that later pipeline modules will exchange. `loader.py` owns file parsing only: Markdown heading sections, folder-based CSV table loading, and plain reference text loading.

**Tech Stack:** Python 3.10+, Pydantic v2, Pandas, Pytest.

---

## File Structure

- Modify `claim_harness/schemas.py`: define `ManuscriptSection`, `Claim`, `EvidenceItem`, `VerificationResult`, and `AuditEvent`.
- Modify `claim_harness/loader.py`: define `load_manuscript(path)`, `load_tables(path)`, and `load_references(path)`.
- Create `tests/test_schemas.py`: model construction and default-list isolation tests.
- Create `tests/test_loader.py`: Markdown section parsing, CSV table loading, and reference loading tests.
- Keep README unchanged unless behavior exposed to users changes; this task adds internals only.

### Task 1: Add Schema Tests

**Files:**
- Create: `tests/test_schemas.py`

- [ ] **Step 1: Write failing schema tests**

Create `tests/test_schemas.py`:

```python
from claim_harness.schemas import (
    AuditEvent,
    Claim,
    EvidenceItem,
    ManuscriptSection,
    VerificationResult,
)


def test_schema_models_accept_expected_fields():
    section = ManuscriptSection(name="Results", text="Metrics improved.", start_line=12)
    claim = Claim(
        claim_id="C001",
        text="The method improves Dice.",
        source_section="Results",
        claim_type="performance_claim",
        strength="strong",
        requires_evidence=["table"],
    )
    evidence = EvidenceItem(
        evidence_id="E001",
        source="table1_metrics",
        evidence_type="quantitative_result",
        text="Dice increased to 0.89.",
        linked_claim_ids=["C001"],
    )
    result = VerificationResult(
        claim_id="C001",
        status="supported",
        reason="The metric table reports the improvement.",
        risk_level="low",
        suggested_revision="No revision needed.",
    )
    event = AuditEvent(step=1, module="loader", message="Loaded inputs", data={"tables": 2})

    assert section.name == "Results"
    assert claim.requires_evidence == ["table"]
    assert evidence.linked_claim_ids == ["C001"]
    assert result.status == "supported"
    assert event.data["tables"] == 2


def test_evidence_linked_claim_ids_default_isolated():
    first = EvidenceItem(
        evidence_id="E001",
        source="references",
        evidence_type="citation",
        text="Reference note.",
    )
    second = EvidenceItem(
        evidence_id="E002",
        source="references",
        evidence_type="citation",
        text="Another reference note.",
    )

    first.linked_claim_ids.append("C001")

    assert first.linked_claim_ids == ["C001"]
    assert second.linked_claim_ids == []
```

- [ ] **Step 2: Run schema tests to verify they fail**

Run:

```bash
.venv\Scripts\python.exe -m pytest tests/test_schemas.py -v
```

Expected: FAIL because `claim_harness.schemas` does not yet define the requested classes.

### Task 2: Implement Schemas

**Files:**
- Modify: `claim_harness/schemas.py`

- [ ] **Step 3: Implement Pydantic models**

Replace `claim_harness/schemas.py` with:

```python
from typing import Any

from pydantic import BaseModel, Field


class ManuscriptSection(BaseModel):
    name: str
    text: str
    start_line: int | None


class Claim(BaseModel):
    claim_id: str
    text: str
    source_section: str
    claim_type: str
    strength: str
    requires_evidence: list[str]


class EvidenceItem(BaseModel):
    evidence_id: str
    source: str
    evidence_type: str
    text: str
    linked_claim_ids: list[str] = Field(default_factory=list)


class VerificationResult(BaseModel):
    claim_id: str
    status: str
    reason: str
    risk_level: str
    suggested_revision: str


class AuditEvent(BaseModel):
    step: int
    module: str
    message: str
    data: dict[str, Any]
```

- [ ] **Step 4: Run schema tests**

Run:

```bash
.venv\Scripts\python.exe -m pytest tests/test_schemas.py -v
```

Expected: PASS.

### Task 3: Add Loader Tests

**Files:**
- Create: `tests/test_loader.py`

- [ ] **Step 5: Write failing loader tests**

Create `tests/test_loader.py`:

```python
from pathlib import Path

import pandas as pd

from claim_harness.loader import load_manuscript, load_references, load_tables


def test_load_manuscript_parses_markdown_headings(tmp_path):
    manuscript = tmp_path / "manuscript.md"
    manuscript.write_text(
        "# Title\n\n"
        "Opening context.\n\n"
        "## Methods\n\n"
        "Method text.\n\n"
        "## Results\n\n"
        "Result text.\n",
        encoding="utf-8",
    )

    sections = load_manuscript(manuscript)

    assert [section.name for section in sections] == ["Title", "Methods", "Results"]
    assert sections[0].text == "Opening context."
    assert sections[0].start_line == 1
    assert sections[1].text == "Method text."
    assert sections[1].start_line == 5
    assert sections[2].text == "Result text."


def test_load_tables_reads_all_csv_files_by_stem(tmp_path):
    tables_dir = tmp_path / "tables"
    tables_dir.mkdir()
    (tables_dir / "metrics.csv").write_text("model,dice\nbaseline,0.81\n", encoding="utf-8")
    (tables_dir / "ablation.csv").write_text("setting,success_rate\nfull,0.86\n", encoding="utf-8")
    (tables_dir / "notes.txt").write_text("ignore me\n", encoding="utf-8")

    tables = load_tables(tables_dir)

    assert sorted(tables) == ["ablation", "metrics"]
    assert isinstance(tables["metrics"], pd.DataFrame)
    assert tables["metrics"].iloc[0]["model"] == "baseline"
    assert tables["ablation"].iloc[0]["success_rate"] == 0.86


def test_load_references_reads_text(tmp_path):
    references = tmp_path / "references.md"
    references.write_text("# References\n\n1. Synthetic reference.\n", encoding="utf-8")

    text = load_references(references)

    assert "Synthetic reference" in text
```

- [ ] **Step 6: Run loader tests to verify they fail**

Run:

```bash
.venv\Scripts\python.exe -m pytest tests/test_loader.py -v
```

Expected: FAIL because `load_manuscript`, `load_tables`, and `load_references` are not yet defined.

### Task 4: Implement Loaders

**Files:**
- Modify: `claim_harness/loader.py`

- [ ] **Step 7: Implement loader functions**

Replace `claim_harness/loader.py` with:

```python
from pathlib import Path

import pandas as pd

from .schemas import ManuscriptSection


def load_manuscript(path: str | Path) -> list[ManuscriptSection]:
    manuscript_path = Path(path)
    lines = manuscript_path.read_text(encoding="utf-8").splitlines()
    sections: list[ManuscriptSection] = []
    current_name: str | None = None
    current_start_line: int | None = None
    current_lines: list[str] = []

    def flush_section() -> None:
        if current_name is None:
            return
        sections.append(
            ManuscriptSection(
                name=current_name,
                text="\n".join(current_lines).strip(),
                start_line=current_start_line,
            )
        )

    for line_number, line in enumerate(lines, start=1):
        stripped = line.strip()
        if stripped.startswith("#"):
            heading = stripped.lstrip("#").strip()
            if heading:
                flush_section()
                current_name = heading
                current_start_line = line_number
                current_lines = []
                continue
        if current_name is not None:
            current_lines.append(line)

    flush_section()
    return sections


def load_tables(path: str | Path) -> dict[str, pd.DataFrame]:
    tables_path = Path(path)
    return {
        csv_path.stem: pd.read_csv(csv_path)
        for csv_path in sorted(tables_path.glob("*.csv"))
    }


def load_references(path: str | Path) -> str:
    return Path(path).read_text(encoding="utf-8")
```

- [ ] **Step 8: Run loader tests**

Run:

```bash
.venv\Scripts\python.exe -m pytest tests/test_loader.py -v
```

Expected: PASS.

### Task 5: Verify And Commit

**Files:**
- Test: `tests/test_schemas.py`
- Test: `tests/test_loader.py`
- Modify: `claim_harness/schemas.py`
- Modify: `claim_harness/loader.py`

- [ ] **Step 9: Run focused Task 3 tests**

Run:

```bash
.venv\Scripts\python.exe -m pytest tests/test_schemas.py tests/test_loader.py -v
```

Expected: PASS.

- [ ] **Step 10: Run full test suite**

Run:

```bash
.venv\Scripts\python.exe -m pytest
```

Expected: PASS.

- [ ] **Step 11: Commit Task 3**

```bash
git add claim_harness/schemas.py claim_harness/loader.py tests/test_schemas.py tests/test_loader.py
git commit -m "Implement schemas and input loaders"
```

## Self-Review

- Spec coverage: defines all requested Pydantic models and the three requested loader functions.
- Placeholder scan: replaces the placeholder module contents in `schemas.py` and `loader.py`; no incomplete code remains in those two modules.
- Scope check: does not implement LLM logic, claim extraction, evidence retrieval, verification, report generation, or CLI pipeline wiring.
- Type consistency: loader signatures accept `str | Path`; schema field names match `AGENTS.md` and the product design.
