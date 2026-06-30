from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path

import streamlit as st

from claim_harness.llm import PROVIDER_PRESETS
from problem_bridge.generator import build_alignment_package
from problem_bridge.guided import (
    FRIENDLY_FILE_LABELS,
    build_ai_practitioner_problem,
    build_workflow_first_problem,
    discover_alignment_outputs,
    friendly_summary,
)
from problem_bridge.document_intake import (
    build_problem_seed_from_intake,
    extract_document,
    write_intake_package,
)
from problem_bridge.interview import (
    answer_question,
    build_problem_from_interview,
    is_ready_for_alignment,
    start_interview,
    summarize_understanding,
)
from problem_bridge.question_discovery import (
    build_problem_from_discovery,
    discover_questions,
    write_question_discovery_package,
)
from problem_bridge.ui_memory import (
    DEFAULT_MEMORY_PATH,
    clear_workbench_memory,
    load_workbench_memory,
    save_workbench_memory,
)
from problem_bridge.writer import write_alignment_package


EXAMPLES = {
    "HSG": Path("examples/problem_bridge/hsg/problem.md"),
    "Chinese painting / VULCA": Path("examples/problem_bridge/chinese_painting/problem.md"),
    "Political education risk": Path("examples/problem_bridge/political_education/problem.md"),
}

RUN_ROOT = Path("outputs/ui_runs")
MEMORY_PATH = DEFAULT_MEMORY_PATH

PAGE_OPTIONS = [
    "Home",
    "Explore examples",
    "Document intake",
    "Question discovery",
    "Domain practitioner wizard",
    "AI practitioner wizard",
    "View generated outputs",
]

WORKFLOW_STEPS = [
    ("01", "Document intake", "Turn local files into auditable text and tables."),
    ("02", "Question discovery", "Find what to ask and who should answer."),
    ("03", "Guided interview", "Reconstruct work, materials, pain points, and boundaries."),
    ("04", "ProblemBridge", "Generate task specs, evidence contracts, and evaluation plans."),
    ("05", "ClaimHarness", "Audit claims after outputs or manuscripts exist."),
]

ACTIVE_WORKFLOW_BY_PAGE = {
    "Document intake": "Document intake",
    "Question discovery": "Question discovery",
    "Domain practitioner wizard": "Guided interview",
    "AI practitioner wizard": "ProblemBridge",
    "Explore examples": "ProblemBridge",
    "View generated outputs": "ProblemBridge",
}

MODULE_CARDS = [
    {
        "title": "Document intake",
        "stage": "File preparation",
        "start_if": "You have Word, text-based PDF, Markdown, TXT, or CSV files.",
        "what_you_get": "extracted_text.md, extracted_tables, source_manifest.json, warnings.",
    },
    {
        "title": "Question discovery",
        "stage": "Before problem framing",
        "start_if": "You know something is unclear, but do not know what to ask.",
        "what_you_get": "question brief, stakeholder map, interview guide, unknowns list.",
    },
    {
        "title": "Domain practitioner wizard",
        "stage": "Workflow understanding",
        "start_if": "You can describe daily work, materials, pain points, and review boundaries.",
        "what_you_get": "workflow-first ProblemBridge alignment package.",
    },
    {
        "title": "AI practitioner wizard",
        "stage": "Task sanity check",
        "start_if": "You already have a candidate AI task and need to check drift.",
        "what_you_get": "misalignment risks, task spec, evidence contract, evaluation protocol.",
    },
]

QUESTION_DISCOVERY_FILES = {
    "question_brief.md": "Question brief",
    "stakeholder_map.md": "Who to ask",
    "expert_interview_guide.md": "Expert interview guide",
    "unknowns_to_validate.md": "Unknowns to validate",
    "discussion_plan.md": "Discussion plan",
    "problem_seed.md": "ProblemBridge seed brief",
}

DOCUMENT_INTAKE_FILES = {
    "extracted_text.md": "Extracted text",
    "source_manifest.json": "Source manifest",
    "extraction_warnings.md": "Extraction warnings",
    "problem_seed.md": "ProblemBridge seed brief",
}

API_PROVIDER_OPTIONS = [
    "mock",
    "qwen",
    "deepseek",
    "openai",
    "openai-compatible",
    "openrouter",
    "groq",
    "mistral",
    "xai",
    "gemini",
    "anthropic",
    "ollama",
]

