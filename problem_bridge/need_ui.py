"""A short local interview and portable handoffs for the shared workbench."""
from pathlib import Path

import streamlit as st

from .handoff import ConceptNote, NeedBrief, build_handoffs, missing_details
from .workbench import FRAME_FIELDS, confirm_problem


NEED_DRAFT_KEYS = [
    *(f"unified_edit_{key}" for key in (*FRAME_FIELDS, "background", "collaborator", "materials", "success_check")),
    "unified_intake_step", "unified_concept_count",
    *(f"unified_edit_{key}_{index}" for index in range(10) for key in ("term", "meaning", "example", "non_example")),
]


def _step(step):
    st.session_state.unified_intake_step = step


def _use_interview(answers):
    values = {"question": answers.get("repeated_work", ""), "observation": answers.get("pain_points", ""),
              "desired_change": answers.get("useful_support", ""), "human_boundary": answers.get("human_boundaries", ""),
              "observation_source": "User interview / 用户访谈", "materials": answers.get("materials", ""),
              "background": answers.get("domain", "")}
    for key, value in values.items():
        st.session_state[f"unified_edit_{key}"] = value
    _step(4)


def _add_concept():
    st.session_state.unified_concept_count = min(10, st.session_state.unified_concept_count + 1)


def render_need_form(root, project_id, current_out, record, text, run_action, save_result, answers):
    brief = record.brief if record and record.brief else NeedBrief()
    for key in FRAME_FIELDS:
        st.session_state.setdefault(f"unified_edit_{key}", getattr(record, key) if record else "")
    for key in ("background", "collaborator", "materials", "success_check"):
        st.session_state.setdefault(f"unified_edit_{key}", getattr(brief, key))
    st.session_state.setdefault("unified_concept_count", max(1, len(brief.concepts)))
    for index, concept in enumerate(brief.concepts):
        for key in ("term", "meaning", "example", "non_example"):
            st.session_state.setdefault(f"unified_edit_{key}_{index}", getattr(concept, key))
    st.session_state.setdefault("unified_intake_step", 4 if record else 0)
    if answers:
        st.button(text("Use my interview answers", "带入已有访谈回答"), key="unified_use_interview",
                  on_click=_use_interview, args=(answers,))
    if st.session_state.get("unified_return_question"):
        st.info(text("Question brought back for clarification: ", "带回继续澄清的问题：") + st.session_state.unified_return_question)
    step = st.session_state.unified_intake_step
    if record or step == 4:
        _review(root, project_id, current_out, record, text, run_action, save_result, answers)
    else:
        with st.container(key="need_layout"):
            question, guide = st.columns([2.15, 1], gap="large")
            with question:
                _interview(step, text)
            with guide:
                _handoff_guide(text)
    with st.expander(text("How is this different from chatting with AI?", "和直接找 AI 聊天有什么不同？")):
        st.write(text(
            "Start with an experience, then correct the wording before handing it over. You get two reusable documents from the same confirmed need: one for a collaborator, one for a language model. You choose where to take them. These local questions do not interpret specialist terminology for you; meanings and missing details stay open for confirmation.",
            "从具体经历开始，先修正理解，再交给别人。这里把同一份确认过的需求整理为两份可带走的说明：给合作伙伴、给大模型。由你决定带到哪里使用。本地引导不会替你解释专业术语，词语含义和缺少的条件会留待确认。"))


def _handoff_guide(text):
    st.markdown(
        '<aside class="brief-guide">'
        f'<p class="guide-kicker">{text("WHAT YOU WILL TAKE AWAY", "整理后，你会拿到")}</p>'
        f'<h3>{text("A shared starting point", "让合作从理解开始")}</h3>'
        '<div class="brief-guide-item"><span class="brief-guide-number" aria-hidden="true">01</span><div>'
        f'<h4>{text("A collaborator brief", "给合作伙伴的说明")}</h4>'
        f'<p>{text("Your context, the help you need, and the terms worth clarifying.", "带上你的背景、需要的帮助，以及容易误解的专业词语。")}</p>'
        '</div></div>'
        '<div class="brief-guide-item"><span class="brief-guide-number" aria-hidden="true">02</span><div>'
        f'<h4>{text("A task for your AI", "给大模型的任务")}</h4>'
        f'<p>{text("The same need, with materials, expected output and a way to check it.", "用同一份需求，写清材料、预期产出和检查方法。")}</p>'
        '</div></div>'
        f'<p class="guide-footnote">{text("Review the wording first. Then copy or download both documents.", "先确认符合你的意思，再复制或下载。")}</p>'
        '</aside>',
        unsafe_allow_html=True,
    )


