"""Cross-disciplinary meaning stays user-owned across handoff and audit stages."""
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

import pytest

from problem_bridge.handoff import ConceptNote, NeedBrief, HANDOFF_ARTIFACTS, build_handoffs, missing_details
from problem_bridge.project_lifecycle import snapshot_completed_run
from problem_bridge.workbench import confirm_problem, load_problem, audit_problem
from problem_bridge.workbench_ui import DEMO_TEXT, DEMO_CSV


def test_both_handoffs_preserve_wording_unknowns_and_version(tmp_path):
    root = tmp_path / "runs"
    out = confirm_problem(root, "project-one", {"question": "比较作品的构图", "hypothesis": "可能是记录方式不同"},
                          brief=NeedBrief(concepts=[ConceptNote(term="构图", non_example="不是艺术价值打分")]))
    record = load_problem(root, out, "project-one")
    files = snapshot_completed_run(out)
    assert set(HANDOFF_ARTIFACTS).issubset(files)
    assert record.schema_version == 2
    assert any("构图" in item for item in missing_details(record, "zh"))
    for filename, content in build_handoffs(record).items():
        assert "比较作品的构图" in content
        assert "可能是记录方式不同" in content
        assert "不是艺术价值打分" in content
        assert record.framing_sha256 in content
        assert files[filename].decode("utf-8") == content
    assert "尚未明确" in files["model_task_zh.md"].decode()
    assert "文件需另附" in files["collaboration_brief_zh.md"].decode()
    assert not (out / "source_files").exists()


def test_domain_terms_and_acceptance_change_fingerprint_without_changing_history(tmp_path):
    root = tmp_path / "runs"
    original = confirm_problem(root, "project-one", {"question": "Compare notes"}, brief=NeedBrief(materials="Public notes"))
    audited = audit_problem(root, "project-one", original, manuscript=DEMO_TEXT, tables={"results.csv": DEMO_CSV.encode()})
    original_files = snapshot_completed_run(audited)
    old = load_problem(root, audited, "project-one")
    new_brief = old.brief.model_copy(update={"success_check": "Source rows must be recoverable",
                                           "concepts": [ConceptNote(term="Quality", meaning="Traceable source")]})
    revised = confirm_problem(root, "project-one", {"question": old.question}, previous=audited, brief=new_brief)
    new = load_problem(root, revised, "project-one")
    assert new.problem_id == old.problem_id
    assert new.framing_sha256 != old.framing_sha256
    assert new.audit is None
    assert snapshot_completed_run(audited) == original_files
    assert "Source rows" in (revised / "model_task_en.md").read_text(encoding="utf-8")
    retained = confirm_problem(root, "project-one", {"question": "Compare a different set"}, previous=revised)
    assert load_problem(root, retained, "project-one").brief == new_brief


def test_version_one_still_loads_and_handoffs_export_as_generated_files(tmp_path, monkeypatch):
    import apps.problem_bridge_wizard as ui
    root = tmp_path / "runs"
    out = confirm_problem(root, "project-one", {"question": "A legacy-style question"})
    record = load_problem(root, out, "project-one")
    assert record.schema_version == 1
    assert record.brief is None
    monkeypatch.setattr(ui, "RUN_ROOT", root)
    with ZipFile(BytesIO(ui._make_archive(out))) as archive:
        assert set(HANDOFF_ARTIFACTS).issubset(archive.namelist())
        assert "A legacy-style question" in archive.read("model_task_en.md").decode()


AppTest = pytest.importorskip("streamlit.testing.v1").AppTest
APP_FILE = Path(__file__).resolve().parents[1] / "apps/problem_bridge_wizard.py"


def click(app, key=None, label=None):
    next(item for item in app.button if (item.key == key if key else item.label == label)).click().run(timeout=30)
    assert not app.exception


def fill(app, key, value):
    next(item for item in [*app.text_area, *app.text_input] if item.key == key).set_value(value)


def confirm(app):
    click(app, label="This reflects my need → prepare both handoffs")


