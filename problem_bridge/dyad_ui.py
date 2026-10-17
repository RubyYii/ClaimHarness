"""A compact role-switching walkthrough on top of the local handoff records."""
from __future__ import annotations

import json

import streamlit as st

from .dyad import (STATUSES, acknowledge, check_sample, confirm_response, handoff_state,
                   read_sample, recipient_reply, save_draft, save_sample)
from .feedback_ui import saved_versions
from .requirements import confirm_requirements, current_trace, render_trace, source_catalog
from .workbench import FRAME_FIELDS, load_problem


def _role(role):
    st.session_state.unified_dyad_role = role


def _labels(text):
    return {"ready": text("Can continue", "可以继续"),
            "partial": text("Can partly continue", "部分可以继续"),
            "discuss": text("Needs discussion", "仍需讨论")}


def _saved(value, token):
    if value:
        st.session_state[token] = value["revision"]
        st.rerun()


def _baseline(out, root, project_id, save_result):
    if out:
        record = load_problem(root, out, project_id)
        for field in FRAME_FIELDS:
            st.session_state[f"unified_edit_{field}"] = getattr(record, field)
        save_result(out, 7)


def render_dyad(root, project_id, current, record, text, run_action, save_result):
    language = text("en", "zh")
    text = lambda en, zh: zh if language == "zh" else en
    st.markdown("""<style>
    .st-key-primary_navigation button[kind="primary"],
    .st-key-primary_navigation button[kind="primary"]:hover {
        background: #e1ece5 !important; color: #214f3d !important;
        border: 1px solid #80a28e !important; border-left: 4px solid #285e46 !important;
    }
    .st-key-primary_navigation button[kind="primary"] p { color: #214f3d !important; }
    [data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] p,
    [data-testid="InputInstructions"] { color: #486157 !important; opacity: 1; }
    </style>""", unsafe_allow_html=True)
    versions = saved_versions(root, record)
    if versions and versions[-1][1].revision > record.revision:
        st.warning(text("A newer need version exists. Open it before continuing.", "这份说明已有新版本，请先打开新版再继续。"))
        if st.button(text("Open the latest version", "打开最新版本"), key="unified_dyad_latest"):
            _baseline(versions[-1][0], root, project_id, save_result)
        return
    state = handoff_state(root, current, record)
    token = f"unified_dyad_revision_{record.problem_id}_{current.name}"
    st.session_state.setdefault(token, state["history"]["revision"])
    expected = st.session_state[token]
    st.caption(text("Use one computer or a shared screen and take turns. Roles record who acted; they are not verified accounts.",
                    "同一台电脑或共享屏幕，轮流操作。角色用于记录谁做了什么，不代表已验证的账号。"))
    role = st.radio(text("Who is operating now?", "现在由谁操作？"), ["B", "A"],
        format_func=lambda r: text("B · Technical collaborator", "B · 技术协作者") if r == "B" else text("A · Domain participant", "A · 领域参与者"),
        horizontal=True, key="unified_dyad_role")
    actor_key = f"unified_dyad_actor_{role}"
    st.session_state.setdefault(actor_key, role)
    actor = st.text_input(text("Your name or participant code", "你的称呼或参与者编号"), key=actor_key, max_chars=500)
    if expected != state["history"]["revision"]:
        st.warning(text("New activity was saved elsewhere. Reload before submitting; your draft stays on screen.",
                        "已有新记录，请重新载入再提交；当前草稿会保留，提交前请重新核对。"))
    if st.button(text("Reload saved handoff", "重新载入交接记录"), key="unified_dyad_reload"):
        st.session_state[token] = state["history"]["revision"]
        st.rerun()
    with st.container(border=True):
        st.markdown(text(f"**Working brief · v{record.revision}**", f"**当前工作说明 · v{record.revision}**"))
        st.write(record.question)
        if record.desired_change:
            st.write(record.desired_change)
        labels = _labels(text)
        columns = st.columns(2)
        for col, who in zip(columns, ("A", "B")):
            ack = state["acknowledgements"].get(who)
            col.write(f"{who} · " + (f"{labels[ack['status']]} · {ack['actor']}" if ack else text("Not confirmed for this version", "尚未确认本版")))
            if ack and ack.get("note"):
                with col.expander(text(f"{who}'s review note", f"{who} 的核对意见")):
                    st.text(ack["note"])
        with st.expander(text("Read the full current brief", "展开当前说明与已有待确认事项")):
            from .handoff import build_handoffs
            st.markdown(build_handoffs(record)[f"collaboration_brief_{language}.md"])
    if state["pending"]:
        st.info(text("Next: A reads B's response and records an answer.", "下一步：A 阅读 B 的回应，说明如何处理。"))
    elif state["response"] and "B" not in state["acknowledgements"]:
        st.info(text("Next: B reviews A's response and the current version.", "下一步：B 核对 A 的回应和当前版本。"))
    elif state["response"] and "A" not in state["acknowledgements"]:
        st.info(text("This version still needs A's own review.", "当前版本还需要 A 单独核对。"))
    elif state["both_ready"]:
        st.info(text("Both recorded that they can continue. Bring back a small sample and check it separately.",
                     "双方已分别记录可以继续。接下来带回一个小样例，另行检查。"))
    elif state["response"]:
        st.info(text("Some points still need discussion. Read each person's review note; B can send a further response below.",
                     "仍有需要讨论的部分。请查看双方核对意见；B 可以在下方发起下一轮回应。"))
    else:
        st.info(text("B can send an understanding and approach; unresolved points remain visible.",
                     "B 可以写下自己的理解和做法；待解决的问题会继续保留。"))
    tabs = st.tabs([text("Handoff and response", "交接与回应"), text("Sample and checks", "样例与检查")])
    with tabs[0]:
        if state["reply"]:
            _show_reply(state["reply"], text)
        if state["response"]:
            _show_response(state["response"], text)
        if role == "A":
            if state["pending"]:
                _response_form(root, project_id, current, record, state, actor, expected, token, text, run_action, save_result)
            elif state["response"]:
                _review_form(root, project_id, current, role, actor, expected, token, text, run_action)
                st.button(text("Hand over to B", "交给 B 查看调整结果"), key="unified_dyad_to_b", on_click=_role, args=("B",))
            else:
                st.write(text("Wait for B to record an understanding and approach.", "先请 B 阅读说明，记录理解和做法。"))
                st.button(text("Let B read and respond", "请 B 接收并回应"), key="unified_dyad_to_b", on_click=_role, args=("B",))
        elif state["pending"]:
            st.success(text("Your response was saved. A can now respond; the need has not changed.", "回应已保存，当前需求尚未改变。接下来请 A 回应。"))
            st.button(text("Hand over to A", "交给 A 回应与调整"), key="unified_dyad_to_a", on_click=_role, args=("A",))
        else:
            if state["response"]:
                _review_form(root, project_id, current, role, actor, expected, token, text, run_action)
                with st.expander(text("Send a further question or suggestion", "还有问题，继续发起一轮回应")):
                    _recipient_form(root, project_id, current, state, actor, expected, token, text, run_action)
            else:
                if state["reply"]:
                    st.warning(text("The earlier reply refers to another version. Read this version and send a new response.",
                                    "先前回应针对旧版本。请阅读当前版本后重新回应，旧记录保留在历史中。"))
                _recipient_form(root, project_id, current, state, actor, expected, token, text, run_action)
    with tabs[1]:
        _samples(root, project_id, current, record, state, role, actor, expected, token, text, run_action, save_result)
    with st.expander(text("Saved history and export", "已保存历史与导出")):
        st.caption(text("Only saved actions are recorded. Drafts are not confirmations. No model calls or automatic messages.",
                        "这里只记录已保存的操作；草稿不算确认。不会调用模型或自动发送消息。"))
        bundle = {"schema_version": 1, "problem": record.model_dump(mode="json"), "handoff": state["history"],
                  "checks": current_trace(root, project_id, current) if record.requirements is not None else None}
        st.download_button(text("Download handoff record (JSON)", "下载交接记录（JSON）"),
            json.dumps(bundle, ensure_ascii=False, indent=2), file_name="two_way_handoff.json", mime="application/json")
        for event in reversed(state["history"]["events"][-12:]):
            st.caption(f"{event['revision']} · {event['kind']} · {event['recorded_at']}")
            if event["kind"] in ("recipient_reply", "acknowledgement"):
                st.json(event["payload"], expanded=False)


