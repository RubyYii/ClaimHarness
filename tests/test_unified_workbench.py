"""Evidence-to-question continuity, without an external model or test-only verdicts."""
import json
from pathlib import Path

import pytest

from problem_bridge.project_lifecycle import is_run_complete, snapshot_completed_run
from problem_bridge.workbench import (
    answer_follow_up, audit_problem, confirm_problem, load_audit, load_problem,
)
from problem_bridge.workbench_ui import DEMO_CSV, DEMO_TEXT


@pytest.fixture
def problem(tmp_path):
    root = tmp_path / "runs"
    out = confirm_problem(root, "project-demo", {
        "question": "Which triage claims have result evidence?",
        "observation": "Two versions have different precision values.",
        "observation_source": "A colleague's report, still to be checked",
        "hypothesis": "The text uses an older table.",
        "human_boundary": "The author confirms corrections.",
    }, interview_answers={"pain_points": "Finding sources takes time"})
    return root, out


def run_demo(root, out):
    return audit_problem(root, "project-demo", out, manuscript=DEMO_TEXT,
                         tables={"results.csv": DEMO_CSV.encode()})


def test_problem_audit_follow_up_and_reframe_keep_identity_and_historical_evidence(problem):
    root, out = problem
    first = load_problem(root, out, "project-demo")
    audit = run_demo(root, out)
    checked = load_problem(root, audit, "project-demo")
    files, feedback = load_audit(root, checked)
    assert is_run_complete(audit)
    assert checked.problem_id == first.problem_id
    assert checked.previous.run_name == out.name
    assert checked.interview_answers == first.interview_answers
    assert checked.framing_sha256 == first.framing_sha256
    assert "applied_evidence_contract.json" not in files  # no generated template promoted to evidence
    conflict = next(item for item in feedback["questions"] if item["kind"] == "conflict")
    assert "0.95" in conflict["claim_text"]
    assert any(item["relation"] == "contradicts" and item["locator"]["row"] for item in conflict["evidence"])
    assert feedback["questions"][-1]["question_id"] == "coverage-review"
    assert files["source_files/tables/results.csv"] == DEMO_CSV.encode()
    assert all(name in files for name in ("claim_table.csv", "evidence_map.json", "audit_report.md", "revision_suggestions.md", "agent_trace.jsonl"))

    answered = answer_follow_up(root, "project-demo", audit, conflict["question_id"], "Ask the author to check the current precision table.")
    response = load_problem(root, answered, "project-demo")
    assert response.problem_id == first.problem_id
    assert response.responses[-1].status == "user_reported_not_verified"
    assert load_audit(root, response)[0]["claim_table.csv"] == files["claim_table.csv"]
    reframed = confirm_problem(root, "project-demo", {"question": "Which version should the report use?"}, previous=answered)
    revised = load_problem(root, reframed, "project-demo")
    assert revised.problem_id == first.problem_id
    assert revised.audit is None
    assert revised.framing_sha256 != first.framing_sha256
    assert revised.responses == response.responses
    assert snapshot_completed_run(audit) == files


def test_no_extraction_is_a_coverage_question_not_a_pass(problem):
    root, out = problem
    audit = audit_problem(root, "project-demo", out, manuscript="# Notes\nHello world.", tables={"results.csv": DEMO_CSV.encode()})
    record = load_problem(root, audit, "project-demo")
    _, feedback = load_audit(root, record)
    assert feedback["claim_count"] == 0
    assert [item["question_id"] for item in feedback["questions"]] == ["coverage-review"]


def test_source_tampering_and_foreign_projects_fail_closed(problem, tmp_path):
    root, out = problem
    with pytest.raises(ValueError, match="another project"):
        load_problem(root, out, "someone-else")
    with pytest.raises(ValueError, match="outside"):
        load_problem(root, tmp_path / out.name, "project-demo")
    audit = run_demo(root, out)
    record = load_problem(root, audit, "project-demo")
    (audit / "source_files/tables/results.csv").write_text("model,precision\na,1", encoding="utf-8")
    with pytest.raises(RuntimeError):
        load_audit(root, record)
    with pytest.raises(RuntimeError):
        answer_follow_up(root, "project-demo", audit, "coverage-review", "Do not accept tampered evidence")


@pytest.mark.parametrize("tables", [
    {}, {"../escape.csv": b"x\n1"}, {"CON.csv": b"x\n1"},
    {"bad.csv": b"x,x\n1,2"}, {"bad.csv": b"x,y\n1"},
    {"bad.csv": b"x,y"}, {"bad.csv": b"\xff"},
    {"A.csv": b"x\n1", "a.csv": b"x\n2"},
])
def test_invalid_materials_do_not_create_a_partial_result(problem, tables):
    root, out = problem
    before = set(root.iterdir())
    with pytest.raises(ValueError):
        audit_problem(root, "project-demo", out, manuscript=DEMO_TEXT, tables=tables)
    assert set(root.iterdir()) == before