def test_novice_can_skip_unknowns_confirm_and_take_two_briefs_without_files(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    app = AppTest.from_file(str(APP_FILE)).run(timeout=30)
    assert len([item for item in app.text_area if item.key.startswith("unified_edit_")]) == 1
    click(app, label="Continue")
    assert any("Name one task" in item.value for item in app.error)
    fill(app, "unified_edit_question", "I want help comparing records")
    click(app, label="Continue")
    fill(app, "unified_edit_observation", "The descriptions differ across departments")
    click(app, label="Continue")
    click(app, "unified_intake_back")
    assert next(item for item in app.text_area if item.key == "unified_edit_observation").value.startswith("The descriptions")
    click(app, label="Continue")
    click(app, label="Not sure yet")
    click(app, label="Not sure yet")
    assert not Path("outputs/ui_runs").exists()  # unconfirmed answers are not a saved need
    confirm(app)
    out = Path(app.session_state["last_problem_dir"])
    assert app.session_state["unified_stage"] == 4
    record = load_problem(Path("outputs/ui_runs"), out, app.session_state["active_project_id"])
    assert record.desired_change == ""
    assert record.observation == "The descriptions differ across departments"
    assert record.audit is None
    assert not (out / "claim_table.csv").exists()
    assert all((out / name).is_file() for name in HANDOFF_ARTIFACTS)
    for language in ("中文", "English"):
        next(item for item in app.radio if item.key == "language_control").set_value(language).run(timeout=30)
        assert not app.exception
        assert app.session_state["unified_stage"] == 4
        assert app.session_state["last_problem_dir"] == str(out)
    reopened = AppTest.from_file(str(APP_FILE)).run(timeout=30)
    assert not reopened.exception
    assert reopened.session_state["unified_stage"] == 4
    assert reopened.session_state["last_problem_dir"] == str(out)


def test_terms_corrections_drafts_and_optional_audit_keep_one_problem(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    app = AppTest.from_file(str(APP_FILE)).run(timeout=30)
    click(app, "unified_need_demo")
    original = Path(app.session_state["last_problem_dir"])
    project_id = app.session_state["active_project_id"]
    click(app, "unified_edit_need")
    assert next(item for item in app.text_input if item.key == "unified_edit_term_0").value == "Composition"
    fill(app, "unified_edit_success_check", "Check one example together before continuing")
    click(app, label="Explain another term")
    fill(app, "unified_edit_term_1", "Similarity")
    fill(app, "unified_edit_non_example_1", "Not the same artist")
    confirm(app)
    revised = Path(app.session_state["last_problem_dir"])
    new = load_problem(Path("outputs/ui_runs"), revised, project_id)
    assert new.brief.success_check.startswith("Check one")
    assert new.brief.concepts[1].meaning == ""
    assert "Similarity" in (revised / "model_task_en.md").read_text(encoding="utf-8")
    assert new.problem_id == load_problem(Path("outputs/ui_runs"), original, project_id).problem_id
    click(app, "unified_edit_need")
    fill(app, "unified_edit_meaning_1", "A draft meaning not confirmed yet")
    next(item for item in app.radio if item.key == "unified_stage_en").set_value(4).run(timeout=30)
    assert any("unsaved wording" in item.value for item in app.warning)
    click(app, "unified_edit_need")
    assert next(item for item in app.text_area if item.key == "unified_edit_meaning_1").value.startswith("A draft")
    confirm(app)
    click(app, "unified_handoff_audit")
    click(app, "unified_sample_materials")
    click(app, "unified_run_audit")
    final = load_problem(Path("outputs/ui_runs"), Path(app.session_state["last_problem_dir"]), project_id)
    assert final.problem_id == new.problem_id
    assert final.brief.concepts[1].meaning.startswith("A draft")
    assert final.audit


def test_unfinished_need_can_be_saved_reopened_and_cleared_with_new_project(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    app = AppTest.from_file(str(APP_FILE)).run(timeout=30)
    fill(app, "unified_edit_question", "Explain archive categories to a software colleague")
    click(app, label="Continue")
    next(item for item in app.checkbox if item.key == "show_workspace_memory").check().run(timeout=30)
    click(app, "memory_save")
    reopened = AppTest.from_file(str(APP_FILE)).run(timeout=30)
    assert reopened.session_state["unified_intake_step"] == 1
    click(reopened, "unified_intake_back")
    assert next(item for item in reopened.text_area if item.key == "unified_edit_question").value.startswith("Explain archive")
    click(reopened, "start_new_project")
    click(reopened, "discard_then_start_project")
    assert reopened.session_state["unified_intake_step"] == 0
    assert next(item for item in reopened.text_area if item.key == "unified_edit_question").value == ""
