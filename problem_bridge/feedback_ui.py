"""Persistent feedback and explicit confirmation in the everyday workbench."""
import json
import streamlit as st

from .clarification import ClarificationState, choose_question
from .feedback import CATEGORIES, add_feedback, confirm_discussion, discussion, respond, start_next_round
from .workbench import load_problem


def saved_versions(root, record):
    versions = []
    for path in root.iterdir() if root.exists() else []:
        if not (path / "problem_record.json").is_file():
            continue
        try:
            raw = json.loads((path / "problem_record.json").read_text(encoding="utf-8"))
            if (raw.get("project_id"), raw.get("problem_id")) == (record.project_id, record.problem_id):
                versions.append((path, load_problem(root, path, record.project_id)))
        except (ValueError, OSError, RuntimeError):
            continue
    return sorted(versions, key=lambda x: (x[1].revision, x[0].name))


def render_feedback(root, project_id, current, record, text, run_action, save_result):
    language = text("en", "zh")
    text = lambda en, zh: zh if language == "zh" else en
    st.subheader(text("Bring feedback back into the discussion", "带回反馈继续讨论"))
    st.caption(text("Feedback remains a proposal until you confirm a new version. Saved discussion survives reopening.",
                    "反馈先作为提议保存；明确确认后才形成新版本。已保存的讨论可以关闭后继续。"))
    _, history, data = discussion(root, record, current)
    token = f"feedback_revision_{record.problem_id}_{current.name}"
    st.session_state.setdefault(token, history["revision"])
    expected = st.session_state[token]
    if expected != history["revision"]:
        st.warning(text("Newer discussion changes exist. Reload before submitting.", "已有较新的讨论记录，请重新载入后再提交。"))
    if st.button(text("Reload saved discussion", "重新载入已保存的讨论"), key="feedback_reload"):
        st.session_state[token] = history["revision"]
        st.rerun()
    choices = {path.name: (path, item) for path, item in saved_versions(root, record)}
    tabs = st.tabs([text("Record feedback", "记录反馈"), text("Discuss and confirm", "讨论并确认")])
    with tabs[0], st.form("feedback_intake"):
        sender = st.text_input(text("Who provided the feedback?", "反馈来自谁？"), key="feedback_sender", max_chars=500)
        sender_kind = st.selectbox(text("Source type", "来源类型"), ["collaborator", "ai", "user"],
            format_func=lambda v: {"collaborator": text("Collaborator", "合作者"), "ai": "AI", "user": text("My own note", "自己的记录")}[v], key="feedback_sender_kind")
        target = st.selectbox(text("Which confirmed version did they read?", "对方看的是哪一版说明？"), ["unknown", *choices],
            index=list(choices).index(current.name) + 1 if current.name in choices else 0,
            format_func=lambda v: text("Unknown / pasted text", "未知／普通文本") if v == "unknown" else f"v{choices[v][1].revision} · {v}", key="feedback_target")
        original = st.text_area(text("Original feedback (kept verbatim)", "反馈原文（完整保留）"), key="feedback_original", height=120, max_chars=20000)
        selected = st.text_area(text("Exact excerpt to discuss (empty means all)", "想讨论的原文片段（留空表示全文）"), key="feedback_selected", height=70, max_chars=4000)
        understanding = st.text_area(text("How I understand this feedback", "我怎样理解这段反馈"), key="feedback_interpretation", height=70, max_chars=4000)
        labels = [text("Goal misunderstanding", "对目标理解不同"), text("Terminology", "对术语理解不同"), text("Missing condition", "缺少材料或条件"), text("Method proposal", "建议改变做法"), text("New goal proposal", "提出新目标")]
        category = st.selectbox(text("What needs discussion?", "这段反馈涉及什么？"), list(CATEGORIES), format_func=dict(zip(CATEGORIES, labels)).get, key="feedback_category")
        question = st.text_input(text("One question to clarify", "一个需要澄清的问题"), key="feedback_question", max_chars=4000)
        alternatives = st.text_area(text("Interpretations, one per line (optional)", "不同理解，每行一种（可留空）"), key="feedback_alternatives", height=70)
        consequence = st.text_area(text("Possible consequence, not yet verified", "可能影响什么（尚未验证）"), key="feedback_consequence", height=70)
        budget = st.number_input(text("Answer budget for a new round", "新一轮讨论的回答次数上限"), min_value=1, max_value=20, value=5, key="feedback_budget")
        submitted = st.form_submit_button(text("Save feedback without changing the need", "保存反馈，保留当前需求"), type="primary")
    if submitted:
        result = run_action(text("Saving feedback…", "正在保存反馈……"), lambda: add_feedback(root, project_id, current,
            target=choices[target][0] if target in choices else None, sender=sender, sender_kind=sender_kind,
            original=original, selected=selected or original, interpretation=understanding, category=category,
            question=question, alternatives=alternatives.splitlines(), consequence=consequence, budget=int(budget), expected_revision=expected))
        if result:
            st.session_state[token] = result["revision"]
            st.rerun()
    with tabs[1]:
        if not data or data["current_run"] != current.name:
            st.info(text("Record feedback to begin. Earlier rounds remain in the history export.", "先记录反馈以开始讨论。较早轮次保留在历史导出中。"))
        else:
            _discuss(root, project_id, current, record, data, expected, token, text, run_action, save_result)
        _example(text)
    with st.expander(text("Discussion history and originals", "讨论历史与反馈原文")):
        st.download_button(text("Download full discussion", "下载完整讨论历史"), json.dumps(history, ensure_ascii=False, indent=2), file_name="feedback_discussion.json", mime="application/json")
        for event in reversed(history["events"][-15:]):
            st.caption(f"{event['revision']} · {event['kind']} · {event['recorded_at']}")
            if event["kind"] == "feedback_added":
                st.text(event["payload"]["feedback"][-1]["original"])