DRAFT_KEY_GROUPS = {
    "question_discovery": [
        "question_seed_text",
        "question_uncertainty",
        "question_desired_change",
    ],
    "domain": [
        "domain_draft_domain",
        "domain_draft_repeated_work",
        "domain_draft_current_owner",
        "domain_draft_result",
        "domain_draft_step_1",
        "domain_draft_step_2",
        "domain_draft_step_3",
        "domain_draft_step_4",
        "domain_draft_additional_notes",
        "domain_draft_time_consuming_step",
        "domain_draft_annoying_step",
        "domain_draft_error_prone_step",
        "domain_draft_expert_judgement_step",
        "domain_draft_materials",
        "domain_draft_critical_materials",
        "domain_draft_missing_materials",
        "domain_draft_never_automated",
        "domain_draft_human_confirmed",
        "domain_draft_serious_mistakes",
        "domain_draft_useful_support",
    ],
    "ai": [
        "ai_draft_domain_problem",
        "ai_draft_candidate_task",
        "ai_draft_inputs",
        "ai_draft_outputs",
        "ai_draft_metric",
        "ai_draft_user",
        "ai_draft_high_risk_mistakes",
    ],
}


def main() -> None:
    st.set_page_config(page_title="ProblemBridge Workbench", layout="wide")
    _inject_visual_theme()
    _render_shell_header()
    _safety_banner()

    st.sidebar.markdown("### Workspace")
    page = st.sidebar.radio(
        "Choose an entry",
        PAGE_OPTIONS,
    )
    st.sidebar.markdown(
        """
        <div class="sidebar-note">
        Local-first mode. Use synthetic or non-sensitive material for first testing.
        </div>
        """,
        unsafe_allow_html=True,
    )
    _render_memory_sidebar()
    _render_workflow_strip(page)

    if page == "Home":
        _home()
    elif page == "Explore examples":
        _examples()
    elif page == "Question discovery":
        _question_discovery()
    elif page == "Document intake":
        _document_intake()
    elif page == "Domain practitioner wizard":
        _domain_wizard()
    elif page == "AI practitioner wizard":
        _ai_wizard()
    else:
        _view_outputs()


def _render_memory_sidebar() -> None:
    _ensure_memory_state()

    st.sidebar.divider()
    st.sidebar.markdown("### Workspace Memory")
    st.sidebar.caption(
        f"Saved locally to `{MEMORY_PATH}` / `workbench_memory.json`. "
        "API key is session-only and is never written to memory."
    )

    last_output = st.session_state.get("last_output_dir")
    if last_output:
        st.sidebar.caption(f"Last output: `{last_output}`")

    st.sidebar.markdown("### API Settings")
    st.sidebar.selectbox("Provider", API_PROVIDER_OPTIONS, key="api_provider")
    provider = st.session_state.get("api_provider", "mock")
    preset = PROVIDER_PRESETS.get(provider)

    st.sidebar.text_input("Base URL", key="api_base_url")
    st.sidebar.text_input("Model", key="api_model")
    api_key = st.sidebar.text_input("API key is session-only", type="password", key="api_key_session")

    if preset and preset.api_key_env:
        st.sidebar.caption(
            f"Key env for this provider: `{preset.api_key_env}`. "
            "Provider, base URL, and model can be remembered; the key is not saved."
        )
    else:
        st.sidebar.caption("This provider does not require an API key for local testing.")

    if st.sidebar.button("Use API key this session", disabled=not bool(api_key) or not preset or not preset.api_key_env):
        os.environ[preset.api_key_env] = api_key
        st.sidebar.success(f"Applied `{preset.api_key_env}` for this session only.")

    col1, col2 = st.sidebar.columns(2)
    with col1:
        if st.button("Load saved memory", key="memory_load"):
            st.session_state.pending_workbench_memory = load_workbench_memory(MEMORY_PATH)
            st.session_state.pending_workbench_memory_clear = True
            st.rerun()
        if st.button("Save current workspace", key="memory_save"):
            payload = _current_workbench_memory()
            save_workbench_memory(payload, MEMORY_PATH)
            st.session_state.workbench_memory = payload
            st.sidebar.success("Workspace memory saved locally.")
    with col2:
        if st.button("Clear memory", key="memory_clear"):
            clear_workbench_memory(MEMORY_PATH)
            st.session_state.pending_workbench_memory = {}
            st.session_state.pending_workbench_memory_clear = True
            st.rerun()


def _ensure_memory_state() -> None:
    if "pending_workbench_memory" in st.session_state:
        memory = st.session_state.pop("pending_workbench_memory")
        clear_existing = bool(st.session_state.pop("pending_workbench_memory_clear", False))
        _apply_memory_to_session(memory, clear_existing=clear_existing)
        st.session_state.workbench_memory = memory
        return

    if "workbench_memory" not in st.session_state:
        memory = load_workbench_memory(MEMORY_PATH)
        _apply_memory_to_session(memory, clear_existing=False)
        st.session_state.workbench_memory = memory


