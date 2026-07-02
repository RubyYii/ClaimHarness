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
        "agent_trace.jsonl",
        "index.html",
    ]
    sample_dir = Path("docs/sample_outputs/claimharness_lab_report_audit_demo")
    for filename in claimharness_required:
        assert (sample_dir / filename).is_file(), sample_dir / filename


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
        "workflow-strip",
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
        "API 设置",
        "ProblemBridge 工作台",
        "模型服务",
        "服务地址",
        "使用服务商默认配置",
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
        "language-switcher",
        "st.query_params",
        "def _sync_language_from_query_params",
        "def _set_language_choice",
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

def test_guided_ui_has_local_memory_and_api_settings():
    ui_text = Path("apps/problem_bridge_wizard.py").read_text(encoding="utf-8")
    provider_guide = Path("MODEL_PROVIDER_GUIDE.md").read_text(encoding="utf-8")

    for phrase in [
        "Show workspace memory",
        "Show API settings",
        "Save current workspace",
        "Clear memory",
        "API key is session-only",
        "workbench_memory.json",
        "qwen",
        "Privacy check before sharing",
        "Clear local memory before sharing",
        "Use provider defaults",
        "on_change=_sync_provider_defaults",
        "on_click=_sync_provider_defaults",
        "def _sync_provider_defaults",
        "api_model_mode",
        "model_mode",
        "MODEL_OPTIONS_BY_PROVIDER",
        "Model selection mode",
        "Use common model list",
        "Manual input",
        "Common model",
        "Custom model name",
    ]:
        assert phrase in ui_text

    import apps.problem_bridge_wizard as ui

    assert ui._model_options_for_provider("qwen")[0] == "qwen-plus"
    assert "qwen-max" in ui._model_options_for_provider("qwen")
    assert ui._model_options_for_provider("deepseek")[0] == "deepseek-v4-flash"
    assert "deepseek-chat" in ui._model_options_for_provider("deepseek")
    assert ui._model_mode_label(ui.MODEL_MODE_COMMON) == "Use common model list"
    assert ui._model_mode_label(ui.MODEL_MODE_MANUAL) == "Manual input"

    assert "DASHSCOPE_API_KEY" in provider_guide
    assert "QWEN_MODEL" in provider_guide
    assert "Use provider defaults" in Path("README.md").read_text(encoding="utf-8")
    assert "Clear local memory before sharing" in Path("README.md").read_text(encoding="utf-8")


def test_guided_ui_keeps_sidebar_advanced_settings_collapsed():
    ui_text = Path("apps/problem_bridge_wizard.py").read_text(encoding="utf-8")

    for phrase in [
        "st.sidebar.checkbox(_text(\"Show workspace memory\", \"显示工作台记忆\"), value=False",
        "st.sidebar.checkbox(_text(\"Show API settings\", \"显示 API 设置\"), value=False",
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
    ui_text = Path("apps/problem_bridge_wizard.py").read_text(encoding="utf-8")

    assert "review workflow" in seed["domain_draft_additional_notes"]
    assert "question discovery" in seed["domain_draft_repeated_work"]
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
    assert "ai_task_spec.yaml" in seed["ai_draft_candidate_task"]
    assert "evidence_contract.yaml" in seed["ai_draft_high_risk_mistakes"]
    assert "Continue to AI practitioner wizard" in ui_text
    assert "_continue_to_ai_wizard_from_alignment" in ui_text
    assert "last_alignment_package_dir" in ui_text


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
        "pip install -e \".[ui,ocr]\"",
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
    required_files = [
        Path("RUN_PROBLEMBRIDGE_WINDOWS.bat"),
        Path("scripts/build_release_zip_powershell.ps1"),
        Path("scripts/test_release_zip_powershell.ps1"),
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
    assert "ProblemBridge-ClaimHarness-v0.3.2-local-webapp.zip" in build_script
    assert "git archive" in build_script
    assert "dist" in build_script

    test_script = Path("scripts/test_release_zip_powershell.ps1").read_text(encoding="utf-8")
    for phrase in [
        "RUN_PROBLEMBRIDGE_WINDOWS.bat",
        "apps/problem_bridge_wizard.py",
        "problem_bridge/document_intake.py",
        "$intakePath",
        "README.zh-CN.md",
        "docs/static_showcase/en.html",
        "docs/static_showcase/zh-CN.html",
        "py_compile",
    ]:
        assert phrase in test_script
    assert "streamlit run" not in test_script

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
    readme = Path("README.md").read_text(encoding="utf-8")

    assert 'cd /d "%~dp0\\.."' in bat
    assert "where py" in bat
    assert "where python" in bat
    assert ".venv\\Scripts\\python.exe" in bat
    assert "http://127.0.0.1:8501" in bat
    assert "--server.headless true" in bat
    assert "pause" in bat.lower()

    assert '$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path' in ps1
    assert "Get-Command py" in ps1
    assert "Get-Command python" in ps1
    assert ".venv\\Scripts\\python.exe" in ps1
    assert "http://127.0.0.1:8501" in ps1
    assert "--server.headless" in ps1

    assert "If the Windows launcher does not load" in readme
    assert "Static HTML is best for viewing examples only" in readme
