"""Actual user flows through native Streamlit components, not a visual-only gate."""
from pathlib import Path
import pytest

from problem_bridge.feedback import discussion
from problem_bridge.workbench import load_problem

AppTest = pytest.importorskip("streamlit.testing.v1").AppTest
APP = Path(__file__).resolve().parents[1] / "apps/problem_bridge_wizard.py"


def click(app, *, key=None, label=None):
    button = next(b for b in app.button if b.key == key) if key else next(b for b in app.button if b.label == label)
    button.click().run(timeout=40)
    assert not app.exception
    assert not app.error, [error.value for error in app.error]


def fill(app, key, value):
    next(w for w in [*app.text_input, *app.text_area] if w.key == key).set_value(value)


def test_feedback_save_reopen_answer_correct_confirm_and_language(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    app = AppTest.from_file(str(APP)).run(timeout=40)
    fill(app, "unified_edit_question", "Explain device differences")
    click(app, key="unified_direct_review")
    click(app, label="This reflects my need → prepare both handoffs")
    original = app.session_state["last_problem_dir"]
    click(app, key="unified_feedback")
    fill(app, "feedback_sender", "Synthetic colleague")
    fill(app, "feedback_original", "Which average do you mean?")
    fill(app, "feedback_question", "How should we average?")
    click(app, label="Save feedback without changing the need")
    root = Path("outputs/ui_runs")
    record = load_problem(root, Path(original), app.session_state["active_project_id"])
    issue = discussion(root, record)[2]["state"]["issues"][0]["issue_id"]
    assert record.revision == 1
    reopened = AppTest.from_file(str(APP)).run(timeout=40)
    click(reopened, key="unified_feedback")
    assert any("Which average" in item.value for item in reopened.text)
    fill(reopened, f"feedback_answer_{issue}", "Average observations first")
    click(reopened, label="Save my response")
    fill(reopened, f"feedback_answer_{issue}", "Average each device first")
    fill(reopened, f"feedback_reason_{issue}", "I meant device weighting")
    click(reopened, label="Save my response")
    for lang in ("中文", "English"):
        next(r for r in reopened.radio if r.key == "language_control").set_value(lang).run(timeout=40)
        assert not reopened.exception
    next(s for s in reopened.selectbox if s.key == "feedback_update_kind").set_value("correction").run(timeout=40)
    fill(reopened, "feedback_confirm_reason", "Correct weighting")
    fill(reopened, "feedback_next_action", "Return a small synthetic sample")
    click(reopened, label="I confirm this update → prepare new briefs")
    updated = load_problem(root, Path(reopened.session_state["last_problem_dir"]), reopened.session_state["active_project_id"])
    assert updated.revision == 2 and updated.question == record.question
    assert updated.continuation["updates"][-1]["answer_history"][-1]["previous_answer"] == "Average observations first"


def test_source_annotation_and_action_are_distinct_from_program_result(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    app = AppTest.from_file(str(APP)).run(timeout=40)
    click(app, key="unified_demo")
    current = Path(app.session_state["last_problem_dir"])
    raw = (current / "audit_snapshot.json").read_text(encoding="utf-8")
    import json
    passage = json.loads(raw)["manuscript"]["text"].splitlines()[2]
    fill(app, "continuity_manual_quote", passage)
    fill(app, "continuity_manual_question", "Check whether this scope is justified")
    click(app, label="Add as unevaluated review item")
    assert any("Not evaluated" in item.value for item in app.info)
    next(s for s in app.selectbox if s.key.startswith("continuity_handling_claim_")).set_value("M001").run(timeout=40)
    fill(app, "continuity_note_text", "Ask the author")
    click(app, label="Save separate handling record")
    from claim_harness.comparison import load_audit_run
    from claim_harness.handling import audit_journal
    history = audit_journal(Path("outputs/ui_runs"), load_audit_run(current)).read()
    assert [e["kind"] for e in history["events"]] == ["manual_claim", "user_action"]


def test_switching_runs_rebinds_claim_titles_and_clears_unsaved_notes(tmp_path):
    from problem_bridge.workbench import audit_problem, confirm_problem
    root = tmp_path / "runs"
    need = confirm_problem(root, "switch-test", {"question": "Check synthetic results"})
    first = audit_problem(root, "switch-test", need, manuscript="The model achieves precision of 0.95.",
                          tables={"results.csv": b"model,precision\nmodel,0.85\n"})
    second = audit_problem(root, "switch-test", first, manuscript="The model achieves precision of 0.55.",
                           tables={"results.csv": b"model,precision\nmodel,0.55\n"})
    app = AppTest.from_string('''
from pathlib import Path
import streamlit as st
from claim_harness.continuity_ui import render_review_tools
current = st.selectbox("Run", st.session_state["paths"], key="test_current")
render_review_tools(Path(st.session_state["workspace"]), Path(current),
                    lambda en, zh: en, lambda label, action: action(), standalone=True)
''')
    app.session_state["workspace"] = str(root)
    app.session_state["paths"] = [str(first), str(second)]
    app.run(timeout=40)
    old_widget = next(s for s in app.selectbox if s.key.startswith("continuity_handling_claim_"))
    assert "0.95" in old_widget.options[0]
    fill(app, "continuity_manual_quote", "The old passage")
    fill(app, "continuity_note_text", "An unsaved note for the first run")
    next(s for s in app.selectbox if s.key == "test_current").set_value(str(second)).run(timeout=40)
    assert not app.exception
    new_widget = next(s for s in app.selectbox if s.key.startswith("continuity_handling_claim_"))
    assert old_widget.key != new_widget.key and "0.55" in new_widget.options[0]
    assert next(t for t in app.text_area if t.key == "continuity_manual_quote").value == ""
    assert next(t for t in app.text_area if t.key == "continuity_note_text").value == ""
