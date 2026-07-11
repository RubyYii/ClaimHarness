import hashlib
from importlib import resources
import json
import os
from pathlib import Path
import re
import subprocess
import shutil
import sys
import zipfile

import pytest


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
    tracked = subprocess.run(
        ["git", "ls-files"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    for relative in tracked:
        path = Path(relative)
        if not path.is_file():
            continue
        if ignored_parts & set(path.parts):
            continue
        if any(part.startswith(".pytest_tmp") for part in path.parts):
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
        "audit_diagnostics.json",
        "human_review_queue.json",
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


def test_github_landing_page_has_visual_portfolio_header():
    readme = Path("README.md").read_text(encoding="utf-8")
    readme_zh = Path("README.zh-CN.md").read_text(encoding="utf-8")
    hero = Path("docs/figures/github-hero-flat-comic.png")
    workflow = Path("docs/figures/github-workflow.svg")

    assert hero.is_file()
    assert workflow.is_file()
    assert hero.read_bytes().startswith(b"\x89PNG")
    assert hero.stat().st_size > 100_000
    assert workflow.read_text(encoding="utf-8").lstrip().startswith("<svg")

    for phrase in [
        "docs/figures/github-hero-flat-comic.png",
        "docs/figures/github-workflow.svg",
        "Project at a glance",
        "Guided workflow",
        "Start locally",
        "No API by default",
        "Document intake -> Question discovery -> Workflow alignment -> AI task check -> Evidence audit",
    ]:
        assert phrase in readme

    for phrase in [
        "docs/figures/github-hero-flat-comic.png",
        "docs/figures/github-workflow.svg",
        "项目一眼看懂",
        "引导式工作流",
        "本地运行",
        "默认不需要 API",
    ]:
        assert phrase in readme_zh


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
    assert workflow_text.count('-e ".[dev,ui]"') == 2

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
        "project_record.json",
        "project_summary_log.md",
        "run_identity.json",
        "run_complete.json",
    ]
    for sample_dir in (
        Path("docs/sample_outputs/quality_inspection_alignment"),
        Path("docs/sample_outputs/cultural_archive_alignment"),
        Path("docs/sample_outputs/training_policy_alignment"),
    ):
        for filename in problembridge_required:
            assert (sample_dir / filename).is_file(), sample_dir / filename

    claimharness_required = [
        "claim_table.csv",
        "audit_report.md",
        "revision_suggestions.md",
        "audit_diagnostics.json",
        "human_review_queue.json",
        "agent_trace.jsonl",
        "run_manifest.json",
        "project_summary_log.md",
        "run_identity.json",
        "run_complete.json",
        "index.html",
    ]
    sample_dir = Path("docs/sample_outputs/claimharness_lab_report_audit_demo")
    for filename in claimharness_required:
        assert (sample_dir / filename).is_file(), sample_dir / filename


def test_committed_sample_runs_have_verifiable_completion_provenance():
    from problem_bridge.project_lifecycle import load_run_completion

    sample_root = Path("docs/sample_outputs")
    sample_names = [
        "claimharness_lab_report_audit_demo",
        "quality_inspection_alignment",
        "cultural_archive_alignment",
        "training_policy_alignment",
    ]
    for name in sample_names:
        sample = sample_root / name
        identity = json.loads((sample / "run_identity.json").read_text(encoding="utf-8"))
        completion = load_run_completion(sample)

        assert completion["project_id"] == identity["project_id"]
        assert completion["run_id"] == identity["run_id"]
        assert completion["artifact_sha256"]


def test_guided_ui_is_documented_for_non_ai_users():
    readme = Path("README.md").read_text(encoding="utf-8")

    assert Path("apps/problem_bridge_wizard.py").is_file()
    assert '.[dev,ui]' in readme
    assert "streamlit run apps/problem_bridge_wizard.py" in readme
    assert "Guided UI for non-AI users" in readme
    assert "Do not upload private patient data" in readme


def test_v031_usability_validation_pack_is_present():
    required_files = [
        Path("NON_AI_USER_GUIDE.md"),
        Path("USABILITY_TEST_PLAN.md"),
        Path("scripts/run_problembridge_ui_windows.bat"),
        Path("scripts/run_problembridge_ui_powershell.ps1"),
        Path("feedback/external_review_log_template.csv"),
    ]
    for path in required_files:
        assert path.is_file(), path

    guide = Path("NON_AI_USER_GUIDE.md").read_text(encoding="utf-8")
    for phrase in [
        "who this is for",
        "what it does",
        "what it does not do",
        "what to prepare",
        "safety and privacy",
        "run the guided UI",
    ]:
        assert phrase in guide

    plan = Path("USABILITY_TEST_PLAN.md").read_text(encoding="utf-8")
    for phrase in [
        "Domain practitioners",
        "AI practitioners",
        "Scientific writing users",
        "workflow map",
        "ai_task_spec.yaml",
        "ClaimHarness",
    ]:
        assert phrase in plan

    readme = Path("README.md").read_text(encoding="utf-8")
    for phrase in [
        "For non-AI users",
        "run_problembridge_ui_windows.bat",
        "Explore examples",
        "Domain practitioner wizard",
    ]:
        assert phrase in readme

    ui_text = Path("apps/problem_bridge_wizard.py").read_text(encoding="utf-8")
    assert "Start with synthetic examples" in ui_text

    feedback_header = Path("feedback/external_review_log_template.csv").read_text(encoding="utf-8").splitlines()[0]
    assert feedback_header == (
        "reviewer_type,domain,ai_background,task_used,installation_success,"
        "ui_clarity,output_usefulness,most_useful_output,most_confusing_part,"
        "suggested_change,would_use_again,notes"
    )


def test_v032_workflow_first_onboarding_is_documented():
    guide = Path("NON_AI_USER_GUIDE.md").read_text(encoding="utf-8")
    readme = Path("README.md").read_text(encoding="utf-8")
    ui_text = Path("apps/problem_bridge_wizard.py").read_text(encoding="utf-8")

    assert "You do not need to describe an AI task" in guide
    for phrase in [
        "What is one task you repeatedly do?",
        "Which step is slow, annoying, error-prone, or expert-dependent?",
        "Who currently makes the judgement?",
        "What materials do you use?",
        "What should AI never decide automatically?",
        "What kind of assistant output would be useful?",
    ]:
        assert phrase in guide

    assert readme.index("Explore examples") < readme.index("Domain practitioner wizard")
    assert "Guided Interview Engine" in readme
    assert "local rule-based question routing" in readme
    assert "理解状态" in Path("README.zh-CN.md").read_text(encoding="utf-8")
    assert "引导式追问" in Path("README.zh-CN.md").read_text(encoding="utf-8")
    assert "Describe your workflow, not an AI task" in ui_text
    assert "You do not need to know AI. Start by describing a repeated task in your work." in ui_text
    assert "Interview mode" in ui_text
    assert "Guided interview" in ui_text
    assert "Understanding so far" in ui_text
    assert "Next question" in ui_text
    assert "Generate alignment package from interview" in ui_text
    assert "completeness" in ui_text


def test_guided_ui_has_visual_workbench_shell():
    ui_text = Path("apps/problem_bridge_wizard.py").read_text(encoding="utf-8")

    for phrase in [
        "ProblemBridge Workbench",
        "visual-shell",
        "workflow_steps_container",
        "module-card",
        "Trust boundary",
        "Start here if",
        "What you get",
        "Download package",
        "stAppDeployButton",
    ]:
        assert phrase in ui_text


def test_guided_ui_has_bilingual_interface_mode():
    ui_text = Path("apps/problem_bridge_wizard.py").read_text(encoding="utf-8")
    readme = Path("README.md").read_text(encoding="utf-8")
    readme_zh = Path("README.zh-CN.md").read_text(encoding="utf-8")

    for phrase in [
        "LANGUAGE_OPTIONS",
        "_text(\"Interface language\", \"界面语言\")",
        "def _text",
        "def _page_label",
        "中文界面",
        "选择入口",
        "问题发现",
        "领域工作流向导",
        "工作台记忆",
        "ProblemBridge 工作台",
        "当前工作台不接收或保存 API 密钥",
        "声明-证据审计",
        "下载结果包",
    ]:
        assert phrase in ui_text

    assert "Language / 语言" not in ui_text
    assert "Interface language / 界面语言" not in ui_text
    assert "bilingual" in readme.lower()
    assert "中英双语" in readme_zh


def test_guided_ui_language_selection_is_visible_and_shareable():
    ui_text = Path("apps/problem_bridge_wizard.py").read_text(encoding="utf-8")

    for phrase in [
        "def _render_language_switcher",
        "st.radio",
        "st.query_params",
        "def _sync_language_from_query_params",
        "def _apply_language_control",
        "LANGUAGE_QUERY_CODES",
    ]:
        assert phrase in ui_text

    import apps.problem_bridge_wizard as ui

    assert ui._normalize_language_choice("zh") == "中文"
    assert ui._normalize_language_choice("en") == "English"
    assert ui._normalize_language_choice(["zh"]) == "中文"
    assert ui._normalize_language_choice("中文") == "中文"
    assert ui._language_query_code("中文") == "zh"
    assert ui._language_query_code("English") == "en"

def test_guided_ui_has_local_memory_without_unwired_api_settings():
    ui_text = Path("apps/problem_bridge_wizard.py").read_text(encoding="utf-8")
    provider_guide = Path("MODEL_PROVIDER_GUIDE.md").read_text(encoding="utf-8")

    for phrase in [
        "Show workspace memory",
        "Save current workspace",
        "Clear memory",
        "workbench_memory.json",
        "Privacy check before sharing",
        "Clear local memory before sharing",
        "does not accept or store API keys",
        "deterministic mock rules",
        "Remote advisory providers are available only through the ClaimHarness CLI",
    ]:
        assert phrase in ui_text

    assert "api_key_session" not in ui_text
    assert "os.environ" not in ui_text
    assert "Show API settings" not in ui_text
    assert "DASHSCOPE_API_KEY" in provider_guide
    assert "QWEN_MODEL" in provider_guide
    assert "Clear local memory before sharing" in Path("README.md").read_text(encoding="utf-8")


def test_guided_ui_keeps_sidebar_advanced_settings_collapsed():
    ui_text = Path("apps/problem_bridge_wizard.py").read_text(encoding="utf-8")

    for phrase in [
        "st.sidebar.checkbox(_text(\"Show workspace memory\", \"显示工作台记忆\"), value=False",
        "Local-first. Use synthetic or non-sensitive material first.",
        "本地优先。首次测试请使用合成或非敏感材料。",
    ]:
        assert phrase in ui_text

    assert "<div class=\"sidebar-note\">" not in ui_text
    assert "st.sidebar.expander" not in ui_text


def test_guided_ui_sidebar_has_readable_theme():
    ui_text = Path("apps/problem_bridge_wizard.py").read_text(encoding="utf-8")

    for phrase in [
        '[data-testid="stSidebar"] {',
        "width: 280px !important;",
        "color: var(--pb-ink);",
        '[data-testid="stHeader"]',
        '[data-testid="stToolbar"]',
        '[data-testid="stMainMenu"]',
        '[data-testid="stSidebar"] [data-testid="stMarkdownContainer"]',
        '[data-testid="stSidebar"] [data-testid="stWidgetLabel"]',
        '[data-testid="stSidebarContent"]',
        '[data-testid="stSidebar"] [role="radiogroup"] label',
        '[data-testid="stSidebar"] [data-testid="stElementContainer"]:has([data-testid="stRadio"])',
        'label[data-baseweb="radio"]:has(input:checked)',
        "box-shadow: inset 3px 0 0 var(--pb-teal);",
        '[data-testid="stSidebar"] [data-testid="stCheckbox"] label',
        '[data-testid="stAlert"]',
        "border-left: 5px solid var(--pb-coral);",
        "color: var(--pb-ink) !important;",
        "color: var(--pb-muted) !important;",
    ]:
        assert phrase in ui_text


def test_document_intake_layer_is_documented_and_in_ui():
    readme = Path("README.md").read_text(encoding="utf-8")
    readme_zh = Path("README.zh-CN.md").read_text(encoding="utf-8")
    guide = Path("NON_AI_USER_GUIDE.md").read_text(encoding="utf-8")
    ui_text = Path("apps/problem_bridge_wizard.py").read_text(encoding="utf-8")

    assert Path("problem_bridge/document_intake.py").is_file()
    for phrase in [
        "Document Intake Layer",
        ".doc",
        ".docx",
        "text-based PDF",
        ".html",
        "public static `http(s)` webpage URLs",
        "optional local OCR",
        "PDF annotations",
        "Word comments",
        "highlighted spans",
        "font-color marks",
        "annotation_map.json",
        "highlighted_spans.csv",
        "comment_threads.md",
        "priority_marks.md",
        "extracted_text.md",
        "source_manifest.json",
        "extraction_warnings.md",
        "no login pages",
        "image understanding",
    ]:
        assert phrase in readme

    assert "文档摄取层" in readme_zh
    assert "文字版 PDF" in readme_zh
    assert "批注" in readme_zh
    assert "高亮" in readme_zh
    assert "可选本地 OCR" in readme_zh
    assert "公开静态" in readme_zh
    assert "Document intake" in guide

    for phrase in [
        "Document intake",
        "Upload Word, PDF, HTML, Markdown, TXT, CSV, or image files",
        "Paste text here if upload does not work",
        "manual_upload_fallback.md",
        "Public static webpage URLs, one per line",
        "Enable optional OCR for images and image-only PDFs",
        "Legacy .doc",
        "text-based PDF",
        "public static http(s) URLs",
        "optional local OCR",
        "DOCX comments",
        "PDF annotations",
        "annotation_map.json",
        "highlighted_spans.csv",
        "comment_threads.md",
        "priority_marks.md",
        "extracted_text.md",
        "source_manifest.json",
        "Generate document intake package",
    ]:
        assert phrase in ui_text


def test_guided_ui_recovers_from_stale_document_intake_module_cache():
    import importlib
    import sys

    import problem_bridge.document_intake as document_intake

    original_extract_url = document_intake.extract_url
    try:
        delattr(document_intake, "extract_url")
        sys.modules.pop("apps.problem_bridge_wizard", None)

        ui = importlib.import_module("apps.problem_bridge_wizard")

        assert callable(ui.extract_url)
        assert hasattr(document_intake, "extract_url")
    finally:
        document_intake.extract_url = original_extract_url
        sys.modules.pop("apps.problem_bridge_wizard", None)


def test_document_intake_accepts_manual_upload_fallback_text():
    import apps.problem_bridge_wizard as ui

    out = ui._run_document_intake([], pasted_text="Manual fallback workflow text")

    assert (out / "source_files" / "manual_upload_fallback.md").is_file()
    assert "Manual fallback workflow text" in (out / "extracted_text.md").read_text(encoding="utf-8")
    assert "Manual fallback workflow text" in (out / "problem_seed.md").read_text(encoding="utf-8")


def test_document_intake_never_overwrites_duplicate_upload_names_or_fallback(tmp_path, monkeypatch):
    import apps.problem_bridge_wizard as ui
    from problem_bridge.project_lifecycle import load_run_completion

    class Upload:
        def __init__(self, name: str, data: bytes):
            self.name = name
            self._data = data

        def getvalue(self):
            return self._data

    monkeypatch.setattr(ui, "RUN_ROOT", tmp_path / "ui_runs")
    out = ui._run_document_intake(
        [
            Upload("notes.md", b"first source"),
            Upload("notes.md", b"second source"),
            Upload("manual_upload_fallback.md", b"uploaded fallback name"),
        ],
        pasted_text="pasted fallback source",
    )

    source_names = sorted(path.name for path in (out / "source_files").iterdir())
    assert source_names == [
        "manual_upload_fallback.md",
        "manual_upload_fallback__2.md",
        "notes.md",
        "notes__2.md",
    ]
    assert (out / "source_files" / "notes.md").read_bytes() == b"first source"
    assert (out / "source_files" / "notes__2.md").read_bytes() == b"second source"
    completion = load_run_completion(out)
    assert "source_files/notes.md" in completion["artifact_sha256"]
    assert "source_files/notes__2.md" in completion["artifact_sha256"]


def test_document_intake_can_continue_into_question_discovery():
    import apps.problem_bridge_wizard as ui

    out = ui._run_document_intake([], pasted_text="A repeated review workflow with unclear expert judgement.")
    seed = ui._question_discovery_seed_from_intake(out)
    ui_text = Path("apps/problem_bridge_wizard.py").read_text(encoding="utf-8")

    assert "A repeated review workflow" in seed["question_seed_text"]
    assert "what to ask" in seed["question_desired_change"]
    assert "Continue to Question discovery" in ui_text
    assert "_continue_to_question_discovery_from_intake" in ui_text
    assert "workspace_page" in ui_text


def test_question_discovery_can_continue_into_domain_wizard():
    import apps.problem_bridge_wizard as ui
    from problem_bridge.question_discovery import discover_questions

    package = discover_questions(
        "A review workflow has unclear expert judgement.",
        uncertainty="We do not know which expert to ask first.",
        desired_change="Prepare better questions before system design.",
    )
    out = ui._run_question_discovery(package)
    seed = ui._domain_wizard_seed_from_discovery(out)
    interview_state = ui._interview_seed_from_discovery(out)
    from problem_bridge.interview import summarize_understanding

    understanding = summarize_understanding(interview_state)
    ui_text = Path("apps/problem_bridge_wizard.py").read_text(encoding="utf-8")

    assert "review workflow" in seed["domain_draft_additional_notes"]
    assert seed["domain_draft_repeated_work"] == "A review workflow has unclear expert judgement."
    assert understanding.completeness == 0.2
    assert understanding.next_question.key == "materials"
    assert set(interview_state.answers) == {"repeated_work"}
    assert "Continue to Domain practitioner wizard" in ui_text
    assert "_continue_to_domain_wizard_from_discovery" in ui_text


def test_domain_alignment_can_continue_into_ai_wizard():
    import apps.problem_bridge_wizard as ui

    out = ui._run_problem_text(
        "A team repeatedly reviews reports, compares evidence, and needs human review boundaries.",
        "domain_practitioner",
    )
    seed = ui._ai_wizard_seed_from_alignment(out)
    ui_text = Path("apps/problem_bridge_wizard.py").read_text(encoding="utf-8")

    assert "reviews reports" in seed["ai_draft_domain_problem"]
    assert "workflow_discovery" in seed["ai_draft_candidate_task"]
    assert "ai_task_spec.yaml" not in seed["ai_draft_candidate_task"]
    assert seed["ai_draft_inputs"] != seed["ai_draft_outputs"]
    assert seed["ai_draft_user"] == ""
    assert "final domain judgement" in seed["ai_draft_high_risk_mistakes"]
    assert "evidence_contract.yaml" not in seed["ai_draft_high_risk_mistakes"]
    assert "Continue to AI practitioner wizard" in ui_text
    assert "_continue_to_ai_wizard_from_alignment" in ui_text
    assert "last_alignment_package_dir" in ui_text


def test_ai_handoff_prefers_nested_repeated_work_over_source_heading(tmp_path):
    import apps.problem_bridge_wizard as ui

    (tmp_path / "problem_card.md").write_text(
        """# Problem Card

## Source Problem

# Guided Interview Problem Brief

## repeated_work
A registrar checks condition records before approving an object loan.

## Domain Goal
Preserve a safe loan-review workflow.
""",
        encoding="utf-8",
    )
    (tmp_path / "ai_task_spec.yaml").write_text(
        """domain_goal: Preserve a safe loan-review workflow.
ai_task_type:
  - workflow_discovery
inputs:
  - condition records
outputs:
  - review checklist
human_review_required:
  - registrar approval
""",
        encoding="utf-8",
    )

    seed = ui._ai_wizard_seed_from_alignment(tmp_path)

    assert seed["ai_draft_domain_problem"] == (
        "A registrar checks condition records before approving an object loan."
    )
    assert "Guided Interview Problem Brief" not in seed["ai_draft_domain_problem"]


def test_ai_alignment_can_continue_to_view_outputs():
    import apps.problem_bridge_wizard as ui

    out = ui._run_problem_text(
        "The candidate AI task summarizes reports, but users need evidence boundaries and review routing.",
        "ai_practitioner",
    )
    ui_text = Path("apps/problem_bridge_wizard.py").read_text(encoding="utf-8")

    assert ui._view_outputs_index_for_last_run([Path("older"), out], str(out)) == 1
    assert ui._view_outputs_index_for_last_run([Path("older"), out], "") == 0
    assert "Continue to View generated outputs" in ui_text
    assert "_continue_to_view_outputs" in ui_text
    assert "last_ai_alignment_dir" in ui_text


def test_ocr_setup_guide_has_visual_install_instructions():
    readme = Path("README.md").read_text(encoding="utf-8")
    guide_path = Path("OCR_SETUP.md")
    html_path = Path("docs/ocr_setup.html")
    figures = [
        Path("docs/figures/ocr-setup-flow.svg"),
        Path("docs/figures/ocr-install-stack.svg"),
        Path("docs/figures/ocr-check-result.svg"),
    ]

    assert guide_path.is_file()
    assert html_path.is_file()
    for figure in figures:
        assert figure.is_file(), figure
        assert figure.read_text(encoding="utf-8").lstrip().startswith("<svg")

    guide = guide_path.read_text(encoding="utf-8")
    html = html_path.read_text(encoding="utf-8")
    for phrase in [
        "pip install -c requirements/constraints.txt -e \".[ui,ocr]\"",
        "UB-Mannheim",
        "brew install tesseract poppler",
        "sudo apt install tesseract-ocr poppler-utils",
        "tesseract --version",
        "pdftoppm -h",
        "chi_sim",
        "OCR is optional",
    ]:
        assert phrase in guide

    for figure in figures:
        assert figure.as_posix() in guide
        assert figure.as_posix() in html

    assert "OCR_SETUP.md" in readme
    assert "docs/ocr_setup.html" in readme


def test_guided_ui_exposes_word_and_pdf_exports():
    readme = Path("README.md").read_text(encoding="utf-8")
    readme_zh = Path("README.zh-CN.md").read_text(encoding="utf-8")
    ui_text = Path("apps/problem_bridge_wizard.py").read_text(encoding="utf-8")

    for phrase in [
        "export_output_report",
        "Download Word report",
        "Download PDF report",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/pdf",
    ]:
        assert phrase in ui_text

    for phrase in ["export_report.docx", "export_report.pdf"]:
        assert phrase in readme
        assert phrase in readme_zh


def test_question_discovery_layer_is_documented_and_in_ui():
    readme = Path("README.md").read_text(encoding="utf-8")
    readme_zh = Path("README.zh-CN.md").read_text(encoding="utf-8")
    guide = Path("NON_AI_USER_GUIDE.md").read_text(encoding="utf-8")
    ui_text = Path("apps/problem_bridge_wizard.py").read_text(encoding="utf-8")
    showcase_en = Path("docs/static_showcase/en.html").read_text(encoding="utf-8")

    assert Path("problem_bridge/question_discovery.py").is_file()
    for phrase in [
        "Question Discovery Layer",
        "discover what to ask",
        "who to ask",
        "Do not propose a solution yet",
    ]:
        assert phrase in readme

    assert "先提出问题" in readme_zh
    assert "识别该问谁" in readme_zh
    assert "question_brief.md" in guide
    assert "stakeholder_map.md" in guide

    for phrase in [
        "Question discovery",
        "Who to ask",
        "Questions to validate",
        "Do not propose a solution yet",
        "Generate question discovery package",
    ]:
        assert phrase in ui_text

    assert "Question Discovery Layer" in showcase_en
    assert "question brief" in showcase_en

def test_release_packaging_support_is_present():
    release_version = "0.4.0"
    package_name = f"ProblemBridge-ClaimHarness-v{release_version}-local-webapp.zip"
    required_files = [
        Path("RUN_PROBLEMBRIDGE_WINDOWS.bat"),
        Path("scripts/build_release_zip_powershell.ps1"),
        Path("scripts/test_release_zip_powershell.ps1"),
        Path("scripts/build_and_test_release_powershell.ps1"),
        Path("scripts/setup_problembridge_windows.ps1"),
        Path("scripts/setup_problembridge_windows.bat"),
        Path("requirements/constraints.txt"),
        Path(".gitattributes"),
        Path("RELEASE_PACKAGE_GUIDE.md"),
        Path("README.zh-CN.md"),
        Path("docs/static_showcase/index.html"),
        Path("docs/static_showcase/en.html"),
        Path("docs/static_showcase/zh-CN.html"),
    ]
    for path in required_files:
        assert path.is_file(), path

    launcher = Path("RUN_PROBLEMBRIDGE_WINDOWS.bat").read_text(encoding="utf-8")
    assert "scripts\\run_problembridge_ui_windows.bat" in launcher
    assert "pause" in launcher.lower()

    build_script = Path("scripts/build_release_zip_powershell.ps1").read_text(encoding="utf-8")
    assert 'Read-ReleaseVersion' in build_script
    assert '$derivedVersion = "v$projectVersion"' in build_script
    assert "Requested release version" in build_script
    assert "git archive" in build_script
    assert "Get-FileHash" in build_script
    assert "manifest.json" in build_script
    assert "sample_runs" in build_script
    assert "archive_entry_count" in build_script
    assert "archive_text_entry_count" in build_script
    assert "Release archive text is not LF-normalized" in build_script
    assert "dist" in build_script

    test_script = Path("scripts/test_release_zip_powershell.ps1").read_text(encoding="utf-8")
    assert "clean-smoke-venv" in test_script
    assert '-c $constraints ".[dev,ui]"' in test_script
    assert "--no-build-isolation" in test_script
    assert "PIP_REQUIRE_VIRTUALENV" in test_script
    assert "$sampleGate" in test_script
    assert f'version = "{release_version}"' in Path("pyproject.toml").read_text(encoding="utf-8")
    assert f'__version__ = "{release_version}"' in Path("claim_harness/__init__.py").read_text(encoding="utf-8")
    assert f'__version__ = "{release_version}"' in Path("problem_bridge/__init__.py").read_text(encoding="utf-8")
    assert package_name in Path("RELEASE_PACKAGE_GUIDE.md").read_text(encoding="utf-8")
    for phrase in [
        "RUN_PROBLEMBRIDGE_WINDOWS.bat",
        "apps/problem_bridge_wizard.py",
        "problem_bridge/document_intake.py",
        "claim_harness/run_records.py",
        "claim_harness/demo_data/manuscript.md",
        "problem_bridge/revision_governance.py",
        "problem_bridge/project_lifecycle.py",
        "problem_bridge/demo_data/problem.md",
        "claim_harness/evidence_contract.py",
        "claim_harness/evaluation.py",
        "claim_harness/eval_data/gold_claims.jsonl",
        "scripts/evaluate_gold_set.py",
        "requirements/constraints.txt",
        "$pythonFiles",
        "README.zh-CN.md",
        "docs/static_showcase/en.html",
        "docs/static_showcase/zh-CN.html",
        "py_compile",
        "pip check",
    ]:
        assert phrase in test_script
    assert "streamlit run" not in test_script
    pyproject = Path("pyproject.toml").read_text(encoding="utf-8")
    gitignore = Path(".gitignore").read_text(encoding="utf-8")
    assert '"demo_data/*.md"' in pyproject
    assert '"demo_data/tables/*.csv"' in pyproject
    assert '"eval_data/*.jsonl"' in pyproject
    assert "build/" in gitignore

    constraints = Path("requirements/constraints.txt").read_text(encoding="utf-8")
    for pinned_requirement in [
        "pip==25.0.1",
        "pydantic==2.10.6",
        "pandas==2.2.3",
        "pypdf==5.1.0",
        "typer==0.15.1",
        "click==8.1.8",
        "rich==13.9.4",
        "pytest==8.3.4",
        "build==1.2.2.post1",
        "setuptools==75.6.0",
        "wheel==0.45.1",
        "streamlit==1.41.1",
        "pytesseract==0.3.13",
        "pdf2image==1.17.0",
        "Pillow==11.0.0",
        "pydantic-core==2.27.2",
        "numpy==2.2.1",
        "packaging==24.2",
        "pyproject-hooks==1.2.0",
    ]:
        assert pinned_requirement in constraints
    assert '"click>=8.1.7,<8.2"' in pyproject

    attributes = Path(".gitattributes").read_text(encoding="utf-8")
    assert "* text=auto eol=lf" in attributes
    assert "*.ps1 text eol=lf" in attributes
    assert "*.bat text eol=lf" in attributes
    assert "*.png binary" in attributes

    guide = Path("RELEASE_PACKAGE_GUIDE.md").read_text(encoding="utf-8")
    for phrase in [
        "local web app package",
        "static showcase package",
        "docs/static_showcase/en.html",
        "docs/static_showcase/zh-CN.html",
        "README.zh-CN.md",
        "requires Python",
        "does not require Python",
        ".venv",
        ".git",
        "API keys",
        "private data",
        "real patient data",
        "confidential manuscripts",
    ]:
        assert phrase in guide

    showcase_index = Path("docs/static_showcase/index.html").read_text(encoding="utf-8")
    assert "Choose your interface" in showcase_index
    assert "English interface" in showcase_index
    assert "中文界面" in showcase_index
    assert "en.html" in showcase_index
    assert "zh-CN.html" in showcase_index
    assert "data-lang-panel" not in showcase_index
    assert "setLanguage" not in showcase_index

    showcase_en = Path("docs/static_showcase/en.html").read_text(encoding="utf-8")
    for phrase in [
        "ProblemBridge + ClaimHarness",
        "Problem alignment before AI work",
        "For non-AI users",
        "Workflow",
        "Features",
        "Run locally",
        "Synthetic examples",
        "Safety boundary",
        "ClaimHarness lab report sample",
        "zh-CN.html",
    ]:
        assert phrase in showcase_en

    showcase_zh = Path("docs/static_showcase/zh-CN.html").read_text(encoding="utf-8")
    for phrase in [
        "ProblemBridge + ClaimHarness",
        "建模前的问题对齐",
        "给非 AI 背景用户",
        "工作流",
        "功能",
        "本地运行",
        "合成样例",
        "安全边界",
        "实验报告审计样例",
        "en.html",
    ]:
        assert phrase in showcase_zh

    readme = Path("README.md").read_text(encoding="utf-8")
    assert "[English](README.md)" in readme
    assert "[简体中文](README.zh-CN.md)" in readme
    assert "README.zh-CN.md" in readme
    assert "docs/static_showcase/en.html" in readme
    assert "中文说明" not in readme
    assert "English Overview" not in readme
    assert "Downloadable local web app package" in readme
    assert "RUN_PROBLEMBRIDGE_WINDOWS.bat" in readme

    readme_zh = Path("README.zh-CN.md").read_text(encoding="utf-8")
    for phrase in [
        "[English](README.md)",
        "[简体中文](README.zh-CN.md)",
        "跨学科 AI 项目",
        "ProblemBridge 负责建模前的问题对齐",
        "ClaimHarness 负责输出后的证据审计",
        "本地运行",
        "RUN_PROBLEMBRIDGE_WINDOWS.bat",
        "不要输入真实患者数据",
        "docs/static_showcase/zh-CN.html",
    ]:
        assert phrase in readme_zh


def test_model_provider_guide_is_present():
    guide_path = Path("MODEL_PROVIDER_GUIDE.md")
    assert guide_path.is_file()
    guide = guide_path.read_text(encoding="utf-8")
    readme = Path("README.md").read_text(encoding="utf-8")

    for provider in [
        "mock",
        "openai",
        "openai-compatible",
        "deepseek",
        "groq",
        "mistral",
        "openrouter",
        "xai",
        "ollama",
        "gemini",
        "anthropic",
    ]:
        assert provider in guide
        assert provider in readme

    for env_name in [
        "DEEPSEEK_API_KEY",
        "GEMINI_API_KEY",
        "ANTHROPIC_API_KEY",
        "OPENROUTER_API_KEY",
        "OLLAMA_MODEL",
    ]:
        assert env_name in guide

    assert "advisory only" in guide
    assert "Do not send private patient data" in guide


def test_windows_launchers_are_robust_for_double_click_usage():
    bat = Path("scripts/run_problembridge_ui_windows.bat").read_text(encoding="utf-8")
    ps1 = Path("scripts/run_problembridge_ui_powershell.ps1").read_text(encoding="utf-8")
    setup = Path("scripts/setup_problembridge_windows.ps1").read_text(encoding="utf-8")
    readme = Path("README.md").read_text(encoding="utf-8")

    assert 'cd /d "%~dp0\\.."' in bat
    assert "setup_problembridge_windows.bat" in bat
    assert ".claimharness_setup_v0.4.0" in bat
    assert ".venv\\Scripts\\python.exe" in bat
    assert "http://127.0.0.1:8501" in bat
    assert "--server.headless true" in bat
    assert "pause" in bat.lower()

    assert '$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path' in ps1
    assert "setup_problembridge_windows.ps1" in ps1
    assert ".claimharness_setup_v0.4.0" in ps1
    assert ".venv\\Scripts\\python.exe" in ps1
    assert "http://127.0.0.1:8501" in ps1
    assert "--server.headless" in ps1

    assert "Get-Command py" in setup
    assert "Get-Command python" in setup
    assert "requirements\\constraints.txt" in setup
    assert '-c $constraints -e ".[dev,ui]"' in setup

    assert "If the Windows launcher does not load" in readme
    assert "Static HTML is best for viewing examples only" in readme


def _assert_immediate_native_exit_check(script_text, invocation):
    lines = script_text.splitlines()
    matching_indexes = [index for index, line in enumerate(lines) if invocation in line]

    assert len(matching_indexes) == 1, invocation
    invocation_index = matching_indexes[0]
    assert lines[invocation_index + 1].strip() == 'if ($LASTEXITCODE -ne 0) {'
    assert any("throw" in line for line in lines[invocation_index + 2 : invocation_index + 4])


def test_powershell_native_commands_check_exit_codes_immediately():
    launcher = Path("scripts/run_problembridge_ui_powershell.ps1").read_text(encoding="utf-8")
    setup = Path("scripts/setup_problembridge_windows.ps1").read_text(encoding="utf-8")
    release_test = Path("scripts/test_release_zip_powershell.ps1").read_text(encoding="utf-8")
    release_build = Path("scripts/build_release_zip_powershell.ps1").read_text(encoding="utf-8")

    for invocation in [
        "& py -3 -m venv .venv",
        "& python -m venv .venv",
        '& $venvPython -m pip install "pip==25.0.1"',
        '& $venvPython -m pip install -c $constraints -e ".[dev,ui]"',
    ]:
        _assert_immediate_native_exit_check(setup, invocation)

    for invocation in [
        "& $venvPython -m streamlit run",
    ]:
        _assert_immediate_native_exit_check(launcher, invocation)

    for invocation in [
        "& $bootstrapPython @bootstrapArgs -m py_compile $pythonFile.FullName",
        "& $bootstrapPython @bootstrapArgs -m venv $smokeVenv",
        '& $venvPython -m pip install --disable-pip-version-check -c $constraints "pip==25.0.1"',
        '& $venvPython -m pip install --disable-pip-version-check --no-build-isolation -c $constraints ".[dev,ui]"',
        "& $venvPython -m pip check",
        "& $venvPython -c $installGate $smokeVenv $repoRoot",
        "& $venvPython -c $sampleGate $packageDir.FullName",
        "& $venvPython -m claim_harness demo --out $claimOut",
        "& $venvPython -m problem_bridge demo --out $problemOut",
        '& $venvPython (Join-Path $packageDir.FullName "scripts\\evaluate_gold_set.py")',
    ]:
        _assert_immediate_native_exit_check(release_test, invocation)

    _assert_immediate_native_exit_check(
        release_build, "git status --porcelain --untracked-files=all"
    )
    _assert_immediate_native_exit_check(release_build, "git archive --format=zip")
    _assert_immediate_native_exit_check(release_build, "git rev-parse HEAD")


def _powershell_executable():
    return shutil.which("powershell") or shutil.which("pwsh")


def _write_release_zip_from_project(zip_path, *, omit=(), overrides=None):
    root = Path.cwd()
    omitted = {Path(path).as_posix() for path in omit}
    overrides = overrides or {}
    roots = [
        Path("claim_harness"),
        Path("problem_bridge"),
        Path("apps"),
        Path("examples/problem_bridge"),
        Path("docs/static_showcase"),
        Path("docs/sample_outputs"),
    ]
    individual_files = [
        Path(".gitattributes"),
        Path("README.md"),
        Path("README.zh-CN.md"),
        Path("NON_AI_USER_GUIDE.md"),
        Path("RUN_PROBLEMBRIDGE_WINDOWS.bat"),
        Path("scripts/run_problembridge_ui_windows.bat"),
        Path("scripts/setup_problembridge_windows.ps1"),
        Path("scripts/setup_problembridge_windows.bat"),
        Path("scripts/evaluate_gold_set.py"),
        Path("requirements/constraints.txt"),
        Path("docs/v0.4_upgrade.md"),
        Path("pyproject.toml"),
    ]
    files = list(individual_files)
    for source_root in roots:
        files.extend(
            path
            for path in source_root.rglob("*")
            if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc"
        )

    with zipfile.ZipFile(zip_path, "w") as archive:
        for relative_path in sorted(set(files)):
            relative = relative_path.as_posix()
            if relative in omitted:
                continue
            archive_name = f"ProblemBridge-ClaimHarness-test/{relative}"
            if relative in overrides:
                archive.writestr(archive_name, overrides[relative])
            else:
                archive.write(root / relative_path, archive_name)


def _run_release_zip_test(zip_path):
    return subprocess.run(
        [
            _powershell_executable(),
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(Path("scripts/test_release_zip_powershell.ps1").resolve()),
            "-ZipPath",
            str(zip_path),
            "-PythonExe",
            sys.executable,
        ],
        cwd=Path.cwd(),
        capture_output=True,
        text=True,
        check=False,
    )


def _skip_if_strict_release_install_is_offline(result):
    output = result.stdout + result.stderr
    if (
        result.returncode != 0
        and "Could not install constrained build tooling" in output
        and (
            "Failed to establish a new connection" in output
            or "Temporary failure in name resolution" in output
            or "No matching distribution found" in output
            or "ResolutionImpossible" in output
        )
    ):
        pytest.skip("Strict clean-venv release smoke needs package-index access.")


def _write_minimal_release_build_fixture(root: Path, *, version: str = "0.4.0") -> None:
    (root / ".gitattributes").write_text("* text=auto eol=lf\n", encoding="utf-8")
    (root / "claim_harness").mkdir(parents=True, exist_ok=True)
    (root / "problem_bridge").mkdir(parents=True, exist_ok=True)
    (root / "pyproject.toml").write_text(
        f'[project]\nname = "release-fixture"\nversion = "{version}"\n',
        encoding="utf-8",
    )
    for package in ("claim_harness", "problem_bridge"):
        (root / package / "__init__.py").write_text(
            f'__version__ = "{version}"\n', encoding="utf-8"
        )

    sample_names = [
        "claimharness_lab_report_audit_demo",
        "quality_inspection_alignment",
        "cultural_archive_alignment",
        "training_policy_alignment",
    ]
    for index, sample_name in enumerate(sample_names, start=1):
        sample = root / "docs" / "sample_outputs" / sample_name
        sample.mkdir(parents=True, exist_ok=True)
        artifact = sample / "artifact.txt"
        artifact.write_bytes(f"sample artifact {index}\n".encode("utf-8"))
        project_id = f"sample-project-{index}"
        run_id = f"run-sample-{index}"
        identity = {
            "schema_version": 2,
            "project_id": project_id,
            "run_id": run_id,
        }
        identity_path = sample / "run_identity.json"
        identity_path.write_text(json.dumps(identity), encoding="utf-8")
        completion = {
            "schema_version": 2,
            "project_id": project_id,
            "run_id": run_id,
            "run_identity_sha256": hashlib.sha256(identity_path.read_bytes()).hexdigest(),
            "artifact_sha256": {
                "artifact.txt": hashlib.sha256(artifact.read_bytes()).hexdigest()
            },
        }
        (sample / "run_complete.json").write_text(
            json.dumps(completion), encoding="utf-8"
        )


def _commit_release_build_fixture(root: Path) -> str:
    subprocess.run(["git", "init"], cwd=root, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "release-test@example.test"],
        cwd=root,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Release Test"], cwd=root, check=True
    )
    subprocess.run(["git", "add", "."], cwd=root, check=True)
    subprocess.run(
        ["git", "commit", "-m", "release fixture"],
        cwd=root,
        check=True,
        capture_output=True,
    )
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


