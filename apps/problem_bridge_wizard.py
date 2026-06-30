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
    st.set_page_config(page_title="ProblemBridge Guided Mode", layout="wide")
    st.title("ProblemBridge Guided Mode")
    _safety_banner()

    page = st.sidebar.radio(
        "选择入口",
        [
            "Home",
            "Explore examples",
            "Question discovery",
            "Document intake",
            "Domain practitioner wizard",
            "AI practitioner wizard",
            "View generated outputs",
        ],
    )

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


def _safety_banner() -> None:
    st.warning(
        "Start with synthetic examples. Do not upload private patient data, "
        "confidential manuscripts, API keys, or sensitive unpublished materials."
    )


def _home() -> None:
    st.header("You do not need to know AI. Start by describing a repeated task in your work.")
    st.write(
        "Describe what you repeatedly do, what materials you check, which decisions "
        "are difficult, and what should never be automated."
    )
    st.write(
        "ProblemBridge turns that into a workflow map, AI-support opportunities, "
        "human-review boundaries, and a technical package that AI practitioners can understand."
    )

    st.subheader("Recommended first step")
    st.info(
        "Start with Explore examples. Generate a synthetic example first, read the friendly "
        "summary, then use Domain practitioner wizard for your own non-sensitive workflow."
    )


def _examples() -> None:
    st.header("看示例")
    choice = st.selectbox("选择一个 synthetic example", list(EXAMPLES))
    problem_path = EXAMPLES[choice]
    st.text_area("示例问题描述", problem_path.read_text(encoding="utf-8"), height=220)

    if st.button("生成这个示例的对齐包"):
        out = _run_problem_text(problem_path.read_text(encoding="utf-8"), f"example_{_slug(choice)}")
        st.success(f"已生成：{out}")
        _render_friendly_output(out)


