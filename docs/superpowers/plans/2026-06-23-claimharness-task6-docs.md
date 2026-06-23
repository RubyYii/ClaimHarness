# ClaimHarness Task 6 Documentation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade README and docs so the runnable mock demo is clear enough for job-application review.

**Architecture:** Documentation should explain the existing CLI-first mock pipeline without changing core behavior. Tests lock required README sections and required docs files.

**Tech Stack:** Markdown, Mermaid, Pytest.

---

## File Structure

- Modify `README.md`: add project title, pitch, architecture Mermaid diagram, quickstart, output examples, Agent Harness framing, limitations, and current status.
- Create `docs/architecture.md`: module responsibilities and data flow.
- Create `docs/demo_walkthrough.md`: install, run, inspect outputs, explain demo inputs.
- Create `docs/limitations.md`: conservative limits and future work.
- Create `tests/test_docs.py`: document coverage tests.

### Task 1: Add Documentation Tests

**Files:**
- Create: `tests/test_docs.py`

- [ ] **Step 1: Write failing tests for README and docs coverage**

Create `tests/test_docs.py`:

```python
from pathlib import Path


README = Path("README.md")
DOCS = {
    "architecture": Path("docs/architecture.md"),
    "walkthrough": Path("docs/demo_walkthrough.md"),
    "limitations": Path("docs/limitations.md"),
}


def test_readme_contains_demo_quality_sections():
    text = README.read_text(encoding="utf-8")
    required_phrases = [
        "ClaimHarness: A Lightweight Agent Harness for Scientific Claim-Evidence Auditing",
        "ClaimHarness turns a scientific manuscript into an auditable claim-evidence package.",
        "```mermaid",
        "Task Spec",
        "Context Manager",
        "Claim Extractor",
        "Evidence Retriever",
        "Verifier",
        "Audit Package",
        "Why this is an Agent Harness",
        "This is not a prompt-only reviewer.",
        "agent_trace.jsonl",
        "Limitations",
    ]

    for phrase in required_phrases:
        assert phrase in text


def test_required_docs_files_exist_and_have_core_topics():
    for path in DOCS.values():
        assert path.exists(), f"Missing documentation file: {path}"
        assert path.read_text(encoding="utf-8").strip()

    architecture = DOCS["architecture"].read_text(encoding="utf-8")
    walkthrough = DOCS["walkthrough"].read_text(encoding="utf-8")
    limitations = DOCS["limitations"].read_text(encoding="utf-8")

    assert "Pipeline" in architecture
    assert "agent_trace.jsonl" in walkthrough
    assert "does not guarantee factual correctness" in limitations
    assert "biomedical claims require human review" in limitations
```

- [ ] **Step 2: Run doc tests to verify they fail**

Run:

```bash
.venv\Scripts\python.exe -m pytest tests/test_docs.py -v
```

Expected: FAIL because README lacks the final sections and the docs files do not exist yet.

### Task 2: Update README

**Files:**
- Modify: `README.md`

- [ ] **Step 3: Replace README with demo-quality narrative**

README must include:

- Title: `ClaimHarness: A Lightweight Agent Harness for Scientific Claim-Evidence Auditing`
- One-paragraph pitch.
- Mermaid architecture diagram:
  `Task Spec -> Context Manager -> Claim Extractor -> Evidence Retriever -> Verifier -> Audit Package`
- Quickstart: install, run mock demo, inspect outputs.
- Output examples, including a small claim table excerpt.
- Explanation of `evidence_map.json` and `agent_trace.jsonl`.
- "Why this is an Agent Harness" section.
- Conservative limitations.

### Task 3: Add Docs Files

**Files:**
- Create: `docs/architecture.md`
- Create: `docs/demo_walkthrough.md`
- Create: `docs/limitations.md`

- [ ] **Step 4: Write architecture documentation**

Document the pipeline modules, schema objects, and output package.

- [ ] **Step 5: Write demo walkthrough**

Document setup, mock run command, expected outputs, and suggested presentation order.

- [ ] **Step 6: Write limitations**

State that ClaimHarness does not guarantee factual correctness, only checks provided files, biomedical claims require human review, mock mode is deterministic and incomplete, and PDF/figure understanding are future work.

### Task 4: Verify And Commit

**Files:**
- Test: `tests/test_docs.py`
- Run: full test suite and mock demo command

- [ ] **Step 7: Run doc tests**

Run:

```bash
.venv\Scripts\python.exe -m pytest tests/test_docs.py -v
```

Expected: PASS.

- [ ] **Step 8: Run full tests**

Run:

```bash
.venv\Scripts\python.exe -m pytest
```

Expected: PASS.

- [ ] **Step 9: Run mock demo command**

Run:

```bash
.venv\Scripts\python.exe -m claim_harness run --manuscript examples/oocyte_demo/manuscript.md --tables examples/oocyte_demo/tables --references examples/oocyte_demo/references.md --out outputs/oocyte_demo_run --llm mock
```

Expected: exit code 0 and all five outputs generated.

- [ ] **Step 10: Commit Task 6**

```bash
git add README.md docs/architecture.md docs/demo_walkthrough.md docs/limitations.md tests/test_docs.py
git commit -m "Add demo documentation and architecture"
```

## Self-Review

- Spec coverage: covers README, architecture diagram, quickstart, output examples, Agent Harness explanation, docs files, and limitations.
- Placeholder scan: no TBD/TODO or empty sections.
- Scope check: does not alter core pipeline behavior.