def _show_reply(reply, text):
    with st.container(border=True):
        st.markdown(text(f"**B's response · {reply['actor']} · v{reply['target']['revision']}**",
                         f"**B 的回应 · {reply['actor']} · v{reply['target']['revision']}**"))
        for key, label in [("understanding", text("My understanding", "我的理解")),
                           ("proposal", text("Approach and limits", "做法与限制")),
                           ("questions", text("Questions for A", "需要 A 回应的地方"))]:
            if reply[key]:
                st.caption(label)
                st.text(reply[key])


def _show_response(update, text):
    with st.container(border=True):
        st.markdown(text(f"**A's response · v{update['from_revision']} → v{update['to_revision']}**",
                         f"**A 的回应 · v{update['from_revision']} → v{update['to_revision']}**"))
        st.text(update["answers"][0]["answer"])
        st.caption(text("Reason", "处理依据"))
        st.text(update["reason"])
        changed = False
        field_labels = {"question": text("Goal", "工作目标"), "desired_change": text("Expected result", "期望结果")}
        for key, after in update["after"].items():
            if after != update["before"].get(key):
                changed = True
                st.write(field_labels.get(key, key))
                before_col, after_col = st.columns(2)
                before_col.caption(text("Before", "调整前"))
                before_col.text(update["before"].get(key, ""))
                after_col.caption(text("After", "调整后"))
                after_col.text(after)
        if not changed:
            st.caption(text("The goal wording was kept; A's response supplements this version.", "目标表述保持不变；本版补充了 A 的回应。"))
        st.write(text("Next action", "下一步谁做什么"))
        st.text(update["next_action"])
        st.write(text("Unresolved points", "仍未解决的事项"))
        for issue in update["open_questions"]:
            st.text("• " + issue["question"])
        if not update["open_questions"]:
            st.caption(text("A explicitly recorded no open points in this round.", "A 已明确记录本轮没有待解决事项。"))


