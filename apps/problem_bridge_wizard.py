from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path

import streamlit as st

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
from problem_bridge.writer import write_alignment_package


EXAMPLES = {
    "HSG": Path("examples/problem_bridge/hsg/problem.md"),
    "Chinese painting / VULCA": Path("examples/problem_bridge/chinese_painting/problem.md"),
    "Political education risk": Path("examples/problem_bridge/political_education/problem.md"),
}

RUN_ROOT = Path("outputs/ui_runs")

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
        )
        uncertainty = st.text_area(
            "What feels unclear right now?",
            placeholder="Example: I do not know whether to ask the practitioner, supervisor, data owner, or AI engineer first.",
            height=90,
        )
        desired_change = st.text_area(
            "What would a useful first conversation achieve?",
            placeholder="Example: Leave with better questions, a short list of experts to interview, and unknowns to validate.",
            height=90,
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
            "domain": st.text_input("What field or setting is this in?"),
            "repeated_work": st.text_area("What is one task people repeatedly do?"),
            "current_owner": st.text_input("Who currently does this task?"),
            "result": st.text_input("What result does the task produce?"),
        }
        st.caption("Examples: review images, organize lab notes, inspect reports, grade work, summarize cases, prepare expert questions.")

        st.subheader("Section B: workflow steps")
        answers.update(
            {
                "step_1": st.text_input("Step 1"),
                "step_2": st.text_input("Step 2"),
                "step_3": st.text_input("Step 3"),
                "step_4": st.text_input("Step 4"),
                "additional_notes": st.text_area("Additional notes"),
            }
        )

        st.subheader("Section C: friction and judgement")
        answers.update(
            {
                "time_consuming_step": st.text_area("Which step is most time-consuming?"),
                "annoying_step": st.text_area("Which step is most annoying or repetitive?"),
                "error_prone_step": st.text_area("Which step is most error-prone?"),
                "expert_judgement_step": st.text_area("Which step depends most on expert judgement?"),
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
                ),
                "critical_materials": st.text_area("Which materials are most critical?"),
                "missing_materials": st.text_area("Which materials are often missing, unclear, or hard to organize?"),
            }
        )

        st.subheader("Section E: human boundaries")
        answers.update(
            {
                "never_automated": st.text_area("What should AI never decide automatically?"),
                "human_confirmed": st.text_area("What must be confirmed by a human?"),
                "serious_mistakes": st.text_area("What mistakes would be serious?"),
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
            "domain_problem": st.text_area("What domain problem are you trying to solve?"),
            "candidate_task": st.text_area("What AI task are you considering?"),
            "inputs": st.text_area("What inputs will the system use?"),
            "outputs": st.text_area("What outputs should the system produce?"),
            "metric": st.text_area("How would you evaluate success?"),
            "user": st.text_area("Who will use or review the output?"),
            "high_risk_mistakes": st.text_area("Which mistakes would cause serious consequences?"),
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
    return out



def _run_question_discovery(package) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = RUN_ROOT / f"{timestamp}_question_discovery"
    out.mkdir(parents=True, exist_ok=True)
    write_question_discovery_package(package, out)
    (out / "problem_seed.md").write_text(build_problem_from_discovery(package), encoding="utf-8")
    return out



def _run_problem_text(problem_text: str, prefix: str) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = RUN_ROOT / f"{timestamp}_{prefix}"
    out.mkdir(parents=True, exist_ok=True)
    (out / "problem.md").write_text(problem_text, encoding="utf-8")
    package = build_alignment_package(problem_text)
    write_alignment_package(package, out)
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