def test_failed_audit_keeps_the_confirmed_problem_and_no_completed_result(problem, monkeypatch):
    import problem_bridge.workbench as workbench
    root, out = problem
    def fail(*args, **kwargs):
        raise OSError("Simulated storage failure")
    monkeypatch.setattr(workbench, "write_local_audit", fail)
    with pytest.raises(OSError):
        run_demo(root, out)
    assert is_run_complete(out)
    incomplete = [path for path in root.iterdir() if path.name.startswith("problem_audit-")]
    assert len(incomplete) == 1
    assert not is_run_complete(incomplete[0])


def test_follow_up_cannot_invent_a_question_or_point_to_a_different_problem(problem):
    root, out = problem
    audit = run_demo(root, out)
    with pytest.raises(ValueError, match="not part"):
        answer_follow_up(root, "project-demo", audit, "invented-question", "answer")
    record = load_problem(root, audit, "project-demo")
    record.framing_sha256 = "0" * 64
    with pytest.raises(ValueError, match="framing"):
        load_audit(root, record)


def test_unified_share_package_keeps_follow_up_and_excludes_original_inputs(problem, monkeypatch):
    from io import BytesIO
    from zipfile import ZipFile
    import apps.problem_bridge_wizard as ui
    root, out = problem
    audit = run_demo(root, out)
    monkeypatch.setattr(ui, "RUN_ROOT", root)
    with ZipFile(BytesIO(ui._make_archive(audit))) as package:
        assert {"problem_record.json", "follow_up.json", "claim_table.csv"}.issubset(package.namelist())
        assert not any(name.startswith("source_files/") for name in package.namelist())
    with ZipFile(BytesIO(ui._make_archive(audit, include_source_files=True))) as package:
        assert package.read("source_files/tables/results.csv") == DEMO_CSV.encode()


AppTest = pytest.importorskip("streamlit.testing.v1").AppTest
APP_FILE = Path(__file__).resolve().parents[1] / "apps/problem_bridge_wizard.py"


def click(app, key):
    next(button for button in app.button if button.key == key).click().run(timeout=30)
    assert not app.exception


def area(app, key, value):
    next(field for field in app.text_area if field.key == key).set_value(value)


def test_ui_one_problem_from_interview_to_audit_to_next_question_and_reopening(tmp_path, monkeypatch):
    from problem_bridge.interview import answer_question, start_interview
    monkeypatch.chdir(tmp_path)
    app = AppTest.from_file(str(APP_FILE)).run(timeout=30)
    interview = answer_question(start_interview(), "repeated_work", "Check a report against source tables")
    interview = answer_question(interview, "pain_points", "Precision differs across versions")
    app.session_state["problem_bridge_interview_state"] = interview
    app.run(timeout=30)
    click(app, "unified_use_interview")
    assert next(field for field in app.text_area if field.key == "unified_edit_question").value == interview.answers["repeated_work"]
    next(button for button in app.button if button.label == "This reflects my need → prepare both handoffs").click().run(timeout=30)
    assert not app.exception
    original = Path(app.session_state["last_problem_dir"])
    click(app, "unified_handoff_audit")
    click(app, "unified_sample_materials")
    click(app, "unified_run_audit")
    audit = Path(app.session_state["last_problem_dir"])
    assert is_run_complete(audit)
    assert (audit / "claim_table.csv").is_file()
    assert original != audit
    area(app, next(field.key for field in app.text_area if field.key.startswith("unified_answer_")), "Ask the author for the current result version")
    click(app, "unified_save_answer")
    answered = Path(app.session_state["last_problem_dir"])
    record = load_problem(Path("outputs/ui_runs"), answered, app.session_state["active_project_id"])
    assert record.responses[-1].answer == "Ask the author for the current result version"
    reopened = AppTest.from_file(str(APP_FILE)).run(timeout=30)
    assert not reopened.exception
    assert reopened.session_state["last_problem_dir"] == str(answered)
    assert reopened.session_state["active_project_id"] == app.session_state["active_project_id"]
    next(radio for radio in reopened.radio if radio.key == "unified_stage_en").set_value(3).run(timeout=30)
    click(reopened, "unified_reframe")
    assert reopened.session_state["unified_stage"] == 1
    assert "Ask the author" in reopened.session_state["unified_return_question"]
    area(reopened, "unified_edit_question", "Which version of the result belongs in the report?")
    next(button for button in reopened.button if button.label == "This reflects my need → prepare both handoffs").click().run(timeout=30)
    assert not reopened.exception
    revised = load_problem(Path("outputs/ui_runs"), Path(reopened.session_state["last_problem_dir"]), record.project_id)
    assert revised.problem_id == record.problem_id
    assert revised.audit is None


