"""User journeys for the compact workbench, isolated from real project data."""

import json
from pathlib import Path

import pytest

from problem_bridge.project_lifecycle import is_run_complete, load_run_identity


AppTest = pytest.importorskip("streamlit.testing.v1").AppTest
APP_FILE = Path(__file__).resolve().parents[1] / "apps/problem_bridge_wizard.py"


@pytest.fixture
def app(tmp_path, monkeypatch):
    source = APP_FILE.parents[1] / "examples/problem_bridge/quality_inspection/problem.md"
    example = tmp_path / "examples/problem_bridge/quality_inspection/problem.md"
    example.parent.mkdir(parents=True)
    example.write_bytes(source.read_bytes())
    monkeypatch.chdir(tmp_path)
    return AppTest.from_file(str(APP_FILE)).run(timeout=30)


def click(app, key):
    return next(button for button in app.button if button.key == key).click().run(timeout=30)


def answer(app, text):
    next(field for field in app.text_area if field.label == "Your answer").set_value(text)
    click(app, "interview_save_answer")
    assert not app.exception


def test_one_click_example_produces_current_project_result_and_preserves_draft(app):
    from problem_bridge.interview import answer_question, start_interview

    project = app.session_state["active_project_id"]
    draft = answer_question(start_interview(), "repeated_work", "My own unsent workflow")
    app.session_state["problem_bridge_interview_state"] = draft
    click(app, "home_run_example")

    assert not app.exception
    assert app.session_state["workspace_page"] == "View generated outputs"
    out = Path(app.session_state["last_output_dir"])
    assert is_run_complete(out)
    assert load_run_identity(out)["project_id"] == project
    assert app.session_state["problem_bridge_interview_state"] == draft
    assert app.get("download_button")
    assert (out / "problem_card.md").is_file()
    assert (out / "evidence_contract.yaml").is_file()


def test_failed_example_keeps_existing_interview_and_gives_retry_feedback(app):
    from problem_bridge.interview import answer_question, start_interview

    Path("examples/problem_bridge/quality_inspection/problem.md").unlink()
    draft = answer_question(start_interview(), "repeated_work", "Keep this work")
    app.session_state["problem_bridge_interview_state"] = draft
    click(app, "home_run_example")

    assert not app.exception
    assert app.session_state["workspace_page"] == "Home"
    assert app.session_state["problem_bridge_interview_state"] == draft
    assert any("inputs are still here" in error.value for error in app.error)
    assert not Path("outputs/ui_runs").exists()


def test_correct_earlier_answer_continue_and_generate(app):
    click(app, "quick_nav_4")
    answer(app, "Compare a report with its tables")
    answer(app, "A draft report and a spreadsheet")
    click(app, "interview_edit_button_repeated_work")
    assert next(field for field in app.text_area if field.label == "Your answer").value == "Compare a report with its tables"
    answer(app, "Check weekly reports against their source tables")
    assert app.session_state["problem_bridge_interview_state"].answers == {
        "repeated_work": "Check weekly reports against their source tables",
        "materials": "A draft report and a spreadsheet",
    }
    answer(app, "Finding the correct source version is slow")
    answer(app, "The author must approve the final conclusion")
    answer(app, "A list of discrepancies and their source rows")
    click(app, "interview_generate")

    assert not app.exception
    out = Path(app.session_state["last_alignment_package_dir"])
    assert is_run_complete(out)
    problem = (out / "problem.md").read_text(encoding="utf-8")
    assert "Check weekly reports against their source tables" in problem
    assert "The author must approve" in problem
    assert "Compare a report with its tables" not in problem


def test_home_resume_and_language_switch_preserve_interview(app):
    click(app, "quick_nav_4")
    answer(app, "Check weekly reports")
    click(app, "quick_nav_0")
    click(app, "home_resume_interview")
    next(radio for radio in app.radio if radio.key == "language_control").set_value("中文").run(timeout=30)

    assert not app.exception
    assert app.session_state["problem_bridge_interview_state"].answers == {"repeated_work": "Check weekly reports"}
    assert any(field.placeholder.startswith("我会看报告") for field in app.text_area)


def test_saved_interview_restores_answers_and_project_after_reopening(app):
    project = app.session_state["active_project_id"]
    click(app, "quick_nav_4")
    answer(app, "Organize evidence tables")
    next(c for c in app.checkbox if c.key == "show_workspace_memory").check().run(timeout=30)
    click(app, "memory_save")
    memory = json.loads(Path("outputs/ui_memory/workbench_memory.json").read_text(encoding="utf-8"))
    assert memory["interview_answers"] == {"repeated_work": "Organize evidence tables"}

    reopened = AppTest.from_file(str(APP_FILE)).run(timeout=30)
    assert not reopened.exception
    assert reopened.session_state["active_project_id"] == project
    click(reopened, "home_resume_interview")
    assert reopened.session_state["problem_bridge_interview_state"].answers == memory["interview_answers"]


def test_unopened_history_controls_do_not_scan_past_runs(app, monkeypatch):
    def unexpected_scan(*args, **kwargs):
        raise AssertionError("History was scanned without a user request")

    import problem_bridge.project_lifecycle as lifecycle
    monkeypatch.setattr(lifecycle, "is_run_complete", unexpected_scan)
    monkeypatch.setattr(lifecycle, "load_run_identity", unexpected_scan)
    past = Path("outputs/ui_runs/old-run")
    past.mkdir(parents=True)
    (past / "run_identity.json").write_text("{}", encoding="utf-8")

    app.run(timeout=30)
    assert not app.exception
    click(app, "quick_nav_4")
    assert not app.exception


def test_empty_results_offer_a_working_return_route(app):
    click(app, "quick_nav_7")
    assert not app.exception
    click(app, "empty_results_home")
    assert app.session_state["workspace_page"] == "Home"
