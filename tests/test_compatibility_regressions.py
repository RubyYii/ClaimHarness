"""Regressions spanning legacy workbench and version-bound two-person handoffs."""
import json
from pathlib import Path

import pytest

from problem_bridge import dyad
from problem_bridge.feedback import require_current
from problem_bridge.workbench import confirm_problem, load_problem


def test_historical_handoff_keeps_its_reply_when_later_rounds_arrive(tmp_path):
    root, project = tmp_path / "runs", "history-test"
    first = confirm_problem(root, project, {"question": "Summarize synthetic rows"})
    record = load_problem(root, first, project)
    dyad.recipient_reply(root, project, first, actor="B", understanding="First understanding", expected_revision=0)
    state = dyad.handoff_state(root, first, record)
    second = dyad.confirm_response(root, project, first, reply_id=state["reply"]["reply_id"], actor="A",
        answer="Keep the source column", reason="It lets us trace the rows", next_action="Make two rows",
        no_open_questions=True, expected_revision=1)
    newer = load_problem(root, second, project)
    assert json.loads((second / "problem_record.json").read_text(encoding="utf-8"))["schema_version"] == 3
    current = dyad.handoff_state(root, second, newer)
    dyad.recipient_reply(root, project, second, actor="B", understanding="A later round",
        expected_revision=current["history"]["revision"])
    old = dyad.handoff_state(root, first, record)
    assert old["reply"]["understanding"] == "First understanding"
    assert old["pending"] and old["response"] is None
    assert dyad.handoff_state(root, second, newer)["reply"]["understanding"] == "A later round"


@pytest.mark.parametrize("damaged", ["{unfinished", "[]", '{"project_id":"unrelated","revision":"invalid"}'])
def test_incomplete_unrelated_record_does_not_block_valid_work(tmp_path, damaged):
    root, project = tmp_path / "runs", "unrelated-test"
    current = confirm_problem(root, project, {"question": "Summarize synthetic rows"})
    partial = root / "uncompleted-run"
    partial.mkdir()
    (partial / "problem_record.json").write_text(damaged, encoding="utf-8")
    record = load_problem(root, current, project)
    require_current(root, record)
    dyad.recipient_reply(root, project, current, actor="B", understanding="A valid reply", expected_revision=0)
    assert dyad.handoff_state(root, current, record)["pending"]


def test_schema_three_does_not_emit_version_four_extension(tmp_path):
    project = "schema3-test"
    current = confirm_problem(tmp_path, project, {"question": "Synthetic task"})
    dyad.recipient_reply(tmp_path, project, current, actor="B", understanding="Return a table", expected_revision=0)
    state = dyad.handoff_state(tmp_path, current, load_problem(tmp_path, current, project))
    newer = dyad.confirm_response(tmp_path, project, current, actor="A", reply_id=state["reply"]["reply_id"],
        answer="Keep the source column", reason="Traceability", next_action="Return two rows",
        no_open_questions=True, expected_revision=1)
    payload = json.loads((newer / "problem_record.json").read_text(encoding="utf-8"))
    assert payload["schema_version"] == 3
    assert payload["continuation"]["updates"]
    assert "requirements" not in payload


def test_restored_exports_preserve_schema_four_and_new_handoff_context(tmp_path):
    from claim_harness.handoff_export import export_problem, export_audit
    from problem_bridge.handoff import NeedBrief
    from problem_bridge.requirements import confirm_requirements
    from problem_bridge.workbench import audit_problem

    root, project = tmp_path / "runs", "v4-export"
    current = confirm_problem(root, project, {"question": "Compare synthetic rows", "desired_change": "Keep source locations"},
        brief=NeedBrief(background="A synthetic domain user", collaborator="Check the table structure",
                        materials="A public toy table", success_check="Locate both source rows"))
    current = confirm_requirements(root, project, current,
        {"select": [{"source_key": "desired_change", "quote": "Keep source locations"}]},
        confirmed=True, expected_revision=1)
    dyad.recipient_reply(root, project, current, actor="B", understanding="Keep a source column", expected_revision=0)
    state = dyad.handoff_state(root, current, load_problem(root, current, project))
    current = dyad.confirm_response(root, project, current, actor="A", reply_id=state["reply"]["reply_id"],
        answer="Retain a source column", reason="Each observation must be traceable", next_action="Return two rows",
        remaining="Decide the missing-value label later", expected_revision=1)
    exported = export_problem(root, current, project, tmp_path / "problem-export", language="en")
    value = json.loads(Path(exported["files"]["problem_context.json"]).read_text(encoding="utf-8"))
    text = Path(exported["files"]["problem_context.md"]).read_text(encoding="utf-8")
    assert value["record"]["schema_version"] == 4
    assert value["record"]["requirements"][0]["status"] == "needs_reconfirmation"
    for expected in ("A synthetic domain user", "Check the table structure", "Locate both source rows",
                     "Keep source locations", "Keep a source column", "Decide the missing-value label later"):
        assert expected in text
    audited = audit_problem(root, project, current, manuscript="The example achieves precision of 0.95.",
                            tables={"results.csv": b"model,precision\nexample,0.85\n"})
    exported = export_audit(audited, tmp_path / "audit-export")
    audit = json.loads(Path(exported["files"]["evidence_brief.json"]).read_text(encoding="utf-8"))
    assert audit["claims"] and audit["pending_findings"]


@pytest.mark.parametrize("language", ["English", "中文"])
def test_all_legacy_ui_routes_remain_reachable_and_keep_the_draft(tmp_path, monkeypatch, language):
    AppTest = pytest.importorskip("streamlit.testing.v1").AppTest
    app_file = Path(__file__).resolve().parents[1] / "apps/problem_bridge_wizard.py"
    monkeypatch.chdir(tmp_path)
    app = AppTest.from_file(str(app_file)).run(timeout=30)
    if language == "中文":
        next(r for r in app.radio if r.key == "language_control").set_value(language).run(timeout=30)
    app.session_state["unified_edit_question"] = "An unfinished synthetic need"
    app.run(timeout=30)
    original_project = app.session_state["active_project_id"]
    # Frozen page inventory from the previously published main workbench.
    for destination in ("Explore examples", "Document intake", "Question discovery",
                        "Domain practitioner wizard", "AI practitioner wizard", "Evidence-gated build",
                        "View generated outputs", "Home"):
        next(r for r in app.radio if r.key.startswith("navigation_")).set_value(destination).run(timeout=30)
        assert not app.exception, (destination, app.exception)
        assert app.session_state["active_project_id"] == original_project
    assert app.session_state["unified_edit_question"] == "An unfinished synthetic need"
