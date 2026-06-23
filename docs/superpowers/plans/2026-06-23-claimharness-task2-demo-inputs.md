# ClaimHarness Task 2 Demo Inputs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add realistic but fully synthetic demo inputs for the oocyte guidance example and tests that verify the files can be loaded.

**Architecture:** This task only adds static demo artifacts and tests around their shape. It does not implement loaders, claim extraction, verification, LLM logic, or the audit pipeline.

**Tech Stack:** Python 3.10+, Pytest, standard-library `csv` and `pathlib`.

---

## File Structure

- Create `examples/oocyte_demo/manuscript.md`: synthetic short manuscript with title, abstract, introduction, methods, results, discussion, and conclusion.
- Create `examples/oocyte_demo/references.md`: 6 placeholder-style references on oocyte imaging, explainable guidance, human review, and audit trails.
- Create `examples/oocyte_demo/tables/table1_metrics.csv`: model metrics table.
- Create `examples/oocyte_demo/tables/table2_ablation.csv`: workflow ablation table.
- Modify `README.md`: add a demo input structure section.
- Create `tests/test_demo_inputs.py`: verify expected files exist, CSV columns match, manuscript sections exist, and the manuscript contains enough claim-like sentences.

### Task 1: Test Demo Input Structure

**Files:**
- Create: `tests/test_demo_inputs.py`

- [ ] **Step 1: Write failing tests for demo inputs**

Create `tests/test_demo_inputs.py`:

```python
import csv
from pathlib import Path


DEMO_ROOT = Path("examples/oocyte_demo")


def test_oocyte_demo_files_exist():
    expected_paths = [
        DEMO_ROOT / "manuscript.md",
        DEMO_ROOT / "references.md",
        DEMO_ROOT / "tables" / "table1_metrics.csv",
        DEMO_ROOT / "tables" / "table2_ablation.csv",
    ]

    for path in expected_paths:
        assert path.exists(), f"Missing demo input: {path}"
        assert path.read_text(encoding="utf-8").strip()


def test_oocyte_manuscript_has_required_sections_and_claims():
    text = (DEMO_ROOT / "manuscript.md").read_text(encoding="utf-8")
    required_headings = [
        "# Human-in-the-loop and Explainable Workflow for Oocyte Injection Guidance",
        "## Abstract",
        "## Introduction",
        "## Methods",
        "## Results",
        "## Discussion",
        "## Conclusion",
    ]
    claim_keywords = [
        "improves",
        "outperforms",
        "robust",
        "reliable",
        "clinically",
        "ready",
        "novel",
        "first",
        "supports",
        "enables",
        "reduces",
        "increases",
        "auditable",
        "explainable",
    ]

    for heading in required_headings:
        assert heading in text

    claim_like_sentences = [
        sentence
        for sentence in text.replace("\n", " ").split(".")
        if any(keyword in sentence.lower() for keyword in claim_keywords)
    ]
    assert 12 <= len(claim_like_sentences) <= 18
    assert "synthetic" in text.lower()
    assert "patient" not in text.lower()


def test_oocyte_demo_metric_table_columns():
    path = DEMO_ROOT / "tables" / "table1_metrics.csv"
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        assert reader.fieldnames == ["model", "dice", "iou", "precision", "recall", "notes"]
        rows = list(reader)

    assert len(rows) >= 3
    assert any(row["model"] == "explainable_guidance_v1" for row in rows)


def test_oocyte_demo_ablation_table_columns():
    path = DEMO_ROOT / "tables" / "table2_ablation.csv"
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        assert reader.fieldnames == [
            "setting",
            "evidence_logging",
            "human_review_gate",
            "trace_replay",
            "success_rate",
            "notes",
        ]
        rows = list(reader)

    assert len(rows) >= 4
    assert any(row["human_review_gate"] == "enabled" for row in rows)
```

- [ ] **Step 2: Run tests to verify they fail before demo files exist**

Run:

```bash
.venv\Scripts\python.exe -m pytest tests/test_demo_inputs.py -v
```

Expected: FAIL because `manuscript.md`, `references.md`, and the CSV files do not exist yet.

### Task 2: Add Synthetic Oocyte Demo Inputs

**Files:**
- Create: `examples/oocyte_demo/manuscript.md`
- Create: `examples/oocyte_demo/references.md`
- Create: `examples/oocyte_demo/tables/table1_metrics.csv`
- Create: `examples/oocyte_demo/tables/table2_ablation.csv`

- [ ] **Step 3: Add the synthetic manuscript**

Create `examples/oocyte_demo/manuscript.md` with a fully synthetic manuscript about "Human-in-the-loop and explainable workflow for oocyte injection guidance". The manuscript must include exactly these Markdown headings:

