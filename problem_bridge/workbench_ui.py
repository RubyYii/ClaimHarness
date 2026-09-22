"""Streamlit presentation for the shared problem record (no pipeline logic)."""
from __future__ import annotations

import csv
import io
from pathlib import Path

import streamlit as st

from .handoff import ConceptNote, NeedBrief
from .need_ui import render_handoffs, render_need_form
from .workbench import (
    FRAME_FIELDS, answer_follow_up, audit_problem, confirm_problem, load_audit, load_problem,
)


DEMO_TEXT = """# Synthetic document triage

All numbers below are invented for a software demonstration.

The triage_reviewer improves macro F1 from 0.70 to 0.82 in the synthetic benchmark.
The triage_reviewer improves precision from 0.76 to 0.95 in the synthetic benchmark.
The model is robust across all document domains.
"""
DEMO_CSV = "model,macro_f1,precision,recall\nbaseline_rules,0.70,0.76,0.65\ntriage_reviewer,0.82,0.86,0.78\n"


def interview_seed(answers: dict[str, str]) -> dict[str, str]:
    return {
        "question": answers.get("repeated_work", ""), "observation": answers.get("pain_points", ""),
        "observation_source": "User interview / 用户访谈",
        "desired_change": answers.get("useful_support", ""), "hypothesis": "",
        "human_boundary": answers.get("human_boundaries", ""),
    }


def _seed_fields(fields: dict[str, str]) -> None:
    for key in FRAME_FIELDS:
        st.session_state[f"unified_edit_{key}"] = fields.get(key, "")


def _seed_demo() -> None:
    st.session_state.unified_manuscript = DEMO_TEXT
    st.session_state.unified_csv = DEMO_CSV
    st.session_state.unified_references = ""
    st.session_state.pop("unified_reused_tables", None)
    st.session_state.pop("unified_uploaded_text", None)
    st.session_state.pop("unified_uploaded_tables", None)
    st.session_state.unified_upload_epoch = st.session_state.get("unified_upload_epoch", 0) + 1


def _go(stage: int) -> None:
    st.session_state.pending_unified_stage = stage


def _select_stage(widget_key: str) -> None:
    selected = st.session_state.get(widget_key)
    if selected in (1, 2, 3, 4):
        st.session_state.unified_stage = selected


def _select_finding(widget_key: str, selection_key: str) -> None:
    selected = st.session_state.get(widget_key)
    if selected:
        st.session_state[selection_key] = selected


def _return_to_problem(question: str, answer: str) -> None:
    st.session_state.unified_return_question = question + ("\n" + answer if answer else "")
    _go(1)


def _remember_uploads(widget_key: str, *, text_file: bool = False) -> None:
    uploaded = st.session_state.get(widget_key)
    if text_file:
        st.session_state.unified_uploaded_text = (uploaded.name, uploaded.getvalue()) if uploaded else None
    else:
        st.session_state.unified_uploaded_tables = [(item.name, item.getvalue()) for item in (uploaded or [])]


def _clear_uploads() -> None:
    st.session_state.pop("unified_uploaded_text", None)
    st.session_state.pop("unified_uploaded_tables", None)
    st.session_state.unified_upload_epoch = st.session_state.get("unified_upload_epoch", 0) + 1


