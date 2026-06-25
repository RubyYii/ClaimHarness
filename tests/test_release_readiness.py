import re
from pathlib import Path
from importlib import resources


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
    ignored_parts = {
        ".git",
        ".venv",
        ".pytest_cache",
        ".pytest_tmp",
        "outputs",
        "__pycache__",
        "tests",
        "superpowers",
    }
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
        "openai-compatible",
        "OPENAI_API_KEY",
        "OPENAI_MODEL",
        "llm_review.json",
        "claim_harness view",
        "index.html",
        "report viewer",
        "claim_harness demo",
        "source_line",
        "match reason",
        "GitHub Actions",
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


def test_ci_workflow_and_packaged_prompt_are_present():
    workflow = Path(".github/workflows/ci.yml")

    assert workflow.exists()
    workflow_text = workflow.read_text(encoding="utf-8")
    assert "pytest" in workflow_text
    assert "python-version" in workflow_text

    prompt = resources.files("claim_harness").joinpath("prompts/audit_summary.md")
    assert prompt.is_file()
    assert "ClaimHarness" in prompt.read_text(encoding="utf-8")


def test_external_review_packaging_is_present():
    required_files = [
        Path("PORTFOLIO_BRIEF.md"),
        Path("DEMO_SCRIPT_3MIN.md"),
        Path("ROADMAP.md"),
        Path("docs/problembridge_vs_storm.md"),
    ]
    for path in required_files:
        assert path.is_file(), path

    portfolio = Path("PORTFOLIO_BRIEF.md").read_text(encoding="utf-8")
    assert "ProblemBridge" in portfolio
    assert "ClaimHarness" in portfolio
    assert "pre-model problem alignment" in portfolio
    assert "post-output evidence auditing" in portfolio

    problembridge_required = [
        "problem_card.md",
        "concept_alignment_table.csv",
        "ai_task_spec.yaml",
        "evidence_contract.yaml",
        "evaluation_protocol.md",
        "misalignment_risk_report.md",
    ]
    for sample_dir in (
        Path("docs/sample_outputs/hsg_alignment"),
        Path("docs/sample_outputs/vulca_alignment"),
        Path("docs/sample_outputs/political_education_alignment"),
    ):
        for filename in problembridge_required:
            assert (sample_dir / filename).is_file(), sample_dir / filename

    claimharness_required = [
        "claim_table.csv",
        "audit_report.md",
        "revision_suggestions.md",
        "agent_trace.jsonl",
        "index.html",
    ]
    sample_dir = Path("docs/sample_outputs/claimharness_oocyte_demo")
    for filename in claimharness_required:
        assert (sample_dir / filename).is_file(), sample_dir / filename


def test_guided_ui_is_documented_for_non_ai_users():
    readme = Path("README.md").read_text(encoding="utf-8")

    assert Path("apps/problem_bridge_wizard.py").is_file()
    assert '.[dev,ui]' in readme
    assert "streamlit run apps/problem_bridge_wizard.py" in readme
    assert "Guided UI for non-AI users" in readme
    assert "Do not upload private patient data" in readme