```markdown
# Human-in-the-loop and Explainable Workflow for Oocyte Injection Guidance
## Abstract
## Introduction
## Methods
## Results
## Discussion
## Conclusion
```

The body must be synthetic, must not mention real patient data, and must contain 12 to 18 claim-like sentences using the Task 2 claim keywords. Include a mix of claims that are clearly table-supported, only narratively supported, unsupported, and intentionally overclaimed.

- [ ] **Step 4: Add references**

Create `examples/oocyte_demo/references.md` with 6 placeholder-style references:

```markdown
# References

1. Alvarez, M. and Chen, Y. (2024). Explainable visual guidance for laboratory micromanipulation workflows. Journal of Synthetic Assisted Reproduction Methods.
2. Banerjee, R. et al. (2023). Human-in-the-loop review gates for high-precision biomedical image analysis. Proceedings of the Workshop on Auditable AI Systems.
3. Ito, S. and Morgan, L. (2022). Segmentation metrics for oocyte and zona pellucida imaging under controlled laboratory conditions. Computational Embryology Reports.
4. Patel, N. et al. (2025). Trace replay and evidence logging in decision-support prototypes. Transactions on Reproducible Machine Learning.
5. Rivera, G. and Novak, P. (2024). Limits of automated injection guidance in synthetic microscopy benchmarks. AI Safety Notes for Biomedical Engineering.
6. Singh, A. et al. (2023). Designing conservative human-review routing for assistive laboratory software. Journal of Human-Centered Scientific Computing.
```

- [ ] **Step 5: Add metric table**

Create `examples/oocyte_demo/tables/table1_metrics.csv`:

```csv
model,dice,iou,precision,recall,notes
baseline_unet,0.81,0.69,0.84,0.78,synthetic benchmark baseline without review routing
explainable_guidance_v1,0.88,0.78,0.90,0.86,adds saliency summary and operator-facing confidence notes
explainable_guidance_v1_with_review,0.89,0.80,0.91,0.87,adds human review gate for low-confidence boundaries
compact_detector,0.76,0.61,0.80,0.72,faster but less reliable around faint zona boundaries
```

- [ ] **Step 6: Add ablation table**

Create `examples/oocyte_demo/tables/table2_ablation.csv`:

```csv
setting,evidence_logging,human_review_gate,trace_replay,success_rate,notes
vision_only,disabled,disabled,disabled,0.71,no claim trace and no explicit review routing
logging_only,enabled,disabled,enabled,0.78,records intermediate evidence but does not pause risky cases
review_gate_only,disabled,enabled,disabled,0.80,routes uncertain cases but cannot replay evidence chain
full_harness,enabled,enabled,enabled,0.86,combines evidence logging human review and replayable trace
```

### Task 3: Update Documentation

**Files:**
- Modify: `README.md`

- [ ] **Step 7: Add demo input structure to README**

Add this section after `## Expected Input`:

```markdown
## Demo Input Structure

The first synthetic demo lives under `examples/oocyte_demo/`:

```text
examples/oocyte_demo/
  manuscript.md
  references.md
  tables/
    table1_metrics.csv
    table2_ablation.csv
```

The manuscript is fully synthetic and describes a human-in-the-loop, explainable workflow for oocyte injection guidance. The tables are toy result tables designed to exercise future claim extraction, evidence retrieval, and verification logic.
```

### Task 4: Verify and Commit

**Files:**
- Test: `tests/test_demo_inputs.py`
- Read: all created demo files

- [ ] **Step 8: Run the demo input tests**

Run:

```bash
.venv\Scripts\python.exe -m pytest tests/test_demo_inputs.py -v
```

Expected: PASS.

- [ ] **Step 9: Run the full test suite**

Run:

```bash
.venv\Scripts\python.exe -m pytest
```

Expected: PASS.

- [ ] **Step 10: Inspect the file tree**

Run:

```bash
rg --files
```

Expected: output includes the manuscript, references, both CSV files, README, and `tests/test_demo_inputs.py`.

- [ ] **Step 11: Commit Task 2**

```bash
git add .
git commit -m "Add synthetic demo inputs"
```

## Self-Review

- Spec coverage: covers the Task 2 request for synthetic oocyte demo inputs, CSV table columns, references, README documentation, and file-loading tests.
- Placeholder scan: no TBD markers or vague implementation placeholders are needed; the references are intentionally placeholder-style by task requirement.
- Scope check: does not implement loaders, LLM behavior, claim extraction, evidence retrieval, or verification.
- Type consistency: tests use only `Path`, `csv.DictReader`, and existing file paths.