def _apply_memory_to_session(memory: dict, clear_existing: bool) -> None:
    keys = ["api_provider", "api_base_url", "api_model", "api_key_session", "last_output_dir"]
    for field_keys in DRAFT_KEY_GROUPS.values():
        keys.extend(field_keys)

    if clear_existing:
        for key in keys:
            st.session_state.pop(key, None)

    api_settings = memory.get("api_settings", {}) if isinstance(memory, dict) else {}
    provider = api_settings.get("provider") or "mock"
    if provider not in API_PROVIDER_OPTIONS:
        provider = "mock"

    defaults = _provider_defaults(provider)
    st.session_state.setdefault("api_provider", provider)
    st.session_state.setdefault("api_base_url", api_settings.get("base_url") or defaults["base_url"])
    st.session_state.setdefault("api_model", api_settings.get("model") or defaults["model"])

    drafts = memory.get("drafts", {}) if isinstance(memory, dict) else {}
    if isinstance(drafts, dict):
        for group, field_keys in DRAFT_KEY_GROUPS.items():
            group_values = drafts.get(group, {})
            if not isinstance(group_values, dict):
                continue
            for key in field_keys:
                if key in group_values:
                    st.session_state.setdefault(key, group_values[key])

    if isinstance(memory, dict) and memory.get("last_output_dir"):
        st.session_state.setdefault("last_output_dir", memory["last_output_dir"])


def _current_workbench_memory() -> dict:
    provider = st.session_state.get("api_provider", "mock")
    return {
        "schema_version": 1,
        "api_settings": {
            "provider": provider,
            "base_url": st.session_state.get("api_base_url", ""),
            "model": st.session_state.get("api_model", ""),
        },
        "drafts": _drafts_from_session(),
        "last_output_dir": st.session_state.get("last_output_dir", ""),
    }


def _drafts_from_session() -> dict:
    drafts = {}
    for group, field_keys in DRAFT_KEY_GROUPS.items():
        values = {}
        for key in field_keys:
            value = st.session_state.get(key)
            if value not in (None, "", []):
                values[key] = value
        if values:
            drafts[group] = values
    return drafts


def _provider_defaults(provider: str) -> dict[str, str]:
    preset = PROVIDER_PRESETS.get(provider)
    if not preset:
        return {"base_url": "", "model": ""}
    return {
        "base_url": preset.default_base_url or "",
        "model": preset.default_model or "",
    }

