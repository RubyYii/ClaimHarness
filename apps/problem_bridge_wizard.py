from __future__ import annotations

import os
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
MEMORY_FILE_LABEL = "workbench_memory.json"

PAGE_OPTIONS = [
    "Home",
    "Explore examples",
    "Document intake",
    "Question discovery",
    "Domain practitioner wizard",
    "AI practitioner wizard",
    "View generated outputs",
]

LANGUAGE_OPTIONS = ["English", "中文"]
LANGUAGE_CODES = {"English": "en", "中文": "zh"}
LANGUAGE_BADGE = {"en": "English interface", "zh": "中文界面"}

PAGE_LABELS = {
    "Home": {"en": "Home", "zh": "首页"},
    "Explore examples": {"en": "Explore examples", "zh": "示例演示"},
    "Document intake": {"en": "Document intake", "zh": "文档摄取"},
    "Question discovery": {"en": "Question discovery", "zh": "问题发现"},
    "Domain practitioner wizard": {"en": "Domain practitioner wizard", "zh": "领域工作流向导"},
    "AI practitioner wizard": {"en": "AI practitioner wizard", "zh": "AI 任务对齐向导"},
    "View generated outputs": {"en": "View generated outputs", "zh": "查看生成结果"},
}

WORKFLOW_STEPS_ZH = [
    ("01", "文档摄取", "把本地文件转成可审计的文本和表格。"),
    ("02", "问题发现", "先找出该问什么、该问谁。"),
    ("03", "引导式访谈", "还原工作材料、痛点、判断边界。"),
    ("04", "ProblemBridge", "生成任务规格、证据契约和评估方案。"),
    ("05", "ClaimHarness", "在输出或文稿产生后审计 claims。"),
]

