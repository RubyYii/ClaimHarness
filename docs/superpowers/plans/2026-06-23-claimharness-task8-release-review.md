# ClaimHarness Task 8 Pre-Release Review Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Perform a strict pre-release review and fix only high-confidence issues that affect demo readiness.

**Architecture:** This task adds automated release-readiness checks and runs the existing mock demo. It should not add major features or change the product scope.

**Tech Stack:** Python 3.10+, Pytest, Git, local CLI smoke test.

---

## File Structure

- Create `tests/test_release_readiness.py`: checks for hardcoded absolute paths, secret-like tokens, demo command documentation, conservative limitations, and absence of real-data language in examples.
- Modify `.gitignore` only if generated local artifacts need to be excluded.
- Modify README/docs only for high-confidence accuracy fixes found by the checks.
- Modify source only for high-confidence release blockers found by the checks.

### Task 1: Add Release-Readiness Tests

**Files:**
- Create: `tests/test_release_readiness.py`

- [ ] **Step 1: Write failing or protective release checks**

Create `tests/test_release_readiness.py`:

```python
import re
from pathlib import Path


TRACKED_TEXT_SUFFIXES = {".md", ".py", ".toml", ".csv", ".json", ".jsonl", ".txt"}
SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
    re.compile(r"(?i)api[_-]?key\s*=\s*['\"][^'\"]+['\"]"),
    re.compile(r"(?i)secret\s*=\s*['\"][^'\"]+['\"]"),
]
ABSOLUTE_PATH_PATTERNS = [
    re.compile(r"[A-Za-z]:\\\\Users\\\\"),
    re.compile(r"/Users/"),
    re.compile(r"/home/"),
]


def iter_project_text_files():
    ignored_parts = {".git", ".venv", ".pytest_cache", ".pytest_tmp", "outputs", "__pycache__"}
    for path in Path(".").rglob("*"):
        if not path.is_file():
            continue
        if ignored_parts & set(path.parts):
            continue
        if path.suffix.lower() in TRACKED_TEXT_SUFFIXES:
            yield path


def test_no_secrets_or_absolute_local_paths_in_project_text():
    offenders = []
    for path in iter_project_text_files():
        text = path.read_text(encoding="utf-8")
        for pattern in SECRET_PATTERNS + ABSOLUTE_PATH_PATTERNS:
            if pattern.search(text):
                offenders.append(str(path))

    assert offenders == []


def test_examples_do_not_claim_real_or_private_data():
    examples_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in Path("examples").rglob("*")
        if path.is_file() and path.suffix.lower() in TRACKED_TEXT_SUFFIXES
    ).lower()

    forbidden = ["real patient", "private patient", "confidential manuscript", "unpublished confidential"]
    for phrase in forbidden:
        assert phrase not in examples_text

    assert "synthetic" in examples_text


def test_readme_documents_runnable_demo_and_required_outputs():
    text = Path("README.md").read_text(encoding="utf-8")
    required = [
        "python.exe -m claim_harness run",
        "--llm mock",
        "claim_table.csv",
        "evidence_map.json",
        "audit_report.md",
        "revision_suggestions.md",
        "agent_trace.jsonl",
        "does not guarantee factual correctness",
    ]

    for phrase in required:
        assert phrase in text


def test_limitations_are_conservative():
    text = Path("docs/limitations.md").read_text(encoding="utf-8").lower()
    required = [
        "not a scientific review authority",
        "does not guarantee factual correctness",
        "biomedical claims require human review",
        "not be presented as a medical device",
        "pdf and figure understanding are future work",
    ]

    for phrase in required:
        assert phrase in text
```

- [ ] **Step 2: Run release-readiness tests**

Run:

```bash
.venv\Scripts\python.exe -m pytest tests/test_release_readiness.py -v
```

Expected: PASS if no blockers are present, or FAIL with a precise high-confidence issue to fix.

### Task 2: Run Strict Review Checks

**Files:**
- Read: tracked project files
- Modify: only high-confidence fixes

- [ ] **Step 3: Inspect tracked files and current git state**

Run:

```bash
git status -sb
git ls-files
```

Expected: clean state except intentional Task 8 edits.

- [ ] **Step 4: Run grep scans**

Run:

```bash
rg -n "sk-|api[_-]?key|secret|C:\\\\Users|/Users/|/home/|real patient|confidential manuscript|unpublished confidential" .
```

Expected: no unsafe secrets, hardcoded local paths, or real/confidential data references outside project policy text.

- [ ] **Step 5: Fix only high-confidence issues**

If the tests or scans find an issue, fix the smallest surface necessary. Do not add OpenAI-compatible provider, Streamlit UI, new features, or broad refactors.

### Task 3: Final Verification

**Files:**
- Run: full tests
- Run: mock demo command
- Inspect: output files

- [ ] **Step 6: Run full test suite**

Run:

```bash
.venv\Scripts\python.exe -m pytest
```

Expected: PASS.

- [ ] **Step 7: Run mock demo command**

Run:

```bash
.venv\Scripts\python.exe -m claim_harness run --manuscript examples/oocyte_demo/manuscript.md --tables examples/oocyte_demo/tables --references examples/oocyte_demo/references.md --out outputs/oocyte_demo_run --llm mock
```

Expected: exit code 0 and all five output files exist.

- [ ] **Step 8: Inspect output package**

Run:

```bash
Get-ChildItem outputs\oocyte_demo_run
```

Expected: `claim_table.csv`, `evidence_map.json`, `audit_report.md`, `revision_suggestions.md`, and `agent_trace.jsonl`.

- [ ] **Step 9: Commit Task 8**

```bash
git add tests/test_release_readiness.py README.md docs claim_harness pyproject.toml .gitignore
git commit -m "Polish ClaimHarness demo for release"
```

## Self-Review

- Spec coverage: checks clean demo command, outputs, hardcoded path risks, secret risks, data sensitivity claims, README accuracy, tests, and conservative limitations.
- Placeholder scan: no TBD/TODO or open-ended fix language.
- Scope check: no major features; fixes only high-confidence release issues.