@pytest.mark.skipif(_powershell_executable() is None, reason="PowerShell is not available")
def test_release_zip_script_runs_both_packaged_demos_from_extracted_source(tmp_path):
    zip_path = tmp_path / "valid-release.zip"
    _write_release_zip_from_project(zip_path)

    result = _run_release_zip_test(zip_path)
    _skip_if_strict_release_install_is_offline(result)

    output = result.stdout + result.stderr
    assert result.returncode == 0, output
    assert "Release zip test passed" in output


@pytest.mark.skipif(_powershell_executable() is None, reason="PowerShell is not available")
def test_release_zip_script_rejects_invalid_python_without_success_message(tmp_path):
    zip_path = tmp_path / "invalid-release.zip"
    _write_release_zip_from_project(
        zip_path,
        overrides={"apps/problem_bridge_wizard.py": "def broken(:\n"},
    )

    result = _run_release_zip_test(zip_path)

    output = result.stdout + result.stderr
    assert result.returncode != 0
    assert "Python syntax check failed for release file:" in output
    assert "problem_bridge_wizard.py" in output
    assert "Release zip test passed" not in output


@pytest.mark.skipif(_powershell_executable() is None, reason="PowerShell is not available")
def test_release_zip_script_rejects_missing_imported_module(tmp_path):
    zip_path = tmp_path / "missing-module-release.zip"
    _write_release_zip_from_project(zip_path, omit={"claim_harness/llm.py"})

    result = _run_release_zip_test(zip_path)
    _skip_if_strict_release_install_is_offline(result)

    output = result.stdout + result.stderr
    assert result.returncode != 0
    assert "ClaimHarness packaged demo failed" in output
    assert "Release zip test passed" not in output


