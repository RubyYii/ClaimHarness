"""Source review, handling journals and conservative run comparison."""
import json
from pathlib import Path

import streamlit as st

from .comparison import compare_runs, load_audit_run, render_comparison, render_pending
from .continuity_store import Journal, digest
from .handling import annotate, audit_journal, record_handling


CHANGE_LABELS = {
    "unchanged": "原句与核查结果未变", "text_modified": "原句已修改", "split_or_merge": "声明拆分或合并",
    "result_changed": "核查判断变化", "evidence_changed": "关联证据变化", "rules_changed": "核查规则变化",
    "rules_unknown": "核查规则版本未知", "text_removed": "原句移除或改写待对应", "not_extracted": "原句仍在但本轮未提取",
    "new_statement": "新增原句或改写待对应", "correspondence_pending": "待确认对应", "unable_to_compare": "无法比较",
}
CHANGE_EXPLANATIONS = {
    "unchanged": "已对应的原句、程序结果、关联证据和规则均未改变。",
    "text_modified": "用户已明确指定改写关系。请对照旧新措辞和本轮程序结果，决定是否还需补充证据。",
    "split_or_merge": "用户已明确指定拆分或合并关系。请分别检查每条新声明及其依据。",
    "result_changed": "原句已对应，程序判断发生变化。材料和规则的变化分别列出，不自动归因为问题已修复。",
    "evidence_changed": "原句已对应，但关联证据或证据位置发生变化。请检查实际内容及本轮判断。",
    "text_removed": "旧句已不再逐字出现，可能被删除或改写。删除不代表补足证据；若为改写，请明确指定对应。",
    "not_extracted": "旧句仍在当前原文中，但本轮没有提取到。请核对可能的漏检。",
    "new_statement": "当前原文出现新的逐字表述，也可能是旧句改写。请检查本轮判断或指定对应关系。",
    "correspondence_pending": "相同或重复表述尚无唯一可靠对应，需要用户确认。",
    "unable_to_compare": "原文快照或对应资料不足，不能从提取清单的变化推断句子已删除或新增。",
}


def available_runs(root: Path, project_id=None):
    result = {}
    for path in root.iterdir() if root.exists() else []:
        if not (path / "run_manifest.json").is_file():
            continue
        run = load_audit_run(path)
        if project_id is None or run.ref["project_id"] == project_id:
            result[path.name] = run
    return dict(sorted(result.items(), key=lambda item: str(item[1].manifest.get("started_at", ""))))


def render_review_tools(workspace: Path, current: Path, text, run_action, *, standalone=False):
    language = text("en", "zh")
    text = lambda en, zh: zh if language == "zh" else en
    run = load_audit_run(current)
    source_context = digest(run.ref)
    if st.session_state.get("continuity_source_context") != source_context:
        # Draft notes belong to one saved source; never carry them into another run.
        for key in list(st.session_state):
            if key.startswith(("continuity_manual_", "continuity_note_")):
                del st.session_state[key]
        st.session_state["continuity_source_context"] = source_context
    with st.expander(text("Compare two audit runs", "比较两次核查"), expanded=standalone):
        _comparison(workspace, run, text, run_action)
    if run.integrity != "verified":
        st.warning(text("This report cannot accept version-bound notes because its completeness/identity is unverified.", "此报告的完整性或身份尚未确认，无法写入版本绑定的处理记录。"))
        return
    journal = audit_journal(workspace, run)
    history = journal.read()
    token = f"audit_note_revision_{digest(run.ref)}"
    st.session_state.setdefault(token, history["revision"])
    expected = st.session_state[token]
    if expected != history["revision"]:
        st.warning(text("Newer notes exist. Reload them before submitting.", "已有较新的处理记录，请载入后再提交。"))
    if st.button(text("Reload source-review notes", "重新载入原文复查记录"), key=f"notes_reload_{run.ref['run_id']}"):
        st.session_state[token] = history["revision"]
        st.rerun()
    with st.expander(text("Original text and missed-statement annotations", "原文对照与遗漏补标"), expanded=standalone):
        _source_review(workspace, run, history, expected, token, text, run_action)
    with st.expander(text("Program results, user actions and human opinions", "程序结果、用户处理与人工意见"), expanded=standalone):
        _handling(workspace, run, history, expected, token, text, run_action)