def _discuss(root, project_id, current, record, data, expected, token, text, run_action, save_result):
    state = ClarificationState.model_validate(data["state"])
    decision = choose_question(state, [])
    if decision.action == "budget_exhausted":
        st.warning(text("Answer budget used. Unanswered questions remain open; corrections are still available.", "回答次数已用完。未解决的问题继续保留；已有回答仍可明确更正。"))
    elif decision.action == "ready":
        st.info(text("These candidate questions have answers; complete understanding is not established.", "本轮候选问题已有回答，不代表需求已经完全清楚。"))
    if state.revision == data["last_confirmed_state_revision"]:
        if st.button(text("Start another round, keeping unanswered questions", "开始下一轮，保留未回答问题"), key="feedback_next_round"):
            value = run_action(text("Starting the next round…", "正在建立下一轮讨论……"), lambda: start_next_round(root, project_id, current, budget=state.budget, expected_revision=expected))
            if value:
                st.session_state[token] = value["revision"]
                st.rerun()
    answers = {r.issue_id: r for r in state.resolutions}
    feedback = {f["feedback_id"]: f for f in data["feedback"]}
    issues = {i.issue_id: i for i in state.issues}
    if not issues:
        return
    preferred = [i for i in issues if i not in answers and i not in data["dispositions"]]
    selected = st.selectbox(text("Choose one question", "选择一个问题继续"), list(issues),
        index=list(issues).index(preferred[0]) if preferred else 0, key=f"feedback_issue_{expected}_{text('en', 'zh')}",
        format_func=lambda i: f"{issues[i].question} · {text('answered', '已回答') if i in answers else data['dispositions'].get(i, {}).get('status', text('open', '待回答'))}")
    issue, origin = issues[selected], feedback[selected]
    target = origin["target"]
    if target is None or target["revision"] != record.revision:
        st.warning(text(f"Feedback target: {target['revision'] if target else 'unknown'}; current revision: {record.revision}.", f"反馈针对版本：{target['revision'] if target else '未知'}；当前版本：{record.revision}。"))
    with st.container(border=True):
        st.caption(text("Original selected wording", "选中的原始表述"))
        st.text(origin["selected"])
        st.write(issue.description)
        st.caption(text("Untested possible impact", "尚未验证的影响判断"))
        st.write(origin["consequence"] or text("Unknown; no execution preview is available.", "未知；当前没有执行预览。"))
        if selected in answers:
            st.write(text("Previous answer: ", "先前回答：") + answers[selected].answer)
        with st.form(f"feedback_reply_{selected}"):
            modes = ["correct"] if selected in answers else ["answer", "none_accurate", "unknown", "defer"]
            labels = {"correct": text("Correct my earlier answer", "更正先前回答"), "answer": text("Answer / choose an interpretation", "回答／选择一种理解"), "none_accurate": text("None are accurate; use my words", "都不准确，用我的表述"), "unknown": text("I do not know yet", "目前不知道"), "defer": text("Defer and discuss another question", "暂时跳过，处理其他问题")}
            mode = st.radio(text("My response", "我的回应"), modes, format_func=labels.get, key=f"feedback_mode_{selected}")
            option = st.selectbox(text("Interpretation (optional)", "选择解释（可留空）"), [None, *[a.interpretation_id for a in issue.alternatives]],
                format_func=lambda v: text("Own words / not selected", "自行表述／尚未选择") if v is None else next(a.instruction for a in issue.alternatives if a.interpretation_id == v), key=f"feedback_option_{selected}")
            answer = st.text_area(text("My words", "我的回答"), key=f"feedback_answer_{selected}", max_chars=8000)
            reason = st.text_input(text("Correction reason (required for corrections)", "更正原因（更正时必填）"), key=f"feedback_reason_{selected}")
            submit = st.form_submit_button(text("Save my response", "保存我的回应"))
        if submit:
            reply = answer or (next(a.instruction for a in issue.alternatives if a.interpretation_id == option) if option and mode in {"answer", "correct"} else "")
            value = run_action(text("Saving discussion…", "正在保存讨论……"), lambda: respond(root, project_id, current,
                issue_id=selected, mode=mode, answer=reply, reason=reason, interpretation_id=option, expected_revision=expected))
            if value:
                st.session_state[token] = value["revision"]
                st.rerun()
    st.subheader(text("Confirm a new need version", "确认新的需求版本"))
    kind = st.selectbox(text("What has changed?", "本次更新属于哪种情况？"), ["supplement", "correction", "goal_change"], key="feedback_update_kind",
        format_func=lambda v: {"supplement": text("Supplement an unknown detail", "补充原先未知的信息"), "correction": text("Correct an earlier answer", "更正先前回答"), "goal_change": text("Change my goal", "改变我的目标")}[v])
    with st.form("feedback_confirm"):
        fields = None
        if kind == "goal_change":
            st.caption(text("Previous goal: ", "原目标：") + record.question)
            fields = {"question": st.text_area(text("New goal I explicitly choose", "我明确选择的新目标"), value=record.question, key=f"feedback_new_goal_{record.revision}"),
                "desired_change": st.text_area(text("New desired result", "新的期望结果"), value=record.desired_change, key=f"feedback_new_result_{record.revision}")}
        reason = st.text_area(text("What changed and why?", "改变了什么，依据是什么？"), key="feedback_confirm_reason",
                              placeholder=text("For example: average each device first because devices have unequal observation counts.", "例如：明确先按设备平均，因为各设备的观测次数不同。"))
        next_action = st.text_area(text("Recipient's next action", "接收方下一步需要做什么？"), key="feedback_next_action",
                                   placeholder=text("For example: check the agreed averaging rule on a small synthetic sample.", "例如：请对方用一份小型合成样例核对约定的平均口径。"))
        st.info(text("Creates a new version and both briefs. Previous audits remain historical.", "建立新版本并更新两份说明；先前核查保留为历史记录。"))
        submit = st.form_submit_button(text("I confirm this update → prepare new briefs", "我确认本次更新 → 生成新版说明"), type="primary")
    if submit:
        out = run_action(text("Confirming new version…", "正在确认新版本……"), lambda: confirm_discussion(root, project_id, current,
            kind=kind, reason=reason, next_action=next_action, fields=fields, expected_revision=expected))
        if out:
            # The confirmed update is now the editable baseline, not an old hidden draft.
            latest = load_problem(root, out, project_id)
            for field in ("question", "observation", "observation_source", "desired_change", "hypothesis", "human_boundary"):
                st.session_state[f"unified_edit_{field}"] = getattr(latest, field)
            save_result(out, 4)


def _example(text):
    with st.expander(text("Synthetic example: two averaging rules", "合成示例：两种平均口径")):
        st.caption(text("Actual local execution of bundled synthetic inputs. This is an explanation, not a preview of your material.", "使用内置合成输入在本地实际执行；仅用于解释，不是对你所提供材料的预览。"))
        if st.button(text("Run the bundled averaging example", "运行内置平均口径示例"), key="feedback_preview_example"):
            from .clarification_demo import public_data, summarize
            inputs = public_data()
            st.write(text("Input: bundled synthetic readings", "输入：内置合成观测值"))
            st.json(inputs)
            for key in ("observations", "sensors"):
                try:
                    st.caption(f"Execution: clarification_demo.summarize · {key}")
                    st.dataframe(summarize(inputs, key), hide_index=True)
                except (ValueError, KeyError, TypeError) as exc:
                    st.error(text("Execution failed: ", "执行失败：") + str(exc))
            st.info(text("Agreement on some samples does not prove equivalence.", "部分样例结果相同，不能据此认定两种理解等价。"))