def _recipient_form(root, project_id, current, state, actor, expected, token, text, run_action):
    prefix = f"unified_dyad_B_{current.name}_"
    draft = state["drafts"].get("B", {})
    st.subheader(text("B · Read and respond", "B · 接收并回应"))
    with st.form(prefix + "form"):
        understanding = st.text_area(text("My understanding of the work", "我理解这项工作要做什么"),
            value=draft.get("understanding", ""), key=prefix + "understanding", max_chars=8000, height=105)
        proposal = st.text_area(text("My proposed approach and limits (optional)", "我的做法与限制（可留空）"),
            value=draft.get("proposal", ""), key=prefix + "proposal", max_chars=8000, height=100)
        questions = st.text_area(text("What A needs to respond to (optional)", "需要 A 回应的地方（可留空）"),
            value=draft.get("questions", ""), key=prefix + "questions", max_chars=8000, height=90)
        draft_button = st.form_submit_button(text("Save B's draft", "保存 B 的草稿"))
        submit = st.form_submit_button(text("Send response back to A", "保存回应，交回 A"), type="primary")
    if draft_button:
        value = run_action(text("Saving draft…", "正在保存草稿……"), lambda: save_draft(root, project_id, current, role="B",
            values={"understanding": understanding, "proposal": proposal, "questions": questions}, expected_revision=expected))
        _saved(value, token)
    if submit:
        value = run_action(text("Saving B's response…", "正在保存 B 的回应……"), lambda: recipient_reply(root, project_id, current,
            actor=actor, understanding=understanding, proposal=proposal, questions=questions, expected_revision=expected))
        _saved(value, token)