def _source_review(workspace, run, history, expected, token, text, run_action):
    st.caption(text("Only extracted positions are marked. Full-text extraction coverage is unknown; no coverage percentage is inferred.",
                    "这里只标明已提取位置。全文提取完整性未知，不由关联比例推算覆盖率。"))
    if run.text is None:
        st.warning(text("This old report has no original snapshot. Run a new check before adding an exact source annotation.", "旧报告没有原文快照。请先重新核查，再补标准确的原文位置。"))
        return
    marks = {}
    for c in run.claims:
        marks.setdefault(c.get("source_line"), []).append(c["claim_id"])
    st.code("\n".join(f"{i:4d} {'[' + ','.join(marks[i]) + ']' if i in marks else '[—]'} {line}" for i, line in enumerate(run.text.splitlines(), 1)), language=None, wrap_lines=True)
    if not run.claims:
        st.warning(text("Zero statements extracted does not mean the text passed.", "零条提取结果不代表全文通过。"))
    st.dataframe([{text("Claim", "声明"): c["claim_id"], text("Line", "原文行"): c.get("source_line"), text("Text", "原句"): c["text"]} for c in run.claims], hide_index=True, use_container_width=True)
    with st.form(f"manual_annotation_{run.ref['run_id']}"):
        quote = st.text_area(text("Paste an exact missed passage from the saved source", "粘贴保存原文中遗漏的一段文字"), key="continuity_manual_quote")
        occurrence = st.number_input(text("Occurrence to select if repeated (1 = first)", "重复出现时选择第几处（1 表示第一处）"), min_value=1, value=1, key="continuity_manual_occurrence")
        question = st.text_area(text("What needs a human check?", "这段文字需要人工核对什么？"), key="continuity_manual_question")
        evidence = st.multiselect(text("Candidate evidence (not verified support)", "候选证据（不等于已验证支持）"), list(run.evidence), key="continuity_manual_evidence")
        submit = st.form_submit_button(text("Add as unevaluated review item", "加入待核对清单（未评价）"))
    if submit:
        def save():
            if not quote:
                raise ValueError("Select an exact non-empty passage.")
            positions, offset = [], 0
            while True:
                found = run.text.find(quote, offset)
                if found < 0:
                    break
                positions.append(found)
                offset = found + len(quote)
            if occurrence > len(positions):
                raise ValueError("That exact passage/occurrence is absent from this saved source.")
            start = positions[int(occurrence) - 1]
            return annotate(workspace, run.path, start=start, end=start + len(quote), question=question,
                            candidate_evidence=evidence, expected_revision=expected)
        value = run_action(text("Saving source annotation…", "正在保存原文补标……"), save)
        if value:
            st.session_state[token] = value["revision"]
            st.rerun()
    for event in history["events"]:
        if event["kind"] == "manual_claim":
            item = event["payload"]
            st.info(f"{item['manual_id']} · {text('Not evaluated; human check needed', '本轮未评价，需人工核对')} · line {item['source']['line']}")
            st.text(item["text"])
            st.write(item["question"])