ACTIVE_WORKFLOW_BY_PAGE_ZH = {
    "Document intake": "文档摄取",
    "Question discovery": "问题发现",
    "Domain practitioner wizard": "引导式访谈",
    "AI practitioner wizard": "ProblemBridge",
    "Explore examples": "ProblemBridge",
    "View generated outputs": "ProblemBridge",
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


def _language_code() -> str:
    choice = st.session_state.get("ui_language", "English")
    return LANGUAGE_CODES.get(choice, "en")


def _text(en: str, zh: str) -> str:
    return zh if _language_code() == "zh" else en


def _page_label(page: str) -> str:
    labels = PAGE_LABELS.get(page, {"en": page, "zh": page})
    return labels.get(_language_code(), page)


def _generated_message(out: Path) -> str:
    return _text(f"Generated: {out}", f"已生成：{out}")


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
    _inject_visual_theme()

    st.sidebar.markdown(f"### {_text('Language', '语言')}")
    st.sidebar.radio(
        _text("Interface language", "界面语言"),
        LANGUAGE_OPTIONS,
        key="ui_language",
        horizontal=True,
    )
    st.sidebar.caption(LANGUAGE_BADGE[_language_code()])

    _render_shell_header()
    _safety_banner()

    st.sidebar.markdown(f"### {_text('Workspace', '工作区')}")
    page = st.sidebar.radio(
        _text("Choose an entry", "选择入口"),
        PAGE_OPTIONS,
        format_func=_page_label,
    )
    st.sidebar.markdown(
        f"""
        <div class="sidebar-note">
        {_text('Local-first mode. Use synthetic or non-sensitive material for first testing.', '本地优先模式。首次测试请使用合成样例或非敏感材料。')}
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
    st.sidebar.markdown(f"### {_text('Workspace Memory', '工作台记忆')}")
    st.sidebar.caption(
        _text(
            f"Saved locally to `{MEMORY_PATH}` (`{MEMORY_FILE_LABEL}`). API keys are session-only and are never written to memory.",
            f"本地保存位置：`{MEMORY_PATH}`（`{MEMORY_FILE_LABEL}`）。API 密钥只在当前会话使用，不会写入记忆文件。",
        )
    )
    st.sidebar.warning(
        _text(
            "Privacy check before sharing: Clear local memory before sharing the folder or zip if your drafts include sensitive workflow details.",
            "分享前隐私检查：如果草稿包含敏感工作流信息，请先清除本地记忆，再分享文件夹或压缩包。",
        )
    )

    last_output = st.session_state.get("last_output_dir")
    if last_output:
        st.sidebar.caption(_text(f"Last output: `{last_output}`", f"最近输出：`{last_output}`"))

    st.sidebar.markdown(f"### {_text('API Settings', 'API 设置')}")
    st.sidebar.selectbox(_text("Provider", "模型服务"), API_PROVIDER_OPTIONS, key="api_provider", on_change=_sync_provider_defaults)
    provider = st.session_state.get("api_provider", "mock")
    preset = PROVIDER_PRESETS.get(provider)

    st.sidebar.text_input(_text("Base URL", "服务地址"), key="api_base_url")
    st.sidebar.text_input(_text("Model", "模型名称"), key="api_model")
    if st.sidebar.button(_text("Use provider defaults", "使用服务商默认配置"), key="api_use_provider_defaults"):
        _sync_provider_defaults()
        st.rerun()
    api_key = st.sidebar.text_input(_text("API key is session-only", "API 密钥仅当前会话使用"), type="password", key="api_key_session")

    if preset and preset.api_key_env:
        st.sidebar.caption(
            _text(
                f"Key env for this provider: `{preset.api_key_env}`. Provider, base URL, and model can be remembered; the key is not saved.",
                f"这个模型服务使用的环境变量：`{preset.api_key_env}`。可以记住服务商、服务地址和模型名称，但不会保存密钥。",
            )
        )
    else:
        st.sidebar.caption(_text("This provider does not require an API key for local testing.", "这个模型服务用于本地测试时不需要 API 密钥。"))

    if st.sidebar.button(_text("Use API key this session", "本次会话使用 API 密钥"), disabled=not bool(api_key) or not preset or not preset.api_key_env):
        os.environ[preset.api_key_env] = api_key
        st.sidebar.success(_text(f"Applied `{preset.api_key_env}` for this session only.", f"已在本次会话应用 `{preset.api_key_env}`。"))

    col1, col2 = st.sidebar.columns(2)
    with col1:
        if st.button(_text("Load saved memory", "加载记忆"), key="memory_load"):
            st.session_state.pending_workbench_memory = load_workbench_memory(MEMORY_PATH)
            st.session_state.pending_workbench_memory_clear = True
            st.rerun()
        if st.button(_text("Save current workspace", "保存当前工作台"), key="memory_save"):
            payload = _current_workbench_memory()
            save_workbench_memory(payload, MEMORY_PATH)
            st.session_state.workbench_memory = payload
            st.sidebar.success(_text("Workspace memory saved locally.", "工作台记忆已保存到本地。"))
    with col2:
        if st.button(_text("Clear memory", "清除记忆"), key="memory_clear"):
            clear_workbench_memory(MEMORY_PATH)
            st.session_state.pending_workbench_memory = {}
            st.session_state.pending_workbench_memory_clear = True
            st.rerun()


def _sync_provider_defaults() -> None:
    provider = st.session_state.get("api_provider", "mock")
    defaults = _provider_defaults(provider)
    st.session_state.api_base_url = defaults["base_url"]
    st.session_state.api_model = defaults["model"]

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
        [data-testid="stDeployButton"] { display: none !important; }
        [data-testid="stAppDeployButton"] { display: none !important; }
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
          letter-spacing: 0;
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
    eyebrow = _text("Local interdisciplinary AI harness", "本地优先的跨学科 AI 工作流工具")
    title = _text("ProblemBridge Workbench", "ProblemBridge 工作台")
    lead = _text(
        "A guided workspace for turning messy domain materials into questions, workflow understanding, AI task specs, and later claim-evidence audits.",
        "一个引导式工作台：把模糊的领域材料转成问题、工作流理解、AI 任务规格，并在输出后进行声明-证据审计。",
    )
    metrics = [
        _text("No API required by default", "默认不需要 API"),
        _text("Local file intake", "本地文件摄取"),
        _text("Question-first workflow", "先提出问题"),
        _text("Traceable outputs", "可追踪输出"),
    ]
    metric_html = "".join(f'<span class="metric-pill">{item}</span>' for item in metrics)
    st.markdown(
        f"""
        <section class="visual-shell">
          <div class="visual-eyebrow">{eyebrow}</div>
          <h1 class="visual-title">{title}</h1>
          <p class="visual-lead">{lead}</p>
          <div class="metric-row">{metric_html}</div>
        </section>
        """,
        unsafe_allow_html=True,
    )


def _render_workflow_strip(active_page: str) -> None:
    steps = WORKFLOW_STEPS_ZH if _language_code() == "zh" else WORKFLOW_STEPS
    active_map = ACTIVE_WORKFLOW_BY_PAGE_ZH if _language_code() == "zh" else ACTIVE_WORKFLOW_BY_PAGE
    active_step = active_map.get(active_page)
    st.markdown('<div class="workflow-strip"></div>', unsafe_allow_html=True)
    columns = st.columns(len(steps))
    for column, (number, title, description) in zip(columns, steps):
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
          <div class="visual-eyebrow">{_text('Workbench step', '工作台步骤')}</div>
          <h2>{title}</h2>
          <p>{body}</p>
          <div class="field-label">{_text('What you get', '你会得到什么')}</div>
          <ul>{output_items}</ul>
        </section>
        <section class="trust-card">
          <strong>{_text('Trust boundary', '信任边界')}</strong>
          <p>{trust}</p>
        </section>
        """,
        unsafe_allow_html=True,
    )


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

def _safety_banner() -> None:
    st.warning(
        _text(
            "Start with synthetic examples. Do not upload private patient data, confidential manuscripts, API keys, or sensitive unpublished materials.",
            "请先使用合成样例。不要上传真实患者数据、机密文稿、API key 或敏感未公开材料。",
        )
    )


def _home() -> None:
    _render_page_intro(
        _text("Choose the right starting point", "选择合适的开始入口"),
        _text(
            "You do not need to know AI. Start from the material or uncertainty you actually have, then move through the workflow one step at a time.",
            "你不需要懂 AI。先从你手里的材料、困惑或日常工作开始，再一步步进入问题发现、工作流对齐和证据审计。",
        ),
        _text(
            "The workbench is a framing and audit aid. It does not replace domain experts, supervisors, clinicians, teachers, or reviewers.",
            "这个工作台只帮助梳理问题和审计输出，不替代领域专家、主管、医生、教师或审稿人。",
        ),
        [
            _text("A clear entry point for documents, vague questions, workflows, or candidate AI tasks.", "根据文档、模糊问题、工作流或候选 AI 任务选择入口。"),
            _text("A visible workflow from intake to question discovery, problem alignment, and claim audit.", "看见从摄取、提问、问题对齐到声明审计的完整流程。"),
            _text("Downloadable local packages that can be reviewed before sharing.", "生成可下载的本地结果包，分享前可先检查。"),
        ],
    )
    _render_module_cards()

    st.subheader(_text("Recommended routes", "推荐路径"))
    route_cards = [
        (_text("Have files?", "已有文件？"), _text("Start with Document intake, inspect extracted text and warnings, then continue to Question discovery.", "先用文档摄取，检查提取文本和警告，再进入问题发现。")),
        (_text("Have a vague concern?", "只有模糊困惑？"), _text("Start with Question discovery to identify what to ask and which experts to involve.", "先用问题发现，明确该问什么、该找哪些专家。")),
        (_text("Know the workflow?", "已经知道工作流？"), _text("Go to Domain practitioner wizard and generate a ProblemBridge alignment package.", "进入领域工作流向导，生成 ProblemBridge 对齐包。")),
    ]
    col1, col2, col3 = st.columns(3)
    for column, (title, body) in zip([col1, col2, col3], route_cards):
        with column:
            st.markdown(f"""
            <section class="page-intro">
            <strong>{title}</strong>
            <p>{body}</p>
            </section>
            """, unsafe_allow_html=True)

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

    if st.button(_text("Generate this example package", "生成这个示例包")):
        out = _run_problem_text(problem_path.read_text(encoding="utf-8"), f"example_{_slug(choice)}")
        st.success(_generated_message(out))
        _render_friendly_output(out)


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
        submitted = st.form_submit_button(_text("Generate question discovery package", "生成问题发现包"))

    if submitted:
        package = discover_questions(seed_text, uncertainty, desired_change)
        out = _run_question_discovery(package)
        st.success(_generated_message(out))
        _render_question_discovery_output(out)


def _render_question_discovery_output(out: Path) -> None:
    st.subheader(_text("Questions to validate", "需要验证的问题"))
    brief_path = out / "question_brief.md"
    if brief_path.is_file():
        st.markdown(brief_path.read_text(encoding="utf-8"))

    st.subheader(_text("Who to ask", "应该问谁"))
    stakeholder_path = out / "stakeholder_map.md"
    if stakeholder_path.is_file():
        st.markdown(stakeholder_path.read_text(encoding="utf-8"))

    st.subheader(_text("Next step", "下一步"))
    st.write(
        _text(
            "Take this package to domain experts first. After the questions are validated, use Domain practitioner wizard to generate a ProblemBridge alignment package.",
            "先把这个包带给领域专家确认。问题被验证后，再使用领域工作流向导生成 ProblemBridge 对齐包。",
        )
    )

    archive = _make_archive(out)
    st.download_button(
        _download_package_label("question discovery"),
        archive.read_bytes(),
        file_name=f"{out.name}.zip",
        mime="application/zip",
    )

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
            "Upload Word, PDF, Markdown, TXT, or CSV files and convert them into local extraction outputs.",
            "上传 Word、PDF、Markdown、TXT 或 CSV 文件，并转成本地可检查的提取结果。",
        ),
        _text(
            "Supports .docx, .md, .txt, .csv, and text-based PDF. Scanned PDF, OCR, images, and figure understanding are not supported.",
            "支持 .docx、.md、.txt、.csv 和文字版 PDF。不支持扫描 PDF、OCR、图片理解或 figure 解释。",
        ),
        ["extracted_text.md", "extracted_tables/", "source_manifest.json", "extraction_warnings.md", "problem_seed.md"],
    )

    uploaded_files = st.file_uploader(
        _text("Upload Word, PDF, Markdown, TXT, or CSV files", "上传 Word、PDF、Markdown、TXT 或 CSV 文件"),
        type=["docx", "pdf", "md", "txt", "csv"],
        accept_multiple_files=True,
    )

    if st.button(_text("Generate document intake package", "生成文档摄取包"), disabled=not uploaded_files):
        out = _run_document_intake(uploaded_files)
        st.success(_generated_message(out))
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
        _download_package_label("document intake"),
        archive.read_bytes(),
        file_name=f"{out.name}.zip",
        mime="application/zip",
    )

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
        _text("Domain practitioner wizard", "领域工作流向导"),
        _text(
            "Describe your workflow, not an AI task. You do not need to know AI. Start by describing a repeated task in your work. The guided interview asks one question at a time; the advanced form is for users who already know the workflow details.",
            "请描述你的工作流，而不是 AI 任务。你不需要懂 AI，先说一项反复发生的真实工作。引导式访谈会一次只问一个问题；高级表单适合已经清楚工作流细节的用户。",
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

    with st.expander(_text("Interview mode", "访谈模式")):
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

    _guided_interview()
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
        submitted = st.form_submit_button(_text("Generate workflow alignment package", "生成工作流对齐包"))

    if submitted:
        problem_text = build_workflow_first_problem(answers)
        out = _run_problem_text(problem_text, "domain_practitioner")
        st.success(_generated_message(out))
        st.download_button(_text("Download problem.md", "下载 problem.md"), problem_text, file_name="problem.md")
        _render_friendly_output(out)

def _guided_interview() -> None:
    st.subheader(_text("Guided interview", "引导式访谈"))
    st.caption(
        _text(
            "ProblemBridge asks one question at a time, tracks what it understands, and routes the next question based on missing information.",
            "ProblemBridge 一次只问一个问题，会记录已经理解的内容，并根据缺失信息决定下一问。",
        )
    )

    if "problem_bridge_interview_state" not in st.session_state:
        st.session_state.problem_bridge_interview_state = start_interview()

    state = st.session_state.problem_bridge_interview_state
    summary = summarize_understanding(state)
    question = summary.next_question

    left, right = st.columns([1.35, 1])
    with left:
        st.markdown(f"### {_text('Next question', '下一个问题')}")
        st.write(_interview_copy(question, "prompt"))
        st.caption(_interview_copy(question, "helper"))
        if question.reframe:
            st.info(_interview_copy(question, "reframe"))

        if question.key != "confirmation":
            answer = st.text_area(_text("Your answer", "你的回答"), key=f"interview_answer_{question.key}")
            if st.button(_text("Save answer and continue", "保存回答并继续"), key="interview_save_answer"):
                st.session_state.problem_bridge_interview_state = answer_question(state, question.key, answer)
                st.rerun()
        else:
            st.success(_text(
                "The core workflow understanding is complete enough to generate an alignment package.",
                "核心工作流信息已经足够生成对齐包。",
            ))

        reset_col, generate_col = st.columns(2)
        with reset_col:
            if st.button(_text("Reset guided interview", "重置访谈"), key="interview_reset"):
                st.session_state.problem_bridge_interview_state = start_interview()
                st.rerun()
        with generate_col:
            ready = is_ready_for_alignment(state)
            if st.button(
                _text("Generate alignment package from interview", "根据访谈生成对齐包"),
                key="interview_generate",
                disabled=not ready,
            ):
                problem_text = build_problem_from_interview(state)
                out = _run_problem_text(problem_text, "guided_interview")
                st.success(_generated_message(out))
                st.download_button(_text("Download guided_interview_problem.md", "下载 guided_interview_problem.md"), problem_text, file_name="problem.md")
                _render_friendly_output(out)
            if not ready:
                st.caption(_text("Answer the missing items before generating the package.", "请先回答缺失项，再生成结果包。"))

    with right:
        st.markdown(f"### {_text('Understanding so far', '当前理解')}")
        st.progress(summary.completeness, text=_text(f"completeness: {int(summary.completeness * 100)}%", f"完整度：{int(summary.completeness * 100)}%"))
        if summary.known_items:
            st.write(_text("Known:", "已知："))
            for item in summary.known_items:
                st.write(f"- {_display_known_item(item)}")
        else:
            st.write(_text("No answers yet.", "还没有回答。"))

        if summary.missing_items:
            st.write(_text("Missing:", "缺失："))
            for item in summary.missing_items:
                st.write(f"- {_display_missing_item(item)}")
        else:
            st.success(_text("No core fields missing.", "核心字段已填写完整。"))


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
        submitted = st.form_submit_button(_text("Check task alignment", "检查任务是否对齐"))

    if submitted:
        problem_text = build_ai_practitioner_problem(answers)
        out = _run_problem_text(problem_text, "ai_practitioner")
        st.success(_generated_message(out))
        st.download_button(_text("Download problem.md", "下载 problem.md"), problem_text, file_name="problem.md")
        _render_friendly_output(out)

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
    runs = sorted([path for path in RUN_ROOT.glob("*") if path.is_dir()], reverse=True)
    if not runs:
        st.info(_text(
            "No UI-generated outputs yet. Run an example, document intake, question discovery, or wizard first.",
            "还没有 UI 生成的输出。请先运行示例、文档摄取、问题发现或向导。",
        ))
        return

    selected = st.selectbox(_text("Choose a generated run", "选择一个生成结果"), runs, format_func=lambda path: path.name)
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
    st.subheader(_text("User-facing summary", "面向用户的摘要"))

    top_left, top_right = st.columns([1.2, 1])
    with top_left:
        st.markdown(f"### {_text('One-sentence conclusion', '一句话结论')}")
        st.success(summary.one_sentence)
    with top_right:
        st.markdown(f"### {_text('Output folder', '输出文件夹')}")
        st.code(str(out), language="text")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f"### {_text('Priority opportunities', '优先机会')}")
        for item in summary.opportunities[:5]:
            st.write(f"- {item}")
    with col2:
        st.markdown(f"### {_text('Human review boundaries', '人工复核边界')}")
        for item in summary.must_review[:5]:
            st.write(f"- {item}")

    st.markdown(f"### {_text('Current workflow map', '当前工作流图')}")
    if summary.workflow_steps:
        for index, step in enumerate(summary.workflow_steps, start=1):
            st.write(f"{index}. {step}")
    else:
        st.write(_text("No clear workflow steps were identified yet.", "还没有识别出清晰的工作流步骤。"))

    st.markdown(f"### {_text('Next steps', '下一步')}")
    for item in summary.next_steps[:5]:
        st.write(f"- {item}")

    archive = _make_archive(out)
    st.download_button(
        _download_package_label("ProblemBridge alignment"),
        archive.read_bytes(),
        file_name=f"{out.name}.zip",
        mime="application/zip",
    )

    with st.expander(_text("Technical delivery package", "技术交付包")):
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