def _response_form(root, project_id, current, record, state, actor, expected, token, text, run_action, save_result):
    prefix = f"unified_dyad_A_{current.name}_"
    draft = state["drafts"].get("A", {})
    prior = (record.continuation or {}).get("updates", [])
    open_points = [i["question"] for i in prior[-1]["open_questions"]] if prior else []
    if state["reply"]["questions"]:
        open_points.append(state["reply"]["questions"])
    st.subheader(text("A · Respond and adjust", "A · 回应与调整"))
    edit = st.checkbox(text("I explicitly want to revise the goal or expected result", "我明确需要修改目标或期望结果"),
                       value=draft.get("edit", "") == "yes", key=prefix + "edit")
    with st.form(prefix + "form"):
        answer = st.text_area(text("My response to B", "我对 B 的回应"), value=draft.get("answer", ""), key=prefix + "answer", max_chars=8000)
        reason = st.text_area(text("What I accept, keep or defer, and why", "哪些采纳、保留或暂缓，依据是什么"),
            value=draft.get("reason", ""), key=prefix + "reason", max_chars=8000, height=90)
        fields = None
        if edit:
            fields = {"question": st.text_area(text("Updated goal", "调整后的工作目标"), value=draft.get("question", record.question),
                        key=prefix + "question", max_chars=20000),
                      "desired_change": st.text_area(text("Updated expected result", "调整后的期望结果"),
                        value=draft.get("desired_change", record.desired_change), key=prefix + "desired_change", max_chars=20000)}
        remaining = st.text_area(text("Still unresolved (one point per line)", "仍未解决的事项（每行一项）"),
            value=draft.get("remaining", "\n".join(dict.fromkeys(open_points))), key=prefix + "remaining", max_chars=8000, height=90)
        no_open = st.checkbox(text("If the list is empty, I confirm no open points remain in this round", "若上方为空，我确认本轮没有待解决事项"), key=prefix + "no_open")
        next_action = st.text_area(text("Who does what next?", "下一步谁做什么？"), value=draft.get("next_action", ""),
                                   key=prefix + "next_action", max_chars=8000, height=90)
        status = st.selectbox(text("A's view of the next step", "A 对下一步的判断"), STATUSES, format_func=_labels(text).get,
                              index=STATUSES.index(draft.get("status", "ready")), key=prefix + "status")
        st.caption(text("Saving a response creates a new version, even if the goal stays the same. B reviews it separately; earlier checks remain historical.",
                        "保存回应会生成新版本，目标可以保持原样。B 将单独核对；旧确认和检查保留为历史。"))
        draft_button = st.form_submit_button(text("Save A's draft", "保存 A 的草稿"))
        submit = st.form_submit_button(text("Confirm my response and return it to B", "确认我的回应，交回 B"), type="primary")
    if draft_button:
        values = {"answer": answer, "reason": reason, "remaining": remaining, "next_action": next_action,
                  "status": status, "edit": "yes" if edit else "", **(fields or {})}
        value = run_action(text("Saving draft…", "正在保存草稿……"), lambda: save_draft(root, project_id, current,
            role="A", values=values, expected_revision=expected))
        _saved(value, token)
    if submit:
        out = run_action(text("Saving A's response and new brief…", "正在保存 A 的回应和新版说明……"), lambda: confirm_response(
            root, project_id, current, reply_id=state["reply"]["reply_id"], actor=actor, answer=answer, reason=reason,
            next_action=next_action, remaining=remaining, no_open_questions=no_open, status=status, fields=fields, expected_revision=expected))
        _baseline(out, root, project_id, save_result)