def _interview(step, text):
    questions = [
        ("question", "What is one real task you would like help with?", "最近工作中，有哪件事让你觉得麻烦？",
         "A fragment is enough. You do not need an AI task or a solution yet.", "说不完整也没关系，先讲你在做的事，不用想好怎么用 AI。",
         "I compare records in different formats and worry about missing something.", "例如：我经常要比较不同格式的记录，担心漏掉信息。"),
        ("observation", "Think of the last time. Where did you get stuck?", "回想最近一次，具体在哪里卡住了？",
         "Describe an example. Keep what happened separate from what you think caused it.", "讲一个例子就可以。先说发生了什么，原因可以之后再讨论。",
         "I opened three files and could not tell which version a number came from.", "例如：打开几份记录后，找不到同一个数字分别来自哪里。"),
        ("desired_change", "What would you like someone to give back to you?", "如果有人来帮忙，你希望最后拿到什么？",
         "A comparison table, a draft, a small tool, or questions to discuss are all possible.", "可以是比较表、初稿、小工具，也可以先得到值得讨论的问题。",
         "A comparison table with a link back to each source.", "例如：一张能回到原文核对的比较表。"),
        ("materials", "What can you show a collaborator or an AI?", "你现在能给对方看什么材料？",
         "Describe what exists. No upload is needed to prepare your brief.", "说说已有材料即可，整理需求时不用上传文件。",
         "A public example document and a blank table. Actual files can be attached later.", "例如：一份公开的示例记录和空白表格；文件之后再附。"),
    ]
    key, en, zh, hint_en, hint_zh, example_en, example_zh = questions[step]
    with st.container(key="need_question_card", border=True):
        segments = "".join(f'<span class="{"is-complete" if index <= step else ""}"></span>' for index in range(4))
        st.markdown(f'<div class="question-progress" aria-hidden="true">{segments}</div>', unsafe_allow_html=True)
        st.caption(text(f"{step + 1} of 4 · You can revise everything before saving", f"第 {step + 1} / 4 问 · 保存前都可以修改"))
        st.subheader(text(en, zh))
        st.caption(text(hint_en, hint_zh))
        with st.form(f"unified_intake_{step}", border=False):
            value = st.text_area(text("Say it in your own words", "用你自己的话说"), key=f"unified_edit_{key}",
                                 height=140, placeholder=text(example_en, example_zh), max_chars=20000)
            col1, col2 = st.columns([1, 1.2])
            with col1:
                next_step = st.form_submit_button(text("Continue", "继续"), type="primary", use_container_width=True)
            with col2:
                skip = st.form_submit_button(text("Not sure yet", "暂时说不清，先跳过"), use_container_width=True) if step else False
    if next_step or skip:
        if step == 0 and not value.strip():
            st.error(text("Name one task first. Even a short fragment is enough.", "先说一件你在做的事，几个字也可以。"))
        else:
            _step(step + 1)
            st.rerun()
    if step:
        st.button(text("Back one question", "返回上一问"), key="unified_intake_back", on_click=_step, args=(step - 1,))
    else:
        with st.expander(text("Need a starting point?", "还是不知道怎么开口？")):
            st.write(text("Try: 'I spend time on …', 'I cannot tell …', or 'I want to explain … to someone from another field'. Pick a real recent example.",
                          "可以从这些半句话开始：“我总要花时间……”“我分不清……”“我想向另一个专业的人解释……”。挑一件最近发生的事就好。"))
        st.button(text("I already have a clear brief", "我已想清楚，直接整理"), key="unified_direct_review", on_click=_step, args=(4,))


