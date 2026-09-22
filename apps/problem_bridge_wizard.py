from __future__ import annotations

import csv
import hashlib
import json
import re
import uuid
from dataclasses import asdict
from datetime import datetime, timezone
from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile
from importlib import reload
from pathlib import Path

import streamlit as st

from claim_harness.report_exporter import export_output_report
from claim_harness.llm import resolve_provider_config
from problem_bridge import __version__ as problem_bridge_version
from problem_bridge.build_contract import (
    BUILD_CONTRACT_RUN_ARTIFACTS,
    BUILD_CONTRACT_SNAPSHOT_DIRECTORIES,
    generate_evidence_gated_build,
)
from problem_bridge.generator import build_alignment_package
from problem_bridge.workbench_ui import interview_seed, render_workbench
from problem_bridge.need_ui import NEED_DRAFT_KEYS
from problem_bridge.guided import (
    FRIENDLY_FILE_LABELS,
    build_ai_practitioner_problem,
    build_workflow_first_problem,
    discover_alignment_outputs,
    friendly_summary,
)
from problem_bridge import document_intake as document_intake_module
from problem_bridge.interview import (
    QUESTION_FLOW,
    REQUIRED_KEYS,
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
from problem_bridge.project_lifecycle import (
    RUN_DELETE_MARKER_NAME,
    RUN_IDENTITY_NAME,
    ProjectLifecycleError,
    RunContext,
    SYSTEM_OWNED_ARTIFACTS,
    SYSTEM_SNAPSHOT_DIRECTORIES,
    allocate_run_directory,
    delete_run_directory,
    is_run_complete,
    is_internal_staging_name,
    is_link_or_reparse,
    load_pending_deletion,
    load_run_identity,
    snapshot_completed_run,
    snapshot_directory_files,
)
from problem_bridge.revision_governance import snapshot_project_governance
from problem_bridge.ui_memory import (
    DEFAULT_MEMORY_PATH,
    clear_workbench_memory,
    load_workbench_memory,
    save_workbench_memory,
)
from problem_bridge.writer import (
    ALIGNMENT_RUN_ARTIFACTS,
    write_alignment_package,
)

if not hasattr(document_intake_module, "extract_url"):
    document_intake_module = reload(document_intake_module)

build_problem_seed_from_intake = document_intake_module.build_problem_seed_from_intake
extract_document = document_intake_module.extract_document
extract_url = document_intake_module.extract_url
write_intake_package = document_intake_module.write_intake_package


EXAMPLES = {
    "Quality inspection": Path("examples/problem_bridge/quality_inspection/problem.md"),
    "Cultural archive": Path("examples/problem_bridge/cultural_archive/problem.md"),
    "Training policy": Path("examples/problem_bridge/training_policy/problem.md"),
}

RUN_ROOT = Path("outputs/ui_runs")
MEMORY_PATH = DEFAULT_MEMORY_PATH
MEMORY_FILE_LABEL = "workbench_memory.json"

PAGE_OPTIONS = [
    "Home",
    "Explore examples",
    "Document intake",
    "Question discovery",
    "Domain practitioner wizard",
    "AI practitioner wizard",
    "Evidence-gated build",
    "View generated outputs",
]

WORKSPACE_FLOW_PAGES = [
    "Document intake",
    "Question discovery",
    "Domain practitioner wizard",
    "AI practitioner wizard",
    "Evidence-gated build",
    "View generated outputs",
]

LANGUAGE_OPTIONS = ["English", "中文"]
LANGUAGE_CODES = {"English": "en", "中文": "zh"}
LANGUAGE_QUERY_CODES = LANGUAGE_CODES
LANGUAGE_BY_QUERY_CODE = {code: choice for choice, code in LANGUAGE_QUERY_CODES.items()}
LANGUAGE_BADGE = {"en": "English interface", "zh": "中文界面"}

PAGE_LABELS = {
    "Home": {"en": "My workbench", "zh": "我的工作台"},
    "Explore examples": {"en": "Try an example", "zh": "试用示例"},
    "Document intake": {"en": "Bring your files", "zh": "整理已有材料"},
    "Question discovery": {"en": "Clarify your question", "zh": "理清问题"},
    "Domain practitioner wizard": {"en": "Describe your work", "zh": "梳理工作流程"},
    "AI practitioner wizard": {"en": "Check an AI task", "zh": "检查 AI 任务"},
    "Evidence-gated build": {"en": "Prepare a build plan", "zh": "准备实现方案"},
    "View generated outputs": {"en": "Results & downloads", "zh": "查看与下载结果"},
}

INTERVIEW_EXAMPLES = {
    "repeated_work": ("Each week I compare a draft report with the result tables, then ask the author about discrepancies.", "每周我要对照结果表检查报告，再把不一致的地方发给作者确认。"),
    "materials": ("I use the report, a spreadsheet of results, and the review checklist.", "我会看报告正文、结果表和审核清单。"),
    "pain_points": ("Finding the source table for each number takes time; versions are easy to mix up.", "最费时间的是找到每个数字对应的表格，还容易混淆版本。"),
    "human_boundaries": ("The author must confirm explanations and conclusions. The assistant cannot approve a report.", "原因解释和最终结论必须由作者确认，助手不能代替审核人批准报告。"),
    "useful_support": ("A list of statements to check, their source rows, and questions to send to the author.", "给我一份待核查句子清单，附上来源表格和需要向作者确认的问题。"),
}

WORKFLOW_STEPS_ZH = [
    ("01", "文档摄取", "把本地文件转成可审计的文本和表格。"),
    ("02", "问题发现", "先找出该问什么、该问谁。"),
    ("03", "引导式访谈", "还原工作材料、痛点、判断边界。"),
    ("04", "ProblemBridge", "生成任务规格、证据契约和评估方案。"),
    ("05", "证据门控", "生成候选能力声明，由 ClaimHarness 保留、降级或拒绝。"),
    ("06", "交付与复核", "导出 Codex 项目包、运行记录和可审计结果。"),
]

ACTIVE_WORKFLOW_BY_PAGE_ZH = {
    "Document intake": "文档摄取",
    "Question discovery": "问题发现",
    "Domain practitioner wizard": "引导式访谈",
    "AI practitioner wizard": "ProblemBridge",
    "Evidence-gated build": "证据门控",
    "Explore examples": "ProblemBridge",
    "View generated outputs": "交付与复核",
}

MODULE_CARDS_ZH = [
    {
        "title": "文档摄取",
        "stage": "文件准备",
        "start_if": "你有 Word、文字版 PDF、Markdown、TXT 或 CSV 文件。",
        "what_you_get": "extracted_text.md、extracted_tables、source_manifest.json、提取警告文件。",
    },
    {
        "title": "问题发现",
        "stage": "问题建模之前",
        "start_if": "你知道哪里不清楚，但还不知道该问什么。",
        "what_you_get": "问题简报、相关人员图、访谈问题、待验证未知项。",
    },
    {
        "title": "领域工作流向导",
        "stage": "理解真实工作流",
        "start_if": "你能描述日常工作、材料、痛点和人工复核边界。",
        "what_you_get": "工作流优先的 ProblemBridge 对齐包。",
    },
    {
        "title": "AI 任务对齐向导",
        "stage": "任务不跑偏检查",
        "start_if": "你已经有候选 AI 任务，需要检查它是否偏离领域问题。",
        "what_you_get": "错位风险、任务规格、证据契约、评价协议。",
    },
    {
        "title": "证据门控构建",
        "stage": "开始实现之前",
        "start_if": "你已有对齐包，需要一份有证据边界、可测试的构建契约。",
        "what_you_get": "声明决策、GPT-5.6 运行记录、可重放轨迹和 Codex 交接包。",
    },
]

WORKFLOW_STEPS = [
    ("01", "Document intake", "Turn local files into auditable text and tables."),
    ("02", "Question discovery", "Find what to ask and who should answer."),
    ("03", "Guided interview", "Reconstruct work, materials, pain points, and boundaries."),
    ("04", "ProblemBridge", "Generate task specs, evidence contracts, and evaluation plans."),
    ("05", "Evidence gate", "Generate capability claims, then retain, downgrade, or reject them."),
    ("06", "Handoff & review", "Export the Codex pack, runtime record, and auditable results."),
]

ACTIVE_WORKFLOW_BY_PAGE = {
    "Document intake": "Document intake",
    "Question discovery": "Question discovery",
    "Domain practitioner wizard": "Guided interview",
    "AI practitioner wizard": "ProblemBridge",
    "Evidence-gated build": "Evidence gate",
    "Explore examples": "ProblemBridge",
    "View generated outputs": "Handoff & review",
}

MODULE_CARDS = [
    {
        "title": "Document intake",
        "stage": "File preparation",
        "start_if": "You have Word, PDF, HTML, webpages, images, Markdown, TXT, or CSV files.",
        "what_you_get": "extracted_text.md, annotation_map.json, extracted_tables, source_manifest.json, warnings.",
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
    {
        "title": "Evidence-gated build",
        "stage": "Before implementation",
        "start_if": "You have an alignment package and need a bounded, testable build contract.",
        "what_you_get": "claim decisions, GPT-5.6 runtime record, replay trace, and Codex Handoff Pack.",
    },
]

INTERVIEW_COPY_ZH = {
    "repeated_work": {
        "prompt": "你想更好理解哪一项反复发生的工作？",
        "helper": "描述一个你或团队会一遍遍做的真实任务。",
        "reframe": "不要先从 AI 任务开始。先从人们已经在做的工作开始。",
    },
    "materials": {
        "prompt": "做这项工作时，你会看哪些材料？",
        "helper": "例如：图片、笔记、表格、报告、案例、评分标准、指南。",
    },
    "pain_points": {
        "prompt": "这项工作在哪些地方变慢、模糊、重复烦人或容易出错？",
        "helper": "指出哪些步骤让人工判断变困难。",
    },
    "human_boundaries": {
        "prompt": "哪些决定必须保留人工复核？",
        "helper": "列出不应自动化的结论、批准或高风险决定。",
    },
    "useful_support": {
        "prompt": "如果 AI 只做辅助，什么输出会有用？",
        "helper": "例如：摘要、风险提示、证据列表、草稿笔记、复核问题。",
    },
    "confirmation": {
        "prompt": "当前理解是否足够准确，可以生成对齐包？",
        "helper": "先检查摘要，必要时修改答案，然后再生成结果包。",
    },
}

INTERVIEW_LABELS_ZH = {
    "repeated work": "反复发生的工作",
    "materials": "判断材料",
    "pain points": "痛点",
    "human review boundaries": "人工复核边界",
    "useful support outputs": "有用的辅助输出",
}

MATERIAL_OPTIONS = [
    "tables",
    "images",
    "reports",
    "text records",
    "experiment logs",
    "historical cases",
    "expert judgement",
    "rules/guidelines",
    "other",
]

MATERIAL_OPTIONS_ZH = [
    "表格",
    "图片",
    "报告",
    "文本记录",
    "实验日志",
    "历史案例",
    "专家判断",
    "规则或指南",
    "其他",
]

SUPPORT_OPTIONS = [
    "organized summary",
    "risk flags",
    "evidence list",
    "draft notes",
    "questions for human review",
    "workflow improvement suggestions",
    "project brief for AI engineers",
]

SUPPORT_OPTIONS_ZH = [
    "结构化摘要",
    "风险提示",
    "证据列表",
    "草稿笔记",
    "人工复核问题",
    "工作流改进建议",
    "给 AI 工程师的项目 brief",
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
    "annotation_map.json": "Annotation map",
    "highlighted_spans.csv": "Highlighted spans",
    "comment_threads.md": "Comment threads",
    "priority_marks.md": "Priority marks",
    "source_manifest.json": "Source manifest",
    "ocr_quality_report.json": "OCR quality report",
    "extraction_warnings.md": "Extraction warnings",
    "problem_seed.md": "ProblemBridge seed brief",
}

# Legacy folders predate governed run identities, so they cannot safely use
# the global system-owned union as a sharing allow-list.  These narrow sets
# are selected only when a package can be identified by workflow-specific
# sentinel files; mixed or unknown legacy folders are refused.
LEGACY_CLAIM_SHARE_FILES = {
    "claim_table.csv",
    "evidence_map.json",
    "audit_report.md",
    "revision_suggestions.md",
    "audit_diagnostics.json",
    "human_review_queue.json",
    "agent_trace.jsonl",
    "llm_review.json",
    "run_manifest.json",
    "project_summary_log.md",
    "applied_evidence_contract.json",
    "index.html",
}
LEGACY_PACKAGE_SENTINELS = {
    "claim-audit": {
        "claim_table.csv",
        "evidence_map.json",
        "audit_report.md",
        "revision_suggestions.md",
        "agent_trace.jsonl",
        "run_manifest.json",
    },
    "alignment": {
        "problem_card.md",
        "workflow_map.md",
        "ai_task_spec.yaml",
        "evidence_contract.yaml",
        "alignment_trace.jsonl",
    },
    "document-intake": set(DOCUMENT_INTAKE_FILES) - {"problem_seed.md"},
    "question-discovery": set(QUESTION_DISCOVERY_FILES) - {"problem_seed.md"},
}
LEGACY_PACKAGE_FILES = {
    "claim-audit": LEGACY_CLAIM_SHARE_FILES,
    "alignment": set(ALIGNMENT_RUN_ARTIFACTS),
    "document-intake": set(DOCUMENT_INTAKE_FILES),
    "question-discovery": set(QUESTION_DISCOVERY_FILES),
}

DRAFT_KEY_GROUPS = {
    "need_brief": NEED_DRAFT_KEYS,
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

PROJECT_SCOPED_SESSION_KEYS = (
    "active_project_id",
    "last_output_dir",
    "last_document_intake_dir",
    "last_question_discovery_dir",
    "last_alignment_package_dir",
    "last_ai_alignment_dir",
    "last_build_contract_dir",
    "last_example_dir",
    "last_problem_dir",
    "pending_unified_stage",
    "pending_problem_seed",
    "problem_bridge_interview_state",
    "interview_seed_source",
    "ai_seed_source_dir",
    "domain_input_mode",
    "confirm_interview_reset",
    "confirm_start_new_project",
    "interview_editing_key",
)
PROJECT_SCOPED_KEY_PREFIXES = ("interview_answer_", "interview_edit_", "unified_")


def _language_code() -> str:
    choice = st.session_state.get("ui_language", "English")
    return LANGUAGE_CODES.get(choice, "en")


def _normalize_language_choice(value: object) -> str:
    if isinstance(value, (list, tuple)):
        value = value[0] if value else ""
    text = str(value or "").strip()
    if text in LANGUAGE_OPTIONS:
        return text
    return LANGUAGE_BY_QUERY_CODE.get(text.lower(), "English")


def _language_query_code(choice: object) -> str:
    return LANGUAGE_QUERY_CODES.get(_normalize_language_choice(choice), "en")


def _query_language_value() -> object:
    try:
        return st.query_params.get("lang")
    except Exception:
        return None


def _sync_language_from_query_params() -> None:
    query_value = _query_language_value()
    if query_value:
        selected = _normalize_language_choice(query_value)
        st.session_state.ui_language = selected
        st.session_state.language_control = selected
        return
    st.session_state.setdefault("ui_language", "English")
    st.session_state.setdefault("language_control", st.session_state.ui_language)


def _set_language_choice(choice: object) -> None:
    selected = _normalize_language_choice(choice)
    st.session_state.ui_language = selected
    st.query_params["lang"] = _language_query_code(selected)


def _apply_language_control() -> None:
    _set_language_choice(st.session_state.get("language_control", "English"))


def _text(en: str, zh: str) -> str:
    return zh if _language_code() == "zh" else en


def _page_label(page: str) -> str:
    labels = PAGE_LABELS.get(page, {"en": page, "zh": page})
    return labels.get(_language_code(), page)


def _generated_message(out: Path) -> str:
    return _text("Your result is ready and saved locally. Review it below, then continue or download.", "结果已生成并保存在本地。先查看下方内容，再继续或下载。")


def _navigate_to_page(page: str) -> None:
    if page not in PAGE_OPTIONS:
        raise ValueError(f"Unknown workspace page: {page}")
    st.session_state.workspace_page = page


def _select_workspace_page(widget_key: str) -> None:
    selected = st.session_state.get(widget_key)
    if selected in PAGE_OPTIONS:
        st.session_state.workspace_page = selected


def _set_flash_message(kind: str, message: str) -> None:
    st.session_state._flash_message = {"kind": kind, "message": message}


def _render_flash_message() -> None:
    payload = st.session_state.pop("_flash_message", None)
    if not isinstance(payload, dict) or not payload.get("message"):
        return
    renderer = {
        "success": st.success,
        "warning": st.warning,
        "error": st.error,
    }.get(str(payload.get("kind")), st.info)
    renderer(str(payload["message"]))


def _has_form_value(value: object) -> bool:
    if isinstance(value, (list, tuple, set, dict)):
        return bool(value)
    return bool(str(value or "").strip())


def _missing_required_fields(fields: dict[str, object]) -> list[str]:
    return [label for label, value in fields.items() if not _has_form_value(value)]


def _render_required_fields_error(missing: list[str]) -> None:
    if not missing:
        return
    st.error(
        _text(
            "Add the required information before generating a package: ",
            "生成结果包前，请补充这些必填信息：",
        )
        + ", ".join(missing)
    )


def _run_ui_action(label: str, action):
    try:
        with st.spinner(label):
            return action()
    except Exception as exc:  # pragma: no cover - exercised through AppTest guards
        st.error(
            _text(
                "This step could not be completed. Your inputs are still here; review the details and try again.",
                "这一步未能完成。你的输入仍然保留；请检查下面的错误信息后重试。",
            )
        )
        st.caption(f"{type(exc).__name__}: {exc}")
        return None


def _download_package_label(package_name: str) -> str:
    return _text(f"Download package: {package_name}", f"下载结果包：{package_name}")


def _interview_copy(question, field: str) -> str:
    if _language_code() == "zh":
        copy = INTERVIEW_COPY_ZH.get(question.key, {})
        if copy.get(field):
            return copy[field]
    return getattr(question, field)


def _display_known_item(item: str) -> str:
    if _language_code() != "zh":
        return item
    for english_label, zh_label in INTERVIEW_LABELS_ZH.items():
        prefix = f"{english_label}:"
        if item.startswith(prefix):
            return f"{zh_label}：{item[len(prefix):].strip()}"
    return item


def _display_missing_item(item: str) -> str:
    return INTERVIEW_LABELS_ZH.get(item, item) if _language_code() == "zh" else item


def main() -> None:
    st.set_page_config(page_title="ProblemBridge Workbench", layout="wide")
    _sync_language_from_query_params()
    _ensure_memory_state()
    # Streamlit otherwise deletes widget values when their step is hidden.
    # Interrupt that cleanup for non-secret text drafts, including tool switches.
    for key in list(st.session_state):
        if key in NEED_DRAFT_KEYS or key in {"unified_manuscript", "unified_csv", "unified_references"}:
            st.session_state[key] = st.session_state[key]
    if "pending_workspace_page" in st.session_state:
        st.session_state.workspace_page = st.session_state.pop("pending_workspace_page")
    _inject_visual_theme()

    st.sidebar.markdown("### ProblemBridge")
    st.sidebar.caption(_text("Explain your work. Prepare a shared task.", "说清专业需求，让合作有个起点。"))
    for destination in ("Home", "Domain practitioner wizard", "View generated outputs"):
        st.sidebar.button(
            _page_label(destination),
            key=f"quick_nav_{PAGE_OPTIONS.index(destination)}",
            on_click=_navigate_to_page,
            args=(destination,),
            use_container_width=True,
        )
    with st.sidebar.expander(_text("All tools", "全部工具")):
        navigation_key = f"navigation_{_language_code()}"
        selected_page = st.session_state.get("workspace_page", "Home")
        st.session_state[navigation_key] = selected_page if selected_page in PAGE_OPTIONS else "Home"
        navigation_labels = {option: _page_label(option) for option in PAGE_OPTIONS}
        page = st.radio(
            _text("Choose an entry", "选择入口"),
            PAGE_OPTIONS,
            format_func=navigation_labels.__getitem__,
            key=navigation_key,
            on_change=_select_workspace_page,
            args=(navigation_key,),
        )
        st.session_state.workspace_page = page
    st.sidebar.caption(_text(
        "Local-first. Use synthetic or non-sensitive material first.",
        "本地优先。首次测试请使用合成或非敏感材料。",
    ))
    with st.sidebar.expander(_text("Drafts & project settings", "草稿与项目设置")):
        _render_memory_sidebar()
        _render_project_sidebar()

    _render_language_switcher()
    if page == "Home" and not st.session_state.get("last_problem_dir") and st.session_state.get("unified_intake_step", 0) == 0:
        _render_shell_header()
    else:
        _render_compact_shell_header(page)
    _safety_banner(compact=True)
    _render_flash_message()

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
    elif page == "Evidence-gated build":
        _evidence_gated_build()
    else:
        _view_outputs()
    if page != "Home":
        with st.expander(_text("Other steps (optional)", "其他步骤（可选）")):
            _render_flow_navigation(page)


def _render_memory_sidebar() -> None:
    _ensure_memory_state()

    st.divider()
    show_memory = st.checkbox(_text("Show workspace memory", "显示工作台记忆"), value=False, key="show_workspace_memory")
    if show_memory:
        st.caption(
            _text(
                f"Saved locally to `{MEMORY_PATH}` (`{MEMORY_FILE_LABEL}`). This workbench does not accept or store API keys.",
                f"本地保存位置：`{MEMORY_PATH}`（`{MEMORY_FILE_LABEL}`）。当前工作台不接收或保存 API 密钥。",
            )
        )
        st.warning(
            _text(
                "Privacy check before sharing: Clear local memory before sharing the folder or zip if your drafts include sensitive workflow details.",
                "分享前隐私检查：如果草稿包含敏感工作流信息，请先清除本地记忆，再分享文件夹或压缩包。",
            )
        )

        last_output = st.session_state.get("last_output_dir")
        if last_output:
            st.caption(_text(f"Last output: `{last_output}`", f"最近输出：`{last_output}`"))

        col1, col2 = st.columns(2)
        with col1:
            if st.button(_text("Load saved memory", "加载记忆"), key="memory_load"):
                st.session_state.pending_workbench_memory = load_workbench_memory(MEMORY_PATH)
                st.session_state.pending_workbench_memory_clear = True
                st.rerun()
            if st.button(_text("Save current workspace", "保存当前工作台"), key="memory_save"):
                payload = _current_workbench_memory()
                save_workbench_memory(payload, MEMORY_PATH)
                st.session_state.workbench_memory = payload
                st.success(_text("Workspace memory saved locally.", "工作台记忆已保存到本地。"))
        with col2:
            if st.button(_text("Clear memory", "清除记忆"), key="memory_clear"):
                clear_workbench_memory(MEMORY_PATH)
                st.session_state.pending_workbench_memory = {}
                st.session_state.pending_workbench_memory_clear = False
                _set_flash_message(
                    "success",
                    _text(
                        "Saved workspace memory cleared; current on-screen drafts were kept.",
                        "已清除保存的工作台记忆；当前页面中的草稿仍然保留。",
                    ),
                )
                st.rerun()

    if show_memory:
        st.caption(
            _text(
                "The guided flow is deterministic by default. Evidence-Gated Build can optionally use GPT-5.6 through an OPENAI_API_KEY environment variable; the UI never accepts or stores the key.",
                "引导流程默认使用确定性 mock。证据门控构建可通过 OPENAI_API_KEY 环境变量选择 GPT-5.6；界面不会接收或保存密钥。",
            )
        )


def _render_project_sidebar() -> None:
    project_id = _active_project_id()
    st.divider()
    st.caption(_text(f"Active project: `{project_id}`", f"当前项目：`{project_id}`"))
    if not st.session_state.get("confirm_start_new_project"):
        if st.button(_text("Start a new project", "开始新项目"), key="start_new_project"):
            st.session_state.confirm_start_new_project = True
            st.rerun()
    else:
        st.warning(
            _text(
                "Starting a new project clears current drafts from this workspace. Existing generated runs stay on disk.",
                "开始新项目会清空当前工作台草稿；已经生成的运行结果仍保留在本地。",
            )
        )
        if st.button(
            _text("Save drafts, then start", "保存草稿后开始"),
            key="save_then_start_project",
        ):
            payload = _current_workbench_memory()
            save_workbench_memory(payload, MEMORY_PATH)
            st.session_state.workbench_memory = payload
            st.session_state.pop("confirm_start_new_project", None)
            _reset_active_project()
            _set_flash_message("success", _text("Drafts saved; started a new local project.", "草稿已保存，并已开始新的本地项目。"))
            st.rerun()
        if st.button(
            _text("Start without saving drafts", "不保存草稿并开始"),
            key="discard_then_start_project",
        ):
            st.session_state.pop("confirm_start_new_project", None)
            _reset_active_project()
            _set_flash_message("success", _text("Started a new local project.", "已开始一个新的本地项目。"))
            st.rerun()
        if st.button(_text("Cancel", "取消"), key="cancel_start_project"):
            st.session_state.pop("confirm_start_new_project", None)
            st.rerun()
    show_project_deletion = st.checkbox(
        _text("Show project deletion controls", "显示项目删除控件"),
        value=False,
        key=f"show_project_deletion_{project_id}",
    )
    if show_project_deletion:
        project_runs = _project_run_paths(project_id)
        st.warning(
            _text(
                f"This permanently deletes {len(project_runs)} local run(s), including original uploads.",
                f"此操作会永久删除 {len(project_runs)} 次本地运行，包括原始上传文件。",
            )
        )
        typed_project_id = st.text_input(
            _text("Type the project ID to confirm", "输入项目 ID 以确认"),
            key=f"delete_project_id_{project_id}",
        )
        if st.button(
            _text("Delete all runs for this project", "删除这个项目的全部运行"),
            disabled=typed_project_id != project_id or not project_runs,
            key=f"delete_project_{project_id}",
        ):
            _delete_ui_project(project_id)
            _reset_active_project()
            _set_flash_message("success", _text("Project runs were permanently deleted.", "这个项目的运行记录已永久删除。"))
            st.rerun()
    _render_incomplete_run_cleanup()


def _render_incomplete_run_cleanup() -> None:
    show_pending = st.checkbox(
        _text(
            "Show incomplete runs",
            "检查未完成的运行",
        ),
        value=False,
        key="show_incomplete_runs",
    )
    if not show_pending:
        return
    pending = _pending_run_records()
    if not pending:
        st.caption(_text("No incomplete runs found.", "没有发现未完成的运行。"))
        return

    selected_index = st.selectbox(
        _text("Incomplete run", "未完成运行"),
        options=list(range(len(pending))),
        format_func=lambda index: (
            f"{pending[index]['project_id']} / {pending[index]['run_id']} / "
            f"{pending[index].get('workflow_type', 'unknown')}"
        ),
        key="selected_incomplete_run",
    )
    selected = pending[selected_index]
    st.caption(str(selected["path"]))
    typed_project = st.text_input(
        _text("Type its project ID", "输入该项目 ID"),
        key="confirm_incomplete_project_id",
    )
    typed_run = st.text_input(
        _text("Type its run ID", "输入该运行 ID"),
        key="confirm_incomplete_run_id",
    )
    if st.button(
        _text("Delete this incomplete run", "删除这次未完成运行"),
        disabled=(
            typed_project != selected["project_id"]
            or typed_run != selected["run_id"]
        ),
        key="delete_incomplete_run",
    ):
        run_root = _resolve_safe_ui_run_root(create=False)
        if run_root is None:
            raise ValueError("Configured UI run directory does not exist.")
        delete_run_directory(
            selected["path"],
            project_id=str(selected["project_id"]),
            run_id=str(selected["run_id"]),
            allow_incomplete=True,
            trusted_parent=run_root,
        )
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
    keys = list(PROJECT_SCOPED_SESSION_KEYS)
    for field_keys in DRAFT_KEY_GROUPS.values():
        keys.extend(field_keys)

    if clear_existing:
        for key in keys:
            st.session_state.pop(key, None)
        for key in list(st.session_state):
            if str(key).startswith(PROJECT_SCOPED_KEY_PREFIXES):
                del st.session_state[key]

    memory_project_id = (
        memory.get("active_project_id") if isinstance(memory, dict) else None
    )
    if not _is_valid_project_id(memory_project_id):
        memory_project_id = None
    existing_project_id = st.session_state.get("active_project_id")
    if clear_existing and memory_project_id is not None:
        st.session_state.active_project_id = memory_project_id
    elif memory_project_id is not None:
        if _is_valid_project_id(existing_project_id) and existing_project_id != memory_project_id:
            return
        st.session_state.setdefault("active_project_id", memory_project_id)

    drafts = memory.get("drafts", {}) if isinstance(memory, dict) else {}
    if isinstance(drafts, dict):
        for group, field_keys in DRAFT_KEY_GROUPS.items():
            group_values = drafts.get(group, {})
            if not isinstance(group_values, dict):
                continue
            for key in field_keys:
                if key in group_values:
                    st.session_state.setdefault(key, group_values[key])

    active_project_id = st.session_state.get("active_project_id")
    saved_answers = memory.get("interview_answers", {}) if isinstance(memory, dict) else {}
    if memory_project_id is not None and isinstance(saved_answers, dict) and "problem_bridge_interview_state" not in st.session_state:
        restored = start_interview()
        for key in ("domain", *REQUIRED_KEYS):
            value = saved_answers.get(key)
            if isinstance(value, str) and value.strip():
                restored = answer_question(restored, key, value)
        if restored.answers:
            st.session_state.problem_bridge_interview_state = restored
    if isinstance(memory, dict) and memory.get("last_output_dir"):
        restored_output = _validated_project_output_path(
            memory["last_output_dir"], active_project_id
        )
        if restored_output is not None:
            st.session_state.setdefault("last_output_dir", str(restored_output))
    if isinstance(memory, dict) and memory.get("last_problem_dir"):
        restored_problem = _validated_project_output_path(memory["last_problem_dir"], active_project_id)
        if restored_problem is not None and (restored_problem / "problem_record.json").is_file():
            st.session_state.setdefault("last_problem_dir", str(restored_problem))


def _current_workbench_memory() -> dict:
    interview = st.session_state.get("problem_bridge_interview_state")
    return {
        "schema_version": 3,
        "drafts": _drafts_from_session(),
        "last_output_dir": st.session_state.get("last_output_dir", ""),
        "last_problem_dir": st.session_state.get("last_problem_dir", ""),
        "active_project_id": _active_project_id(),
        "interview_answers": dict(interview.answers) if interview else {},
    }


def _active_project_id() -> str:
    project_id = st.session_state.get("active_project_id")
    if not _is_valid_project_id(project_id):
        project_id = f"project-{uuid.uuid4().hex}"
        st.session_state.active_project_id = project_id
    return project_id


def _is_valid_project_id(value: object) -> bool:
    return isinstance(value, str) and bool(
        re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", value)
    )


def _reset_active_project() -> str:
    keys = list(PROJECT_SCOPED_SESSION_KEYS)
    for field_keys in DRAFT_KEY_GROUPS.values():
        keys.extend(field_keys)
    for key in keys:
        st.session_state.pop(key, None)
    for key in list(st.session_state):
        if str(key).startswith(PROJECT_SCOPED_KEY_PREFIXES):
            del st.session_state[key]
    project_id = f"project-{uuid.uuid4().hex}"
    st.session_state.active_project_id = project_id
    st.session_state.pending_workspace_page = "Home"
    return project_id


def _resolve_safe_ui_run_root(*, create: bool = False) -> Path | None:
    """Resolve RUN_ROOT only after rejecting symlink/junction ancestors."""

    raw_root = Path(RUN_ROOT).absolute()

    def reject_reparse_ancestors() -> None:
        for candidate in (raw_root, *raw_root.parents):
            if (candidate.exists() or candidate.is_symlink()) and is_link_or_reparse(
                candidate
            ):
                raise ValueError(
                    "Configured UI run directory or one of its ancestors is linked or unsafe."
                )

    reject_reparse_ancestors()
    if not raw_root.exists():
        if not create:
            return None
        raw_root.mkdir(parents=True, exist_ok=True)
        reject_reparse_ancestors()
    if not raw_root.is_dir() or is_link_or_reparse(raw_root):
        raise ValueError("Configured UI run directory is missing or unsafe.")
    return raw_root.resolve()


def _resolve_safe_ui_run_candidate(
    out: Path, *, run_root: Path | None = None
) -> Path:
    trusted_root = run_root or _resolve_safe_ui_run_root(create=False)
    if trusted_root is None:
        raise ValueError("Configured UI run directory does not exist.")
    candidate = Path(out).absolute()
    if (
        is_internal_staging_name(candidate.name)
        or not candidate.is_dir()
        or is_link_or_reparse(candidate)
    ):
        raise ValueError("Output directory is missing, linked, or unsafe.")
    resolved = candidate.resolve()
    if resolved == trusted_root or resolved.parent != trusted_root:
        raise ValueError("Output directory must be a direct child of the configured UI run root.")
    return resolved


def _allocate_ui_run(
    prefix: str,
    *,
    project_id: str | None = None,
    owned_artifacts: tuple[str, ...] = (),
    required_artifacts: tuple[str, ...] = (),
    snapshot_directories: tuple[str, ...] = (),
    run_spec: object | None = None,
) -> RunContext:
    workflow_type = f"problem_bridge.{prefix}"
    run_root = _resolve_safe_ui_run_root(create=True)
    assert run_root is not None
    return allocate_run_directory(
        run_root,
        project_id=project_id or _active_project_id(),
        prefix=prefix,
        owned_artifacts=owned_artifacts,
        required_artifacts=required_artifacts,
        snapshot_directories=snapshot_directories,
        workflow_type=workflow_type,
        run_spec_sha256=_run_spec_sha256(workflow_type, run_spec),
    )


def _complete_ui_run(context: RunContext) -> None:
    # Writers may create nested extraction directories, so the completion
    # transaction publishes the identity-bound completion marker last and
    # hashes every present flat system artifact in its allow-list.
    with context.transaction():
        pass


def _run_spec_sha256(workflow_type: str, payload: object | None) -> str:
    canonical = json.dumps(
        {
            "workflow_type": workflow_type,
            "tool_version": problem_bridge_version,
            "payload": payload,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _adopt_project_from_run(out: Path) -> None:
    if not (out / RUN_IDENTITY_NAME).is_file():
        return
    identity = load_run_identity(out)
    st.session_state.active_project_id = str(identity["project_id"])


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


def _inject_visual_theme() -> None:
    st.markdown(
        """
        <style>
        :root {
          --pb-ink: #203632;
          --pb-muted: #60716d;
          --pb-line: #dce5e1;
          --pb-paper: #ffffff;
          --pb-canvas: #f5f8f6;
          --pb-teal: #0f766e;
          --pb-blue: #1d4ed8;
          --pb-coral: #b45309;
          --pb-soft-teal: #eaf7f5;
          --pb-soft-blue: #edf4ff;
          --pb-soft-amber: #fff7ed;
        }
        .stApp { background: var(--pb-canvas); color: var(--pb-ink); }
        [data-testid="stHeader"] {
          background: transparent !important;
          box-shadow: none !important;
        }
        [data-testid="stMainMenu"] {
          display: none !important;
        }
        [data-testid="stDeployButton"] { display: none !important; }
        [data-testid="stAppDeployButton"] { display: none !important; }
        [data-testid="stSidebar"] {
          background: linear-gradient(180deg, #ffffff 0%, #f8fbfc 100%);
          border-right: 1px solid var(--pb-line);
          color: var(--pb-ink);
        }
        [data-testid="stSidebar"][aria-expanded="true"] {
          width: 280px !important;
          min-width: 280px !important;
          max-width: 280px !important;
        }
        [data-testid="stSidebarContent"] {
          padding: 0 14px 20px !important;
        }
        [data-testid="stSidebarUserContent"] {
          padding-top: 6px;
        }
        [data-testid="stSidebar"] h3 {
          font-size: 19px;
          line-height: 1.2;
          margin-bottom: 12px;
        }
        [data-testid="stSidebar"] [data-testid="stMarkdownContainer"],
        [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] *,
        [data-testid="stSidebar"] [data-testid="stWidgetLabel"],
        [data-testid="stSidebar"] [data-testid="stWidgetLabel"] *,
        [data-testid="stSidebar"] label,
        [data-testid="stSidebar"] label * {
          color: var(--pb-ink) !important;
        }
        [data-testid="stSidebar"] [data-testid="stCaptionContainer"],
        [data-testid="stSidebar"] [data-testid="stCaptionContainer"] * {
          color: var(--pb-muted) !important;
          opacity: 1 !important;
          font-size: 14px !important;
          line-height: 1.5 !important;
        }
        [data-testid="stSidebar"] [role="radiogroup"],
        [data-testid="stSidebar"] [data-testid="stRadio"],
        [data-testid="stSidebar"] [data-testid="stCheckbox"],
        [data-testid="stSidebar"] [data-testid="stElementContainer"]:has([data-testid="stRadio"]),
        [data-testid="stSidebar"] [data-testid="stElementContainer"]:has([data-testid="stCheckbox"]) {
          width: 100% !important;
        }
        [data-testid="stSidebar"] [role="radiogroup"] {
          display: flex;
          flex-direction: column;
          gap: 4px;
        }
        [data-testid="stSidebar"] [role="radiogroup"] label[data-baseweb="radio"] {
          width: 100%;
          min-height: 34px;
          padding: 7px 10px;
          border: 1px solid transparent;
          border-radius: 8px;
          background: transparent;
          cursor: pointer;
          transition: background .16s ease, border-color .16s ease, box-shadow .16s ease;
        }
        [data-testid="stSidebar"] [role="radiogroup"] label[data-baseweb="radio"] > div:first-child {
          position: absolute !important;
          width: 1px !important;
          height: 1px !important;
          padding: 0 !important;
          margin: -1px !important;
          overflow: hidden !important;
          clip: rect(0, 0, 0, 0) !important;
          white-space: nowrap !important;
          border: 0 !important;
        }
        [data-testid="stSidebar"] [role="radiogroup"] label[data-baseweb="radio"]:hover {
          background: var(--pb-soft-teal);
        }
        [data-testid="stSidebar"] [role="radiogroup"] label[data-baseweb="radio"]:has(input:focus-visible) {
          outline: 3px solid #1d4ed8;
          outline-offset: 2px;
        }
        [data-testid="stSidebar"] [role="radiogroup"] label[data-baseweb="radio"]:has(input:checked) {
          background: #edf8f6;
          border-color: rgba(15, 118, 110, .24);
          box-shadow: inset 3px 0 0 var(--pb-teal);
        }
        [data-testid="stSidebar"] [role="radiogroup"] label[data-baseweb="radio"]:has(input:checked) [data-testid="stMarkdownContainer"],
        [data-testid="stSidebar"] [role="radiogroup"] label[data-baseweb="radio"]:has(input:checked) [data-testid="stMarkdownContainer"] * {
          color: var(--pb-teal) !important;
          font-weight: 850;
        }
        [data-testid="stSidebar"] [data-testid="stCheckbox"] label {
          width: 100%;
          min-height: 36px;
          padding: 7px 9px;
          border: 1px solid var(--pb-line);
          border-radius: 8px;
          background: #fbfdff;
          box-shadow: 0 5px 16px rgba(23, 32, 42, .04);
          transition: background .16s ease, border-color .16s ease, box-shadow .16s ease;
        }
        [data-testid="stSidebar"] [data-testid="stCheckbox"] label:hover {
          background: #ffffff;
          border-color: rgba(15, 118, 110, .28);
          box-shadow: 0 8px 20px rgba(23, 32, 42, .07);
        }
        .block-container { padding: 2rem 2.5rem 3rem; max-width: 1120px; }
        [data-testid="stMain"] h2, [data-testid="stMain"] h3 {
          color: var(--pb-ink);
          letter-spacing: -.02em;
          line-height: 1.45;
        }
        [data-testid="stMain"] h3 { font-size: 23px; }
        [data-testid="stMain"] [data-testid="stCaptionContainer"],
        [data-testid="stMain"] [data-testid="stCaptionContainer"] * { color: var(--pb-muted) !important; opacity: 1; line-height: 1.65; }
        .st-key-app_topbar { margin-bottom: 8px; }
        .st-key-app_topbar [data-testid="stHorizontalBlock"] { align-items: center; gap: 12px; }
        .app-wordmark { display: flex; align-items: center; gap: 10px; font-size: 16px; font-weight: 750; letter-spacing: -.02em; }
        .app-mark { display: grid; place-items: center; width: 30px; height: 30px; border-radius: 10px; background: var(--pb-teal); color: white; }
        .app-mark svg { width: 20px; height: 20px; }
        .st-key-unified_steps { margin: 2px 0 8px; }
        .st-key-unified_steps [role="radiogroup"] { gap: 8px; }
        .st-key-unified_steps label[data-baseweb="radio"] {
          padding: 9px 16px;
          border: 1px solid transparent;
          border-radius: 10px;
          background: transparent;
          color: var(--pb-muted);
        }
        .st-key-unified_steps label[data-baseweb="radio"] > div:first-child {
          position: absolute;
          width: 1px;
          height: 1px;
          overflow: hidden;
          opacity: 0;
        }
        .st-key-unified_steps label[data-baseweb="radio"]:has(input:checked) {
          background: var(--pb-soft-teal);
          border-color: #bddbd3;
          color: var(--pb-teal);
          box-shadow: inset 0 -2px 0 var(--pb-teal);
        }
        .st-key-unified_steps label[data-baseweb="radio"]:has(input:focus-visible) {
          outline: 3px solid #1d4ed8;
          outline-offset: 2px;
        }
        .st-key-language_control [role="radiogroup"] {
          display: flex;
          flex-direction: row;
          flex-wrap: nowrap;
          justify-content: flex-end;
          gap: 6px;
        }
        .st-key-language_control label[data-baseweb="radio"] {
          min-height: 34px;
          margin: 0 !important;
          padding: 5px 12px;
          border: 1px solid var(--pb-line);
          border-radius: 8px;
          background: #ffffff;
          color: var(--pb-ink) !important;
        }
        .st-key-language_control label[data-baseweb="radio"] > div:first-child {
          position: absolute;
          opacity: 0;
          pointer-events: none;
        }
        .st-key-language_control label[data-baseweb="radio"]:has(input:checked) {
          border-color: var(--pb-teal) !important;
          background: var(--pb-soft-teal) !important;
          color: var(--pb-teal) !important;
        }
        .st-key-language_control label[data-baseweb="radio"] * {
          color: inherit !important;
        }
        .st-key-language_control label[data-baseweb="radio"]:has(input:focus-visible) {
          outline: 3px solid #1d4ed8 !important;
          outline-offset: 2px;
        }
        .compact-shell {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 12px;
          padding: 10px 0;
          margin-bottom: 0;
          border-bottom: 1px solid var(--pb-line);
          color: var(--pb-muted);
        }
        .compact-shell strong { color: var(--pb-ink); }
        .compact-shell h1 {
          margin: 0 !important;
          padding: 0 !important;
          color: var(--pb-muted);
          font-size: 15px;
          line-height: 1.35;
          font-weight: 700;
        }
        .visual-shell {
          padding: 18px 0 6px;
          margin-bottom: 0;
        }
        .visual-eyebrow {
          color: var(--pb-teal);
          font-size: 12px;
          line-height: 1;
          font-weight: 800;
          letter-spacing: 0;
          margin-bottom: 10px;
        }
        .visual-shell h1.visual-title {
          font-size: clamp(26px, 2.4vw, 34px) !important;
          line-height: 1.35 !important;
          font-weight: 750;
          letter-spacing: -.035em;
          margin: 0 !important;
          padding: 0 !important;
          overflow-wrap: anywhere;
        }
        .visual-lead { max-width: 760px; color: var(--pb-muted); font-size: 15px; line-height: 1.7; margin: 10px 0 0; }
        .metric-row { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 10px; }
        .metric-pill {
          color: var(--pb-teal);
          font-size: 12px;
        }
        .metric-pill + .metric-pill::before { content: "·"; margin-right: 8px; color: var(--pb-muted); }
        .st-key-need_question_card {
          padding: 24px !important;
          background: var(--pb-paper);
          border: 1px solid var(--pb-line) !important;
          border-radius: 18px !important;
          box-shadow: 0 8px 30px rgba(32, 54, 50, .04);
        }
        .st-key-need_question_card h3 { padding-top: 0; font-size: 23px; }
        .question-progress { display: flex; gap: 5px; width: 104px; padding: 2px 0; }
        .question-progress span { height: 4px; flex: 1; background: #e5ece8; border-radius: 3px; }
        .question-progress .is-complete { background: var(--pb-teal); }
        .brief-guide { padding: 22px 0 18px; }
        .brief-guide .guide-kicker { margin: 0 0 10px; color: var(--pb-teal); font-size: 11px; letter-spacing: .08em; font-weight: 700; }
        .brief-guide h3 { font-size: 20px; margin: 0 0 12px; padding: 0; }
        .brief-guide-item { display: flex; gap: 12px; padding: 20px 0; border-bottom: 1px solid var(--pb-line); }
        .brief-guide-number { color: var(--pb-teal); font-size: 12px; line-height: 26px; font-weight: 700; }
        .brief-guide-item h4 { padding: 0; margin: 0 0 8px; font-size: 15px; font-weight: 650; }
        .brief-guide-item p, .brief-guide .guide-footnote { margin: 0; font-size: 13px; color: var(--pb-muted); line-height: 1.8; }
        .brief-guide .guide-footnote { padding-top: 18px; font-size: 12px; }
        .st-key-need_review_card [data-testid="stForm"] { padding: 24px !important; background: white; border-radius: 16px !important; }
        [class*="st-key-handoff_preview_"] { padding: 24px !important; background: white; border-radius: 14px !important; }
        [class*="st-key-handoff_preview_"] p, [class*="st-key-handoff_preview_"] li { line-height: 1.8; }
        [class*="st-key-handoff_preview_"] h4 { font-size: 17px; }
        [data-testid="stTabs"] [role="tablist"] { gap: 24px; }
        [data-testid="stTabs"] [role="tab"][aria-selected="true"] { color: var(--pb-teal); }
        [data-testid="stTabs"] [data-baseweb="tab-highlight"] { background-color: var(--pb-teal); }
        .st-key-workflow_steps_container {
          margin: 12px 0 22px;
        }
        .st-key-workflow_steps_container [data-testid="stHorizontalBlock"] {
          gap: 10px;
          align-items: stretch;
        }
        .st-key-workflow_steps_container [data-testid="stColumn"] {
          min-width: 0;
        }
        .workflow-step {
          min-height: 112px;
          padding: 14px;
          border: 1px solid var(--pb-line);
          border-radius: 8px;
          background: #ffffff;
          box-shadow: 0 8px 24px rgba(23, 32, 42, .04);
          transition: border-color .16s ease, box-shadow .16s ease, transform .16s ease;
        }
        .workflow-step:hover {
          border-color: rgba(15, 118, 110, .28);
          box-shadow: 0 14px 30px rgba(23, 32, 42, .08);
          transform: translateY(-1px);
        }
        .workflow-step.is-active {
          border-color: var(--pb-teal);
          background: linear-gradient(180deg, #ffffff 0%, var(--pb-soft-teal) 100%);
          box-shadow: inset 0 0 0 1px rgba(15, 118, 110, .22);
        }
        .workflow-step.is-compact {
          min-height: 70px;
          padding: 10px 12px;
        }
        .workflow-step.is-compact strong { margin-bottom: 0; font-size: 14px; }
        .workflow-current {
          display: inline-flex;
          margin-left: 6px;
          color: var(--pb-teal);
          font-size: 11px;
          font-weight: 850;
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
          box-shadow: 0 10px 28px rgba(23, 32, 42, .045);
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
        [data-testid="stAlert"],
        [data-testid="stAlert"] * {
          color: var(--pb-ink) !important;
        }
        [data-testid="stAlert"] {
          border: 1px solid #f5dfa8;
          border-left: 5px solid var(--pb-coral);
          border-radius: 8px;
          box-shadow: 0 8px 24px rgba(180, 83, 9, .08);
        }
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
        div.stButton > button, div.stDownloadButton > button, div.stFormSubmitButton > button {
          min-height: 42px;
          border-radius: 10px;
          border: 1px solid var(--pb-line);
          background: #ffffff;
          color: var(--pb-ink);
          font-weight: 600;
        }
        button[data-testid="stBaseButton-primary"], button[data-testid="stBaseButton-primaryFormSubmit"] {
          border-color: var(--pb-teal) !important;
          background: var(--pb-teal) !important;
          color: #ffffff !important;
        }
        button[data-testid="stBaseButton-primary"]:hover, button[data-testid="stBaseButton-primaryFormSubmit"]:hover {
          background: #0b615a !important;
          color: #ffffff !important;
        }
        div.stButton > button:hover, div.stDownloadButton > button:hover {
          border-color: var(--pb-teal);
          color: var(--pb-teal);
        }
        textarea, input { border-radius: 10px !important; }
        [data-testid="stTextArea"] [data-baseweb="textarea"], [data-testid="stTextInput"] [data-baseweb="input"] {
          border: 1px solid var(--pb-line);
          border-radius: 10px;
          background: #f8faf9;
        }
        [data-testid="stTextArea"] textarea, [data-testid="stTextInput"] input { background: #f8faf9; color: var(--pb-ink); }
        [data-testid="stTextArea"] [data-baseweb="textarea"]:focus-within, [data-testid="stTextInput"] [data-baseweb="input"]:focus-within {
          border-color: var(--pb-teal);
          box-shadow: 0 0 0 3px rgba(15, 118, 110, .12);
        }
        [data-testid="stExpander"] details { border-color: var(--pb-line); border-radius: 10px; background: rgba(255,255,255,.45); }
        .st-key-quick_start_demo { background: var(--pb-soft-teal); }
        [class*="st-key-home_route_card_"] { background: var(--pb-paper); }
        [class*="st-key-home_route_card_"] [data-testid="stMarkdownContainer"] p {
          min-height: 48px;
        }
        button:focus-visible, summary:focus-visible {
          outline: 3px solid var(--pb-blue) !important;
          outline-offset: 3px;
        }
        @media (max-width: 600px) {
          .block-container { padding: 3.25rem 1rem 1.5rem !important; }
          .st-key-app_topbar [data-testid="stHorizontalBlock"] { flex-wrap: nowrap; }
          .st-key-app_topbar [data-testid="stColumn"] { min-width: 0 !important; width: auto !important; flex: 1 1 auto !important; }
          .st-key-app_topbar [data-testid="stColumn"]:last-child { flex: 0 0 148px !important; }
          .st-key-language_control label[data-baseweb="radio"] { padding: 5px 9px; }
          .app-wordmark { font-size: 14px; gap: 7px; }
          .app-mark { width: 26px; height: 26px; border-radius: 8px; }
          .compact-shell { flex-wrap: wrap; }
          .visual-shell h1.visual-title { font-size: 25px !important; line-height: 1.4 !important; }
          .visual-shell .visual-lead { font-size: 14px; line-height: 1.6; }
          .visual-shell { padding: 8px 0 0; }
          .visual-eyebrow, .visual-shell .metric-row { display: none; }
          .st-key-unified_steps label[data-baseweb="radio"] { padding: 8px 11px; }
          .st-key-need_question_card { padding: 18px !important; border-radius: 14px !important; }
          .st-key-need_question_card h3 { font-size: 21px; }
          .brief-guide { padding: 6px 0 14px; }
          .st-key-need_review_card [data-testid="stForm"], [class*="st-key-handoff_preview_"] { padding: 16px !important; }
          [class*="st-key-home_route_card_"] [data-testid="stMarkdownContainer"] p { min-height: 0; }
        }
        @media (max-width: 900px) {
          .st-key-workflow_steps_container [data-testid="stHorizontalBlock"] {
            flex-direction: row;
            flex-wrap: nowrap;
            overflow-x: auto;
            scroll-snap-type: x proximity;
            padding-bottom: 4px;
          }
          .st-key-workflow_steps_container [data-testid="stColumn"] {
            width: 168px !important;
            min-width: 168px !important;
            flex: 0 0 168px !important;
            scroll-snap-align: start;
          }
          .st-key-need_layout > [data-testid="stHorizontalBlock"] { flex-wrap: wrap; }
          .st-key-need_layout > [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] { width: 100%; flex: 1 1 100%; min-width: 0; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _render_language_switcher() -> None:
    with st.container(key="app_topbar"):
        brand, language = st.columns([3, 1])
        with brand:
            st.markdown(
                '<div class="app-wordmark"><span class="app-mark" aria-hidden="true">'
                '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7">'
                '<path d="M4 18V8m16 10V8M4 14C4 4 20 4 20 14M4 14h16M8 10v4m8-4v4"/>'
                '</svg></span>ProblemBridge</div>', unsafe_allow_html=True,
            )
        with language:
            st.radio(
                _text("Interface language", "界面语言"),
                LANGUAGE_OPTIONS,
                key="language_control",
                horizontal=True,
                label_visibility="collapsed",
                on_change=_apply_language_control,
            )


def _render_shell_header() -> None:
    eyebrow = _text("ProblemBridge Workbench", "ProblemBridge 工作台")
    title = _text("Help people and AI understand what you need.", "让合作者和 AI 明白你需要什么")
    lead = _text(
        "Start with one real task. Clarify your meaning, then take a brief to a collaborator or a language model.",
        "从一件具体工作开始，逐步说清楚，再带走给合作伙伴或大模型的任务说明。",
    )
    metrics = [
        _text("No prompt-writing experience needed", "不用先学提示词"),
        _text("Start without uploading files", "没有材料也能开始"),
    ]
    metric_html = "".join(f'<span class="metric-pill">{item}</span>' for item in metrics)
    st.markdown(
        f"""
        <section class="visual-shell" aria-label="{eyebrow}">
          <h1 class="visual-title">{title}</h1>
          <p class="visual-lead">{lead}</p>
          <div class="metric-row">{metric_html}</div>
        </section>
        """,
        unsafe_allow_html=True,
    )


def _render_compact_shell_header(page: str) -> None:
    st.markdown(
        f"""
        <section class="compact-shell">
          <h1>{_page_label(page)}</h1>
          <span>{_text("Local workspace", "本地工作空间")}</span>
        </section>
        """,
        unsafe_allow_html=True,
    )


def _render_workflow_strip(active_page: str, *, compact: bool = False) -> None:
    steps = WORKFLOW_STEPS_ZH if _language_code() == "zh" else WORKFLOW_STEPS
    active_map = ACTIVE_WORKFLOW_BY_PAGE_ZH if _language_code() == "zh" else ACTIVE_WORKFLOW_BY_PAGE
    active_step = active_map.get(active_page)
    with st.container(key="workflow_steps_container"):
        columns = st.columns(len(steps))
        for column, (number, title, description) in zip(columns, steps):
            is_active = title == active_step
            css_parts = ["workflow-step"]
            if is_active:
                css_parts.append("is-active")
            if compact:
                css_parts.append("is-compact")
            css_class = " ".join(css_parts)
            aria_current = ' aria-current="step"' if is_active else ""
            current_badge = (
                f'<span class="workflow-current">{_text("Current", "当前")}</span>'
                if is_active
                else ""
            )
            description_html = "" if compact else f"<p>{description}</p>"
            with column:
                st.markdown(
                    f"""
                    <article class="{css_class}"{aria_current}>
                      <span class="step-num">{number}</span>
                      {current_badge}
                      <strong>{title}</strong>
                      {description_html}
                    </article>
                    """,
                    unsafe_allow_html=True,
                )


def _render_flow_navigation(active_page: str) -> None:
    if active_page not in WORKSPACE_FLOW_PAGES:
        return
    current_index = WORKSPACE_FLOW_PAGES.index(active_page)
    previous_page = (
        WORKSPACE_FLOW_PAGES[current_index - 1] if current_index > 0 else None
    )
    next_page = (
        WORKSPACE_FLOW_PAGES[current_index + 1]
        if current_index + 1 < len(WORKSPACE_FLOW_PAGES)
        else None
    )
    with st.container(key="flow_navigation_container"):
        previous_col, progress_col, next_col = st.columns([1, 1.1, 1])
        with previous_col:
            if previous_page is not None:
                st.button(
                    _text(
                        f"← Previous: {_page_label(previous_page)}",
                        f"← 上一步：{_page_label(previous_page)}",
                    ),
                    key=f"flow_previous_{current_index}",
                    on_click=_navigate_to_page,
                    args=(previous_page,),
                    use_container_width=True,
                )
        with progress_col:
            st.caption(
                _text(
                    f"Workflow step {current_index + 1} of {len(WORKSPACE_FLOW_PAGES)}",
                    f"工作流第 {current_index + 1}/{len(WORKSPACE_FLOW_PAGES)} 步",
                )
            )
        with next_col:
            if next_page is not None:
                st.button(
                    _text(
                        f"Next: {_page_label(next_page)} →",
                        f"下一步：{_page_label(next_page)} →",
                    ),
                    key=f"flow_next_{current_index}",
                    on_click=_navigate_to_page,
                    args=(next_page,),
                    type="secondary",
                    use_container_width=True,
                )


def _render_page_intro(title: str, body: str, trust: str, outputs: list[str]) -> None:
    st.subheader(title)
    st.write(body)
    with st.expander(_text("What you get · scope & details", "你会得到什么 · 功能说明")):
        st.markdown(f"**{_text('What you get', '你会得到什么')}**")
        for item in outputs:
            st.write(f"- {item}")
        st.markdown(f"**{_text('Trust boundary', '使用范围')}**")
        st.write(trust)


def _render_module_cards() -> None:
    cards = MODULE_CARDS_ZH if _language_code() == "zh" else MODULE_CARDS
    columns = st.columns(2)
    for index, card in enumerate(cards):
        with columns[index % 2]:
            st.markdown(
                f"""
                <article class="module-card">
                  <span class="module-stage">{card['stage']}</span>
                  <h3>{card['title']}</h3>
                  <div class="field-label">{_text('Start here if', '适合从这里开始')}</div>
                  <p>{card['start_if']}</p>
                  <div class="field-label">{_text('What you get', '你会得到什么')}</div>
                  <p>{card['what_you_get']}</p>
                </article>
                """,
                unsafe_allow_html=True,
            )

def _safety_banner(*, compact: bool = False) -> None:
    message = _text(
        "Start with synthetic examples. Do not upload private patient data, confidential manuscripts, API keys, or sensitive unpublished materials.",
        "请先使用合成样例。不要上传真实患者数据、机密文稿、API key 或敏感未公开材料。",
    )
    if compact:
        st.caption(f"🔒 {message}")
    else:
        st.warning(message)


def _home() -> None:
    root = _resolve_safe_ui_run_root(create=False) or RUN_ROOT.absolute()
    current = _last_output_path("last_problem_dir")
    if st.session_state.get("last_problem_dir") and current is None:
        st.error(_text("The current problem record is unavailable or changed. Inspect its saved run before continuing.", "当前问题记录不可用或已被修改，请先检查已保存的运行。"))
    else:
        state = st.session_state.get("problem_bridge_interview_state")
        render_workbench(
            root=root, project_id=_active_project_id(), current_out=current,
            text=_text, run_action=_run_ui_action, save_result=_save_unified_result,
            interview_answers=dict(state.answers) if state else {},
            render_downloads=_render_share_controls,
        )
    with st.expander(_text("Optional helpers · interview, file intake and earlier tools", "辅助工具 · 访谈、文件整理与原有功能")):
        _home_tools()


def _save_unified_result(out: Path, stage: int) -> None:
    st.session_state.last_problem_dir = str(out)
    st.session_state.last_output_dir = str(out)
    st.session_state.pending_unified_stage = stage
    # A confirmed problem, audit or follow-up is an explicit save action. Only
    # the validated pointer is added to memory; uploaded materials stay in runs.
    try:
        payload = _current_workbench_memory()
        save_workbench_memory(payload, MEMORY_PATH)
        st.session_state.workbench_memory = payload
        _set_flash_message("success", _text("Saved locally. Continue with the same problem.", "已保存到本地，可以围绕同一个问题继续。"))
    except OSError:
        _set_flash_message("warning", _text("The result was saved, but the workspace resume pointer could not be saved. Keep the result directory.", "结果已保存，但无法保存工作台续接位置，请保留结果目录。"))
    st.rerun()


def _continue_problem_from_interview() -> None:
    state = st.session_state.get("problem_bridge_interview_state")
    st.session_state.pending_problem_seed = interview_seed(dict(state.answers) if state else {})
    _navigate_to_page("Home")


def _home_tools() -> None:
    latest = _last_output_path("last_output_dir")
    state = st.session_state.get("problem_bridge_interview_state")
    if latest or (state and state.answers):
        with st.container(border=True):
            st.markdown(f"**{_text('Pick up where you left off', '接着上次继续')}**")
            if state and state.answers:
                count = len(REQUIRED_KEYS) - len(summarize_understanding(state).missing_items)
                st.button(
                    _text(f"Continue interview · {count}/5 answers saved", f"继续梳理 · 已回答 {count}/5 项"),
                    key="home_resume_interview", on_click=_navigate_to_page,
                    args=("Domain practitioner wizard",), use_container_width=True,
                )
            if latest:
                st.button(
                    _text("Open my latest result", "打开最近一次结果"),
                    key="home_resume_result", on_click=_navigate_to_page,
                    args=("View generated outputs",), use_container_width=True,
                )
    with st.container(border=True, key="quick_start_demo"):
        copy_col, action_col = st.columns([2, 1])
        with copy_col:
            st.markdown(f"**{_text('First time? See a finished example.', '第一次用？先看一份实际结果。')}**")
            st.caption(_text(
                "Run the synthetic quality-inspection example locally. Nothing to upload or configure.",
                "用合成的质检示例走通流程，无需上传文件或配置。",
            ))
        with action_col:
            if st.button(_text("Run a sample now", "一键体验示例"), key="home_run_example", type="primary", use_container_width=True):
                out = _run_ui_action(
                    _text("Preparing your example result…", "正在生成示例结果……"),
                    lambda: _run_problem_text(EXAMPLES["Quality inspection"].read_text(encoding="utf-8"), "example_quality_inspection"),
                )
                if out:
                    st.session_state.pending_workspace_page = "View generated outputs"
                    _set_flash_message("success", _text("Synthetic example ready. Review the summary, then try your own workflow.", "合成示例已生成。先看摘要，再试着描述自己的工作。"))
                    st.rerun()

    st.subheader(_text("What would you like to do?", "你现在想做什么？"))
    route_cards = [
        (_text("I have a question", "有困惑，还没想清楚"), _text("Describe what feels unclear. Get questions to ask and people to consult.", "写下不清楚的地方，得到值得追问的问题和该咨询的人。"), "Question discovery", _text("Clarify my question", "帮我理清问题")),
        (_text("I want to improve a workflow", "有工作流程，想改进"), _text("Answer five short questions. Get a workflow brief and review boundaries.", "回答 5 个简短问题，整理工作流程和需要人工判断的环节。"), "Domain practitioner wizard", _text("Describe my work", "开始梳理工作")),
        (_text("I have files to organize", "有现成材料，想整理"), _text("Bring documents or paste text. Inspect the extracted text and tables.", "上传文档或直接粘贴文字，检查提取的正文与表格。"), "Document intake", _text("Start with files", "从文件开始")),
    ]
    col1, col2, col3 = st.columns(3)
    for index, (column, (title, body, destination, button_label)) in enumerate(zip([col1, col2, col3], route_cards)):
        with column:
            with st.container(border=True, key=f"home_route_card_{index}"):
                st.markdown(f"**{title}**")
                st.write(body)
                st.button(
                    button_label,
                    key=f"home_route_{index}",
                    on_click=_navigate_to_page,
                    args=(destination,),
                    use_container_width=True,
                )
    st.caption(_text("Choose any starting point. You do not have to complete every tool.", "按需要选择入口，无需依次走完所有工具。"))
    with st.expander(_text("How the tools connect", "了解完整流程与工具")):
        _render_workflow_strip("Home", compact=True)
        st.write(_text(
            "The workbench connects problem framing, local claim–evidence checks and follow-up questions in one saved problem. The CLI and optional tools remain available.",
            "工作台把问题梳理、本地声明与证据核查、后续追问连接在同一份问题记录中。命令行和辅助工具仍可单独使用。",
        ))
        _render_module_cards()

def _examples() -> None:
    _render_page_intro(
        _text("Explore synthetic examples", "查看合成示例"),
        _text(
            "Generate a complete sample package before testing your own material, so reviewers can see the expected outputs first.",
            "先生成一个完整样例包，再测试自己的材料；这样测试者能先看到预期输出长什么样。",
        ),
        _text(
            "Examples are synthetic and are for demonstration only. Do not infer deployment claims from them.",
            "示例都是合成材料，只用于演示结构，不代表真实部署结论。",
        ),
        [
            _text("Friendly summary", "面向用户的摘要"),
            "ProblemBridge technical files",
            _text("Downloadable example package", "可下载示例包"),
        ],
    )
    choice = st.selectbox(_text("Choose a synthetic example", "选择一个合成示例"), list(EXAMPLES))
    problem_path = EXAMPLES[choice]
    st.text_area(_text("Example problem brief", "示例问题 brief"), problem_path.read_text(encoding="utf-8"), height=220)

    generated_out = None
    if st.button(
        _text("Generate this example package", "生成这个示例包"),
        type="primary",
    ):
        generated_out = _run_ui_action(
            _text("Generating the synthetic example…", "正在生成合成示例……"),
            lambda: _run_problem_text(
                problem_path.read_text(encoding="utf-8"),
                f"example_{_slug(choice)}",
            ),
        )
    display_out = generated_out or _last_output_path("last_example_dir")
    if display_out:
        if generated_out:
            st.success(_generated_message(display_out))
        else:
            st.info(_text("Most recent example result is shown below.", "下方显示最近一次示例结果。"))
        _render_friendly_output(display_out)


def _question_discovery() -> None:
    _render_page_intro(
        _text("Question discovery", "问题发现"),
        _text(
            "Use this when you do not yet know what to ask, who to ask, or whether the issue is an AI task.",
            "当你还不知道该问什么、该问谁，甚至不确定这是不是 AI 任务时，从这里开始。",
        ),
        _text(
            "Do not propose a solution yet. First discover what to ask and who to ask.",
            "先不要急着提出方案。先找出值得问的问题，以及应该找哪些专业人士回答。",
        ),
        ["question_brief.md", "stakeholder_map.md", "expert_interview_guide.md", "unknowns_to_validate.md", "discussion_plan.md"],
    )

    with st.form("question_discovery"):
        seed_text = st.text_area(
            _text("What are you trying to understand?", "你现在想理解什么？"),
            placeholder=_text(
                "Example: Our review process is slow, but I do not know which part is the real problem.",
                "例：我们的审核流程很慢，但我不知道真正的问题在哪一步。",
            ),
            height=120,
            key="question_seed_text",
        )
        uncertainty = st.text_area(
            _text("What feels unclear right now?", "现在最不清楚的地方是什么？"),
            placeholder=_text(
                "Example: I do not know whether to ask the practitioner, supervisor, data owner, or AI engineer first.",
                "例：我不知道应该先问一线从业者、负责人、数据所有者，还是 AI 工程师。",
            ),
            height=90,
            key="question_uncertainty",
        )
        desired_change = st.text_area(
            _text("What would a useful first conversation achieve?", "一次有用的初步沟通应该达成什么？"),
            placeholder=_text(
                "Example: Leave with better questions, a short list of experts to interview, and unknowns to validate.",
                "例：得到更好的问题、要访谈的专家名单，以及需要验证的未知项。",
            ),
            height=90,
            key="question_desired_change",
        )
        submitted = st.form_submit_button(
            _text("Generate question discovery package", "生成问题发现包"),
            type="primary",
        )

    if submitted:
        missing = _missing_required_fields(
            {
                _text("what you are trying to understand", "想理解的问题"): seed_text,
                _text("a useful first-conversation outcome", "初步沟通目标"): desired_change,
            }
        )
        if missing:
            _render_required_fields_error(missing)
        else:
            package = discover_questions(seed_text, uncertainty, desired_change)
            out = _run_ui_action(
                _text("Generating question discovery…", "正在生成问题发现结果……"),
                lambda: _run_question_discovery(package),
            )
            if out:
                st.success(_generated_message(out))
                _render_question_discovery_output(out)
    else:
        previous_out = _last_output_path("last_question_discovery_dir")
        if previous_out:
            _render_previous_result_card(
                previous_out,
                _render_question_discovery_output,
                key_suffix="question-discovery",
                label=_text("question discovery result", "问题发现结果"),
            )


def _render_question_discovery_output(out: Path) -> None:
    st.success(
        _text(
            "Question discovery is ready. Review the questions with domain experts before defining an AI task.",
            "问题发现结果已生成。定义 AI 任务前，请先与领域专家核对这些问题。",
        )
    )
    st.subheader(_text("Next step", "下一步"))
    st.write(
        _text(
            "Take this package to domain experts first. After the questions are validated, use Domain practitioner wizard to generate a ProblemBridge alignment package.",
            "先把这个包带给领域专家确认。问题被验证后，再使用领域工作流向导生成 ProblemBridge 对齐包。",
        )
    )
    st.button(
        _text("Continue to Domain practitioner wizard", "继续到领域工作流向导"),
        key=f"continue_to_domain_wizard_{out.name}",
        on_click=_continue_to_domain_wizard_from_discovery,
        args=(out,),
        type="primary",
        use_container_width=True,
    )

    with st.expander(_text("Review questions and stakeholders", "查看问题与相关人员"), expanded=True):
        st.subheader(_text("Questions to validate", "需要验证的问题"))
        brief_path = out / "question_brief.md"
        if brief_path.is_file():
            st.markdown(brief_path.read_text(encoding="utf-8"))

        st.subheader(_text("Who to ask", "应该问谁"))
        stakeholder_path = out / "stakeholder_map.md"
        if stakeholder_path.is_file():
            st.markdown(stakeholder_path.read_text(encoding="utf-8"))

    _render_share_controls(out, "question discovery")
    _render_report_export_buttons(out)

    with st.expander(_text("All discovery files", "全部问题发现文件")):
        for filename, label in QUESTION_DISCOVERY_FILES.items():
            path = out / filename
            if path.is_file():
                st.markdown(f"### {label}")
                st.caption(filename)
                st.code(path.read_text(encoding="utf-8"), language="markdown")

def _document_intake() -> None:
    _render_page_intro(
        _text("Document intake", "文档摄取"),
        _text(
            "Upload Word, PDF, HTML, Markdown, TXT, CSV, or image files, or add public static webpage URLs, and convert them into local extraction outputs.",
            "上传 Word、PDF、HTML、Markdown、TXT、CSV 或图片文件，也可添加公开静态网页 URL，并转成本地可检查的提取结果。",
        ),
        _text(
            "Supports .docx, .html, .htm, .md, .txt, .csv, text-based PDF, public static http(s) URLs, and optional local OCR for images or image-only PDFs. Legacy .doc uploads only return conversion guidance. No login pages, JavaScript execution, crawling, image understanding, or figure interpretation.",
            "支持 .docx、.html、.htm、.md、.txt、.csv、文字版 PDF、公开静态 http(s) URL，以及图片或纯扫描 PDF 的可选本地 OCR。.doc 旧版 Word 上传后只返回转换提示。不执行登录网页、JavaScript、爬取、图片语义理解或图表解释。",
        ),
        [
            "extracted_text.md",
            "annotation_map.json",
            "highlighted_spans.csv",
            "comment_threads.md",
            "priority_marks.md",
            "extracted_tables/",
            "source_manifest.json",
            "extraction_warnings.md",
            "problem_seed.md",
        ],
    )
    st.caption(
        _text(
            "DOCX comments, PDF annotations, highlighted spans, and font-color marks are extracted as annotation signals when available.",
            "可用时会提取 DOCX 批注、PDF 批注、高亮文本和字体颜色，作为标注信号。",
        )
    )

    uploaded_files = st.file_uploader(
        _text("Upload Word, PDF, HTML, Markdown, TXT, CSV, or image files", "上传 Word、PDF、HTML、Markdown、TXT、CSV 或图片文件"),
        type=["doc", "docx", "pdf", "html", "htm", "md", "txt", "csv", "png", "jpg", "jpeg", "tif", "tiff", "bmp"],
        accept_multiple_files=True,
    )
    pasted_text = st.text_area(
        _text("Paste text here if upload does not work", "如果上传按钮无法使用，可以把文本粘贴到这里"),
        placeholder=_text(
            "Optional fallback: paste copied document or webpage text here.",
            "备用输入：可以粘贴复制出来的文档或网页正文。",
        ),
        key="manual_upload_fallback_text",
    )
    st.caption(
        _text(
            "Fallback pasted text is saved as manual_upload_fallback.md in the generated package.",
            "粘贴文本会保存为生成包里的 manual_upload_fallback.md。",
        )
    )
    urls_text = st.text_area(
        _text("Public static webpage URLs, one per line", "公开静态网页 URL，每行一个"),
        placeholder="https://example.org/workflow-guide",
        key="document_intake_urls",
    )
    enable_ocr = st.checkbox(
        _text("Enable optional OCR for images and image-only PDFs", "启用图片和图片型 PDF 的可选 OCR"),
        value=False,
        help=_text(
            "OCR runs locally only if optional OCR dependencies and system tools are installed. No API key is required.",
            "OCR 只在本机安装了可选 OCR 依赖和系统工具时运行，不需要 API key。",
        ),
    )
    ocr_language = "eng"
    if enable_ocr:
        ocr_language = st.selectbox(
            _text("OCR language", "OCR 语言"),
            options=["eng", "chi_sim", "eng+chi_sim"],
            index=2 if _language_code() == "zh" else 0,
            help=_text(
                "The selected Tesseract language pack must be installed locally.",
                "所选 Tesseract 语言包必须已安装在本机。",
            ),
        )
    urls = [line.strip() for line in urls_text.splitlines() if line.strip()]
    pasted_text = pasted_text.strip()

    generated_out = None
    if st.button(
        _text("Generate document intake package", "生成文档摄取包"),
        disabled=not uploaded_files and not urls and not pasted_text,
        type="primary",
    ):
        out = _run_ui_action(
            _text("Extracting and verifying local sources…", "正在提取并验证本地材料……"),
            lambda: _run_document_intake(
                uploaded_files or [],
                urls=urls,
                enable_ocr=enable_ocr,
                ocr_language=ocr_language,
                pasted_text=pasted_text,
            ),
        )
        if out:
            st.success(_generated_message(out))
            _render_document_intake_output(out)
            generated_out = out

    if generated_out is None:
        previous_out = _last_output_path("last_document_intake_dir")
        if previous_out:
            _render_previous_result_card(
                previous_out,
                _render_document_intake_output,
                key_suffix="document-intake",
                label=_text("document intake result", "文档摄取结果"),
            )


def _render_document_intake_output(out: Path) -> None:
    st.success(
        _text(
            "Document extraction is complete. Check the context and warnings before continuing.",
            "文档提取已完成。继续前请检查提取上下文和警告。",
        )
    )
    warnings_text = _read_output_text(out, "extraction_warnings.md").strip()
    if warnings_text and "No extraction warnings" not in warnings_text:
        st.warning(warnings_text)
    else:
        st.caption(_text("No extraction warnings were reported.", "没有报告提取警告。"))

    st.subheader(_text("Next step", "下一步"))
    st.write(
        _text(
            "Use the extracted problem seed as the starting point for Question discovery. Review and edit it there before generating questions.",
            "把提取出的 problem seed 带入问题发现。进入下一步后，请先检查和修改，再生成问题。",
        )
    )
    st.button(
        _text("Continue to Question discovery", "继续到问题发现"),
        key=f"continue_to_question_discovery_{out.name}",
        on_click=_continue_to_question_discovery_from_intake,
        args=(out,),
        type="primary",
        use_container_width=True,
    )

    problem_seed = out / "problem_seed.md"
    if problem_seed.is_file():
        with st.expander(_text("Review extracted problem context", "检查提取的问题上下文"), expanded=True):
            st.markdown(problem_seed.read_text(encoding="utf-8"))

    _render_share_controls(out, "document intake", allow_source_files=True)
    _render_report_export_buttons(out)

    with st.expander(_text("All intake files", "全部摄取文件")):
        for filename, label in DOCUMENT_INTAKE_FILES.items():
            path = out / filename
            if path.is_file():
                st.markdown(f"### {label}")
                st.caption(filename)
                st.code(path.read_text(encoding="utf-8"), language=_language_for(filename))
        table_dir = out / "extracted_tables"
        if table_dir.is_dir():
            for table_path in sorted(table_dir.glob("*.csv")):
                st.markdown(f"### {_text('Extracted table', '提取表格')}: {table_path.name}")
                st.code(table_path.read_text(encoding="utf-8"), language="csv")


def _domain_wizard() -> None:
    _render_page_intro(
        _text("Describe your work, one question at a time", "一次回答一个问题，把工作说清楚"),
        _text(
            "Answer five short questions to get a workflow brief. You can revise any saved answer along the way.",
            "回答 5 个简短问题，得到一份工作流程说明。已回答的内容随时可以修改。",
        ),
        _text(
            "This page captures workflow understanding. It does not decide what should be automated or replace professional judgement.",
            "这个页面只用于理解工作流，不决定什么应该被自动化，也不替代专业判断。",
        ),
        [
            _text("Guided interview state", "引导式访谈状态"),
            _text("Workflow-first problem brief", "工作流优先的问题 brief"),
            "ProblemBridge alignment package",
            _text("Download package", "下载结果包"),
        ],
    )

    with st.expander(_text("Interview mode", "填写方式与访谈提示")):
        mode = st.segmented_control(
            _text("Choose an input mode", "选择填写方式"),
            ["guided", "advanced"],
            default="guided",
            format_func=lambda value: (
                _text("Guided interview", "引导式访谈")
                if value == "guided"
                else _text("Advanced full form", "高级完整表单")
            ),
            key="domain_input_mode",
            selection_mode="single",
            required=True,
        )
        st.write(_text(
            "Use this mode when you are helping someone else describe their workflow.",
            "当你在帮助别人描述工作流时，可以用这套访谈提醒。",
        ))
        st.markdown(
            _text(
                """
                - Do not ask for an AI task first.
                - Ask what people repeatedly inspect, decide, organize, or write.
                - Ask what materials they use when making the judgement.
                - Ask which step is slow, ambiguous, error-prone, or expert-dependent.
                - Ask what must stay under human confirmation.
                """,
                """
                - 不要一开始就问“你想做什么 AI”。
                - 先问对方反复检查、判断、整理或撰写什么。
                - 再问做判断时依赖哪些材料。
                - 再问哪一步慢、模糊、容易出错或依赖专家。
                - 最后问哪些决定必须保留人工确认。
                """,
            )
        )

    if st.session_state.get("interview_seed_source"):
        st.info(
            _text(
                "Question discovery supplied a provisional description of the repeated work. Confirm the remaining workflow, evidence, and human-boundary questions in the interview.",
                "问题发现仅提供了暂定的反复工作描述。请在访谈中继续确认工作流、证据材料和人工边界。",
            )
        )
    if mode == "guided":
        generated_out = _guided_interview()
        if generated_out is None:
            previous_out = _last_output_path("last_alignment_package_dir")
            if previous_out:
                _render_previous_result_card(
                    previous_out,
                    _render_workflow_alignment_result,
                    key_suffix="guided-alignment",
                    label=_text("workflow alignment result", "工作流对齐结果"),
                )
        return

    st.divider()
    st.subheader(_text("Advanced: full workflow form", "高级：完整工作流表单"))
    st.caption(_text(
        "Use this manual form when you already know the workflow details.",
        "当你已经比较清楚工作流细节时，可以直接填写这个表单。",
    ))

    with st.form("domain_practitioner"):
        st.subheader(_text("Section A: repeated work", "A 部分：反复发生的工作"))
        answers = {
            "domain": st.text_input(_text("What field or setting is this in?", "这项工作属于什么领域或场景？"), key="domain_draft_domain"),
            "repeated_work": st.text_area(_text("What is one task people repeatedly do?", "人们反复在做的一项任务是什么？"), key="domain_draft_repeated_work"),
            "current_owner": st.text_input(_text("Who currently does this task?", "现在是谁在做这项任务？"), key="domain_draft_current_owner"),
            "result": st.text_input(_text("What result does the task produce?", "这项任务会产出什么结果？"), key="domain_draft_result"),
        }
        st.caption(_text(
            "Examples: review images, organize lab notes, inspect reports, grade work, summarize cases, prepare expert questions.",
            "例：看图像、整理实验记录、检查报告、批改作业、总结案例、准备专家问题。",
        ))

        st.subheader(_text("Section B: workflow steps", "B 部分：工作流步骤"))
        answers.update(
            {
                "step_1": st.text_input(_text("Step 1", "步骤 1"), key="domain_draft_step_1"),
                "step_2": st.text_input(_text("Step 2", "步骤 2"), key="domain_draft_step_2"),
                "step_3": st.text_input(_text("Step 3", "步骤 3"), key="domain_draft_step_3"),
                "step_4": st.text_input(_text("Step 4", "步骤 4"), key="domain_draft_step_4"),
                "additional_notes": st.text_area(_text("Additional notes", "补充说明"), key="domain_draft_additional_notes"),
            }
        )

        st.subheader(_text("Section C: friction and judgement", "C 部分：卡点与判断"))
        answers.update(
            {
                "time_consuming_step": st.text_area(_text("Which step is most time-consuming?", "哪一步最耗时？"), key="domain_draft_time_consuming_step"),
                "annoying_step": st.text_area(_text("Which step is most annoying or repetitive?", "哪一步最重复、最烦或最机械？"), key="domain_draft_annoying_step"),
                "error_prone_step": st.text_area(_text("Which step is most error-prone?", "哪一步最容易出错？"), key="domain_draft_error_prone_step"),
                "expert_judgement_step": st.text_area(_text("Which step depends most on expert judgement?", "哪一步最依赖专家判断？"), key="domain_draft_expert_judgement_step"),
            }
        )

        st.subheader(_text("Section D: judgement materials", "D 部分：判断材料"))
        answers.update(
            {
                "materials": st.multiselect(
                    _text("What materials do people use?", "人们会使用哪些材料？"),
                    MATERIAL_OPTIONS_ZH if _language_code() == "zh" else MATERIAL_OPTIONS,
                    key="domain_draft_materials",
                ),
                "critical_materials": st.text_area(_text("Which materials are most critical?", "哪些材料最关键？"), key="domain_draft_critical_materials"),
                "missing_materials": st.text_area(_text("Which materials are often missing, unclear, or hard to organize?", "哪些材料经常缺失、不清楚或难整理？"), key="domain_draft_missing_materials"),
            }
        )

        st.subheader(_text("Section E: human boundaries", "E 部分：人工边界"))
        answers.update(
            {
                "never_automated": st.text_area(_text("What should AI never decide automatically?", "哪些事情不应该让 AI 自动决定？"), key="domain_draft_never_automated"),
                "human_confirmed": st.text_area(_text("What must be confirmed by a human?", "哪些内容必须由人确认？"), key="domain_draft_human_confirmed"),
                "serious_mistakes": st.text_area(_text("What mistakes would be serious?", "哪些错误会造成严重后果？"), key="domain_draft_serious_mistakes"),
                "useful_support": st.multiselect(
                    _text("If AI only supported the work, what output would be useful?", "如果 AI 只做辅助，哪些输出会有用？"),
                    SUPPORT_OPTIONS_ZH if _language_code() == "zh" else SUPPORT_OPTIONS,
                    key="domain_draft_useful_support",
                ),
            }
        )
        submitted = st.form_submit_button(
            _text("Generate workflow alignment package", "生成工作流对齐包"),
            type="primary",
        )

    if submitted:
        missing = _missing_required_fields(
            {
                _text("the repeated work", "反复发生的工作"): answers["repeated_work"],
                _text("the current task owner", "当前任务负责人"): answers["current_owner"],
                _text("a non-automatable decision", "不可自动化的决定"): answers["never_automated"],
            }
        )
        if missing:
            _render_required_fields_error(missing)
        else:
            problem_text = build_workflow_first_problem(answers)
            out = _run_ui_action(
                _text("Generating workflow alignment…", "正在生成工作流对齐结果……"),
                lambda: _run_problem_text(problem_text, "domain_practitioner"),
            )
            if out:
                st.success(_generated_message(out))
                st.download_button(_text("Download problem.md", "下载 problem.md"), problem_text, file_name="problem.md")
                _render_alignment_next_step(out)
                _render_friendly_output(out)
    else:
        previous_out = _last_output_path("last_alignment_package_dir")
        if previous_out:
            _render_previous_result_card(
                previous_out,
                _render_workflow_alignment_result,
                key_suffix="advanced-alignment",
                label=_text("workflow alignment result", "工作流对齐结果"),
            )

def _edit_interview_answer(key: str) -> None:
    if key not in REQUIRED_KEYS:
        raise ValueError("Unknown interview question")
    state = st.session_state.problem_bridge_interview_state
    st.session_state.interview_editing_key = key
    st.session_state[f"interview_answer_{key}"] = state.answers.get(key, "")


def _guided_interview() -> Path | None:
    generated_out: Path | None = None

    if "problem_bridge_interview_state" not in st.session_state:
        st.session_state.problem_bridge_interview_state = start_interview()

    state = st.session_state.problem_bridge_interview_state
    summary = summarize_understanding(state)
    editing_key = st.session_state.get("interview_editing_key")
    question = next((item for item in QUESTION_FLOW if item.key == editing_key), summary.next_question)
    answered = len(REQUIRED_KEYS) - len(summary.missing_items)
    st.progress(summary.completeness, text=_text(f"{answered}/5 answers saved · review before generating", f"已回答 {answered}/5 项 · 生成前可再次核对"))
    if answered:
        st.button(_text("Continue with this problem in the workbench", "把回答带到问题工作台继续"),
                  key="interview_to_workbench", on_click=_continue_problem_from_interview,
                  type="secondary")

    left, right = st.columns([1.35, 1])
    with left:
        if question.key in REQUIRED_KEYS:
            position = REQUIRED_KEYS.index(question.key) + 1
            st.caption(_text(f"Question {position} of 5", f"第 {position}/5 问"))
        st.write(_interview_copy(question, "prompt"))
        st.caption(_interview_copy(question, "helper"))

        if question.key != "confirmation":
            answer = st.text_area(
                _text("Your answer", "你的回答"),
                key=f"interview_answer_{question.key}",
                placeholder=_text(*INTERVIEW_EXAMPLES[question.key]),
                height=130,
            )
            if st.button(
                _text("Save answer and continue", "保存回答并继续"),
                key="interview_save_answer",
                type="primary",
            ):
                if not answer.strip():
                    st.error(_text("Add an answer before continuing.", "请填写回答后再继续。"))
                else:
                    st.session_state.problem_bridge_interview_state = answer_question(state, question.key, answer)
                    st.session_state.pop("interview_editing_key", None)
                    _set_flash_message("success", _text("Answer saved. You can edit it in the summary.", "回答已保存，可以在摘要中修改。"))
                    st.rerun()
        else:
            st.success(_text(
                "The core workflow understanding is complete enough to generate an alignment package.",
                "核心工作流信息已经足够生成对齐包。",
            ))
            edit_fields = [
                ("repeated_work", _text("Repeated work", "反复发生的工作")),
                ("materials", _text("Judgement materials", "判断材料")),
                ("pain_points", _text("Pain points", "痛点")),
                ("human_boundaries", _text("Human review boundaries", "人工复核边界")),
                ("useful_support", _text("Useful support outputs", "有用的辅助输出")),
            ]
            with st.expander(_text("Review or edit answers", "检查或修改答案"), expanded=False):
                with st.form("interview_edit_form"):
                    edited_answers = {
                        key: st.text_area(
                            label,
                            value=state.answers.get(key, ""),
                            key=f"interview_edit_{key}",
                        )
                        for key, label in edit_fields
                    }
                    apply_edits = st.form_submit_button(
                        _text("Apply answer edits", "应用答案修改")
                    )
                if apply_edits:
                    missing = _missing_required_fields(
                        {label: edited_answers[key] for key, label in edit_fields}
                    )
                    if missing:
                        _render_required_fields_error(missing)
                    else:
                        updated = start_interview()
                        if state.answers.get("domain"):
                            updated = answer_question(updated, "domain", state.answers["domain"])
                        for key, _label in edit_fields:
                            updated = answer_question(updated, key, edited_answers[key])
                        st.session_state.problem_bridge_interview_state = updated
                        _set_flash_message("success", _text("Interview answers updated.", "访谈答案已更新。"))
                        st.rerun()

        reset_col, generate_col = st.columns(2)
        with reset_col:
            if not st.session_state.get("confirm_interview_reset"):
                if st.button(_text("Reset guided interview", "重置访谈"), key="interview_reset"):
                    st.session_state.confirm_interview_reset = True
                    st.rerun()
            else:
                st.warning(
                    _text(
                        "Resetting removes the current interview answers.",
                        "重置会清除当前访谈答案。",
                    )
                )
                if st.button(
                    _text("Confirm interview reset", "确认重置访谈"),
                    key="confirm_interview_reset_button",
                ):
                    st.session_state.problem_bridge_interview_state = start_interview()
                    st.session_state.pop("interview_editing_key", None)
                    st.session_state.pop("interview_seed_source", None)
                    st.session_state.pop("confirm_interview_reset", None)
                    for key in list(st.session_state):
                        if str(key).startswith(("interview_answer_", "interview_edit_")):
                            del st.session_state[key]
                    _set_flash_message("success", _text("Guided interview reset.", "引导式访谈已重置。"))
                    st.rerun()
                if st.button(
                    _text("Cancel reset", "取消重置"),
                    key="cancel_interview_reset",
                ):
                    st.session_state.pop("confirm_interview_reset", None)
                    st.rerun()
        with generate_col:
            ready = is_ready_for_alignment(state)
            if ready and not editing_key and st.button(
                _text("Generate alignment package from interview", "根据访谈生成对齐包"),
                key="interview_generate",
                type="primary",
            ):
                problem_text = build_problem_from_interview(state)
                generated_out = _run_ui_action(
                    _text("Generating workflow alignment…", "正在生成工作流对齐结果……"),
                    lambda: _run_problem_text(problem_text, "guided_interview"),
                )
                if generated_out:
                    st.success(_generated_message(generated_out))
                    st.download_button(_text("Download guided_interview_problem.md", "下载 guided_interview_problem.md"), problem_text, file_name="problem.md")
                    _render_alignment_next_step(generated_out)
                    _render_friendly_output(generated_out)
            if not ready:
                st.caption(_text(f"{5 - answered} answers to go before your brief is ready.", f"再回答 {5 - answered} 项，就可以生成工作流程说明。"))

    with right:
        st.markdown(f"### {_text('Understanding so far', '当前理解')}")
        if summary.known_items:
            for key in REQUIRED_KEYS:
                if not state.answers.get(key):
                    continue
                label = _display_missing_item({"repeated_work": "repeated work", "human_boundaries": "human review boundaries", "useful_support": "useful support outputs"}.get(key, key.replace("_", " ")))
                with st.expander(label, expanded=False):
                    st.write(state.answers[key])
                    st.button(
                        _text(f"Edit {label}", f"修改：{label}"),
                        key=f"interview_edit_button_{key}",
                        on_click=_edit_interview_answer, args=(key,),
                    )
        else:
            st.caption(_text("Your saved answers will appear here. Short, concrete sentences are enough.", "保存的回答会出现在这里。先写简短、具体的一句话就好。"))
        if not summary.missing_items:
            st.success(_text("No core fields missing.", "核心字段已填写完整。"))
        st.caption(_text("To continue after closing the browser, save under Drafts & project settings.", "关闭浏览器前，可在「草稿与项目设置」中保存当前工作台，下次继续。"))

    return generated_out


def _ai_wizard() -> None:
    _render_page_intro(
        _text("AI practitioner wizard", "AI 任务对齐向导"),
        _text(
            "Use this when an AI task already exists and you need to check whether it still matches the original domain problem.",
            "当你已经有一个候选 AI 任务，并需要检查它是否仍然贴合原始领域问题时，使用这个页面。",
        ),
        _text(
            "This page is a misalignment check. It does not prove feasibility, safety, deployment readiness, or domain correctness.",
            "这个页面只做错位风险检查，不证明可行性、安全性、部署就绪或领域正确性。",
        ),
        [
            _text("AI-task problem brief", "AI 任务问题 brief"),
            _text("Misalignment risks", "错位风险"),
            "Evidence contract",
            "Evaluation protocol",
        ],
    )
    if st.session_state.get("ai_seed_source_dir"):
        st.info(
            _text(
                "This form was prefilled with a structured summary from the previous alignment package. Review each field before running the check; the original technical files remain unchanged.",
                "此表单已使用上一步对齐包的结构化摘要预填。运行检查前请逐项确认；原始技术文件不会被修改。",
            )
        )
    with st.form("ai_practitioner"):
        answers = {
            "domain_problem": st.text_area(_text("What domain problem are you trying to solve?", "你想解决的领域问题是什么？"), key="ai_draft_domain_problem"),
            "candidate_task": st.text_area(_text("What AI task are you considering?", "你正在考虑什么 AI 任务？"), key="ai_draft_candidate_task"),
            "inputs": st.text_area(_text("What inputs will the system use?", "系统会使用哪些输入？"), key="ai_draft_inputs"),
            "outputs": st.text_area(_text("What outputs should the system produce?", "系统应该产生什么输出？"), key="ai_draft_outputs"),
            "metric": st.text_area(_text("How would you evaluate success?", "你会如何评价是否成功？"), key="ai_draft_metric"),
            "user": st.text_area(_text("Who will use or review the output?", "谁会使用或复核输出？"), key="ai_draft_user"),
            "high_risk_mistakes": st.text_area(_text("Which mistakes would cause serious consequences?", "哪些错误会造成严重后果？"), key="ai_draft_high_risk_mistakes"),
        }
        submitted = st.form_submit_button(
            _text("Check task alignment", "检查任务是否对齐"),
            type="primary",
        )

    if submitted:
        missing = _missing_required_fields(
            {
                _text("the domain problem", "领域问题"): answers["domain_problem"],
                _text("the candidate AI task", "候选 AI 任务"): answers["candidate_task"],
                _text("the intended inputs", "预期输入"): answers["inputs"],
                _text("the intended outputs", "预期输出"): answers["outputs"],
                _text("high-risk mistakes", "高风险错误"): answers["high_risk_mistakes"],
            }
        )
        if missing:
            _render_required_fields_error(missing)
        else:
            problem_text = build_ai_practitioner_problem(answers)
            out = _run_ui_action(
                _text("Checking task alignment…", "正在检查任务对齐……"),
                lambda: _run_problem_text(problem_text, "ai_practitioner"),
            )
            if out:
                st.success(_generated_message(out))
                st.download_button(_text("Download problem.md", "下载 problem.md"), problem_text, file_name="problem.md")
                _render_evidence_gate_next_step(out)
                _render_friendly_output(out)
    else:
        previous_out = _last_output_path("last_ai_alignment_dir")
        if previous_out:
            _render_previous_result_card(
                previous_out,
                _render_ai_alignment_result,
                key_suffix="ai-alignment",
                label=_text("AI alignment result", "AI 对齐结果"),
            )

def _evidence_gated_build() -> None:
    _render_page_intro(
        _text("Evidence-gated build", "证据门控构建"),
        _text(
            "Turn a completed alignment package into candidate capability claims, gate every claim against approved workflow evidence, and export a Codex-ready implementation contract.",
            "把已完成的对齐包转成候选能力声明，逐条对照获准的工作流证据进行门控，再导出可交给 Codex 的实现契约。",
        ),
        _text(
            "Workflow evidence supports bounded design intent, not real-world accuracy. Remote mode sends the selected synthetic or non-sensitive problem brief to OpenAI; the API key stays in the environment and is never saved.",
            "工作流证据只能支持有边界的设计意图，不能证明真实准确率。远程模式会把所选的合成或非敏感问题 brief 发送给 OpenAI；API 密钥只保留在环境变量中，绝不会写入文件。",
        ),
        [
            "claim_decisions.csv",
            "build_contract.md",
            "gpt_5_6_runtime.json",
            "build_record.jsonl",
            "codex_handoff/",
        ],
    )
    candidates = [
        path
        for path in _project_run_paths(_active_project_id())
        if is_run_complete(path)
        and (path / "problem.md").is_file()
        and (path / "evidence_contract.yaml").is_file()
        and not (path / "build_contract.json").is_file()
    ]
    if not candidates:
        st.info(
            _text(
                "Generate a ProblemBridge alignment package first, then return here.",
                "请先生成 ProblemBridge 对齐包，然后回到这里。",
            )
        )
        return

    candidates = sorted(candidates, key=lambda path: path.stat().st_mtime, reverse=True)
    source = st.selectbox(
        _text("Alignment package", "对齐包"),
        candidates,
        format_func=lambda path: path.name,
        key="build_contract_source",
    )
    problem_text = (source / "problem.md").read_text(encoding="utf-8")
    with st.expander(_text("Review source problem", "检查源问题")):
        st.code(problem_text, language="markdown")

    provider = st.radio(
        _text("Proposal runtime", "候选声明运行方式"),
        ["mock", "openai"],
        format_func=lambda value: (
            _text("Deterministic mock — no API key", "确定性 mock——不需要 API 密钥")
            if value == "mock"
            else _text("OpenAI GPT-5.6 — OPENAI_API_KEY required", "OpenAI GPT-5.6——需要 OPENAI_API_KEY")
        ),
        horizontal=True,
        key="build_contract_provider",
    )
    if provider == "openai":
        st.warning(
            _text(
                "Remote call: confirm this brief contains no patient data, confidential manuscript text, credentials, or unpublished private material.",
                "远程调用：请确认该 brief 不包含患者数据、保密稿件、凭据或未公开的私密材料。",
            )
        )
        st.caption(
            _text(
                "The competition path uses the OpenAI Responses API with strict structured output and records non-secret model metadata.",
                "参赛路径使用 OpenAI Responses API 的严格结构化输出，并记录不含密钥的模型元数据。",
            )
        )

    generated_out = None
    if st.button(
        _text("Generate evidence-gated build contract", "生成证据门控构建契约"),
        type="primary",
        key="generate_evidence_gated_build",
        use_container_width=True,
    ):
        generated_out = _run_ui_action(
            _text("Generating and gating capability claims…", "正在生成并门控能力声明……"),
            lambda: _run_evidence_gated_build(source, provider),
        )

    display_out = generated_out or _last_output_path("last_build_contract_dir")
    if display_out:
        if generated_out:
            st.success(_generated_message(display_out))
        else:
            st.info(_text("Most recent build contract is shown below.", "下方显示最近一次构建契约。"))
        _render_build_contract_output(display_out)


def _view_outputs() -> None:
    _render_page_intro(
        _text("View generated outputs", "查看生成结果"),
        _text(
            "Open previous local UI runs and inspect their friendly summary, technical files, and downloadable package.",
            "打开之前的本地 UI 运行结果，查看用户摘要、技术文件和可下载结果包。",
        ),
        _text(
            "Review outputs before sharing. Generated packages may include sensitive text if the user entered sensitive material.",
            "分享前请先检查输出。如果用户输入过敏感材料，生成包也可能包含敏感文本。",
        ),
        [
            _text("Friendly summary", "面向用户的摘要"),
            _text("Technical delivery files", "技术交付文件"),
            _text("Download package", "下载结果包"),
        ],
    )
    try:
        resolved_run_root = _resolve_safe_ui_run_root(create=False)
    except ValueError as exc:
        st.error(str(exc))
        return
    if resolved_run_root is None:
        st.info(_text(
            "No UI-generated outputs yet. Run an example, document intake, question discovery, or wizard first.",
            "还没有 UI 生成的输出。请先运行示例、文档摄取、问题发现或向导。",
        ))
        _render_empty_results_actions()
        return
    active_project = _active_project_id()
    show_all_projects = st.checkbox(
        _text("Show runs from all projects", "显示所有项目的运行结果"),
        value=False,
        key="show_all_output_projects",
        help=_text(
            "Off by default to reduce the risk of opening or sharing the wrong project's output.",
            "默认关闭，以降低打开或分享错误项目结果的风险。",
        ),
    )
    all_runs = [
        path
        for path in resolved_run_root.iterdir()
        if path.is_dir()
        and not is_internal_staging_name(path.name)
        and not is_link_or_reparse(path)
        and path.resolve().parent == resolved_run_root
    ]
    # Scope by project before verifying completion hashes. Opening one project's
    # results must not reread the contents of every other project's artifacts.
    scoped_candidates = all_runs if show_all_projects else [
        path for path in all_runs if _run_belongs_to_project(path, active_project)
    ]
    viewable_runs = [
        path
        for path in scoped_candidates
        if not (
            (path / RUN_DELETE_MARKER_NAME).exists()
            or (path / RUN_DELETE_MARKER_NAME).is_symlink()
        )
        and (not (path / RUN_IDENTITY_NAME).is_file() or is_run_complete(path))
    ]
    incomplete_count = len(scoped_candidates) - len(viewable_runs)
    if incomplete_count:
        st.caption(
            _text(
                f"{incomplete_count} incomplete run(s) are hidden until resumed, replaced, or deleted.",
                f"有 {incomplete_count} 次未完成运行已隐藏，请恢复、替换或删除后再查看。",
            )
        )
    runs, run_labels = _sort_view_output_runs(viewable_runs)
    other_project_count = len(all_runs) - len(scoped_candidates)
    if other_project_count and not show_all_projects:
        st.caption(
            _text(
                f"{other_project_count} run(s) from other or legacy projects are hidden.",
                f"已隐藏其他项目或旧版项目的 {other_project_count} 次运行。",
            )
        )
    if not runs:
        st.info(_text(
            "No completed outputs are available for the current project. Generate one, or explicitly show all projects.",
            "当前项目还没有可查看的完整结果。请先生成结果，或显式选择显示所有项目。",
        ))
        _render_empty_results_actions()
        return

    selected = st.selectbox(
        _text("Choose a generated run", "选择一个生成结果"),
        runs,
        index=_view_outputs_index_for_last_run(runs, st.session_state.get("last_output_dir", "")),
        format_func=lambda path: run_labels[path],
    )
    _render_output_for_run(selected)


def _render_empty_results_actions() -> None:
    st.button(
        _text("Start from the home page", "回首页选择一个入口"),
        key="empty_results_home", type="primary",
        on_click=_navigate_to_page, args=("Home",),
    )


def _output_kind(out: Path) -> str:
    """Return the narrow renderer kind for one verified or legacy output package."""

    if (out / RUN_IDENTITY_NAME).is_file():
        _project_id, workflow_type = _view_output_identity_details(out)
        suffix = workflow_type.removeprefix("problem_bridge.")
        if suffix == "document_intake":
            return "document-intake"
        if suffix == "question_discovery":
            return "question-discovery"
        if suffix in {"claim_audit", "claim-harness", "audit", "problem_audit"} or workflow_type == "claim_harness.audit":
            return "claim-audit"
        if suffix in {"problem", "problem_follow_up"}:
            return "problem-record"
        if suffix == "build_contract":
            return "build-contract"
        return "alignment"
    return _detect_legacy_package_type(out)


def _detect_legacy_package_type(out: Path) -> str:
    detected = [
        package_type
        for package_type, sentinels in LEGACY_PACKAGE_SENTINELS.items()
        if any((out / name).is_file() for name in sentinels)
    ]
    if len(detected) != 1:
        raise ValueError(
            "Legacy output must contain exactly one recognizable package type; "
            "regenerate mixed or unknown folders as a governed run."
        )
    return detected[0]


def _render_output_for_run(out: Path) -> None:
    try:
        kind = _output_kind(out)
    except (OSError, ValueError, ProjectLifecycleError) as exc:
        st.error(
            _text(
                "This output package cannot be opened safely.",
                "无法安全打开这个输出包。",
            )
        )
        st.caption(str(exc))
        return
    if kind == "document-intake":
        _render_document_intake_output(out)
    elif kind == "question-discovery":
        _render_question_discovery_output(out)
    elif kind == "claim-audit":
        _render_claim_audit_output(out)
    elif kind == "build-contract":
        _render_build_contract_output(out)
    elif kind == "problem-record":
        st.markdown((out / "problem_record.md").read_text(encoding="utf-8"))
        _render_problem_continue(out)
        _render_share_controls(out, "ProblemBridge problem record")
    else:
        _render_friendly_output(out)


def _render_build_contract_output(out: Path) -> None:
    st.subheader(_text("Evidence-gated build summary", "证据门控构建摘要"))
    runtime = _read_optional_json_object(
        out / "gpt_5_6_runtime.json", _text("runtime record", "运行记录")
    )
    decisions: list[dict[str, str]] = []
    decisions_path = out / "claim_decisions.csv"
    if decisions_path.is_file():
        try:
            with decisions_path.open(newline="", encoding="utf-8") as handle:
                decisions = list(csv.DictReader(handle))
        except (OSError, UnicodeError, csv.Error) as exc:
            st.warning(str(exc))

    counts: dict[str, int] = {}
    for row in decisions:
        status = row.get("status", "unknown")
        counts[status] = counts.get(status, 0) + 1
    col1, col2, col3, col4 = st.columns(4)
    col1.metric(_text("Claims", "声明数"), len(decisions))
    col2.metric(_text("Supported", "已支持"), counts.get("supported", 0))
    col3.metric(_text("Downgraded", "已降级"), sum(row.get("action") == "downgrade" for row in decisions))
    col4.metric(
        "GPT-5.6",
        _text("Verified", "已验证") if runtime.get("gpt_5_6_used") else _text("Mock / not called", "Mock／未调用"),
    )
    st.caption(
        _text(
            f"Provider: {runtime.get('provider', 'unknown')} · Model: {runtime.get('model', 'unknown')}",
            f"Provider：{runtime.get('provider', 'unknown')} · 模型：{runtime.get('model', 'unknown')}",
        )
    )
    if decisions:
        st.dataframe(
            decisions,
            use_container_width=True,
            hide_index=True,
            column_order=[
                "claim_id",
                "status",
                "action",
                "original_statement",
                "final_statement",
                "accepted_evidence_refs",
            ],
        )
    contract_path = out / "build_contract.md"
    if contract_path.is_file():
        st.markdown(contract_path.read_text(encoding="utf-8"))
    handoff = out / "codex_handoff"
    if handoff.is_dir():
        with st.expander(_text("Codex Handoff Pack", "Codex 交接包"), expanded=True):
            st.write(
                _text(
                    "These files are ready to copy into a new implementation workspace.",
                    "这些文件可以直接复制到新的实现工作区。",
                )
            )
            for name in sorted(path.name for path in handoff.iterdir() if path.is_file()):
                st.code(name, language="text")
    _render_share_controls(out, "Evidence-Gated Build")


def _render_claim_audit_output(out: Path) -> None:
    if (out / "problem_record.json").is_file():
        _render_problem_continue(out)
    st.subheader(_text("Claim audit summary", "声明审计摘要"))
    diagnostics_path = out / "audit_diagnostics.json"
    queue_path = out / "human_review_queue.json"
    diagnostics = _read_optional_json_object(
        diagnostics_path, _text("audit diagnostics", "审计诊断")
    )
    queue = _read_optional_json_object(
        queue_path, _text("human-review queue", "人工复核队列")
    )
    metrics = diagnostics.get("metrics", {}) if diagnostics else {}

    claim_path = out / "claim_table.csv"
    rows: list[dict[str, str]] = []
    if claim_path.is_file():
        try:
            with claim_path.open(newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
        except (OSError, UnicodeError, csv.Error) as exc:
            st.warning(
                _text(
                    f"Claim table is unavailable: {exc}",
                    f"声明表不可用：{exc}",
                )
            )

    def metric_value(name: str) -> str:
        metric = metrics.get(name, {})
        if not isinstance(metric, dict) or "numerator" not in metric:
            return _text("Unavailable", "不可用")
        return f"{metric.get('numerator', 0)}/{metric.get('denominator', 0)}"

    needs_review_count = sum(
        row.get("status") == "needs_human_review" for row in rows
    )
    pending_items = (
        queue.get("counts", {}).get("pending_items", 0)
        if queue is not None and isinstance(queue.get("counts", {}), dict)
        else _text("Unavailable", "不可用")
    )

    col1, col2, col3, col4 = st.columns(4)
    col1.metric(_text("Claims", "声明"), len(rows))
    col2.metric(_text("Support relations", "支持关系"), metric_value("support_relation_coverage"))
    col3.metric(
        _text("Needs human review", "需人工复核"),
        f"{needs_review_count}/{len(rows)}" if rows else _text("Unavailable", "不可用"),
    )
    col4.metric(_text("Pending review items", "待复核事项"), pending_items)
    st.caption(
        _text(
            "Structural diagnostics describe this run only; they are not factual-correctness or scientific-validity scores.",
            "结构诊断只描述本次运行，不是事实正确性或科学有效性评分。",
        )
    )
    if diagnostics is None or queue is None:
        st.info(
            _text(
                "This older package does not contain every diagnostic artifact; unavailable values are not treated as zero.",
                "这个旧版结果包缺少部分诊断文件；不可用的数值不会按零处理。",
            )
        )

    if rows:
        attention = [row for row in rows if row.get("status") != "supported"]
        st.markdown(f"### {_text('Claims needing attention', '需要处理的声明')}")
        if attention:
            st.dataframe(
                [
                    {
                        "claim_id": row.get("claim_id", ""),
                        "status": row.get("status", ""),
                        "risk": row.get("risk_level", ""),
                        "claim": row.get("text", ""),
                        "next_action": row.get("suggested_revision", ""),
                    }
                    for row in attention
                ],
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.success(_text("No claims need follow-up in this run.", "本次运行没有需要跟进的声明。"))

    _render_share_controls(out, "ClaimHarness audit")
    _render_report_export_buttons(out)
    with st.expander(_text("Audit files", "审计文件")):
        for filename in (
            "audit_report.md",
            "revision_suggestions.md",
            "audit_diagnostics.json",
            "human_review_queue.json",
        ):
            path = out / filename
            if path.is_file():
                st.markdown(f"### {filename}")
                st.code(path.read_text(encoding="utf-8"), language=_language_for(filename))


def _render_problem_continue(out: Path) -> None:
    if _run_belongs_to_project(out, _active_project_id()):
        if st.button(_text("Continue this problem in my workbench", "在工作台继续这个问题"), key=f"resume_problem_{out.name}"):
            st.session_state.last_problem_dir = str(out)
            st.session_state.pending_unified_stage = 3 if (out / "claim_table.csv").is_file() else 4
            st.session_state.pending_workspace_page = "Home"
            for key in list(st.session_state):
                if str(key).startswith("unified_"):
                    del st.session_state[key]
            st.rerun()


def _read_optional_json_object(path: Path, label: str) -> dict | None:
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        st.warning(_text(f"Could not read {label}: {exc}", f"无法读取{label}：{exc}"))
        return None
    if not isinstance(payload, dict):
        st.warning(
            _text(
                f"Could not read {label}: expected a JSON object.",
                f"无法读取{label}：应为 JSON 对象。",
            )
        )
        return None
    return payload


def _sort_view_output_runs(paths: list[Path]) -> tuple[list[Path], dict[Path, str]]:
    """Order governed runs by identity time and label legacy runs explicitly."""

    entries: list[tuple[float, str, Path, str]] = []
    for path in paths:
        try:
            created_at, legacy = _view_output_created_at(path)
        except (OSError, ValueError, TypeError, OverflowError, ProjectLifecycleError):
            # A governed run whose identity cannot be verified is not safe to
            # present as history. Concurrently removed paths are also skipped.
            continue
        timestamp = created_at.timestamp()
        safe_time = created_at.strftime("%Y-%m-%d %H:%M:%S UTC")
        project_id, workflow_type = _view_output_identity_details(path)
        workflow_label = workflow_type.removeprefix("problem_bridge.").replace("_", " ")
        project_label = project_id if len(project_id) <= 24 else f"{project_id[:12]}…"
        legacy_marker = " · legacy" if legacy else ""
        label = (
            f"{safe_time} · {workflow_label} · {project_label} · "
            f"{path.name}{legacy_marker}"
        )
        entries.append((timestamp, path.name.casefold(), path, label))
    entries.sort(key=lambda item: (item[0], item[1]), reverse=True)
    ordered = [item[2] for item in entries]
    return ordered, {item[2]: item[3] for item in entries}


def _view_output_created_at(path: Path) -> tuple[datetime, bool]:
    identity_path = path / RUN_IDENTITY_NAME
    if identity_path.is_file():
        identity = load_run_identity(path)
        raw_created_at = identity.get("run_created_at") or identity.get(
            "directory_created_at"
        )
        if not isinstance(raw_created_at, str) or not raw_created_at.strip():
            raise ValueError("Governed run identity has no creation time.")
        created_at = datetime.fromisoformat(raw_created_at.replace("Z", "+00:00"))
        if created_at.tzinfo is None:
            raise ValueError("Governed run creation time must include a timezone.")
        return created_at.astimezone(timezone.utc), False
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc), True


def _view_output_identity_details(path: Path) -> tuple[str, str]:
    identity_path = path / RUN_IDENTITY_NAME
    if not identity_path.is_file():
        return "unbound", "legacy"
    identity = load_run_identity(path)
    return str(identity["project_id"]), str(identity.get("workflow_type", "unknown"))


def _run_belongs_to_project(path: Path, project_id: str) -> bool:
    try:
        actual_project_id, _workflow_type = _view_output_identity_details(path)
    except (OSError, ValueError, TypeError, ProjectLifecycleError):
        return False
    return actual_project_id == project_id


def _render_alignment_next_step(out: Path) -> None:
    st.subheader(_text("Next step", "下一步"))
    st.write(
        _text(
            "Use this alignment package to check whether the candidate AI task still matches the domain problem, evidence contract, evaluation protocol, and human-review boundaries.",
            "把这个对齐包带入 AI 任务对齐向导，检查候选 AI 任务是否仍然贴合领域问题、证据契约、评价协议和人工复核边界。",
        )
    )
    st.button(
        _text("Continue to AI practitioner wizard", "继续到 AI 任务对齐向导"),
        key=f"continue_to_ai_wizard_{out.name}",
        on_click=_continue_to_ai_wizard_from_alignment,
        args=(out,),
        type="primary",
        use_container_width=True,
    )


def _render_workflow_alignment_result(out: Path) -> None:
    _render_alignment_next_step(out)
    _render_friendly_output(out)


def _render_evidence_gate_next_step(out: Path) -> None:
    st.subheader(_text("Next step", "下一步"))
    st.write(
        _text(
            "Generate bounded capability claims, inspect how ClaimHarness retains or downgrades them, and export a Codex Handoff Pack.",
            "生成有边界的能力声明，检查 ClaimHarness 如何保留或降级它们，再导出 Codex 交接包。",
        )
    )
    st.button(
        _text("Continue to Evidence-gated build", "继续到证据门控构建"),
        key=f"continue_to_evidence_gate_{out.name}",
        on_click=_continue_to_evidence_gate,
        args=(out,),
        type="primary",
        use_container_width=True,
    )


def _render_ai_alignment_result(out: Path) -> None:
    _render_evidence_gate_next_step(out)
    _render_friendly_output(out)


def _render_previous_result_card(
    out: Path,
    renderer,
    *,
    key_suffix: str,
    label: str,
) -> None:
    st.info(
        _text(
            f"A previous {label} is available. It does not include edits currently in this form.",
            f"已有上一次{label}。它不包含当前表单中尚未生成的修改。",
        )
    )
    show_previous = st.checkbox(
        _text(f"Show most recent {label}", f"显示最近一次{label}"),
        value=False,
        key=f"show_previous_{key_suffix}_{out.name}",
    )
    if show_previous:
        renderer(out)


def _last_output_path(session_key: str) -> Path | None:
    value = st.session_state.get(session_key)
    if not value:
        return None
    return _validated_project_output_path(value, _active_project_id())


def _validated_project_output_path(
    value: str | Path,
    project_id: object,
) -> Path | None:
    if not _is_valid_project_id(project_id):
        return None
    try:
        path = _resolve_ui_run_for_read(Path(value))
        identity = load_run_identity(path)
    except (OSError, ValueError, ProjectLifecycleError):
        return None
    if identity.get("project_id") != project_id or not is_run_complete(path):
        return None
    return path


def _read_output_text(out: Path, filename: str) -> str:
    path = Path(out) / filename
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def _markdown_section(text: str, title: str) -> str:
    marker = f"## {title}".casefold()
    lines = text.splitlines()
    start = next(
        (index + 1 for index, line in enumerate(lines) if line.strip().casefold() == marker),
        None,
    )
    if start is None:
        return ""
    collected: list[str] = []
    for line in lines[start:]:
        if line.strip().startswith("## "):
            break
        collected.append(line)
    return "\n".join(collected).strip()


def _compact_seed_text(text: str, *, max_chars: int = 1400) -> str:
    cleaned_lines = []
    for raw_line in text.splitlines():
        line = re.sub(r"^#{1,6}\s*", "", raw_line.strip())
        line = re.sub(r"^[-*]\s+", "", line)
        if line and line not in {"```", "---"}:
            cleaned_lines.append(line)
    compact = re.sub(r"\s+", " ", " ".join(cleaned_lines)).strip()
    if len(compact) <= max_chars:
        return compact
    shortened = compact[: max_chars - 1].rsplit(" ", 1)[0].rstrip(" ,;:")
    return f"{shortened}…"


def _yaml_scalar(text: str, key: str) -> str:
    prefix = f"{key}:"
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith(prefix):
            return stripped[len(prefix) :].strip().strip('"\'')
    return ""


def _yaml_list(text: str, key: str) -> list[str]:
    lines = text.splitlines()
    prefix = f"{key}:"
    for index, line in enumerate(lines):
        if line.strip() != prefix:
            continue
        values: list[str] = []
        for candidate in lines[index + 1 :]:
            if candidate.startswith("  - "):
                values.append(candidate[4:].strip().strip('"\''))
                continue
            if candidate.strip():
                break
        return values
    return []


def _markdown_bullets(text: str, *, limit: int = 8) -> list[str]:
    return [
        line.strip()[2:].strip()
        for line in text.splitlines()
        if line.strip().startswith("- ")
    ][:limit]


def _field_lines(values: list[str]) -> str:
    return "\n".join(f"- {value}" for value in values if value.strip())


def _question_discovery_seed_from_intake(out: Path) -> dict[str, str]:
    problem_seed = _read_output_text(out, "problem_seed.md")
    extracted_context = _markdown_section(problem_seed, "Extracted context")
    seed_text = _compact_seed_text(
        extracted_context or _read_output_text(out, "extracted_text.md")
    )
    warnings = _read_output_text(out, "extraction_warnings.md").strip()
    uncertainty_parts = [
        _text(
            "Review the extracted text, tables, annotations, and warnings to decide what needs expert validation.",
            "请检查提取文本、表格、批注和警告，判断哪些内容需要专家确认。",
        ),
    ]
    if warnings and "No extraction warnings" not in warnings:
        uncertainty_parts.append(_compact_seed_text(warnings, max_chars=600))
    return {
        "question_seed_text": seed_text,
        "question_uncertainty": "\n\n".join(uncertainty_parts),
        "question_desired_change": _text(
            "Identify what to ask, who to ask, and which unknowns must be validated before proposing an AI solution.",
            "在提出 AI 方案前，明确该问什么、该问谁，以及哪些未知项必须先验证。",
        ),
    }


def _continue_to_question_discovery_from_intake(out: Path) -> None:
    _adopt_project_from_run(out)
    seed = _question_discovery_seed_from_intake(out)
    for key, value in seed.items():
        st.session_state[key] = value
    st.session_state.last_document_intake_dir = str(out)
    st.session_state.workspace_page = "Question discovery"


def _domain_wizard_seed_from_discovery(out: Path) -> dict[str, str]:
    problem_seed = _read_output_text(out, "problem_seed.md")
    source_context = _compact_seed_text(
        _markdown_section(problem_seed, "Source context")
        or _read_output_text(out, "question_brief.md")
    )
    notes = _compact_seed_text(_read_output_text(out, "question_brief.md"), max_chars=1600)
    return {
        "domain_draft_repeated_work": source_context,
        "domain_draft_additional_notes": notes,
    }


def _interview_seed_from_discovery(out: Path):
    problem_seed = _read_output_text(out, "problem_seed.md")
    seeded = start_interview()
    values = {
        "repeated_work": _compact_seed_text(
            _markdown_section(problem_seed, "Source context"), max_chars=1000
        ),
    }
    for key, value in values.items():
        if value:
            seeded = answer_question(seeded, key, value)
    return seeded


def _continue_to_domain_wizard_from_discovery(out: Path) -> None:
    _adopt_project_from_run(out)
    seed = _domain_wizard_seed_from_discovery(out)
    for key, value in seed.items():
        st.session_state[key] = value
    for key in list(st.session_state):
        if str(key).startswith(("interview_answer_", "interview_edit_")):
            del st.session_state[key]
    st.session_state.problem_bridge_interview_state = _interview_seed_from_discovery(out)
    st.session_state.interview_seed_source = str(out)
    st.session_state.last_question_discovery_dir = str(out)
    st.session_state.workspace_page = "Domain practitioner wizard"


def _ai_wizard_seed_from_alignment(out: Path) -> dict[str, str]:
    problem_card = _read_output_text(out, "problem_card.md") or _read_output_text(out, "problem.md")
    task_spec = _read_output_text(out, "ai_task_spec.yaml")
    risk_report = _read_output_text(out, "misalignment_risk_report.md")
    repeated_work = _compact_seed_text(
        _markdown_section(problem_card, "repeated_work"), max_chars=1000
    )
    source_problem = _compact_seed_text(
        _markdown_section(problem_card, "Source Problem"), max_chars=1000
    )
    usable_source_problem = (
        "" if source_problem.lstrip().startswith("#") else source_problem
    )
    domain_goal = (
        repeated_work
        or usable_source_problem
        or _yaml_scalar(task_spec, "domain_goal")
        or _compact_seed_text(
            _markdown_section(problem_card, "Domain Goal") or problem_card,
            max_chars=1000,
        )
    )
    not_allowed = _yaml_scalar(task_spec, "not_allowed_goal")
    task_types = _yaml_list(task_spec, "ai_task_type")
    inputs = _yaml_list(task_spec, "inputs")
    outputs = _yaml_list(task_spec, "outputs")
    evaluation = _yaml_list(task_spec, "evaluation")
    human_review = _yaml_list(task_spec, "human_review_required")
    risks = _markdown_bullets(risk_report)
    high_risk_parts = list(
        dict.fromkeys(part for part in [not_allowed, *human_review, *risks] if part)
    )
    return {
        "ai_draft_domain_problem": domain_goal,
        "ai_draft_candidate_task": _field_lines(task_types),
        "ai_draft_inputs": _field_lines(inputs),
        "ai_draft_outputs": _field_lines(outputs),
        "ai_draft_metric": _field_lines(evaluation),
        "ai_draft_user": "",
        "ai_draft_high_risk_mistakes": _field_lines(high_risk_parts),
    }


def _continue_to_ai_wizard_from_alignment(out: Path) -> None:
    _adopt_project_from_run(out)
    seed = _ai_wizard_seed_from_alignment(out)
    for key, value in seed.items():
        st.session_state[key] = value
    st.session_state.ai_seed_source_dir = str(out)
    st.session_state.last_alignment_package_dir = str(out)
    st.session_state.last_output_dir = str(out)
    st.session_state.workspace_page = "AI practitioner wizard"


def _continue_to_evidence_gate(out: Path) -> None:
    _adopt_project_from_run(out)
    st.session_state.last_ai_alignment_dir = str(out)
    st.session_state.last_output_dir = str(out)
    st.session_state.workspace_page = "Evidence-gated build"


def _view_outputs_index_for_last_run(runs: list[Path], last_output_dir: str) -> int:
    if not last_output_dir:
        return 0
    try:
        return [str(path) for path in runs].index(str(Path(last_output_dir)))
    except ValueError:
        return 0


def _run_document_intake(
    uploaded_files,
    *,
    urls: list[str] | None = None,
    enable_ocr: bool = False,
    ocr_language: str | None = None,
    pasted_text: str = "",
) -> Path:
    uploaded_payloads = [
        (Path(uploaded_file.name).name, uploaded_file.getvalue())
        for uploaded_file in uploaded_files
    ]
    run_spec = {
        "uploads": [
            {
                "name": name,
                "size_bytes": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
            }
            for name, data in uploaded_payloads
        ],
        "urls": list(urls or []),
        "enable_ocr": enable_ocr,
        "ocr_language": ocr_language or "engine-default",
        "pasted_text_sha256": hashlib.sha256(
            pasted_text.strip().encode("utf-8")
        ).hexdigest(),
    }
    context = _allocate_ui_run(
        "document_intake",
        owned_artifacts=tuple(
            name for name in DOCUMENT_INTAKE_FILES if name in SYSTEM_OWNED_ARTIFACTS
        ),
        required_artifacts=tuple(DOCUMENT_INTAKE_FILES),
        snapshot_directories=("source_files", "extracted_tables"),
        run_spec=run_spec,
    )
    out = context.path
    with context.transaction():
        source_dir = out / "source_files"
        source_dir.mkdir(parents=True, exist_ok=True)

        results = []
        used_names: set[str] = set()
        for original_name, data in uploaded_payloads:
            safe_name = _unique_source_name(original_name, used_names)
            source_path = source_dir / safe_name
            source_path.write_bytes(data)
            results.append(
                extract_document(
                    source_path,
                    enable_ocr=enable_ocr,
                    ocr_language=ocr_language,
                )
            )
        if pasted_text.strip():
            fallback_name = _unique_source_name("manual_upload_fallback.md", used_names)
            fallback_path = source_dir / fallback_name
            fallback_path.write_text(pasted_text.strip() + "\n", encoding="utf-8")
            results.append(extract_document(fallback_path))
        for url in urls or []:
            results.append(extract_url(url))

        write_intake_package(results, out)
        (out / "problem_seed.md").write_text(
            build_problem_seed_from_intake(results), encoding="utf-8"
        )
    st.session_state.last_document_intake_dir = str(out)
    st.session_state.last_output_dir = str(out)
    return out



def _run_question_discovery(package) -> Path:
    context = _allocate_ui_run(
        "question_discovery",
        owned_artifacts=tuple(
            name for name in QUESTION_DISCOVERY_FILES if name in SYSTEM_OWNED_ARTIFACTS
        ),
        required_artifacts=tuple(QUESTION_DISCOVERY_FILES),
        run_spec=asdict(package),
    )
    out = context.path
    with context.transaction():
        write_question_discovery_package(package, out)
        (out / "problem_seed.md").write_text(
            build_problem_from_discovery(package), encoding="utf-8"
        )
    st.session_state.last_question_discovery_dir = str(out)
    st.session_state.last_output_dir = str(out)
    return out



def _run_problem_text(problem_text: str, prefix: str) -> Path:
    context = _allocate_ui_run(
        prefix,
        owned_artifacts=tuple(ALIGNMENT_RUN_ARTIFACTS),
        required_artifacts=(*ALIGNMENT_RUN_ARTIFACTS, "problem.md"),
        run_spec={"problem_text_sha256": hashlib.sha256(problem_text.encode("utf-8")).hexdigest()},
    )
    out = context.path
    with context.transaction():
        (out / "problem.md").write_text(problem_text, encoding="utf-8")
        package = build_alignment_package(problem_text)
        write_alignment_package(package, out, project_id=context.project_id)
    if prefix in {"domain_practitioner", "guided_interview"}:
        st.session_state.last_alignment_package_dir = str(out)
    if prefix == "ai_practitioner":
        st.session_state.last_ai_alignment_dir = str(out)
    if prefix.startswith("example_"):
        st.session_state.last_example_dir = str(out)
    st.session_state.last_output_dir = str(out)
    return out


def _run_evidence_gated_build(source_out: Path, provider: str) -> Path:
    source = _validated_project_output_path(source_out, _active_project_id())
    if source is None or not (source / "problem.md").is_file():
        raise ValueError("A completed current-project alignment package is required.")
    problem_text = (source / "problem.md").read_text(encoding="utf-8")
    provider_config = resolve_provider_config(provider)
    package = build_alignment_package(problem_text)
    source_identity = load_run_identity(source)
    required = tuple(
        [
            *ALIGNMENT_RUN_ARTIFACTS,
            *BUILD_CONTRACT_RUN_ARTIFACTS,
            "problem.md",
        ]
    )
    context = _allocate_ui_run(
        "build_contract",
        owned_artifacts=tuple(
            [*ALIGNMENT_RUN_ARTIFACTS, *BUILD_CONTRACT_RUN_ARTIFACTS]
        ),
        required_artifacts=required,
        snapshot_directories=BUILD_CONTRACT_SNAPSHOT_DIRECTORIES,
        run_spec={
            "source_run_id": source_identity["run_id"],
            "problem_text_sha256": hashlib.sha256(
                problem_text.encode("utf-8")
            ).hexdigest(),
            "provider": provider_config.provider,
            "api_style": provider_config.api_style,
            "model": provider_config.model,
        },
    )
    out = context.path
    with context.transaction():
        (out / "problem.md").write_text(problem_text, encoding="utf-8")
        write_alignment_package(package, out, project_id=context.project_id)
        generate_evidence_gated_build(
            package,
            out,
            provider_config=provider_config,
            project_id=context.project_id,
        )
    st.session_state.last_build_contract_dir = str(out)
    st.session_state.last_output_dir = str(out)
    return out


def _unique_source_name(original_name: str, used_names: set[str]) -> str:
    """Return a safe, stable filename without overwriting another upload."""

    candidate = Path(original_name).name.strip() or "uploaded_source"
    stem = Path(candidate).stem or "uploaded_source"
    suffix = Path(candidate).suffix
    index = 1
    while candidate.casefold() in used_names:
        index += 1
        candidate = f"{stem}__{index}{suffix}"
    used_names.add(candidate.casefold())
    return candidate


def _render_friendly_output(out: Path) -> None:
    summary = friendly_summary(out)
    st.subheader(_text("User-facing summary", "面向用户的摘要"))

    st.markdown(f"### {_text('One-sentence conclusion', '一句话结论')}")
    st.success(summary.one_sentence)
    st.caption(_text("This template-based brief needs your review; it does not validate a solution.", "这份说明由本地模板生成，请结合实际工作核对；它不代表方案已获验证。"))
    st.button(
        _text("Describe my own workflow", "梳理我自己的工作"),
        key=f"own_workflow_{out.name}",
        on_click=_navigate_to_page, args=("Domain practitioner wizard",),
    )

    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f"### {_text('Priority opportunities', '优先机会')}")
        if summary.opportunities:
            for item in summary.opportunities[:5]:
                st.write(f"- {item}")
        else:
            st.caption(_text("No priority opportunities were identified yet.", "暂未识别出优先机会。"))
    with col2:
        st.markdown(f"### {_text('Human review boundaries', '人工复核边界')}")
        if summary.must_review:
            for item in summary.must_review[:5]:
                st.write(f"- {item}")
        else:
            st.caption(_text("No explicit human-review boundary was found; add one before sharing.", "尚未找到明确的人工复核边界；分享前请补充。"))

    st.markdown(f"### {_text('Current workflow map', '当前工作流图')}")
    if summary.workflow_steps:
        for index, step in enumerate(summary.workflow_steps, start=1):
            st.write(f"{index}. {step}")
    else:
        st.write(_text("No clear workflow steps were identified yet.", "还没有识别出清晰的工作流步骤。"))

    st.markdown(f"### {_text('Next steps', '下一步')}")
    if summary.next_steps:
        for item in summary.next_steps[:5]:
            st.write(f"- {item}")
    else:
        st.caption(_text("No next step was generated; review the technical package and define one.", "尚未生成下一步；请检查技术文件并补充行动。"))

    _render_share_controls(out, "ProblemBridge alignment")
    _render_report_export_buttons(out)

    with st.expander(_text("Technical delivery package", "技术交付包")):
        st.caption(_text("Output folder", "输出文件夹"))
        st.code(str(out), language="text")
        for item in discover_alignment_outputs(out):
            st.markdown(f"### {FRIENDLY_FILE_LABELS.get(item.filename, item.filename)}")
            st.caption(item.filename)
            st.code(item.path.read_text(encoding="utf-8"), language=_language_for(item.filename))

def _render_report_export_buttons(out: Path) -> None:
    st.markdown(f"### {_text('Portable report exports', '可分享报告导出')}")
    try:
        token = _completed_run_cache_token(out)
        if token is None:
            package = export_output_report(out)
            docx_name = package.docx_path.name
            pdf_name = package.pdf_path.name
            docx_bytes = package.docx_path.read_bytes()
            pdf_bytes = package.pdf_path.read_bytes()
        else:
            docx_name, docx_bytes, pdf_name, pdf_bytes = _cached_report_payload(
                str(out), token
            )
    except Exception as exc:  # pragma: no cover - defensive UI guard
        st.warning(_text(f"Could not generate report exports: {exc}", f"无法生成报告导出：{exc}"))
        return

    col1, col2 = st.columns(2)
    with col1:
        st.download_button(
            _text("Download Word report", "下载 Word 报告"),
            docx_bytes,
            file_name=docx_name,
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            key=f"download_docx_{out.name}",
        )
    with col2:
        st.download_button(
            _text("Download PDF report", "下载 PDF 报告"),
            pdf_bytes,
            file_name=pdf_name,
            mime="application/pdf",
            key=f"download_pdf_{out.name}",
        )


def _render_share_controls(
    out: Path,
    package_name: str,
    *,
    allow_source_files: bool = False,
) -> None:
    """Render privacy-preserving download and explicit project deletion controls."""

    include_source_files = False
    if allow_source_files and (out / "source_files").is_dir():
        st.caption(
            _text(
                "Privacy default: original uploads are excluded from the share package.",
                "隐私默认设置：分享包不包含原始上传文件。",
            )
        )
        include_source_files = st.checkbox(
            _text(
                "Include original source files in this download",
                "在本次下载中包含原始文件",
            ),
            value=False,
            key=f"include_source_files_{out.name}",
            help=_text(
                "Only enable this after checking that the originals are safe to share.",
                "只有在确认原始文件可以安全分享后才启用。",
            ),
        )
        if include_source_files:
            st.warning(
                _text(
                    "This download will contain the original uploads. Review the recipients and data policy first.",
                    "本次下载将包含原始上传文件。请先确认接收者和数据政策。",
                )
            )

    token = _completed_run_cache_token(out)
    archive_bytes = (
        _cached_archive_payload(str(out), token, False)
        if token is not None and not include_source_files
        else _make_archive(out, include_source_files=include_source_files)
    )
    st.download_button(
        _download_package_label(package_name),
        archive_bytes,
        file_name=f"{out.name}.zip",
        mime="application/zip",
        key=f"download_archive_{out.name}_{include_source_files}",
    )
    st.caption(
        _text(
            "The package includes share_manifest.json with an exact content list and SHA-256 hashes.",
            "分享包内含 share_manifest.json，列出全部内容及其 SHA-256。",
        )
    )

    with st.expander(_text("Delete this local run", "删除这次本地运行")):
        confirmed = st.checkbox(
            _text(
                "I understand this permanently deletes this run and its original uploads.",
                "我确认永久删除这次运行及其原始上传文件。",
            ),
            value=False,
            key=f"confirm_delete_{out.name}",
        )
        if st.button(
            _text("Delete the complete local run", "删除完整本地运行"),
            disabled=not confirmed,
            key=f"delete_run_{out.name}",
        ):
            _delete_ui_run(out)
            _set_flash_message("success", _text("Local run permanently deleted.", "本地运行已永久删除。"))
            st.rerun()


def _completed_run_cache_token(out: Path) -> str | None:
    identity = out / RUN_IDENTITY_NAME
    completion = out / "run_complete.json"
    if not identity.is_file() or not completion.is_file():
        return None
    try:
        if not is_run_complete(out):
            return None
    except (OSError, ValueError, ProjectLifecycleError):
        return None
    digest = hashlib.sha256(completion.read_bytes())
    if (out / "project_record.json").is_file():
        governance = snapshot_project_governance(out)
        for name, data in sorted(governance.items()):
            digest.update(name.encode("utf-8"))
            digest.update(b"\0")
            digest.update(data)
    return digest.hexdigest()


@st.cache_data(show_spinner=False, ttl=300, max_entries=8)
def _cached_archive_payload(
    out_value: str,
    completion_token: str,
    include_source_files: bool,
) -> bytes:
    del completion_token
    return _make_archive(
        Path(out_value), include_source_files=include_source_files
    )


@st.cache_data(show_spinner=False, ttl=300, max_entries=8)
def _cached_report_payload(
    out_value: str,
    completion_token: str,
) -> tuple[str, bytes, str, bytes]:
    del completion_token
    package = export_output_report(Path(out_value))
    return (
        package.docx_path.name,
        package.docx_path.read_bytes(),
        package.pdf_path.name,
        package.pdf_path.read_bytes(),
    )


def _clear_export_caches() -> None:
    _cached_archive_payload.clear()
    _cached_report_payload.clear()


def _make_archive(out: Path, *, include_source_files: bool = False) -> bytes:
    """Build a verified allow-list archive from one immutable byte snapshot."""

    out = _resolve_ui_run_for_read(out)
    files: dict[str, bytes] = {}
    governed = (out / RUN_IDENTITY_NAME).is_file()
    legacy_package_type: str | None = None
    if governed:
        files.update(snapshot_completed_run(out))
    else:
        # Legacy folders have no immutable declaration. Detect exactly one
        # workflow from narrow sentinels; a global union would leak stale files
        # from another workflow (including local workbench drafts).
        try:
            legacy_package_type = _detect_legacy_package_type(out)
        except ValueError as exc:
            raise ValueError(
                "Legacy output cannot be shared safely: expected exactly one "
                "recognizable package type. Regenerate it as a governed run."
            ) from exc
        for name in sorted(LEGACY_PACKAGE_FILES[legacy_package_type]):
            path = out / name
            if path.is_file() and not path.is_symlink():
                files[name] = path.read_bytes()
        if legacy_package_type == "document-intake":
            extracted_tables = out / "extracted_tables"
            if extracted_tables.is_dir() and not extracted_tables.is_symlink():
                for path in snapshot_directory_files(out, "extracted_tables"):
                    files[path.relative_to(out).as_posix()] = path.read_bytes()
        if include_source_files and legacy_package_type == "document-intake":
            source_dir = out / "source_files"
            if source_dir.is_dir() and not source_dir.is_symlink():
                for path in snapshot_directory_files(out, "source_files"):
                    files[path.relative_to(out).as_posix()] = path.read_bytes()

    # Mutable governance records are separately allow-listed. Reading bytes
    # first means the ZIP entry and its manifest hash always describe the same
    # content even if a later revision updates the live file.
    if (out / "project_record.json").is_file():
        governance_files = snapshot_project_governance(out)
        for name, data in governance_files.items():
            # ClaimHarness may already have committed its summary as an
            # immutable run artifact; a mutable live file must not overwrite
            # that verified byte snapshot.
            files.setdefault(name, data)

    source_names = [name for name in files if name.startswith("source_files/")]
    if not include_source_files:
        for name in source_names:
            files.pop(name, None)

    source_live_files = {
        path.relative_to(out).as_posix()
        for path in snapshot_directory_files(out, "source_files")
    }
    excluded_source_count = sum(
        1 for name in source_live_files if name not in files
    )
    excluded_unknown_count = sum(
        1
        for path in out.iterdir()
        if path.name not in SYSTEM_SNAPSHOT_DIRECTORIES
        and path.name not in files
    )
    included: list[dict[str, object]] = []

    buffer = BytesIO()
    with ZipFile(buffer, "w", compression=ZIP_DEFLATED) as package:
        for portable_name, data in sorted(files.items()):
            package.writestr(portable_name, data)
            included.append(
                {
                    "path": portable_name,
                    "size_bytes": len(data),
                    "sha256": hashlib.sha256(data).hexdigest(),
                }
            )

        manifest = {
            "schema_version": 1,
            "package_type": "problem-bridge-share",
            "source_package_type": legacy_package_type or "governed-run",
            "verification_status": (
                "governed-verified" if governed else "legacy-unverified"
            ),
            "run_name": out.name,
            "original_source_files_included": include_source_files,
            "included_files": included,
            "excluded_original_source_file_count": excluded_source_count,
            "excluded_unknown_entry_count": excluded_unknown_count,
            "privacy_note": (
                "Original source files are included by explicit user choice."
                if include_source_files
                else "Original source files are excluded by default."
            ),
        }
        package.writestr(
            "share_manifest.json",
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        )

    return buffer.getvalue()


def _resolve_ui_run_for_read(out: Path) -> Path:
    """Resolve one real direct UI-run child and reject deletion/reparse state."""

    resolved = _resolve_safe_ui_run_candidate(out)
    marker = resolved / RUN_DELETE_MARKER_NAME
    if marker.exists() or marker.is_symlink():
        raise ValueError("Output directory is pending deletion and cannot be viewed or shared.")
    return resolved


def _delete_ui_run(out: Path) -> None:
    """Delete one complete UI run, refusing paths outside the configured run root."""

    run_root = _resolve_safe_ui_run_root(create=False)
    if run_root is None:
        raise ValueError("Configured UI run directory does not exist.")
    try:
        candidate = _resolve_safe_ui_run_candidate(out, run_root=run_root)
    except ValueError as exc:
        raise ValueError("Refusing to delete a path outside the UI run directory.") from exc
    identity = load_run_identity(candidate)
    delete_run_directory(
        candidate,
        project_id=str(identity["project_id"]),
        run_id=str(identity["run_id"]),
        trusted_parent=run_root,
    )
    archive = candidate.parent / f"{candidate.name}.zip"
    if archive.is_file():
        archive.unlink()
    _clear_export_caches()


def _project_run_paths(
    project_id: str, *, run_root: Path | None = None
) -> list[Path]:
    root = run_root or _resolve_safe_ui_run_root(create=False)
    if root is None:
        return []
    matches: list[Path] = []
    for candidate in sorted(root.iterdir()):
        if not candidate.is_dir() or is_link_or_reparse(candidate):
            continue
        try:
            identity = load_run_identity(candidate)
        except Exception:
            try:
                identity = load_pending_deletion(candidate)
            except Exception:
                continue
        if identity.get("project_id") == project_id:
            matches.append(candidate)
    return matches


def _pending_run_records() -> list[dict[str, object]]:
    root = _resolve_safe_ui_run_root(create=False)
    if root is None:
        return []
    pending: list[dict[str, object]] = []
    for candidate in sorted(root.iterdir()):
        if not candidate.is_dir() or is_link_or_reparse(candidate):
            continue
        try:
            identity = load_run_identity(candidate)
        except Exception:
            try:
                identity = load_pending_deletion(candidate)
            except Exception:
                continue
        if is_run_complete(candidate):
            continue
        pending.append({**identity, "path": candidate})
    return pending


def _delete_ui_project(project_id: str) -> int:
    run_root = _resolve_safe_ui_run_root(create=False)
    runs = [] if run_root is None else _project_run_paths(project_id, run_root=run_root)
    for candidate in runs:
        try:
            identity = load_run_identity(candidate)
        except Exception:
            identity = load_pending_deletion(candidate)
        if identity.get("project_id") != project_id:
            raise ValueError("Project identity changed during deletion; no further runs were deleted.")
        delete_run_directory(
            candidate,
            project_id=project_id,
            run_id=str(identity["run_id"]),
            allow_incomplete=True,
            trusted_parent=run_root,
        )
        legacy_archive = candidate.parent / f"{candidate.name}.zip"
        legacy_archive.unlink(missing_ok=True)
    memory = load_workbench_memory(MEMORY_PATH)
    if memory.get("active_project_id") == project_id:
        clear_workbench_memory(MEMORY_PATH)
    _clear_export_caches()
    return len(runs)


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