def _inject_visual_theme() -> None:
    st.markdown(
        """
        <style>
        :root {
          --pb-ink: #17202a;
          --pb-muted: #5b6978;
          --pb-line: #d9e2ea;
          --pb-paper: #ffffff;
          --pb-canvas: #f6f8fb;
          --pb-teal: #0f766e;
          --pb-blue: #1d4ed8;
          --pb-coral: #b45309;
          --pb-soft-teal: #eaf7f5;
          --pb-soft-blue: #edf4ff;
          --pb-soft-amber: #fff7ed;
        }
        .stApp { background: var(--pb-canvas); color: var(--pb-ink); }
        [data-testid="stSidebar"] { background: #ffffff; border-right: 1px solid var(--pb-line); }
        .block-container { padding-top: 1.6rem; max-width: 1180px; }
        .visual-shell {
          padding: 26px 28px;
          border: 1px solid var(--pb-line);
          border-radius: 8px;
          background: var(--pb-paper);
          box-shadow: 0 18px 45px rgba(23, 32, 42, .08);
          margin-bottom: 18px;
        }
        .visual-eyebrow {
          color: var(--pb-teal);
          font-size: 12px;
          line-height: 1;
          font-weight: 800;
          text-transform: uppercase;
          letter-spacing: .08em;
          margin-bottom: 10px;
        }
        .visual-title {
          font-size: clamp(30px, 5vw, 54px);
          line-height: 1.04;
          font-weight: 850;
          letter-spacing: 0;
          margin: 0;
        }
        .visual-lead { max-width: 830px; color: var(--pb-muted); font-size: 18px; margin-top: 14px; }
        .metric-row { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 18px; }
        .metric-pill {
          padding: 8px 11px;
          border: 1px solid var(--pb-line);
          border-radius: 8px;
          background: #fbfdff;
          color: var(--pb-ink);
          font-weight: 750;
          font-size: 13px;
        }
        .workflow-strip {
          display: grid;
          grid-template-columns: repeat(5, minmax(0, 1fr));
          gap: 10px;
          margin: 12px 0 22px;
        }
        .workflow-step {
          min-height: 112px;
          padding: 14px;
          border: 1px solid var(--pb-line);
          border-radius: 8px;
          background: #ffffff;
        }
        .workflow-step.is-active {
          border-color: var(--pb-teal);
          background: linear-gradient(180deg, #ffffff 0%, var(--pb-soft-teal) 100%);
          box-shadow: inset 0 0 0 1px rgba(15, 118, 110, .22);
        }
        .workflow-step strong { display: block; margin: 6px 0 4px; color: var(--pb-ink); }
        .workflow-step p { margin: 0; color: var(--pb-muted); font-size: 13px; line-height: 1.45; }
        .step-num {
          display: inline-flex;
          min-width: 34px;
          height: 24px;
          align-items: center;
          justify-content: center;
          border-radius: 8px;
          background: var(--pb-soft-blue);
          color: var(--pb-blue);
          font-weight: 850;
          font-size: 12px;
        }
        .page-intro, .module-card, .trust-card {
          border: 1px solid var(--pb-line);
          border-radius: 8px;
          background: var(--pb-paper);
          padding: 18px;
          margin-bottom: 14px;
        }
        .module-card { min-height: 230px; }
        .module-card h3 { margin: 4px 0 10px; font-size: 20px; }
        .module-card p, .page-intro p, .trust-card p { color: var(--pb-muted); margin: 8px 0 0; }
        .module-stage {
          display: inline-flex;
          padding: 4px 8px;
          border-radius: 8px;
          background: var(--pb-soft-teal);
          color: var(--pb-teal);
          font-size: 12px;
          font-weight: 800;
        }
        .field-label { margin-top: 12px; font-weight: 850; color: var(--pb-ink); }
        .trust-card { border-left: 5px solid var(--pb-coral); background: var(--pb-soft-amber); }
        .sidebar-note {
          margin-top: 14px;
          padding: 12px;
          border: 1px solid var(--pb-line);
          border-radius: 8px;
          color: var(--pb-muted);
          background: #fbfdff;
          font-size: 13px;
          line-height: 1.45;
        }
        div.stButton > button, div.stDownloadButton > button {
          border-radius: 8px;
          border: 1px solid var(--pb-teal);
          background: var(--pb-teal);
          color: white;
          font-weight: 800;
        }
        textarea, input { border-radius: 8px !important; }
        @media (max-width: 900px) {
          .workflow-strip { grid-template-columns: 1fr; }
          .visual-shell { padding: 22px 18px; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _render_shell_header() -> None:
    st.markdown(
        """
        <section class="visual-shell">
          <div class="visual-eyebrow">Local interdisciplinary AI harness</div>
          <h1 class="visual-title">ProblemBridge Workbench</h1>
          <p class="visual-lead">
            A guided workspace for turning messy domain materials into questions,
            workflow understanding, AI task specs, and later claim-evidence audits.
          </p>
          <div class="metric-row">
            <span class="metric-pill">No API required by default</span>
            <span class="metric-pill">Local file intake</span>
            <span class="metric-pill">Question-first workflow</span>
            <span class="metric-pill">Traceable outputs</span>
          </div>
        </section>
        """,
        unsafe_allow_html=True,
    )


def _render_workflow_strip(active_page: str) -> None:
    active_step = ACTIVE_WORKFLOW_BY_PAGE.get(active_page)
    st.markdown('<div class="workflow-strip"></div>', unsafe_allow_html=True)
    columns = st.columns(len(WORKFLOW_STEPS))
    for column, (number, title, description) in zip(columns, WORKFLOW_STEPS):
        css_class = "workflow-step is-active" if title == active_step else "workflow-step"
        with column:
            st.markdown(
                f"""
                <article class="{css_class}">
                  <span class="step-num">{number}</span>
                  <strong>{title}</strong>
                  <p>{description}</p>
                </article>
                """,
                unsafe_allow_html=True,
            )


def _render_page_intro(title: str, body: str, trust: str, outputs: list[str]) -> None:
    output_items = "".join(f"<li>{item}</li>" for item in outputs)
    st.markdown(
        f"""
        <section class="page-intro">
          <div class="visual-eyebrow">Workbench step</div>
          <h2>{title}</h2>
          <p>{body}</p>
          <div class="field-label">What you get</div>
          <ul>{output_items}</ul>
        </section>
        <section class="trust-card">
          <strong>Trust boundary</strong>
          <p>{trust}</p>
        </section>
        """,
        unsafe_allow_html=True,
    )


def _render_module_cards() -> None:
    columns = st.columns(2)
    for index, card in enumerate(MODULE_CARDS):
        with columns[index % 2]:
            st.markdown(
                f"""
                <article class="module-card">
                  <span class="module-stage">{card['stage']}</span>
                  <h3>{card['title']}</h3>
                  <div class="field-label">Start here if</div>
                  <p>{card['start_if']}</p>
                  <div class="field-label">What you get</div>
                  <p>{card['what_you_get']}</p>
                </article>
                """,
                unsafe_allow_html=True,
            )

def _safety_banner() -> None:
    st.warning(
        "Start with synthetic examples. Do not upload private patient data, "
        "confidential manuscripts, API keys, or sensitive unpublished materials."
    )


def _home() -> None:
    _render_page_intro(
        "Choose the right starting point",
        "You do not need to know AI. Start from the material or uncertainty you actually have, then move through the workflow one step at a time.",
        "The workbench is a framing and audit aid. It does not replace domain experts, supervisors, clinicians, teachers, or reviewers.",
        [
            "A clear entry point for documents, vague questions, workflows, or candidate AI tasks.",
            "A visible workflow from intake to question discovery, problem alignment, and claim audit.",
            "Downloadable local packages that can be reviewed before sharing.",
        ],
    )
    _render_module_cards()

    st.subheader("Recommended routes")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("""
        <section class="page-intro">
        <strong>Have files?</strong>
        <p>Start with Document intake, inspect extracted text and warnings, then continue to Question discovery.</p>
        </section>
        """, unsafe_allow_html=True)
    with col2:
        st.markdown("""
        <section class="page-intro">
        <strong>Have a vague concern?</strong>
        <p>Start with Question discovery to identify what to ask and which experts to involve.</p>
        </section>
        """, unsafe_allow_html=True)
    with col3:
        st.markdown("""
        <section class="page-intro">
        <strong>Know the workflow?</strong>
        <p>Go to Domain practitioner wizard and generate a ProblemBridge alignment package.</p>
        </section>
        """, unsafe_allow_html=True)

def _examples() -> None:
    _render_page_intro(
        "Explore synthetic examples",
        "Generate a complete sample package before testing your own material, so reviewers can see the expected outputs first.",
        "Examples are synthetic and are for demonstration only. Do not infer deployment claims from them.",
        ["Friendly summary", "ProblemBridge technical files", "Downloadable example package"],
    )
    choice = st.selectbox("Choose a synthetic example", list(EXAMPLES))
    problem_path = EXAMPLES[choice]
    st.text_area("Example problem brief", problem_path.read_text(encoding="utf-8"), height=220)

    if st.button("Generate this example package"):
        out = _run_problem_text(problem_path.read_text(encoding="utf-8"), f"example_{_slug(choice)}")
        st.success(f"已生成：{out}")
        _render_friendly_output(out)


def _question_discovery() -> None:
    _render_page_intro(
        "Question discovery",
        "Use this when you do not yet know what to ask, who to ask, or whether the issue is an AI task.",
        "Do not propose a solution yet. First discover what to ask and who to ask.",
        ["question_brief.md", "stakeholder_map.md", "expert_interview_guide.md", "unknowns_to_validate.md", "discussion_plan.md"],
    )

    with st.form("question_discovery"):
        seed_text = st.text_area(
            "What are you trying to understand?",
            placeholder="Example: Our review process is slow, but I do not know which part is the real problem.",
            height=120,
            key="question_seed_text",
        )
        uncertainty = st.text_area(
            "What feels unclear right now?",
            placeholder="Example: I do not know whether to ask the practitioner, supervisor, data owner, or AI engineer first.",
            height=90,
            key="question_uncertainty",
        )
        desired_change = st.text_area(
            "What would a useful first conversation achieve?",
            placeholder="Example: Leave with better questions, a short list of experts to interview, and unknowns to validate.",
            height=90,
            key="question_desired_change",
        )
        submitted = st.form_submit_button("Generate question discovery package")

    if submitted:
        package = discover_questions(seed_text, uncertainty, desired_change)
        out = _run_question_discovery(package)
        st.success(f"Generated: {out}")
        _render_question_discovery_output(out)


def _render_question_discovery_output(out: Path) -> None:
    st.subheader("Questions to validate")
    brief_path = out / "question_brief.md"
    if brief_path.is_file():
        st.markdown(brief_path.read_text(encoding="utf-8"))

    st.subheader("Who to ask")
    stakeholder_path = out / "stakeholder_map.md"
    if stakeholder_path.is_file():
        st.markdown(stakeholder_path.read_text(encoding="utf-8"))

    st.subheader("Next step")
    st.write(
        "Take this package to domain experts first. After the questions are validated, "
        "use Domain practitioner wizard to generate a ProblemBridge alignment package."
    )

    archive = _make_archive(out)
    st.download_button(
        "Download package: question discovery",
        archive.read_bytes(),
        file_name=f"{out.name}.zip",
        mime="application/zip",
    )

    with st.expander("All discovery files"):
        for filename, label in QUESTION_DISCOVERY_FILES.items():
            path = out / filename
            if path.is_file():
                st.markdown(f"### {label}")
                st.caption(filename)
                st.code(path.read_text(encoding="utf-8"), language="markdown")

def _document_intake() -> None:
    _render_page_intro(
        "Document intake",
        "Upload Word, PDF, Markdown, TXT, or CSV files and convert them into local extraction outputs.",
        "Supports .docx, .md, .txt, .csv, and text-based PDF. Scanned PDF, OCR, images, and figure understanding are not supported.",
        ["extracted_text.md", "extracted_tables/", "source_manifest.json", "extraction_warnings.md", "problem_seed.md"],
    )

    uploaded_files = st.file_uploader(
        "Upload Word, PDF, Markdown, TXT, or CSV files",
        type=["docx", "pdf", "md", "txt", "csv"],
        accept_multiple_files=True,
    )

    if st.button("Generate document intake package", disabled=not uploaded_files):
        out = _run_document_intake(uploaded_files)
        st.success(f"Generated: {out}")
        _render_document_intake_output(out)


def _render_document_intake_output(out: Path) -> None:
    st.subheader("extracted_text.md")
    extracted_text = out / "extracted_text.md"
    if extracted_text.is_file():
        st.markdown(extracted_text.read_text(encoding="utf-8"))

    st.subheader("source_manifest.json")
    manifest = out / "source_manifest.json"
    if manifest.is_file():
        st.code(manifest.read_text(encoding="utf-8"), language="json")

    warnings_path = out / "extraction_warnings.md"
    if warnings_path.is_file():
        st.subheader("extraction_warnings.md")
        st.markdown(warnings_path.read_text(encoding="utf-8"))

    archive = _make_archive(out)
    st.download_button(
        "Download package: document intake",
        archive.read_bytes(),
        file_name=f"{out.name}.zip",
        mime="application/zip",
    )

    with st.expander("All intake files"):
        for filename, label in DOCUMENT_INTAKE_FILES.items():
            path = out / filename
            if path.is_file():
                st.markdown(f"### {label}")
                st.caption(filename)
                st.code(path.read_text(encoding="utf-8"), language=_language_for(filename))
        table_dir = out / "extracted_tables"
        if table_dir.is_dir():
            for table_path in sorted(table_dir.glob("*.csv")):
                st.markdown(f"### Extracted table: {table_path.name}")
                st.code(table_path.read_text(encoding="utf-8"), language="csv")


def _domain_wizard() -> None:
    _render_page_intro(
        "Domain practitioner wizard",
        "Describe your workflow, not an AI task. You do not need to know AI. Start by describing a repeated task in your work. The guided interview asks one question at a time; the advanced form is for users who already know the workflow details.",
        "This page captures workflow understanding. It does not decide what should be automated or replace professional judgement.",
        ["Guided interview state", "Workflow-first problem brief", "ProblemBridge alignment package", "Download package"],
    )

    with st.expander("Interview mode"):
        st.write("Use this mode when you are helping someone else describe their workflow.")
        st.markdown(
            """
            - Do not ask for an AI task first.
            - Ask what people repeatedly inspect, decide, organize, or write.
            - Ask what materials they use when making the judgement.
            - Ask which step is slow, ambiguous, error-prone, or expert-dependent.
            - Ask what must stay under human confirmation.
            """
        )

    _guided_interview()
    st.divider()
    st.subheader("Advanced: full workflow form")
    st.caption("Use this manual form when you already know the workflow details.")

    with st.form("domain_practitioner"):
        st.subheader("Section A: repeated work")
        answers = {
            "domain": st.text_input("What field or setting is this in?", key="domain_draft_domain"),
            "repeated_work": st.text_area("What is one task people repeatedly do?", key="domain_draft_repeated_work"),
            "current_owner": st.text_input("Who currently does this task?", key="domain_draft_current_owner"),
            "result": st.text_input("What result does the task produce?", key="domain_draft_result"),
        }
        st.caption("Examples: review images, organize lab notes, inspect reports, grade work, summarize cases, prepare expert questions.")

        st.subheader("Section B: workflow steps")
        answers.update(
            {
                "step_1": st.text_input("Step 1", key="domain_draft_step_1"),
                "step_2": st.text_input("Step 2", key="domain_draft_step_2"),
                "step_3": st.text_input("Step 3", key="domain_draft_step_3"),
                "step_4": st.text_input("Step 4", key="domain_draft_step_4"),
                "additional_notes": st.text_area("Additional notes", key="domain_draft_additional_notes"),
            }
        )

        st.subheader("Section C: friction and judgement")
        answers.update(
            {
                "time_consuming_step": st.text_area("Which step is most time-consuming?", key="domain_draft_time_consuming_step"),
                "annoying_step": st.text_area("Which step is most annoying or repetitive?", key="domain_draft_annoying_step"),
                "error_prone_step": st.text_area("Which step is most error-prone?", key="domain_draft_error_prone_step"),
                "expert_judgement_step": st.text_area("Which step depends most on expert judgement?", key="domain_draft_expert_judgement_step"),
            }
        )

        st.subheader("Section D: judgement materials")
        answers.update(
            {
                "materials": st.multiselect(
                    "What materials do people use?",
                    [
                        "tables",
                        "images",
                        "reports",
                        "text records",
                        "experiment logs",
                        "historical cases",
                        "expert judgement",
                        "rules/guidelines",
                        "other",
                    ],
                    key="domain_draft_materials",
                ),
                "critical_materials": st.text_area("Which materials are most critical?", key="domain_draft_critical_materials"),
                "missing_materials": st.text_area("Which materials are often missing, unclear, or hard to organize?", key="domain_draft_missing_materials"),
            }
        )

        st.subheader("Section E: human boundaries")
        answers.update(
            {
                "never_automated": st.text_area("What should AI never decide automatically?", key="domain_draft_never_automated"),
                "human_confirmed": st.text_area("What must be confirmed by a human?", key="domain_draft_human_confirmed"),
                "serious_mistakes": st.text_area("What mistakes would be serious?", key="domain_draft_serious_mistakes"),
                "useful_support": st.multiselect(
                    "If AI only supported the work, what output would be useful?",
                    [
                        "organized summary",
                        "risk flags",
                        "evidence list",
                        "draft notes",
                        "questions for human review",
                        "workflow improvement suggestions",
                        "project brief for AI engineers",
                    ],
                    key="domain_draft_useful_support",
                ),
            }
        )
        submitted = st.form_submit_button("Generate workflow alignment package")

    if submitted:
        problem_text = build_workflow_first_problem(answers)
        out = _run_problem_text(problem_text, "domain_practitioner")
        st.success(f"Generated: {out}")
        st.download_button("Download problem.md", problem_text, file_name="problem.md")
        _render_friendly_output(out)

def _guided_interview() -> None:
    st.subheader("Guided interview")
    st.caption(
        "ProblemBridge asks one question at a time, tracks what it understands, "
        "and routes the next question based on missing information."
    )

    if "problem_bridge_interview_state" not in st.session_state:
        st.session_state.problem_bridge_interview_state = start_interview()

    state = st.session_state.problem_bridge_interview_state
    summary = summarize_understanding(state)
    question = summary.next_question

    left, right = st.columns([1.35, 1])
    with left:
        st.markdown("### Next question")
        st.write(question.prompt)
        st.caption(question.helper)
        if question.reframe:
            st.info(question.reframe)

        if question.key != "confirmation":
            answer = st.text_area("Your answer", key=f"interview_answer_{question.key}")
            if st.button("Save answer and continue", key="interview_save_answer"):
                st.session_state.problem_bridge_interview_state = answer_question(state, question.key, answer)
                st.rerun()
        else:
            st.success("The core workflow understanding is complete enough to generate an alignment package.")

        reset_col, generate_col = st.columns(2)
        with reset_col:
            if st.button("Reset guided interview", key="interview_reset"):
                st.session_state.problem_bridge_interview_state = start_interview()
                st.rerun()
        with generate_col:
            ready = is_ready_for_alignment(state)
            if st.button(
                "Generate alignment package from interview",
                key="interview_generate",
                disabled=not ready,
            ):
                problem_text = build_problem_from_interview(state)
                out = _run_problem_text(problem_text, "guided_interview")
                st.success(f"已生成：{out}")
                st.download_button("下载 guided_interview_problem.md", problem_text, file_name="problem.md")
                _render_friendly_output(out)
            if not ready:
                st.caption("Answer the missing items before generating the package.")

    with right:
        st.markdown("### Understanding so far")
        st.progress(summary.completeness, text=f"completeness: {int(summary.completeness * 100)}%")
        if summary.known_items:
            st.write("Known:")
            for item in summary.known_items:
                st.write(f"- {item}")
        else:
            st.write("No answers yet.")

        if summary.missing_items:
            st.write("Missing:")
            for item in summary.missing_items:
                st.write(f"- {item}")
        else:
            st.success("No core fields missing.")


def _ai_wizard() -> None:
    _render_page_intro(
        "AI practitioner wizard",
        "Use this when an AI task already exists and you need to check whether it still matches the original domain problem.",
        "This page is a misalignment check. It does not prove feasibility, safety, deployment readiness, or domain correctness.",
        ["AI-task problem brief", "Misalignment risks", "Evidence contract", "Evaluation protocol"],
    )
    with st.form("ai_practitioner"):
        answers = {
            "domain_problem": st.text_area("What domain problem are you trying to solve?", key="ai_draft_domain_problem"),
            "candidate_task": st.text_area("What AI task are you considering?", key="ai_draft_candidate_task"),
            "inputs": st.text_area("What inputs will the system use?", key="ai_draft_inputs"),
            "outputs": st.text_area("What outputs should the system produce?", key="ai_draft_outputs"),
            "metric": st.text_area("How would you evaluate success?", key="ai_draft_metric"),
            "user": st.text_area("Who will use or review the output?", key="ai_draft_user"),
            "high_risk_mistakes": st.text_area("Which mistakes would cause serious consequences?", key="ai_draft_high_risk_mistakes"),
        }
        submitted = st.form_submit_button("Check task alignment")

    if submitted:
        problem_text = build_ai_practitioner_problem(answers)
        out = _run_problem_text(problem_text, "ai_practitioner")
        st.success(f"Generated: {out}")
        st.download_button("Download problem.md", problem_text, file_name="problem.md")
        _render_friendly_output(out)

def _view_outputs() -> None:
    _render_page_intro(
        "View generated outputs",
        "Open previous local UI runs and inspect their friendly summary, technical files, and downloadable package.",
        "Review outputs before sharing. Generated packages may include sensitive text if the user entered sensitive material.",
        ["Friendly summary", "Technical delivery files", "Download package"],
    )
    runs = sorted([path for path in RUN_ROOT.glob("*") if path.is_dir()], reverse=True)
    if not runs:
        st.info("No UI-generated outputs yet. Run an example, document intake, question discovery, or wizard first.")
        return

    selected = st.selectbox("Choose a generated run", runs, format_func=lambda path: path.name)
    _render_friendly_output(selected)

def _run_document_intake(uploaded_files) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = RUN_ROOT / f"{timestamp}_document_intake"
    source_dir = out / "source_files"
    source_dir.mkdir(parents=True, exist_ok=True)

    results = []
    for uploaded_file in uploaded_files:
        safe_name = Path(uploaded_file.name).name
        source_path = source_dir / safe_name
        source_path.write_bytes(uploaded_file.getvalue())
        results.append(extract_document(source_path))

    write_intake_package(results, out)
    (out / "problem_seed.md").write_text(build_problem_seed_from_intake(results), encoding="utf-8")
    st.session_state.last_output_dir = str(out)
    return out



def _run_question_discovery(package) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = RUN_ROOT / f"{timestamp}_question_discovery"
    out.mkdir(parents=True, exist_ok=True)
    write_question_discovery_package(package, out)
    (out / "problem_seed.md").write_text(build_problem_from_discovery(package), encoding="utf-8")
    st.session_state.last_output_dir = str(out)
    return out



def _run_problem_text(problem_text: str, prefix: str) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = RUN_ROOT / f"{timestamp}_{prefix}"
    out.mkdir(parents=True, exist_ok=True)
    (out / "problem.md").write_text(problem_text, encoding="utf-8")
    package = build_alignment_package(problem_text)
    write_alignment_package(package, out)
    st.session_state.last_output_dir = str(out)
    return out


def _render_friendly_output(out: Path) -> None:
    summary = friendly_summary(out)
    st.subheader("User-facing summary")

    top_left, top_right = st.columns([1.2, 1])
    with top_left:
        st.markdown("### One-sentence conclusion")
        st.success(summary.one_sentence)
    with top_right:
        st.markdown("### Output folder")
        st.code(str(out), language="text")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("### Priority opportunities")
        for item in summary.opportunities[:5]:
            st.write(f"- {item}")
    with col2:
        st.markdown("### Human review boundaries")
        for item in summary.must_review[:5]:
            st.write(f"- {item}")

    st.markdown("### Current workflow map")
    if summary.workflow_steps:
        for index, step in enumerate(summary.workflow_steps, start=1):
            st.write(f"{index}. {step}")
    else:
        st.write("No clear workflow steps were identified yet.")

    st.markdown("### Next steps")
    for item in summary.next_steps[:5]:
        st.write(f"- {item}")

    archive = _make_archive(out)
    st.download_button(
        "Download package: ProblemBridge alignment",
        archive.read_bytes(),
        file_name=f"{out.name}.zip",
        mime="application/zip",
    )

    with st.expander("Technical delivery package"):
        for item in discover_alignment_outputs(out):
            st.markdown(f"### {FRIENDLY_FILE_LABELS.get(item.filename, item.filename)}")
            st.caption(item.filename)
            st.code(item.path.read_text(encoding="utf-8"), language=_language_for(item.filename))

def _make_archive(out: Path) -> Path:
    archive_base = out / out.name
    archive_path = archive_base.with_suffix(".zip")
    if archive_path.exists():
        return archive_path
    created = shutil.make_archive(str(archive_base), "zip", out)
    return Path(created)


def _slug(value: str) -> str:
    return (
        value.lower()
        .replace(" / ", "_")
        .replace(" ", "_")
        .replace("-", "_")
    )


def _language_for(filename: str) -> str:
    if filename.endswith(".yaml"):
        return "yaml"
    if filename.endswith(".csv"):
        return "csv"
    if filename.endswith(".jsonl"):
        return "json"
    return "markdown"


if __name__ == "__main__":
    main()
