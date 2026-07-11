from pathlib import Path

import pytest


streamlit_testing = pytest.importorskip("streamlit.testing.v1")
AppTest = streamlit_testing.AppTest
APP_FILE = Path(__file__).resolve().parents[1] / "apps" / "problem_bridge_wizard.py"


@pytest.fixture
def isolated_app_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    return str(APP_FILE)


def test_streamlit_workbench_renders_project_and_document_intake_controls(isolated_app_file):
    app = AppTest.from_file(isolated_app_file).run(timeout=30)

    assert not app.exception
    assert len(app.sidebar.radio) == 1
    assert any(button.label == "Start a new project" for button in app.sidebar.button)

    app.sidebar.radio[0].set_value("Document intake").run(timeout=30)

    assert not app.exception
    assert any("OCR" in checkbox.label for checkbox in app.checkbox)


def test_home_route_keeps_one_workspace_session(isolated_app_file):
    app = AppTest.from_file(isolated_app_file).run(timeout=30)
    original_project = app.session_state["active_project_id"]

    start_with_files = next(
        button for button in app.button if button.label == "Start with files"
    )
    start_with_files.click().run(timeout=30)

    assert not app.exception
    assert app.sidebar.radio[0].value == "Document intake"
    assert app.session_state["active_project_id"] == original_project


def test_compact_next_step_navigation_keeps_one_workspace_session(isolated_app_file):
    app = AppTest.from_file(isolated_app_file).run(timeout=30)
    original_project = app.session_state["active_project_id"]
    app.sidebar.radio[0].set_value("Document intake").run(timeout=30)

    next(
        button
        for button in app.button
        if button.label == "Next: Question discovery →"
    ).click().run(timeout=30)

    assert not app.exception
    assert app.sidebar.radio[0].value == "Question discovery"
    assert app.session_state["active_project_id"] == original_project


def test_language_switch_keeps_one_workspace_session(isolated_app_file):
    app = AppTest.from_file(isolated_app_file).run(timeout=30)
    original_project = app.session_state["active_project_id"]

    language = next(radio for radio in app.radio if radio.label == "Interface language")
    language.set_value("中文").run(timeout=30)

    assert not app.exception
    assert app.session_state["active_project_id"] == original_project
    assert app.session_state["ui_language"] == "中文"
    assert app.query_params["lang"] in ("zh", ["zh"])


def test_question_discovery_empty_submit_shows_inline_validation(isolated_app_file):
    app = AppTest.from_file(isolated_app_file).run(timeout=30)
    app.sidebar.radio[0].set_value("Question discovery").run(timeout=30)

    submit = next(
        button
        for button in app.button
        if button.label == "Generate question discovery package"
    )
    submit.click().run(timeout=30)

    assert not app.exception
    assert app.error
    assert "required information" in app.error[0].value


def test_guided_interview_and_ai_check_reject_blank_inputs(isolated_app_file):
    app = AppTest.from_file(isolated_app_file).run(timeout=30)
    app.sidebar.radio[0].set_value("Domain practitioner wizard").run(timeout=30)

    save_answer = next(
        button for button in app.button if button.label == "Save answer and continue"
    )
    save_answer.click().run(timeout=30)

    assert not app.exception
    assert app.error[0].value == "Add an answer before continuing."

    app.sidebar.radio[0].set_value("AI practitioner wizard").run(timeout=30)
    check_alignment = next(
        button for button in app.button if button.label == "Check task alignment"
    )
    check_alignment.click().run(timeout=30)

    assert not app.exception
    assert any("required information" in error.value for error in app.error)


def test_question_discovery_success_continues_with_provisional_interview_seed(isolated_app_file):
    app = AppTest.from_file(isolated_app_file).run(timeout=30)
    app.sidebar.radio[0].set_value("Question discovery").run(timeout=30)

    fields = {text_area.label: text_area for text_area in app.text_area}
    fields["What are you trying to understand?"].set_value(
        "A registrar repeats condition checks before object loans."
    )
    fields["What feels unclear right now?"].set_value(
        "The duplicate handoff is unclear."
    )
    fields["What would a useful first conversation achieve?"].set_value(
        "Identify the records and people to validate."
    )
    next(
        button
        for button in app.button
        if button.label == "Generate question discovery package"
    ).click().run(timeout=30)

    assert not app.exception
    next(
        button
        for button in app.button
        if button.label == "Continue to Domain practitioner wizard"
    ).click().run(timeout=30)

    state = app.session_state["problem_bridge_interview_state"]
    assert not app.exception
    assert app.sidebar.radio[0].value == "Domain practitioner wizard"
    assert state.answers == {
        "repeated_work": "A registrar repeats condition checks before object loans."
    }