def _review_form(root, project_id, current, role, actor, expected, token, text, run_action):
    prefix = f"unified_dyad_review_{current.name}_{role}_"
    st.subheader(text(f"{role} · Review this version", f"{role} · 核对当前版本"))
    with st.form(prefix + "form"):
        status = st.selectbox(text("My review", "我的核对结论"), STATUSES, format_func=_labels(text).get, key=prefix + "status")
        note = st.text_area(text("Scope I can proceed with, or what needs discussion", "可以继续的范围，或仍需讨论的地方"), key=prefix + "note", max_chars=8000, height=90)
        st.caption(text("Only your own review is recorded. A partial/discussion status needs a note.", "只记录你本人的判断；选择部分可继续或仍需讨论时，请说明原因。"))
        submit = st.form_submit_button(text("Save my review of this version", "保存我对本版的核对"), type="primary")
    if submit:
        value = run_action(text("Saving review…", "正在保存核对记录……"), lambda: acknowledge(root, project_id, current,
            role=role, actor=actor, status=status, note=note, expected_revision=expected))
        _saved(value, token)


def _requirements_editor(root, project_id, current, record, text, run_action, save_result):
    with st.expander(text("A · Select or reconfirm a key requirement", "A · 选取或重新确认一条关键要求")):
        st.caption(text("Select exact wording from the confirmed brief. This saves a new version; both people must review it again. Checks cover selected requirements only.",
                        "从已确认说明中选取原话。保存后生成新版本，双方需重新核对；检查只覆盖已选要求。"))
        active = {r.requirement_id: r for r in record.requirements or [] if r.status != "retired"}
        item_id = st.selectbox(text("Requirement to manage", "管理哪条要求"), ["new", *active],
            format_func=lambda v: text("Select a new requirement", "选取新要求") if v == "new" else active[v].text[:100],
            key=f"unified_dyad_requirement_{current.name}")
        action = st.radio(text("Action", "操作"), ["select", "retire"] if item_id != "new" else ["select"],
            format_func=lambda v: text("Confirm exact wording", "确认原话") if v == "select" else text("Retire with a reason", "说明理由并撤回"),
            horizontal=True, key=f"unified_dyad_req_action_{current.name}_{item_id}")
        sources = source_catalog(record)
        labels = {"question": text("Work / goal", "工作与目标"), "desired_change": text("Expected result", "期望结果"),
                  "observation": text("Experience / difficulty", "具体经历或困难"),
                  "observation_source": text("Observation source", "观察来源"),
                  "hypothesis": text("Unverified possible cause", "尚待验证的原因"),
                  "human_boundary": text("Human decisions", "人工判断边界"),
                  "brief.background": text("Professional background", "专业背景"),
                  "brief.collaborator": text("Collaborator's contribution", "希望合作者贡献什么"),
                  "brief.materials": text("Available materials", "可提供的材料"),
                  "brief.success_check": text("How to check usefulness", "怎样判断有用")}
        def source_label(key):
            if key.startswith("answer."):
                return text("Confirmed response", "已确认的答复")
            if key.startswith("brief.concepts."):
                return text("Term explanation", "专业词语解释")
            return labels.get(key, text("Confirmed wording", "已确认表述"))
        if action == "select":
            source = st.selectbox(text("Confirmed source", "已确认的来源"), list(sources),
                format_func=lambda v: source_label(v) + " · " + sources[v][:65], key=f"unified_dyad_source_{current.name}_{item_id}")
            st.text(sources[source])
            with st.form(f"unified_dyad_select_{current.name}_{item_id}_{source}"):
                quote = st.text_area(text("Exact wording to track", "要跟踪的原话"),
                    value=active[item_id].text if item_id != "new" else sources[source][:8000], max_chars=8000)
                acceptance = st.text_area(text("How will you check it? (can stay unknown)", "准备怎样检查？（可以暂时未知）"),
                    value=active[item_id].acceptance if item_id != "new" else "", max_chars=4000)
                submit = st.form_submit_button(text("Confirm requirement in a new version", "确认这条要求，更新版本"))
            if submit:
                changes = {"select": [{"requirement_id": None if item_id == "new" else item_id,
                    "source_key": source, "quote": quote, "acceptance": acceptance}]}
                out = run_action(text("Saving requirement…", "正在保存关键要求……"), lambda: confirm_requirements(root, project_id,
                    current, changes, confirmed=True, expected_revision=record.revision))
                _baseline(out, root, project_id, save_result)
        else:
            with st.form(f"unified_dyad_retire_{current.name}_{item_id}"):
                reason = st.text_input(text("Why retire this requirement?", "为什么撤回这条要求？"), max_chars=4000)
                submit = st.form_submit_button(text("Retire in a new version", "撤回并更新版本"))
            if submit:
                out = run_action(text("Retiring requirement…", "正在撤回要求……"), lambda: confirm_requirements(root, project_id,
                    current, {"retire": {item_id: reason}}, confirmed=True, expected_revision=record.revision))
                _baseline(out, root, project_id, save_result)