def test_ui_complete_demo_and_new_project_do_not_mix_materials(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    app = AppTest.from_file(str(APP_FILE)).run(timeout=30)
    click(app, "unified_demo")
    assert app.session_state["unified_stage"] == 3
    project = app.session_state["active_project_id"]
    click(app, "unified_rerun")
    assert "triage_reviewer" in next(field for field in app.text_area if field.key == "unified_manuscript").value
    click(app, "start_new_project")
    click(app, "discard_then_start_project")
    assert app.session_state["active_project_id"] != project
    assert "last_problem_dir" not in app.session_state
    assert "unified_reused_tables" not in app.session_state
    assert app.session_state["unified_stage"] == 1


def test_ui_incomplete_inputs_show_specific_guidance_without_creating_a_run(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    app = AppTest.from_file(str(APP_FILE)).run(timeout=30)
    click(app, "unified_direct_review")
    next(button for button in app.button if button.label == "This reflects my need → prepare both handoffs").click().run(timeout=30)
    assert any("Write the task" in error.value for error in app.error)
    assert not Path("outputs/ui_runs").exists()
    area(app, "unified_edit_question", "Which claims are supported?")
    next(button for button in app.button if button.label == "This reflects my need → prepare both handoffs").click().run(timeout=30)
    original = app.session_state["last_problem_dir"]
    click(app, "unified_handoff_audit")
    click(app, "unified_run_audit")
    assert any("text to check" in error.value for error in app.error)
    area(app, "unified_manuscript", "The model improves precision to 0.95.")
    click(app, "unified_run_audit")
    assert any("CSV result table" in error.value for error in app.error)
    assert app.session_state["last_problem_dir"] == original
    assert len(list(Path("outputs/ui_runs").iterdir())) == 1


def test_ui_material_draft_survives_step_and_tool_switch_and_marks_old_results(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    app = AppTest.from_file(str(APP_FILE)).run(timeout=30)
    click(app, "unified_demo")
    click(app, "unified_rerun")
    area(app, "unified_manuscript", "A new statement not checked yet.")
    next(radio for radio in app.radio if radio.key == "unified_stage_en").set_value(3).run(timeout=30)
    assert any("draft has changed" in warning.value for warning in app.warning)
    click(app, "quick_nav_4")
    click(app, "quick_nav_0")
    click(app, "unified_rerun")
    assert next(field for field in app.text_area if field.key == "unified_manuscript").value == "A new statement not checked yet."


def test_ui_selected_uploads_override_paste_and_keep_exact_audited_materials(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    app = AppTest.from_file(str(APP_FILE)).run(timeout=30)
    click(app, "unified_demo")
    click(app, "unified_rerun")
    replacement = DEMO_TEXT.replace("0.95", "0.86")
    app.session_state["unified_uploaded_text"] = ("new-report.md", replacement.encode())
    app.session_state["unified_uploaded_tables"] = [("results.csv", DEMO_CSV.encode())]
    app.run(timeout=30)
    next(radio for radio in app.radio if radio.key == "unified_stage_en").set_value(3).run(timeout=30)
    assert any("draft has changed" in warning.value for warning in app.warning)
    click(app, "unified_rerun")
    assert app.session_state["unified_uploaded_text"][1] == replacement.encode()
    click(app, "unified_run_audit")
    assert not any("draft has changed" in warning.value for warning in app.warning)
    out = Path(app.session_state["last_problem_dir"])
    assert (out / "source_files/manuscript.md").read_text(encoding="utf-8") == replacement


def test_language_switch_preserves_both_navigation_levels_and_the_problem(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    app = AppTest.from_file(str(APP_FILE)).run(timeout=30)
    click(app, "unified_demo")
    original = app.session_state["last_problem_dir"]
    next(box for box in app.selectbox if box.key.startswith("unified_finding_")).set_value("coverage-review").run(timeout=30)
    for language in ("中文", "English", "中文"):
        next(radio for radio in app.radio if radio.key == "language_control").set_value(language).run(timeout=30)
        assert not app.exception
        assert app.session_state["workspace_page"] == "Home"
        assert app.session_state["unified_stage"] == 3
        assert app.session_state["last_problem_dir"] == original
        assert any(button.key == "unified_save_answer" for button in app.button)
        assert next(box for box in app.selectbox if box.key.startswith("unified_finding_")).value == "coverage-review"
