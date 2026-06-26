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
from problem_bridge.writer import write_alignment_package


EXAMPLES = {
    "HSG": Path("examples/problem_bridge/hsg/problem.md"),
    "Chinese painting / VULCA": Path("examples/problem_bridge/chinese_painting/problem.md"),
    "Political education risk": Path("examples/problem_bridge/political_education/problem.md"),
}

RUN_ROOT = Path("outputs/ui_runs")


def main() -> None:
    st.set_page_config(page_title="ProblemBridge Guided Mode", layout="wide")
    st.title("ProblemBridge Guided Mode")
    _safety_banner()

    page = st.sidebar.radio(
        "选择入口",
        [
            "Home",
            "Explore examples",
            "Domain practitioner wizard",
            "AI practitioner wizard",
            "View generated outputs",
        ],
    )

    if page == "Home":
        _home()
    elif page == "Explore examples":
        _examples()
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