def _review(root, project_id, current_out, record, text, run_action, save_result, answers):
    st.subheader(text("Does this say what you mean?", "这些内容准确表达你的意思吗？"))
    st.caption(text("Edit anything below. Empty fields stay open questions in both handoffs.", "下面都可以改。未填写的内容会作为待确认问题，保留在两份说明里。"))
    with st.container(key="need_review_card"), st.form("unified_problem_form"):
        context, outcome = st.columns(2, gap="large")
        with context:
            fields = {
                "question": st.text_area(text("My work / need", "我的工作与需求"), key="unified_edit_question", height=110, max_chars=20000),
                "observation": st.text_area(text("A concrete experience or difficulty", "具体经历或困难"), key="unified_edit_observation", height=110, max_chars=20000),
            }
        with outcome:
            fields["desired_change"] = st.text_area(text("The result I want", "我希望拿到的结果"), key="unified_edit_desired_change", height=110, max_chars=20000)
            materials = st.text_area(text("Materials I can provide (a list is enough)", "可提供的材料（先列清单即可）"), key="unified_edit_materials", height=110, max_chars=20000)
        with st.expander(text("Make it easier for another discipline to understand (optional)", "帮助其他专业的人理解（可选）")):
            background = st.text_input(text("My professional background", "我的专业背景"), key="unified_edit_background", max_chars=4000)
            collaborator = st.text_area(text("Who could help, and with what?", "希望谁来帮忙，贡献哪部分？"), key="unified_edit_collaborator", height=80, max_chars=4000)
            success = st.text_area(text("How would I tell a small sample is useful?", "先做一个小样例，我怎样判断它有用？"), key="unified_edit_success_check", height=80, max_chars=4000)
            concepts = []
            invalid_concept = False
            for index in range(st.session_state.unified_concept_count):
                st.markdown(text(f"**Term {index + 1} that could be misunderstood**", f"**容易误解的词语 {index + 1}**"))
                term = st.text_input(text("Term", "词语"), key=f"unified_edit_term_{index}", max_chars=500)
                meaning = st.text_area(text("What I mean in this task", "我在这项工作里指什么"), key=f"unified_edit_meaning_{index}", height=70, max_chars=4000)
                example = st.text_input(text("An example", "一个正例"), key=f"unified_edit_example_{index}", max_chars=4000)
                non_example = st.text_input(text("A counterexample or common misunderstanding", "一个反例或常见误解"), key=f"unified_edit_non_example_{index}", max_chars=4000)
                if term.strip():
                    concepts.append(ConceptNote(term=term, meaning=meaning, example=example, non_example=non_example))
                elif any(value.strip() for value in (meaning, example, non_example)):
                    invalid_concept = True
            add_concept = st.form_submit_button(text("Explain another term", "再解释一个词"), disabled=st.session_state.unified_concept_count >= 10)
        with st.expander(text("Sources, possible causes and boundaries (optional)", "来源、可能原因与判断边界（可选）")):
            fields["observation_source"] = st.text_input(text("Where did the observation come from?", "观察来自哪里？"), key="unified_edit_observation_source", max_chars=20000)
            fields["hypothesis"] = st.text_area(text("Possible cause, still to be checked", "你猜测的原因，尚待验证"), key="unified_edit_hypothesis", height=80, max_chars=20000)
            fields["human_boundary"] = st.text_area(text("What should a person decide?", "哪些判断应交给人来做？"), key="unified_edit_human_boundary", height=80, max_chars=20000)
        if record and record.audit:
            st.caption(text("Saving changed needs starts a new version; the previous audit remains in history.", "保存会建立新的需求版本；原有核查保留在历史中，需要时重新核查。"))
        submitted = st.form_submit_button(text("This reflects my need → prepare both handoffs", "这符合我的意思 → 整理两份说明"), type="primary")
    if add_concept:
        _add_concept()
        st.rerun()
    if submitted:
        if not fields["question"].strip():
            st.error(text("Write the task you would like help with first.", "请先写下希望有人帮忙的一件事。"))
            return
        if invalid_concept:
            st.error(text("Give each explanation a term, or clear that explanation.", "请为术语解释填写对应词语，或清空这条解释。"))
            return
        brief = NeedBrief(background=background, collaborator=collaborator, materials=materials, success_check=success, concepts=concepts)
        out = run_action(text("Preparing both handoffs locally…", "正在本地整理两份说明……"),
                         lambda: confirm_problem(root, project_id, fields, previous=current_out, brief=brief, interview_answers=answers or None))
        if out:
            save_result(out, 4)
    if not record:
        st.button(text("Return to the short questions", "返回逐步提问"), key="unified_back_interview", on_click=_step, args=(0,))