def render_workbench(*, root: Path, project_id: str, current_out: Path | None,
                     text, run_action, save_result, interview_answers: dict[str, str],
                     render_downloads) -> None:
    """Callbacks retain the host's project/memory and error-handling policies."""
    record = None
    if current_out:
        try:
            record = load_problem(root, current_out, project_id)
        except (OSError, ValueError, RuntimeError, KeyError) as exc:
            st.error(text("The saved problem could not be verified. Open history or start a new project.", "保存的问题记录校验失败。请检查历史结果，或开始新项目。"))
            st.caption(str(exc))
            return
    if "pending_unified_stage" in st.session_state:
        st.session_state.unified_stage = st.session_state.pop("pending_unified_stage")
    if "pending_problem_seed" in st.session_state:
        _seed_fields(st.session_state.pop("pending_problem_seed"))
        st.session_state.unified_intake_step = 4
        st.session_state.unified_stage = 1
    st.session_state.setdefault("unified_stage", 3 if record and record.audit else (4 if record else 1))
    labels = {1: text("1 · Describe your work", "1 · 说清需求"),
              4: text("2 · Take your briefs", "2 · 带走说明"),
              2: text("3 · Check results (optional)", "3 · 核查材料（可选）"),
              3: text("4 · Follow up findings", "4 · 处理核查发现")}
    # Keep logical navigation separate from translated widget options. A fresh
    # language widget cannot deserialize a label left over from the other one.
    stage_key = text("unified_stage_en", "unified_stage_zh")
    st.session_state[stage_key] = st.session_state.unified_stage
    stages = [1, 4, 2, 3] if (record and record.audit) or st.session_state.unified_stage in (2, 3) else [1, 4]
    with st.container(key="unified_steps"):
        stage = st.radio(text("From your experience to a shared task", "从具体经历到共同理解的任务"), stages,
                         format_func=labels.get, key=stage_key, horizontal=True,
                         on_change=_select_stage, args=(stage_key,))
    if record and stage == 4:
        with st.expander(text(f"Your confirmed need · revision {record.revision}", f"已确认的需求 · 第 {record.revision} 次记录")):
            st.write(record.question)
            st.caption(text("Saved locally. Observations and hypotheses remain user-reported.", "已保存到本地，观察与假设仍保留为用户陈述。"))
    elif record and stage != 1:
        st.markdown(f"**{text('Current question', '当前问题')}**")
        st.write(record.question)
        st.caption(text(f"Saved locally · revision {record.revision}. Observations and hypotheses remain user-reported.",
                        f"已保存到本地 · 第 {record.revision} 次记录。观察与假设仍保留为用户陈述。"))
    if stage == 1:
        _problem_form(root, project_id, current_out, record, text, run_action, save_result, interview_answers)
    elif record is None:
        st.info(text("Start with one real task, then confirm the wording before preparing a handoff.",
                     "先从一件实际工作开始，确认表述后就能整理说明。"))
        st.button(text("Describe my work", "说说我的工作"), key="unified_back_start", on_click=_go, args=(1,))
    elif stage == 4:
        render_handoffs(current_out, record, text, _go, render_downloads)
    elif stage == 2:
        _materials_form(root, project_id, current_out, record, text, run_action, save_result)
    elif record.audit is None:
        st.info(text("This version of the question has no audit yet. Earlier results remain in history.",
                     "当前问题版本还没有核查结果；先前结果仍保存在历史记录中。"))
        st.button(text("Add materials", "补充材料并核查"), key="unified_no_audit", on_click=_go, args=(2,))
    else:
        _findings(root, project_id, current_out, record, text, run_action, save_result, render_downloads)


def _problem_form(root, project_id, current_out, record, text, run_action, save_result, answers):
    render_need_form(root, project_id, current_out, record, text, run_action, save_result, answers)
    if record is None:
        if st.button(text("See an example: researcher → collaborator / AI", "看一份示例：研究者怎样向合作者和 AI 提需求"), key="unified_need_demo"):
            def need_demo():
                return confirm_problem(root, project_id, {
                    "question": text("I want help comparing compositions in a few public paintings.", "我想找人帮忙比较几幅公开作品的构图。"),
                    "observation": text("My notes use different descriptions for the same feature.", "我记笔记时，对同一特征用了不同的描述，比较起来很费劲。"),
                    "observation_source": text("Invented example for this product demo.", "为产品演示编写的合成示例。"),
                    "desired_change": text("A comparison table with the work and region supporting each observation.", "一张比较表，每条观察能找到对应作品和画面位置。"),
                    "human_boundary": text("The researcher confirms interpretations and the comparison criteria.", "由研究者确认解释与比较标准。"),
                }, brief=NeedBrief(
                    background=text("Art researcher (synthetic example)", "艺术研究者（合成示例）"),
                    collaborator=text("A colleague who can help organize consistent observation fields.", "希望熟悉数据整理的同事一起确定统一的观察字段。"),
                    materials=text("Public reproductions and existing notes, not attached to this example.", "公开作品图片与已有笔记；此示例尚未附图。"),
                    success_check=text("Try two works first; I can locate each observation and correct the categories.", "先试两幅作品，我能定位每条观察，并修改不合适的分类。"),
                    concepts=[ConceptNote(term=text("Composition", "构图"), meaning=text("Positions and relationships of visible elements in this task.", "这里指画面元素的位置及相互关系。"),
                                          non_example=text("Not a ranking of artistic quality.", "不等于给作品艺术价值打分。"))]))
            out = run_action(text("Preparing a synthetic handoff example…", "正在整理合成需求示例……"), need_demo)
            if out:
                for key in list(st.session_state):
                    if str(key).startswith("unified_edit_"):
                        del st.session_state[key]
                save_result(out, 4)
        _audit_example(root, project_id, text, run_action, save_result)


