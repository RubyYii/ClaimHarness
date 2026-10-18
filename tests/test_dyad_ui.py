from pathlib import Path

import pytest

from problem_bridge.dyad import handoff_state
from problem_bridge.workbench import load_problem

AppTest = pytest.importorskip("streamlit.testing.v1").AppTest
APP = Path(__file__).resolve().parents[1] / "apps/problem_bridge_wizard.py"


def click(app, *, key=None, label=None):
    next(b for b in app.button if (b.key == key if key else b.label == label)).click().run(timeout=30)
    assert not app.exception
    assert not app.error, [e.value for e in app.error]


def field(app, suffix):
    return next(f for f in app.text_area if f.key and f.key.endswith(suffix))


def test_real_ui_two_way_cycle_and_saved_draft_reopen(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    app = AppTest.from_file(str(APP)).run(timeout=30)
    app.session_state["unified_edit_question"] = "Compare the synthetic records"
    app.run(timeout=30)
    click(app, key="main_nav_6")
    click(app, key="unified_confirm_need")
    click(app, key="unified_start_dyad")
    field(app, "_understanding").set_value("I will compare the source rows")
    field(app, "_proposal").set_value("Start with two sample rows")
    field(app, "_questions").set_value("Which columns matter?")
    click(app, label="Save B's draft")
    assert any("Not confirmed" in m.value for m in app.markdown)
    # A fresh Streamlit session restores the saved task; the draft is loaded from the journal.
    app = AppTest.from_file(str(APP)).run(timeout=30)
    click(app, key="main_nav_7")
    assert field(app, "_understanding").value == "I will compare the source rows"
    click(app, label="Send response back to A")
    click(app, key="unified_dyad_to_a")
    field(app, "_answer").set_value("Keep the source and location columns")
    field(app, "_reason").set_value("They let me trace each observation")
    field(app, "_remaining").set_value("Missing rows need a rule")
    field(app, "_next_action").set_value("B prepares two rows; A checks traceability")
    click(app, label="Confirm my response and return it to B")
    click(app, key="unified_dyad_to_b")
    field(app, "_note").set_value("I can prepare these two rows")
    click(app, label="Save my review of this version")
    root = Path("outputs/ui_runs")
    current = Path(app.session_state["last_problem_dir"])
    record = load_problem(root, current, app.session_state["active_project_id"])
    state = handoff_state(root, current, record)
    assert state["both_ready"] and record.revision == 2
    assert state["response"]["open_questions"][0]["question"] == "Missing rows need a rule"
    next(f for f in app.text_input if f.key and "sample_title" in f.key).set_value("Two-row sample")
    field(app, "sample_content_" + current.name).set_value("source,location\npublic-example,line 1")
    click(app, label="Save sample for this version")
    assert len(handoff_state(root, current, record)["samples"]) == 1
    click(app, key="main_nav_4")
    click(app, key="main_nav_7")
    assert not app.exception


def test_chinese_role_switch_keeps_unsaved_text(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    app = AppTest.from_file(str(APP)).run(timeout=30)
    next(r for r in app.radio if r.label == "Interface language").set_value("中文").run(timeout=30)
    app.session_state["unified_edit_question"] = "整理合成记录"
    app.run(timeout=30)
    click(app, key="main_nav_6")
    click(app, key="unified_confirm_need")
    click(app, key="main_nav_7")
    field(app, "_understanding").set_value("先整理两条记录")
    click(app, label="保存 B 的草稿")
    next(r for r in app.radio if r.key == "unified_dyad_role").set_value("A").run(timeout=30)
    assert not app.exception
    click(app, key="unified_dyad_to_b")
    assert field(app, "_understanding").value == "先整理两条记录"


def test_ui_selects_requirements_and_records_a_real_sample_check(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    app = AppTest.from_file(str(APP)).run(timeout=30)
    app.session_state["unified_edit_question"] = "Summarize synthetic sites"
    app.session_state["unified_edit_desired_change"] = "Each site has equal weight"
    app.run(timeout=30)
    click(app, key="main_nav_6")
    click(app, key="unified_confirm_need")
    click(app, key="main_nav_7")
    next(r for r in app.radio if r.key == "unified_dyad_role").set_value("A").run(timeout=30)
    next(s for s in app.selectbox if s.label == "Confirmed source").select("desired_change").run(timeout=30)
    click(app, label="Confirm requirement in a new version")
    click(app, key="unified_dyad_to_b")
    field(app, "_understanding").set_value("Give each site equal weight")
    click(app, label="Send response back to A")
    click(app, key="unified_dyad_to_a")
    field(app, "_answer").set_value("Yes, retain equal weights")
    field(app, "_reason").set_value("Each site represents one unit")
    field(app, "_next_action").set_value("B returns the two-site mean")
    next(c for c in app.checkbox if c.key and c.key.endswith("_no_open")).check()
    click(app, label="Confirm my response and return it to B")
    current = Path(app.session_state["last_problem_dir"])
    project = app.session_state["active_project_id"]
    root = Path("outputs/ui_runs")
    requirement_id = load_problem(root, current, project).requirements[0].requirement_id
    next(s for s in app.selectbox if s.label == "Requirement to manage").select(requirement_id).run(timeout=30)
    next(s for s in app.selectbox if s.label == "Confirmed source").select("desired_change").run(timeout=30)
    click(app, label="Confirm requirement in a new version")
    click(app, label="Save my review of this version")
    click(app, key="unified_dyad_to_b")
    click(app, label="Save my review of this version")
    current = Path(app.session_state["last_problem_dir"])
    next(f for f in app.text_input if f.label == "Sample title").set_value("Mean of two sites")
    field(app, "sample_content_" + current.name).set_value("site,mean\nNorth,10\nSouth,20\nAll,15\n")
    click(app, label="Save sample for this version")
    next(r for r in app.radio if r.key == "unified_dyad_role").set_value("A").run(timeout=30)
    next(s for s in app.selectbox if s.label == "My check result").select("met")
    next(f for f in app.text_input if f.label == "How did you check?").set_value("Manual arithmetic")
    next(f for f in app.text_input if f.label.startswith("Location in this sample")).set_value("All row, mean column")
    next(f for f in app.text_area if f.label == "What did you observe?").set_value("(10+20)/2 = 15")
    click(app, label="Save my attributed check")
    from problem_bridge.requirements import current_trace
    check = current_trace(root, project, current)["requirements"][0]["check"]
    assert check["applicable"] and check["actor"] == "A · A" and check["result"] == "met"