def render_handoffs(current_out: Path, record, text, go, render_downloads):
    language = text("en", "zh")
    drafts_differ = any(
        key in st.session_state and st.session_state[key].strip() != getattr(record, field)
        for field in FRAME_FIELDS for key in [f"unified_edit_{field}"]
    )
    saved_brief = record.brief or NeedBrief()
    drafts_differ |= any(
        f"unified_edit_{field}" in st.session_state and st.session_state[f"unified_edit_{field}"].strip() != getattr(saved_brief, field)
        for field in ("background", "collaborator", "materials", "success_check")
    )
    for index in range(st.session_state.get("unified_concept_count", len(saved_brief.concepts))):
        saved = saved_brief.concepts[index] if index < len(saved_brief.concepts) else None
        for field in ("term", "meaning", "example", "non_example"):
            key = f"unified_edit_{field}_{index}"
            if key in st.session_state and st.session_state[key].strip() != (getattr(saved, field) if saved else ""):
                drafts_differ = True
    if drafts_differ:
        st.warning(text("You have unsaved wording changes. These handoffs still use the last confirmed version.", "需求草稿已修改。下面的说明仍使用上次确认的版本；请返回确认后再交给对方。"))
    st.subheader(text("One confirmed need, two ways to hand it over", "同一份需求，两种交付方式"))
    st.caption(text("Copy or download a document, then choose where to use it. Nothing is sent automatically. Described files must be attached separately.",
                    "复制或下载后，由你选择交给谁。这里不会自动发送；清单中的材料需要另行附上。"))
    pending = missing_details(record, language)
    if pending:
        with st.expander(text(f"{len(pending)} things to clarify with the recipient", f"还有 {len(pending)} 项可以和对方继续确认")):
            for item in pending:
                st.write("• " + item)
    st.button(text("Revise my wording or add context", "修改需求或补充条件"), key="unified_edit_need", on_click=go, args=(1,))
    handoffs = build_handoffs(record)
    tabs = st.tabs([text("For a collaborator", "给合作伙伴"), text("For a language model", "给大模型")])
    for tab, kind in zip(tabs, ("collaboration_brief", "model_task")):
        with tab:
            st.caption(text("Share the context and agree on what to do together.", "交代背景、对齐含义，再一起商量怎么做。") if kind == "collaboration_brief" else
                       text("Copy this into your preferred AI, with any materials attached separately.", "带到你常用的 AI 中使用，相关材料另行附上。"))
            filename = f"{kind}_{language}.md"
            # Old records did not contain these files; their view is derived and labelled.
            path = current_out / filename
            content = path.read_text(encoding="utf-8") if path.is_file() else handoffs[filename]
            if not path.is_file():
                st.caption(text("Prepared from an older saved record; confirm it again to save this handoff.", "这是由旧记录整理的预览，重新确认需求后可保存这份说明。"))
            st.download_button(text("Download this brief", "下载这份说明"), data=content, file_name=filename, mime="text/markdown",
                               key=f"unified_download_{kind}", type="primary")
            with st.expander(text("Copy the full text", "复制完整说明")):
                st.code(content, language=None, wrap_lines=True)
            with st.container(height=480, border=True, key=f"handoff_preview_{kind}"):
                preview = "\n".join("##" + line if line.startswith(("# ", "## ")) else line for line in content.splitlines())
                st.markdown(preview)
    with st.expander(text("Have results to check? (optional)", "已有结果，想进一步核查？（可选）")):
        st.caption(text("The current checker compares supported English numerical statements with CSV tables. It cannot validate every specialist task.",
                        "当前核查器针对可识别的英文数值表述与 CSV 表格，不适用于所有专业任务。"))
        st.button(text("Check text against result tables", "对照结果表核查正文"), key="unified_handoff_audit", on_click=go, args=(2,))
    with st.expander(text("Download the saved record and both handoffs", "下载记录与两份说明")):
        render_downloads(current_out, "ProblemBridge handoff")