def _handling(workspace, run, history, expected, token, text, run_action):
    claims = {c["claim_id"]: c for c in run.claims}
    manual = {e["payload"]["manual_id"]: e["payload"] for e in history["events"] if e["kind"] == "manual_claim"}
    options = {**claims, **manual}
    if not options:
        st.info(text("No extracted findings. Use the original-text panel to add an unevaluated item.", "尚无提取发现，可在原文对照中加入未评价的项目。"))
        return
    selected = st.selectbox(text("Finding to handle", "要处理的发现"), list(options), format_func=lambda k: f"{k} · {options[k]['text'][:90]}", key=f"continuity_handling_claim_{digest(run.ref)}")
    st.markdown(text("**Program result for this saved version**", "**本保存版本的程序结果**"))
    item = options[selected]
    st.text(item["text"])
    if selected in manual:
        st.info(text("Not evaluated; annotation does not supply support.", "本轮未评价；手工补标不产生支持判定。"))
    else:
        status = item["status"]
        conflict = bool(item.get("contradicting_evidence_ids"))
        st.write(text("Evidence conflict", "存在证据冲突") if conflict else text("Evidence insufficient", "证据不足") if status == "unsupported" else status)
        st.write(item.get("reason", ""))
        for link in item.get("evidence_links", []):
            loc = link.get("locator") or {}
            st.caption(f"{link['evidence_id']} · {link['relation']} · {loc.get('source_file') or loc.get('source_name')} · row {loc.get('row')} / line {loc.get('line')}")
    for layer, label in [("user_action", text("User handling records", "用户处理记录")), ("human_review", text("Attributed human opinions", "注明来源的人工意见"))]:
        st.markdown(f"**{label}**")
        notes = [e for e in history["events"] if e["kind"] == layer and e["payload"]["claim_id"] == selected]
        if not notes:
            st.caption(text("None recorded", "尚未记录"))
        for e in notes:
            n = e["payload"]
            st.write(f"{n['action']} · {n['note']}")
            st.caption(f"{e['recorded_at']} · {n['actor']} · {n['source']}")
            if n.get("rerun"):
                st.caption(text("Linked rerun: ", "关联的新一轮核查：") + str(n["rerun"]["run"]["run_id"]))
                for change in n["rerun"]["changes"]:
                    st.write(change["reason"])
                    for c in change["current"]:
                        st.write(f"{c['claim_id']} · {c['status']} · {c['text']}")
    runs = available_runs(workspace, run.ref["project_id"])
    with st.form(f"handling_note_{run.ref['run_id']}"):
        layer = st.selectbox(text("Record type", "记录类型"), ["user_action", "human_review"], format_func=lambda v: text("User action", "用户处理") if v == "user_action" else text("Human opinion", "人工意见"), key="continuity_note_layer")
        action = st.selectbox(text("Action status", "行动状态"), ["planned", "done", "retain_with_explanation", "request_review"],
            format_func=lambda v: {"planned": text("Planned", "计划做"), "done": text("User reports done", "用户报告已完成"), "retain_with_explanation": text("Keep wording and explain", "保留原文并解释"), "request_review": text("Ask for review", "请人复核")}[v], key="continuity_note_action")
        note = st.text_area(text("What will / did you do, or what was the opinion?", "计划／已经做了什么，或复核意见是什么？"), key="continuity_note_text")
        actor = st.text_input(text("Reviewer name (for human opinions)", "复核者姓名（人工意见需填写）"), key="continuity_note_actor")
        source = st.text_input(text("Opinion source and material version", "意见来源与所针对材料版本"), key="continuity_note_source")
        candidates = [k for k, r in runs.items() if r.ref["run_id"] != run.ref["run_id"] and r.integrity == "verified"]
        rerun = st.selectbox(text("Link a completed rerun (optional)", "关联已完成的新一轮核查（可选）"), [None, *candidates], key="continuity_note_rerun")
        same = st.checkbox(text("The linked rerun is this same task", "关联的核查属于同一任务"), key="continuity_note_same_task")
        st.caption(text("Plans and 'done' notes do not close program findings. Reviewer identity/qualifications are not authenticated.", "计划和“已完成”记录不会关闭程序发现；此处没有核验复核者身份或资格。"))
        submit = st.form_submit_button(text("Save separate handling record", "单独保存处理记录"))
    if submit:
        value = run_action(text("Saving handling note…", "正在保存处理记录……"), lambda: record_handling(workspace, run.path,
            claim_id=selected, layer=layer, action=action, note=note, actor=actor, source=source,
            expected_revision=expected, rerun=runs[rerun].path if rerun else None, same_task=same))
        if value:
            st.session_state[token] = value["revision"]
            st.rerun()
    st.download_button(text("Download source annotations and handling history", "下载原文补标与处理历史"), json.dumps(history, ensure_ascii=False, indent=2), file_name="handling_history.json", mime="application/json")


