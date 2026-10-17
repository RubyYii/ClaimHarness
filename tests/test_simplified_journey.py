from pathlib import Path

import pytest

AppTest = pytest.importorskip("streamlit.testing.v1").AppTest
APP = Path(__file__).resolve().parents[1] / "apps/problem_bridge_wizard.py"


def click(app, key):
    next(button for button in app.button if button.key == key).click().run(timeout=30)
    assert not app.exception


def test_direct_audit_does_not_confirm_an_unfinished_need(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    app = AppTest.from_file(str(APP)).run(timeout=30)
    # This unfinished intent must remain a draft when the user enters checking.
    app.session_state["unified_edit_question"] = "Unconfirmed different work"
    app.run(timeout=30)
    click(app, "main_nav_2")
    next(field for field in app.text_input if field.key == "unified_audit_scope").set_value("Check these synthetic numbers")
    click(app, "unified_sample_materials")
    click(app, "unified_run_audit")
    from problem_bridge.workbench import load_problem
    record = load_problem(Path("outputs/ui_runs"), Path(app.session_state["last_problem_dir"]), app.session_state["active_project_id"])
    assert record.question == "Check these synthetic numbers"
    assert app.session_state["unified_edit_question"] == "Unconfirmed different work"
    assert record.audit
    assert next(button for button in app.button if button.key == "main_nav_3").disabled is False
    # Supported claims must be inspectable alongside problematic claims.
    click(app, "claim_card_C001")
    assert any("Sources for C001" in item.value for item in app.subheader)
    assert app.dataframe
    click(app, "main_nav_1")
    assert next(field for field in app.text_area if field.key == "unified_edit_question").value == "Unconfirmed different work"


def test_confirmation_navigation_preserves_unconfirmed_wording(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    app = AppTest.from_file(str(APP)).run(timeout=30)
    next(field for field in app.text_area if field.key == "unified_edit_question").set_value("Compare the weekly report")
    next(button for button in app.button if button.label == "Continue").click().run(timeout=30)
    click(app, "main_nav_6")
    assert next(field for field in app.text_area if field.key == "unified_edit_question").value == "Compare the weekly report"
    assert "last_problem_dir" not in app.session_state
    assert next(button for button in app.button if button.key == "main_nav_4").disabled


def test_leaving_review_retains_draft_without_changing_confirmed_brief(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    app = AppTest.from_file(str(APP)).run(timeout=30)
    next(field for field in app.text_area if field.key == "unified_edit_question").set_value("Compare the weekly report").run(timeout=30)
    click(app, "main_nav_6")
    click(app, "unified_confirm_need")
    saved_run = app.session_state["last_problem_dir"]
    click(app, "main_nav_6")
    next(field for field in app.text_area if field.key == "unified_edit_observation").set_value("An unconfirmed change").run(timeout=30)
    click(app, "main_nav_4")
    assert any("unsaved wording" in item.value for item in app.warning)
    assert app.session_state["last_problem_dir"] == saved_run
    from problem_bridge.workbench import load_problem
    saved = load_problem(Path("outputs/ui_runs"), Path(saved_run), app.session_state["active_project_id"])
    assert saved.observation == ""
    click(app, "main_nav_6")
    assert next(field for field in app.text_area if field.key == "unified_edit_observation").value == "An unconfirmed change"