def _question_discovery() -> None:
    st.header("Question discovery")
    st.caption(
        "Use this when you do not yet know what to ask, who to ask, or whether the issue is an AI task."
    )
    st.info("Do not propose a solution yet. First discover what to ask and who to ask.")

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
        "Download question discovery package",
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
    st.header("Document intake")
    st.caption("Upload Word, PDF, Markdown, TXT, or CSV files and convert them into local extraction outputs.")
    st.info("Supports .docx, .md, .txt, .csv, and text-based PDF. Scanned PDF, OCR, images, and figure understanding are not supported.")

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
        "Download document intake package",
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
    st.header("Describe your workflow, not an AI task.")
    st.caption("先说你平时怎么工作，不用懂 AI。")

    with st.expander("Interview mode"):
        st.write("Use this mode when you are helping someone else describe their workflow.")
        st.markdown(
            """
            - 不用想 AI。最近工作里有没有一件事，你总是要重复看、重复判断、重复整理？
            - 这件事一般从哪里开始？
            - 你判断的时候看什么？
            - 哪一步最容易判断错？
            - 如果助手只做提醒、不替你做决定，会不会有帮助？
            - 什么结果你一定要自己确认？
            """
        )

    _guided_interview()
    st.divider()
    st.subheader("Advanced: full workflow form")
    st.caption("Use this manual form when you already know the workflow details.")

    with st.form("domain_practitioner"):
        st.subheader("Section A: What repeated work do you do?")
        answers = {
            "domain": st.text_input("What field are you in? / 你所在领域是什么？"),
            "repeated_work": st.text_area("What is one task you repeatedly do? / 你平时反复做的一件工作是什么？"),
            "current_owner": st.text_input("Who currently does this task? / 这件工作通常由谁完成？"),
            "result": st.text_input("What result does this task produce? / 这件工作最后会产生什么结果？"),
        }
        st.caption("例如：整理实验结果、检查影像、写报告、审核学生作业、整理展览资料、判断图像内容、回复客户问题。")

        st.subheader("Section B: What are the steps?")
        answers.update(
            {
                "step_1": st.text_input("Step 1"),
                "step_2": st.text_input("Step 2"),
                "step_3": st.text_input("Step 3"),
                "step_4": st.text_input("Step 4"),
                "additional_notes": st.text_area("Additional notes / 可以很粗略，例如：先看图片 -> 再查记录 -> 再判断 -> 最后写报告"),
            }
        )

        st.subheader("Section C: Where does it get difficult?")
        answers.update(
            {
                "time_consuming_step": st.text_area("Which step is most time-consuming?"),
                "annoying_step": st.text_area("Which step is most annoying?"),
                "error_prone_step": st.text_area("Which step is most error-prone?"),
                "expert_judgement_step": st.text_area("Which step depends most on expert judgement?"),
            }
        )

        st.subheader("Section D: What materials do you use?")
        answers.update(
            {
                "materials": st.multiselect(
                    "What materials do you use?",
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

        st.subheader("Section E: What should AI not decide?")
        answers.update(
            {
                "never_automated": st.text_area("What should never be automated?"),
                "human_confirmed": st.text_area("What must be confirmed by a human?"),
                "serious_mistakes": st.text_area("What mistakes would be serious?"),
                "useful_support": st.multiselect(
                    "If AI only gave support, what would be useful?",
                    [
                        "整理好的摘要",
                        "需要注意的风险提示",
                        "证据清单",
                        "初步草稿",
                        "待人工确认的问题列表",
                        "工作流改进建议",
                        "给 AI 工程师看的项目说明",
                    ],
                ),
            }
        )
        submitted = st.form_submit_button("生成工作流对齐包")

    if submitted:
        problem_text = build_workflow_first_problem(answers)
        out = _run_problem_text(problem_text, "domain_practitioner")
        st.success(f"已生成：{out}")
        st.download_button("下载 problem.md", problem_text, file_name="problem.md")
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
    st.header("帮我理解这个领域问题，避免做偏")
    with st.form("ai_practitioner"):
        answers = {
            "domain_problem": st.text_area("你想解决的领域问题是什么？"),
            "candidate_task": st.text_area("你目前打算把它做成什么 AI 任务？"),
            "inputs": st.text_area("你的输入数据是什么？"),
            "outputs": st.text_area("你希望模型输出什么？"),
            "metric": st.text_area("你准备用什么指标评价？"),
            "user": st.text_area("这个输出最后由谁使用？"),
            "high_risk_mistakes": st.text_area("哪些错误会造成严重后果？"),
        }
        submitted = st.form_submit_button("检查这个项目会不会做偏")

    if submitted:
        problem_text = build_ai_practitioner_problem(answers)
        out = _run_problem_text(problem_text, "ai_practitioner")
        st.success(f"已生成：{out}")
        st.download_button("下载 problem.md", problem_text, file_name="problem.md")
        _render_friendly_output(out)


def _view_outputs() -> None:
    st.header("查看输出")
    runs = sorted([path for path in RUN_ROOT.glob("*") if path.is_dir()], reverse=True)
    if not runs:
        st.info("还没有 UI 生成的输出。请先运行示例或问卷。")
        return

    selected = st.selectbox("选择一次生成结果", runs, format_func=lambda path: path.name)
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
    st.subheader("普通用户摘要")

    st.subheader("一句话结论")
    st.success(summary.one_sentence)

    st.subheader("可以优先尝试")
    for item in summary.opportunities[:5]:
        st.write(f"- {item}")

    st.subheader("需要人工确认 / 不建议自动化")
    for item in summary.must_review[:5]:
        st.write(f"- {item}")

    st.subheader("当前工作流地图")
    if summary.workflow_steps:
        for index, step in enumerate(summary.workflow_steps, start=1):
            st.write(f"{index}. {step}")
    else:
        st.write("还没有识别出明确工作流步骤。")

    st.subheader("下一步可以怎么做")
    for item in summary.next_steps[:5]:
        st.write(f"- {item}")

    archive = _make_archive(out)
    st.download_button(
        "下载给 AI 工程师的项目包",
        archive.read_bytes(),
        file_name=f"{out.name}.zip",
        mime="application/zip",
    )

    with st.expander("技术交付包：给 AI 工程师 / 高级查看"):
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