def _samples(root, project_id, current, record, state, role, actor, expected, token, text, run_action, save_result):
    st.caption(text("A small text/table sample is enough. These are human-reported checks, separate from ClaimHarness verdicts and domain validation.",
                    "用一小段文字或表格即可。这里保存人工检查记录，独立于 ClaimHarness 判断，也不代表专业有效性。"))
    if role == "A":
        _requirements_editor(root, project_id, current, record, text, run_action, save_result)
    trace = current_trace(root, project_id, current) if record.requirements is not None else None
    if trace:
        statuses = {"confirmed": text("Confirmed", "已确认"), "needs_reconfirmation": text("Needs reconfirmation", "需要重新确认"),
                    "retired": text("Retired", "已撤回")}
        results = {"met": text("Meets this requirement", "符合这条要求"), "not_met": text("Does not meet it", "不符合这条要求"),
                   "not_checked": text("Not checked", "尚未检查")}
        rows = [{text("Requirement", "要求"): r["text"], text("State", "状态"): statuses[r["status"]],
                 text("Check", "检查"): results[r["check"]["result"]] if r["check"] else results["not_checked"],
                 text("Applies to saved evidence", "适用于保存的样例"): bool(r["check"] and r["check"]["applicable"])} for r in trace["requirements"]]
        st.dataframe(rows, hide_index=True, use_container_width=True)
        with st.expander(text("Check methods, reviewers and observations", "查看检查方法、记录者与观察")):
            for item in trace["requirements"]:
                st.write(item["text"])
                st.caption(text("Agreed check method", "约定的检查方法"))
                st.text(item["acceptance"] or text("Not specified yet", "尚未明确"))
                check = item["check"]
                if check:
                    st.text(text("Recorded by: ", "记录者：") + check["actor"])
                    st.text(text("Method: ", "实际检查方法：") + check["method"])
                    st.text(check["note"])
                    if check["evidence"]:
                        st.text(text("Sample location: ", "样例位置：") + check["evidence"]["location"])
        st.download_button(text("Download requirement checks", "下载要求与检查记录"), render_trace(trace), file_name="requirement_checks.md")
    else:
        st.info(text("No key requirements selected yet. A can select wording from the confirmed brief above.", "尚未选取关键要求。A 可以从当前已确认说明中选取原话。"))
    if role == "B":
        with st.form(f"unified_dyad_sample_{current.name}"):
            title = st.text_input(text("Sample title", "样例名称"), key=f"unified_dyad_sample_title_{current.name}", max_chars=500)
            content = st.text_area(text("Paste a small result (text or CSV)", "粘贴小样例结果（文字或 CSV）"),
                                   key=f"unified_dyad_sample_content_{current.name}", height=135, max_chars=500000)
            uploaded = st.file_uploader(text("Or select a UTF-8 TXT, Markdown or CSV file (replaces pasted text)", "或选择 UTF-8 TXT、Markdown、CSV 文件（替代粘贴内容）"),
                                        type=["txt", "md", "csv"], max_upload_size=2, key=f"unified_dyad_sample_upload_{current.name}")
            submit = st.form_submit_button(text("Save sample for this version", "保存当前版本的小样例"))
        if submit:
            def run():
                body = uploaded.getvalue().decode("utf-8-sig") if uploaded else content
                return save_sample(root, project_id, current, actor=actor, title=title, content=body, expected_revision=expected)
            _saved(run_action(text("Saving sample…", "正在保存小样例……"), run), token)
    if not state["samples"]:
        st.write(text("B has not brought back a sample for this version yet.", "B 还没有带回当前版本的小样例。"))
        return
    samples = {s["evidence"]["path"]: s for s in state["samples"]}
    path = st.selectbox(text("Saved sample", "已保存的小样例"), list(samples), index=len(samples) - 1,
                        format_func=lambda v: samples[v]["title"], key=f"unified_dyad_selected_sample_{current.name}")
    try:
        body = read_sample(root, samples[path])
    except (ValueError, OSError) as exc:
        st.error(text("Sample missing or changed; save a new copy before checking.", "样例已丢失或被修改，请重新保存后再检查。"))
        st.caption(str(exc))
        return
    with st.expander(text("Read or download sample", "查看或下载样例"), expanded=True):
        st.code(body, language=None, wrap_lines=True)
        st.download_button(text("Download sample", "下载样例"), body, file_name="handoff_sample.txt")
    confirmed = {r.requirement_id: r for r in record.requirements or [] if r.status == "confirmed"}
    if not confirmed:
        st.info(text("A needs to select/reconfirm a requirement before recording a check.", "记录检查前，请 A 选取或重新确认关键要求。"))
        return
    check_token = f"unified_dyad_checks_{current.name}"
    st.session_state.setdefault(check_token, trace["journal_revision"])
    if st.session_state[check_token] != trace["journal_revision"]:
        st.warning(text("New checks exist. Reload checks before submitting.", "已有新检查记录，请重新载入后再提交。"))
    if st.button(text("Reload checks", "重新载入检查记录"), key="unified_dyad_reload_checks"):
        st.session_state[check_token] = trace["journal_revision"]
        st.rerun()
    with st.form(f"unified_dyad_check_{current.name}_{role}"):
        rid = st.selectbox(text("Which requirement?", "检查哪条要求？"), list(confirmed), format_func=lambda v: confirmed[v].text)
        result = st.selectbox(text("My check result", "我的检查结果"), ["not_checked", "met", "not_met"],
            format_func=lambda v: {"not_checked": text("Not checked", "尚未检查"), "met": text("Meets this requirement", "符合这条要求"), "not_met": text("Does not meet it", "不符合这条要求")}[v])
        method = st.text_input(text("How did you check?", "怎样检查的？"), max_chars=4000)
        location = st.text_input(text("Location in this sample (row, line or section)", "样例中的位置（行、列或段落）"), max_chars=4000)
        note = st.text_area(text("What did you observe?", "你观察到了什么？"), max_chars=4000)
        submit = st.form_submit_button(text("Save my attributed check", "保存我的检查记录"))
    if submit:
        value = run_action(text("Saving check…", "正在保存检查记录……"), lambda: check_sample(root, project_id, current,
            sample_path=path, requirement_id=rid, role=role, actor=actor, result=result, method=method, note=note,
            location=location, expected_revision=st.session_state[check_token], expected_handoff_revision=expected))
        _saved(value, check_token)