@pytest.mark.skipif(_powershell_executable() is None, reason="PowerShell is not available")
def test_release_zip_script_rejects_missing_packaged_demo_resource(tmp_path):
    zip_path = tmp_path / "missing-resource-release.zip"
    _write_release_zip_from_project(
        zip_path,
        omit={"claim_harness/demo_data/references.md"},
    )

    result = _run_release_zip_test(zip_path)

    output = result.stdout + result.stderr
    assert result.returncode != 0
    assert "Missing required file in release zip: claim_harness/demo_data/references.md" in output
    assert "Release zip test passed" not in output


@pytest.mark.skipif(_powershell_executable() is None, reason="PowerShell is not available")
def test_release_build_script_reports_git_status_failure(tmp_path):
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir()
    copied_script = scripts_dir / "build_release_zip_powershell.ps1"
    copied_script.write_text(
        Path("scripts/build_release_zip_powershell.ps1").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    env = os.environ.copy()
    env["GIT_DIR"] = str(tmp_path / "missing.git")

    result = subprocess.run(
        [
            _powershell_executable(),
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(copied_script),
            "-Version",
            "test",
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    output = result.stdout + result.stderr
    assert result.returncode != 0
    assert "git status failed while checking release readiness" in output
    assert "Release package written" not in output


@pytest.mark.skipif(
    _powershell_executable() is None or shutil.which("git") is None,
    reason="PowerShell and Git are required",
)
def test_release_build_script_rejects_dirty_worktree(tmp_path):
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir()
    copied_script = scripts_dir / "build_release_zip_powershell.ps1"
    copied_script.write_text(
        Path("scripts/build_release_zip_powershell.ps1").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "release-test@example.test"],
        cwd=tmp_path,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Release Test"],
        cwd=tmp_path,
        check=True,
    )
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "commit", "-m", "release fixture"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    (tmp_path / "untracked-change.txt").write_text("not committed\n", encoding="utf-8")

    result = subprocess.run(
        [
            _powershell_executable(),
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(copied_script),
            "-Version",
            "test",
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )

    output = result.stdout + result.stderr
    assert result.returncode != 0
    assert "Working tree is dirty" in output
    assert "Release package written" not in output


@pytest.mark.skipif(
    _powershell_executable() is None or shutil.which("git") is None,
    reason="PowerShell and Git are required",
)
def test_release_build_writes_commit_bound_manifest_and_sha256(tmp_path):
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir()
    copied_script = scripts_dir / "build_release_zip_powershell.ps1"
    copied_script.write_text(
        Path("scripts/build_release_zip_powershell.ps1").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (tmp_path / "README.md").write_text("release fixture\n", encoding="utf-8")
    _write_minimal_release_build_fixture(tmp_path)
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "release-test@example.test"],
        cwd=tmp_path,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Release Test"],
        cwd=tmp_path,
        check=True,
    )
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "commit", "-m", "release fixture"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )

    result = subprocess.run(
        [
            _powershell_executable(),
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(copied_script),
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )

    output = result.stdout + result.stderr
    package = tmp_path / "dist" / "ProblemBridge-ClaimHarness-v0.4.0-local-webapp.zip"
    manifest_path = Path(f"{package}.manifest.json")
    sha_path = Path(f"{package}.sha256")
    assert result.returncode == 0, output
    assert package.is_file()
    assert manifest_path.is_file()
    assert sha_path.is_file()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    actual_hash = hashlib.sha256(package.read_bytes()).hexdigest()
    expected_commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert manifest["git_commit"] == expected_commit
    assert manifest["sha256"] == actual_hash
    assert manifest["version"] == "v0.4.0"
    assert manifest["project_version"] == "0.4.0"
    assert manifest["archive_root"] == "ProblemBridge-ClaimHarness-v0.4.0"
    assert manifest["archive_entry_count"] > 0
    assert manifest["archive_text_entry_count"] > 0
    assert len(manifest["sample_runs"]) == 4
    assert sha_path.read_text(encoding="ascii").startswith(actual_hash)


@pytest.mark.skipif(
    _powershell_executable() is None or shutil.which("git") is None,
    reason="PowerShell and Git are required",
)
def test_release_build_rejects_version_override_mismatch(tmp_path):
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir()
    copied_script = scripts_dir / "build_release_zip_powershell.ps1"
    copied_script.write_text(
        Path("scripts/build_release_zip_powershell.ps1").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    _write_minimal_release_build_fixture(tmp_path)
    _commit_release_build_fixture(tmp_path)

    result = subprocess.run(
        [
            _powershell_executable(),
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(copied_script),
            "-Version",
            "v9.9.9",
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )

    output = result.stdout + result.stderr
    assert result.returncode != 0
    assert "does not match project version v0.4.0" in output
    assert "Release package written" not in output


@pytest.mark.skipif(
    _powershell_executable() is None or shutil.which("git") is None,
    reason="PowerShell and Git are required",
)
def test_release_build_rejects_package_metadata_version_mismatch(tmp_path):
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir()
    copied_script = scripts_dir / "build_release_zip_powershell.ps1"
    copied_script.write_text(
        Path("scripts/build_release_zip_powershell.ps1").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    _write_minimal_release_build_fixture(tmp_path)
    (tmp_path / "problem_bridge" / "__init__.py").write_text(
        '__version__ = "0.3.9"\n', encoding="utf-8"
    )
    _commit_release_build_fixture(tmp_path)

    result = subprocess.run(
        [
            _powershell_executable(),
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(copied_script),
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )

    output = result.stdout + result.stderr
    assert result.returncode != 0
    assert "Release version mismatch" in output
    assert "problem_bridge=0.3.9" in output
    assert "Release package written" not in output


@pytest.mark.skipif(
    _powershell_executable() is None or shutil.which("git") is None,
    reason="PowerShell and Git are required",
)
def test_release_build_rejects_corrupt_sample_provenance(tmp_path):
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir()
    copied_script = scripts_dir / "build_release_zip_powershell.ps1"
    copied_script.write_text(
        Path("scripts/build_release_zip_powershell.ps1").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    _write_minimal_release_build_fixture(tmp_path)
    corrupt_artifact = (
        tmp_path
        / "docs"
        / "sample_outputs"
        / "quality_inspection_alignment"
        / "artifact.txt"
    )
    corrupt_artifact.write_text("content changed after completion\n", encoding="utf-8")
    _commit_release_build_fixture(tmp_path)

    result = subprocess.run(
        [
            _powershell_executable(),
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(copied_script),
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )

    output = result.stdout + result.stderr
    assert result.returncode != 0
    assert "Sample completion SHA-256 mismatch" in output
    assert "Release package written" not in output
    assert not (tmp_path / "dist" / "ProblemBridge-ClaimHarness-v0.4.0-local-webapp.zip").exists()


@pytest.mark.skipif(
    _powershell_executable() is None or shutil.which("git") is None,
    reason="PowerShell and Git are required",
)
def test_release_build_rejects_non_lf_release_text(tmp_path):
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir()
    copied_script = scripts_dir / "build_release_zip_powershell.ps1"
    copied_script.write_text(
        Path("scripts/build_release_zip_powershell.ps1").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    _write_minimal_release_build_fixture(tmp_path)
    (tmp_path / ".gitattributes").write_bytes(b"* text=auto eol=lf\r\nbad.txt -text\r\n")
    (tmp_path / "bad.txt").write_bytes(b"not normalized\r\n")
    _commit_release_build_fixture(tmp_path)

    result = subprocess.run(
        [
            _powershell_executable(),
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(copied_script),
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )

    output = result.stdout + result.stderr
    assert result.returncode != 0
    assert "Release archive text is not LF-normalized: bad.txt" in output
    assert "Release package written" not in output
    assert not (tmp_path / "dist" / "ProblemBridge-ClaimHarness-v0.4.0-local-webapp.zip").exists()