def _audit_example(root, project_id, text, run_action, save_result):
    with st.expander(text("Try the optional evidence-checking example", "体验可选的材料核查示例")):
        if st.button(text("Try the complete synthetic example", "用合成示例体验完整流程"), key="unified_demo"):
            def demo():
                problem = confirm_problem(root, project_id, {
                    "question": text("Which document-triage claims are supported by the result table?", "文档分流报告中的结论，哪些有结果表支持？"),
                    "observation": text("The report and table contain different precision values (invented).", "报告和表格的 precision 数值不同（合成数据）。"),
                    "observation_source": "Synthetic demo / 合成演示", "hypothesis": text("One number may come from a different version.", "数字可能来自不同版本。"),
                    "desired_change": text("Identify the source and questions for the author.", "找到来源，并明确应向作者追问什么。"),
                    "human_boundary": text("The author confirms explanations and final conclusions.", "原因解释和最终结论由作者确认。"),
                })
                return audit_problem(root, project_id, problem, manuscript=DEMO_TEXT, tables={"results.csv": DEMO_CSV.encode()})
            out = run_action(text("Checking the synthetic example locally…", "正在本地核查合成示例……"), demo)
            if out:
                save_result(out, 3)


def _materials_form(root, project_id, current_out, record, text, run_action, save_result):
    st.caption(text("Local checks compare supported claim patterns with CSV results. English numerical claims work best; extraction coverage is unknown. Alignment templates are context, not experimental evidence.",
                    "本地规则核对可识别的表述与 CSV 结果，目前以英文数值声明为主，提取是否完整仍需人工检查。流程模板仅作背景，不是实验凭据。"))
    # On reopening, restore exact audited source bytes instead of requiring re-entry.
    if record.audit and "unified_manuscript" not in st.session_state:
        try:
            files, _ = load_audit(root, record)
            st.session_state.unified_manuscript = files["source_files/manuscript.md"].decode("utf-8")
            st.session_state.unified_references = files.get("source_files/references.md", b"").decode("utf-8")
            st.session_state.unified_reused_tables = {Path(name).name: data for name, data in files.items() if name.startswith("source_files/tables/")}
        except (OSError, ValueError, RuntimeError, KeyError) as exc:
            st.error(text("Could not restore the verified source snapshot.", "无法恢复经过校验的来源快照。"))
            st.caption(str(exc))
            return
    st.button(text("Fill with synthetic sample materials", "填入合成样例材料"), key="unified_sample_materials", on_click=_seed_demo)
    st.caption(text("Up to 2 MB per input, 10 MB total; CSV tables need column names and data rows.", "每份输入不超过 2 MB，合计不超过 10 MB；CSV 需包含列名和数据行。"))
    manuscript = st.text_area(text("Text to check", "待核查正文"), key="unified_manuscript", height=160)
    epoch = st.session_state.get("unified_upload_epoch", 0)
    with st.expander(text("Upload text instead (Markdown / TXT)", "也可上传正文（Markdown / TXT）")):
        st.file_uploader(text("Uploaded text replaces the pasted text above", "上传正文将替代上方粘贴的正文"), type=["md", "txt"], key=f"unified_text_upload_{epoch}", max_upload_size=2,
                         on_change=_remember_uploads, args=(f"unified_text_upload_{epoch}",), kwargs={"text_file": True})
    st.file_uploader(text("Result tables (CSV)", "结果表（CSV）"), type=["csv"], accept_multiple_files=True, key=f"unified_table_upload_{epoch}", max_upload_size=2,
                     on_change=_remember_uploads, args=(f"unified_table_upload_{epoch}",))
    uploaded_text = st.session_state.get("unified_uploaded_text")
    uploads = st.session_state.get("unified_uploaded_tables", [])
    if uploaded_text or uploads:
        names = ([uploaded_text[0]] if uploaded_text else []) + [name for name, _ in uploads]
        st.caption(text("Selected files kept in this session: ", "本次会话已暂存上传文件：") + ", ".join(names))
        st.button(text("Clear selected uploads", "清除暂存的上传文件"), key="unified_clear_uploads", on_click=_clear_uploads)
    pasted_csv = st.text_area(text("Or paste one CSV table, including column names", "或粘贴一份 CSV 表格，包含列名"),
                             key="unified_csv", height=115, placeholder="model,precision\nbaseline,0.76\nproposed,0.86")
    reused = st.session_state.get("unified_reused_tables", {})
    if reused and not uploads and not pasted_csv.strip():
        st.caption(text("Reusing saved tables: ", "沿用上次已保存的表格：") + ", ".join(reused))
    st.caption(text("New uploads or pasted CSV replace the saved tables. If both are supplied, both are checked.",
                    "上传或粘贴新表格会替换上次的表格；同时上传和粘贴时，会一同核查。"))
    with st.expander(text("Reference text (optional)", "参考文字（可选）")):
        references = st.text_area(text("References or source notes", "参考资料或来源说明"), key="unified_references")
    if st.button(text("Run local evidence check", "开始本地核查"), key="unified_run_audit", type="primary"):
        if not uploaded_text and not manuscript.strip():
            st.error(text("Paste or upload the text to check first.", "请先粘贴或上传待核查正文。"))
            return
        if not uploads and not pasted_csv.strip() and not reused:
            st.error(text("Upload or paste at least one CSV result table.", "请上传或粘贴至少一份 CSV 结果表。"))
            return
        def run():
            supplied = {}
            for name, data in uploads:
                if name in supplied:
                    raise ValueError("Duplicate CSV filenames: rename one of the tables.")
                supplied[name] = data
            if pasted_csv.strip():
                name = "pasted_results.csv"
                if name in supplied:
                    raise ValueError("Rename uploaded pasted_results.csv before also pasting a table.")
                supplied[name] = pasted_csv.encode("utf-8")
            body = uploaded_text[1].decode("utf-8-sig") if uploaded_text else manuscript
            return audit_problem(root, project_id, current_out, manuscript=body, tables=supplied or reused, references=references)
        out = run_action(text("Checking statements and source tables…", "正在核对表述与来源表格……"), run)
        if out:
            save_result(out, 3)