def test_starting_new_project_requires_confirmation_before_clearing_state(isolated_app_file):
    app = AppTest.from_file(isolated_app_file).run(timeout=30)
    original_project = app.session_state["active_project_id"]
    for key in [
        "last_example_dir",
        "interview_seed_source",
        "ai_seed_source_dir",
        "interview_answer_materials",
        "confirm_interview_reset",
    ]:
        app.session_state[key] = "old-project-value"

    next(
        button for button in app.sidebar.button if button.label == "Start a new project"
    ).click().run(timeout=30)

    assert not app.exception
    assert app.session_state["active_project_id"] == original_project
    assert all(
        app.session_state[key] == "old-project-value"
        for key in [
            "last_example_dir",
            "interview_seed_source",
            "ai_seed_source_dir",
            "interview_answer_materials",
            "confirm_interview_reset",
        ]
    )
    assert any(
        button.label == "Start without saving drafts" for button in app.sidebar.button
    )

    next(
        button
        for button in app.sidebar.button
        if button.label == "Start without saving drafts"
    ).click().run(timeout=30)

    assert not app.exception
    assert app.session_state["active_project_id"] != original_project
    assert app.sidebar.radio[0].value == "Home"
    for key in [
        "last_example_dir",
        "interview_seed_source",
        "ai_seed_source_dir",
        "interview_answer_materials",
        "confirm_interview_reset",
    ]:
        assert key not in app.session_state


def test_saved_drafts_restore_their_original_project_identity(isolated_app_file):
    app = AppTest.from_file(isolated_app_file).run(timeout=30)
    original_project = app.session_state["active_project_id"]
    app.session_state["question_seed_text"] = "Draft from the original project"

    next(
        button for button in app.sidebar.button if button.label == "Start a new project"
    ).click().run(timeout=30)
    next(
        button
        for button in app.sidebar.button
        if button.label == "Save drafts, then start"
    ).click().run(timeout=30)

    new_project = app.session_state["active_project_id"]
    assert new_project != original_project
    assert "question_seed_text" not in app.session_state

    next(
        checkbox
        for checkbox in app.sidebar.checkbox
        if checkbox.label == "Show workspace memory"
    ).set_value(True).run(timeout=30)
    next(
        button for button in app.sidebar.button if button.label == "Load saved memory"
    ).click().run(timeout=30)

    assert not app.exception
    assert app.session_state["active_project_id"] == original_project
    assert app.session_state["question_seed_text"] == "Draft from the original project"


def test_guided_interview_reset_requires_confirmation(isolated_app_file):
    from problem_bridge.interview import answer_question

    app = AppTest.from_file(isolated_app_file).run(timeout=30)
    app.sidebar.radio[0].set_value("Domain practitioner wizard").run(timeout=30)
    state = answer_question(
        app.session_state["problem_bridge_interview_state"],
        "domain",
        "Museum collections",
    )
    app.session_state["problem_bridge_interview_state"] = state

    next(
        button for button in app.button if button.label == "Reset guided interview"
    ).click().run(timeout=30)

    assert not app.exception
    assert app.session_state["problem_bridge_interview_state"].answers["domain"] == "Museum collections"
    assert any(button.label == "Confirm interview reset" for button in app.button)

    next(
        button for button in app.button if button.label == "Cancel reset"
    ).click().run(timeout=30)

    assert not app.exception
    assert app.session_state["problem_bridge_interview_state"].answers["domain"] == "Museum collections"
    assert any(button.label == "Reset guided interview" for button in app.button)

    app.session_state["interview_answer_materials"] = "temporary widget value"
    app.session_state["interview_edit_domain"] = "temporary edit value"
    next(
        button for button in app.button if button.label == "Reset guided interview"
    ).click().run(timeout=30)
    next(
        button for button in app.button if button.label == "Confirm interview reset"
    ).click().run(timeout=30)

    assert not app.exception
    assert app.session_state["problem_bridge_interview_state"].answers == {}
    assert "interview_answer_materials" not in app.session_state
    assert "interview_edit_domain" not in app.session_state
    assert "confirm_interview_reset" not in app.session_state


def test_clear_saved_memory_keeps_current_draft(isolated_app_file):
    app = AppTest.from_file(isolated_app_file).run(timeout=30)
    app.session_state["question_seed_text"] = "Keep this unsaved draft"
    app.session_state["domain_draft_repeated_work"] = "Keep domain draft"
    app.session_state["ai_draft_candidate_task"] = "Keep AI draft"

    show_memory = next(
        checkbox
        for checkbox in app.sidebar.checkbox
        if checkbox.label == "Show workspace memory"
    )
    show_memory.set_value(True).run(timeout=30)
    next(
        button
        for button in app.sidebar.button
        if button.label == "Save current workspace"
    ).click().run(timeout=30)
    memory_path = Path("outputs/ui_memory/workbench_memory.json")
    assert memory_path.is_file()

    next(
        button for button in app.sidebar.button if button.label == "Clear memory"
    ).click().run(timeout=30)

    assert not app.exception
    assert app.session_state["question_seed_text"] == "Keep this unsaved draft"
    assert app.session_state["domain_draft_repeated_work"] == "Keep domain draft"
    assert app.session_state["ai_draft_candidate_task"] == "Keep AI draft"
    assert not memory_path.exists()
    assert app.session_state["workbench_memory"] == {}
    assert "pending_workbench_memory" not in app.session_state


def test_ui_action_failure_is_recoverable(monkeypatch):
    from contextlib import nullcontext

    import apps.problem_bridge_wizard as ui

    errors = []
    captions = []
    monkeypatch.setattr(ui.st, "spinner", lambda _label: nullcontext())
    monkeypatch.setattr(ui.st, "error", errors.append)
    monkeypatch.setattr(ui.st, "caption", captions.append)

    result = ui._run_ui_action("Working", lambda: (_ for _ in ()).throw(ValueError("bad input")))

    assert result is None
    assert errors
    assert "inputs are still here" in errors[0]
    assert captions == ["ValueError: bad input"]