def _comparison(workspace, current, text, run_action):
    runs = available_runs(workspace, current.ref["project_id"])
    if not runs:
        st.info(text("No saved audit packages found.", "尚未找到保存的核查包。"))
        return
    keys = list(runs)
    old_key = st.selectbox(text("Previous audit", "上一轮核查"), keys, index=max(0, len(keys) - 2), key="continuity_previous")
    new_key = st.selectbox(text("Current audit", "当前核查"), keys, index=keys.index(current.path.name) if current.path.name in keys else len(keys) - 1, key="continuity_current")
    old, new = runs[old_key], runs[new_key]
    pair = {"kind": "claim_correspondence", "previous": old.ref, "current": new.ref}
    pair_key = digest(pair)
    confirmed = st.checkbox(text("I confirm these are the same task and document lineage", "我确认这两轮属于要比较的同一任务与正文版本"), key=f"continuity_same_{pair_key}")
    journal = Journal(workspace, pair)
    saved = journal.read()
    links = saved["events"][-1]["payload"]["mappings"] if saved["events"] else []
    token = f"mapping_revision_{pair_key}"
    st.session_state.setdefault(token, saved["revision"])
    with st.expander(text("Confirm rewritten, split or merged statements", "明确改写、拆分或合并的声明对应")):
        st.caption(text("Select one or several statements on each side. IDs are local to their run. Unselected items remain unresolved.", "可在两侧各选一条或多条。编号只属于各自运行；不选择的对应保持未确认。"))
        with st.form(f"mapping_{pair_key}"):
            a = st.multiselect(text("Previous statements", "上一轮声明"), [c["claim_id"] for c in old.claims], format_func=lambda k: k + " · " + next(c["text"] for c in old.claims if c["claim_id"] == k), key=f"mapping_old_{pair_key}")
            b = st.multiselect(text("Current statements", "当前声明"), [c["claim_id"] for c in new.claims], format_func=lambda k: k + " · " + next(c["text"] for c in new.claims if c["claim_id"] == k), key=f"mapping_new_{pair_key}")
            reason = st.text_input(text("Why these statements correspond", "这些声明如何对应，依据是什么"), key=f"mapping_reason_{pair_key}")
            submit = st.form_submit_button(text("Save this correspondence", "保存这个对应关系"), disabled=not confirmed)
        if submit:
            proposed = [*links, {"previous_ids": a, "current_ids": b, "reason": reason}]
            def save_mapping():
                value = compare_runs(old, new, same_task=True, mappings=proposed)
                if value["comparability"] == "blocked":
                    raise ValueError("Incomplete or invalid runs cannot receive mappings.")
                return journal.append("mapping", {"mappings": proposed}, expected_revision=st.session_state[token])
            result = run_action(text("Saving correspondence…", "正在保存对应关系……"), save_mapping)
            if result:
                st.session_state[token] = result["revision"]
                st.rerun()
        if links and st.button(text("Clear user mappings (keep history)", "清空手工对应（保留历史）"), key=f"mapping_clear_{pair_key}"):
            value = run_action(text("Saving change…", "正在保存修改……"), lambda: journal.append("mapping_reset", {"mappings": []}, expected_revision=st.session_state[token]))
            if value:
                st.session_state[token] = value["revision"]
                st.rerun()
    value = compare_runs(old, new, same_task=confirmed, mappings=links, workspace=workspace)
    st.write(text("Comparability: " + value["comparability"], "可比性：" + {"blocked": "暂不能比较", "limited": "有限可比", "comparable": "可比较"}[value["comparability"]]))
    for limitation in value["limitations"]:
        if limitation.startswith("Confirm that"):
            st.warning(text(limitation, "请先确认这两轮属于你要比较的同一任务与正文版本。"))
        elif "snapshot is missing" in limitation:
            st.warning(text(limitation, "旧记录缺少原文或规则快照，不能仅凭少了一条提取结果认定原句被删除。"))
        elif "Checking rules" in limitation:
            st.warning(text(limitation, "核查规则已改变或版本未知；判断变化不能直接解释为用户修复了问题。"))
        else:
            st.warning(limitation)
    if value["comparability"] == "blocked":
        return
    st.markdown(text("**Checking rules**", "**核查规则**"))
    st.write(text(value["rules"]["state"], {"changed": "规则已改变", "unchanged": "规则一致", "unknown": "规则版本未知"}[value["rules"]["state"]]))
    with st.expander(text("Rule version details", "规则版本详情")):
        st.json(value["rules"])
    st.markdown(text("**Changed input materials**", "**输入材料变化**"))
    if not value["materials"]:
        st.caption(text("No input hash changes.", "输入哈希未改变。"))
    for material in value["materials"]:
        st.write(material["source"])
        if material["cells"]:
            st.dataframe(material["cells"], hide_index=True, use_container_width=True)
        st.caption(text("Related changes: ", "涉及变化项：") + ", ".join(material["affected_changes"]))
    changes = value["changes"]
    if changes:
        selected = st.selectbox(text("Inspect a change", "查看一项变化"), list(range(len(changes))),
                               format_func=lambda i: f"{changes[i]['change_id']} · {text(changes[i]['kind'], CHANGE_LABELS.get(changes[i]['kind'], changes[i]['kind']))}", key=f"change_choice_{pair_key}_{saved['revision']}_{text('en', 'zh')}")
        change = changes[selected]
        st.info(text(change["reason"], CHANGE_EXPLANATIONS.get(change["kind"], "请对照下面的原句、证据和规则变化，保留尚未明确的判断。")))
        with st.expander(text("Recorded correspondence and change reason", "记录的对应依据与变化原因")):
            st.write(change["reason"])
        for side, label in [("previous", text("Previous wording and result", "上一轮原句与判断")), ("current", text("Current wording and result", "当前原句与判断"))]:
            with st.container(border=True):
                st.markdown(f"**{label}**")
                for claim in change[side]:
                    st.text(claim["text"])
                    st.write(f"{claim['claim_id']} · {claim['status']} · {claim.get('source_section')} · line {claim.get('source_line')}")
                    st.write(claim.get("reason", ""))
                    with st.expander(text("Evidence locations", "证据位置")):
                        st.json(claim["evidence"])
        if change.get("text_diff"):
            st.code(change["text_diff"], language="diff")
    st.write(text("Deleted wording, missing extractions, changed rules and user plans do not automatically mean a finding is resolved.", "删除原句、漏提取、规则变化或用户计划，都不自动表示发现已解决。"))
    with st.container(horizontal=True):
        for name, content, mime in [("audit_changes.md", render_comparison(value), "text/markdown"), ("audit_changes.json", json.dumps(value, ensure_ascii=False, indent=2), "application/json"), ("pending_questions.md", render_pending(value), "text/markdown")]:
            st.download_button(text("Download ", "下载 ") + name, content, file_name=name, mime=mime, key=f"download_{pair_key}_{name}")
    if st.checkbox(text("Prepare optional research questions for AWT / collaborator clarification", "按需准备给 AWT 或材料提供者的后续问题"), key=f"research_export_{pair_key}"):
        st.download_button(text("Download research discussion input", "下载研究讨论输入"), render_pending(value, research=True), file_name="research_questions.md", mime="text/markdown")