def _findings(root, project_id, current_out, record, text, run_action, save_result, render_downloads):
    try:
        files, feedback = load_audit(root, record)
    except (OSError, ValueError, RuntimeError, KeyError) as exc:
        st.error(text("The linked audit could not be verified. Keep it for inspection and run a new check.", "关联的核查结果无法通过校验，请保留供检查并重新核查。"))
        st.caption(str(exc))
        st.button(text("Return to materials", "返回材料核查"), key="unified_retry_materials", on_click=_go, args=(2,))
        return
    rows = list(csv.DictReader(io.StringIO(files["claim_table.csv"].decode("utf-8"))))
    normalize = lambda value: value.replace("\r\n", "\n").strip()
    text_draft = st.session_state.get("unified_manuscript")
    uploaded_text = st.session_state.get("unified_uploaded_text")
    if uploaded_text:
        text_draft = uploaded_text[1].decode("utf-8-sig", errors="replace")
    csv_draft = st.session_state.get("unified_csv", "")
    reference_draft = st.session_state.get("unified_references")
    changed_draft = (
        text_draft is not None and normalize(text_draft) != normalize(files["source_files/manuscript.md"].decode("utf-8"))
        or reference_draft is not None and normalize(reference_draft) != normalize(files.get("source_files/references.md", b"").decode("utf-8"))
    )
    uploaded_tables = st.session_state.get("unified_uploaded_tables", [])
    if uploaded_tables or csv_draft.strip():
        draft_tables = {name: normalize(data.decode("utf-8-sig", errors="replace")) for name, data in uploaded_tables}
        if csv_draft.strip():
            draft_tables["pasted_results.csv"] = normalize(csv_draft)
        saved_tables = {Path(name).name: normalize(data.decode("utf-8-sig")) for name, data in files.items() if name.startswith("source_files/tables/")}
        changed_draft = changed_draft or draft_tables != saved_tables
    if changed_draft:
        st.warning(text("Your material draft has changed. These findings still refer to the last saved audit; run a new check to include your edits.",
                        "材料草稿已修改。下面仍是上次保存的核查结果，不包含这些修改；请返回材料步骤重新核查。"))
    questions = feedback["questions"]
    count = feedback["claim_count"]
    attention = len([item for item in questions if item["claim_id"]])
    st.markdown(text(f"**{count} statements extracted · {attention} to follow up**",
                     f"**已提取 {count} 条表述 · 其中 {attention} 条需要跟进**"))
    if count == 0:
        st.warning(text("No claims were extracted. This does not mean the text passed; inspect it manually or use an explicit numerical sentence.",
                        "没有提取到可核查声明。这不代表正文已通过；请人工检查，或补充明确的数值表述。"))
    else:
        st.caption(text("Findings apply only to these extracted statements and this saved material version. Compare the full text for missed claims.",
                        "发现仅针对已提取表述及本次保存的材料版本，请对照原文检查遗漏。"))
    labels = {
        "conflict": text("Source discrepancy", "来源不一致"), "human_review": text("Human review", "需人工复核"),
        "evidence_gap": text("Missing evidence", "缺少证据"), "coverage": text("Check for missed statements", "检查提取遗漏"),
    }
    by_id = {item["question_id"]: item for item in questions}
    selection_key = f"unified_selected_{record.audit.run_id}"
    finding_key = text(f"unified_finding_{record.audit.run_id}_en", f"unified_finding_{record.audit.run_id}_zh")
    st.session_state[finding_key] = st.session_state.get(selection_key, next(iter(by_id)))
    selected = st.selectbox(text("Choose a finding to work on", "选择一条发现，继续处理"), list(by_id),
                            format_func=lambda key: f"{labels[by_id[key]['kind']]} · {by_id[key].get('claim_text', '')[:80]}".rstrip(" ·"),
                            key=finding_key, on_change=_select_finding, args=(finding_key, selection_key))
    item = by_id[selected]
    with st.container(border=True):
        if item.get("claim_text"):
            st.write(item["claim_text"])
            statuses = {"supported": text("Supported by supplied evidence", "所提供证据支持"),
                        "weakly_supported": text("Limited support", "支持有限"),
                        "unsupported": text("No adequate support found", "未找到充分支持"),
                        "overclaimed": text("Claim exceeds evidence", "表述超出证据范围"),
                        "needs_human_review": text("Human review needed", "需要人工复核")}
            st.caption(f"{item['claim_id']} · {statuses.get(item['status'], item['status'])}")
        question = text(item["question_en"], item["question_zh"])
        st.info(question)
        with st.expander(text("Why this was flagged / source locations", "为什么被标记／查看来源位置")):
            st.write(item.get("reason", ""))
            st.write(item.get("suggested_revision", ""))
            for evidence in item.get("evidence", []):
                locator = evidence.get("locator") or {}
                st.caption(f"{evidence['evidence_id']} · {evidence['relation']} · {locator.get('source_file') or locator.get('source_name', '')} · row {locator.get('row') or '—'} / line {locator.get('line') or '—'}")
                st.write(evidence.get("text", ""))
                if locator.get("cells"):
                    st.dataframe(locator["cells"], hide_index=True, use_container_width=True)
        responses = [response for response in record.responses if response.audit_run_id == record.audit.run_id and response.question_id == selected]
        if responses:
            st.caption(text("Last recorded answer (not verified)", "最近一次回答（尚未验证）"))
            st.write(responses[-1].answer)
        answer = st.text_area(text("What will you check, ask, or change next?", "你接下来准备查什么、问谁，或修改哪里？"),
                              key=f"unified_answer_{record.audit.run_id}_{selected}", height=95)
        st.caption(text("Saving an answer records your plan; it does not resolve the finding or approve the claim.",
                        "保存回答只记录你的计划，不会自动消除发现或批准结论。"))
        if st.button(text("Save this next action", "保存这条下一步行动"), key="unified_save_answer", type="primary"):
            if not answer.strip():
                st.error(text("Write what you plan to check or whom you will ask.", "请先填写准备查什么，或准备向谁确认。"))
                return
            out = run_action(text("Saving the follow-up…", "正在保存追问记录……"),
                             lambda: answer_follow_up(root, project_id, current_out, selected, answer))
            if out:
                save_result(out, 3)
    left, right = st.columns(2)
    left.button(text("Bring this question back to framing", "带着这条追问重新梳理"), key="unified_reframe",
                on_click=_return_to_problem, args=(question, responses[-1].answer if responses else ""))
    right.button(text("Update materials and check again", "补充材料，再核查一次"), key="unified_rerun", on_click=_go, args=(2,))
    with st.expander(text("All extracted statements", "全部已提取表述")):
        st.dataframe([{text("Statement", "表述"): row["text"], text("Status", "状态"): row["status"], "claim_id": row["claim_id"]} for row in rows], hide_index=True, use_container_width=True)
    with st.expander(text("Download / inspect records", "下载与检查记录")):
        st.download_button(text("Download next questions", "下载下一步问题清单"), files["follow_up.md"], file_name="follow_up.md")
        render_downloads(root / record.audit.run_name, "ProblemBridge evidence check")
        if current_out.name != record.audit.run_name:
            render_downloads(current_out, "ProblemBridge follow-up")
