"""Observable requirement preservation, explicit ownership and version-scoped checks."""
import hashlib
import json

import pytest
from typer.testing import CliRunner

from problem_bridge.cli import app
from problem_bridge.handoff import NeedBrief
from problem_bridge.project_lifecycle import snapshot_completed_run
from problem_bridge.requirements import (confirm_requirements, current_trace, export_trace,
    record_check, source_catalog)
from problem_bridge.workbench import FRAME_FIELDS, audit_problem, confirm_problem, load_problem


PROJECT = "requirement-test"
QUOTE = "Keep missing readings; do not replace them with zero."


def setup(root):
    first = confirm_problem(root, PROJECT, {"question": "Summarize daily conditions.",
        "desired_change": QUOTE + " Round only the final mean to 2 decimal places."},
        brief=NeedBrief(success_check="North must average to 22."))
    selected = confirm_requirements(root, PROJECT, first,
        {"select": [{"source_key": "desired_change", "quote": QUOTE,
                     "acceptance": "Inspect missing-site rows."}]}, confirmed=True, expected_revision=1)
    return first, selected, load_problem(root, selected, PROJECT)


def test_exact_requirement_reaches_all_handoffs_with_real_locations_and_hashes(tmp_path):
    first, selected, record = setup(tmp_path)
    original = snapshot_completed_run(first)
    assert record.schema_version == 4
    item = current_trace(tmp_path, PROJECT, selected)["requirements"][0]
    assert item["text"] == QUOTE and item["check"] is None
    source = item["source"]
    assert source["record_sha256"] == hashlib.sha256(original["problem_record.json"]).hexdigest()
    raw = json.loads(original["problem_record.json"])[source["key"]]
    assert raw[source["start"]:source["end"]] == QUOTE
    assert {x["file"] for x in item["handoff_locations"]} == {
        "collaboration_brief_en.md", "collaboration_brief_zh.md", "model_task_en.md", "model_task_zh.md"}
    for location in item["handoff_locations"]:
        data = (selected / location["file"]).read_bytes()
        assert hashlib.sha256(data).hexdigest() == location["sha256"]
        span = data.decode().splitlines()[location["start_line"] - 1:location["end_line"]]
        assert "> " + QUOTE in span
    assert snapshot_completed_run(first) == original


def test_selection_requires_explicit_confirmation_exact_source_and_current_revision(tmp_path):
    first, selected, _ = setup(tmp_path)
    with pytest.raises(ValueError, match="Explicit"):
        confirm_requirements(tmp_path, PROJECT, selected, {"select": []}, confirmed=False, expected_revision=2)
    with pytest.raises(ValueError, match="Stale"):
        confirm_requirements(tmp_path, PROJECT, first, {"select": [{"source_key": "question", "quote": "Summarize"}]}, confirmed=True, expected_revision=1)
    with pytest.raises(ValueError, match="exactly"):
        confirm_requirements(tmp_path, PROJECT, selected, {"select": [{"source_key": "desired_change", "quote": "Replace missing readings with zero."}]}, confirmed=True, expected_revision=2)
    with pytest.raises(ValueError, match="Stale"):
        confirm_requirements(tmp_path, PROJECT, selected, {"select": [{"source_key": "question", "quote": "Summarize"}]}, confirmed=True, expected_revision=0)


def test_repeated_source_needs_offset_and_ids_cannot_be_silently_repurposed(tmp_path):
    first = confirm_problem(tmp_path, PROJECT, {"question": "Keep all rows. Keep all rows."})
    selection = {"source_key": "question", "quote": "Keep all rows."}
    with pytest.raises(ValueError, match="offset"):
        confirm_requirements(tmp_path, PROJECT, first, {"select": [selection]}, confirmed=True, expected_revision=1)
    selected = confirm_requirements(tmp_path, PROJECT, first, {"select": [{**selection, "start": 15}]}, confirmed=True, expected_revision=1)
    record = load_problem(tmp_path, selected, PROJECT)
    item = record.requirements[0]
    assert item.source.start == 15
    with pytest.raises(ValueError, match="same text"):
        confirm_requirements(tmp_path, PROJECT, selected, {"select": [{"requirement_id": item.requirement_id,
            "source_key": "question", "quote": "rows.", "start": 9}]}, confirmed=True, expected_revision=2)
    with pytest.raises(ValueError, match="once"):
        confirm_requirements(tmp_path, PROJECT, selected, {"select": [
            {**selection, "start": 0, "requirement_id": item.requirement_id}] * 2}, confirmed=True, expected_revision=2)


def test_change_requires_reconfirmation_retirement_is_explicit_and_historical_data_survives(tmp_path):
    _, selected, record = setup(tmp_path)
    old_files = snapshot_completed_run(selected)
    changed = confirm_problem(tmp_path, PROJECT, {**{k: getattr(record, k) for k in FRAME_FIELDS},
        "question": "Compare daily conditions instead."}, previous=selected)
    new = load_problem(tmp_path, changed, PROJECT)
    rid = new.requirements[0].requirement_id
    assert new.requirements[0].status == "needs_reconfirmation"
    with pytest.raises(ValueError, match="confirmed requirement"):
        record_check(tmp_path, PROJECT, changed, requirement_id=rid, result="not_checked",
            actor="Tester", method="Pending", note="Pending", expected_revision=0)
    restored = confirm_requirements(tmp_path, PROJECT, changed, {"select": [{"requirement_id": rid,
        "source_key": "desired_change", "quote": QUOTE}]}, confirmed=True, expected_revision=3)
    assert load_problem(tmp_path, restored, PROJECT).requirements[0].status == "confirmed"
    retired = confirm_requirements(tmp_path, PROJECT, restored, {"retire": {rid: "User changed the output scope."}}, confirmed=True, expected_revision=4)
    final = load_problem(tmp_path, retired, PROJECT)
    assert final.requirements[0].status == "retired" and final.requirements[0].text == QUOTE
    assert "User changed the output scope." in (retired / "requirement_trace.md").read_text(encoding="utf-8")
    assert snapshot_completed_run(selected) == old_files


def test_checks_are_attributed_version_bound_and_report_changed_or_missing_evidence(tmp_path):
    _, selected, record = setup(tmp_path)
    old_files = snapshot_completed_run(selected)
    rid = record.requirements[0].requirement_id
    evidence = tmp_path / "result.csv"
    evidence.write_text("site,mean\nWest,\n", encoding="utf-8")
    args = dict(requirement_id=rid, result="met", actor="Tester", method="Inspect missing-site rows",
                note="West has a blank mean.", artifact="result.csv", location="row 2", expected_revision=0)
    with pytest.raises(ValueError, match="evidence file"):
        record_check(tmp_path, PROJECT, selected, **{**args, "artifact": ""})
    record_check(tmp_path, PROJECT, selected, **args)
    check = current_trace(tmp_path, PROJECT, selected)["requirements"][0]["check"]
    assert check["authority"] == "user_reported_not_verified" and check["applicable"]
    with pytest.raises(ValueError, match="Stale"):
        record_check(tmp_path, PROJECT, selected, **args)
    evidence.write_text("site,mean\nWest,0\n", encoding="utf-8")
    check = current_trace(tmp_path, PROJECT, selected)["requirements"][0]["check"]
    assert check["evidence_state"] == "changed" and not check["applicable"]
    evidence.unlink()
    assert current_trace(tmp_path, PROJECT, selected)["requirements"][0]["check"]["evidence_state"] == "missing_or_unreadable"
    clone = confirm_problem(tmp_path, PROJECT, {k: getattr(record, k) for k in FRAME_FIELDS}, previous=selected)
    assert current_trace(tmp_path, PROJECT, clone)["requirements"][0]["check"] is None
    assert snapshot_completed_run(selected) == old_files


def test_audit_keeps_selected_requirements_but_check_does_not_change_verdicts(tmp_path):
    _, selected, record = setup(tmp_path)
    audited = audit_problem(tmp_path, PROJECT, selected, manuscript="The model achieves accuracy of 0.90.",
        tables={"results.csv": b"model,accuracy\nmodel,0.90\n"})
    original = snapshot_completed_run(audited)
    assert load_problem(tmp_path, audited, PROJECT).requirements[0].status == "confirmed"
    record_check(tmp_path, PROJECT, audited, requirement_id=record.requirements[0].requirement_id,
        result="not_checked", actor="Tester", method="Domain review still needed", note="No acceptance judgement yet.", expected_revision=0)
    assert snapshot_completed_run(audited) == original
    export_trace(tmp_path, PROJECT, audited, tmp_path / "review")
    value = json.loads((tmp_path / "review/requirement_trace.json").read_text(encoding="utf-8"))
    assert value["completeness"] == "unknown" and len(value["check_history"]) == 1
    with pytest.raises(ValueError, match="fresh"):
        export_trace(tmp_path, PROJECT, audited, audited / "nested-export")
    with pytest.raises(ValueError, match="fresh"):
        export_trace(tmp_path, PROJECT, audited, tmp_path / "review")


def test_evidence_path_escape_and_unknown_requirement_are_rejected(tmp_path):
    _, selected, record = setup(tmp_path)
    args = dict(requirement_id=record.requirements[0].requirement_id, result="met", actor="Tester",
        method="Inspect row", note="Reported", location="row 1", expected_revision=0)
    for path in ("../outside.csv", str(tmp_path / "absolute.csv"), "result.csv:stream"):
        with pytest.raises(ValueError, match="relative"):
            record_check(tmp_path, PROJECT, selected, artifact=path, **args)
    with pytest.raises(ValueError, match="confirmed requirement"):
        record_check(tmp_path, PROJECT, selected, artifact="result.csv", **{**args, "requirement_id": "R-000000000000"})


def test_cli_demo_and_read_commands_work_with_legacy_sources(tmp_path):
    result = CliRunner().invoke(app, ["requirements-demo", "--out", str(tmp_path / "demo")])
    assert result.exit_code == 0, result.output
    manifest = json.loads(result.output)
    assert manifest["remaining_unchecked"] == 2 and manifest["external_calls"] == 0
    root = tmp_path / "demo/workspace"
    selected = tmp_path / "demo" / manifest["confirmed_run"]
    sources = CliRunner().invoke(app, ["requirement-sources", "--workspace", str(root), "--run", str(selected), "--project-id", manifest["project_id"]])
    assert sources.exit_code == 0 and "Give each sensor equal weight." in sources.output
    legacy = confirm_problem(tmp_path / "legacy", PROJECT, {"question": "Keep my original wording."})
    record = load_problem(tmp_path / "legacy", legacy, PROJECT)
    assert record.schema_version == 1 and source_catalog(record)["question"] == "Keep my original wording."


def test_unconfirmed_feedback_is_not_a_requirement_source(tmp_path):
    from problem_bridge.feedback import add_feedback, confirm_discussion, respond
    first = confirm_problem(tmp_path, PROJECT, {"question": "Explain, do not predict."})
    history = add_feedback(tmp_path, PROJECT, first, target=first, sender="AI", sender_kind="ai",
        original="Build a predictor instead.", selected="Build a predictor instead.", interpretation="Unaccepted suggestion",
        category="new_goal", question="Keep explanation?", expected_revision=0)
    issue = history["events"][-1]["payload"]["feedback"][0]["feedback_id"]
    assert "Build a predictor" not in json.dumps(source_catalog(load_problem(tmp_path, first, PROJECT)))
    respond(tmp_path, PROJECT, first, issue_id=issue, mode="answer", answer="Keep explanation.", expected_revision=1)
    updated = confirm_discussion(tmp_path, PROJECT, first, kind="supplement", reason="Preserve scope", next_action="Produce a small explanation sample", expected_revision=2)
    sources = source_catalog(load_problem(tmp_path, updated, PROJECT))
    assert sources[f"answer.{issue}"] == "Keep explanation."
    assert "Build a predictor" not in json.dumps(sources)


def test_all_cli_writes_have_explicit_selection_and_versioned_checks(tmp_path):
    runner = CliRunner()
    first = confirm_problem(tmp_path, PROJECT, {"question": "Keep all rows."})
    changes = tmp_path / "changes.json"
    changes.write_text(json.dumps({"select": [{"source_key": "question", "quote": "Keep all rows."}]}), encoding="utf-8")
    command = ["confirm-requirements", "--workspace", str(tmp_path), "--run", str(first),
        "--project-id", PROJECT, "--changes", str(changes), "--expected-revision", "1"]
    assert runner.invoke(app, command).exit_code != 0
    result = runner.invoke(app, command + ["--confirm"])
    assert result.exit_code == 0, result.output
    from pathlib import Path
    selected = Path(result.output.strip().removeprefix("out="))
    record = load_problem(tmp_path, selected, PROJECT)
    base = ["--workspace", str(tmp_path), "--run", str(selected), "--project-id", PROJECT]
    check = runner.invoke(app, ["record-requirement-check", *base,
        "--requirement-id", record.requirements[0].requirement_id, "--result", "not_checked",
        "--actor", "Tester", "--method", "Pending", "--note", "Waiting for output", "--expected-revision", "0"])
    assert check.exit_code == 0 and "journal_revision=1" in check.output
    exported = runner.invoke(app, ["export-requirements", *base, "--out", str(tmp_path / "export")])
    assert exported.exit_code == 0, exported.output
    trace = json.loads((tmp_path / "export/requirement_trace.json").read_text(encoding="utf-8"))
    assert trace["requirements"][0]["check"]["result"] == "not_checked"
    assert trace["requirements"][0]["check"]["applicable"] is False


def test_selecting_requirements_keeps_pending_feedback_answerable(tmp_path):
    from problem_bridge.feedback import add_feedback, confirm_discussion, discussion, respond
    first = confirm_problem(tmp_path, PROJECT, {"question": "Keep all rows."})
    added = add_feedback(tmp_path, PROJECT, first, target=first, sender="Colleague", sender_kind="collaborator",
        original="Which rows?", selected="Which rows?", interpretation="Clarify output scope",
        category="missing_condition", question="Include missing rows?", expected_revision=0)
    issue = added["events"][-1]["payload"]["feedback"][0]["feedback_id"]
    selected = confirm_requirements(tmp_path, PROJECT, first, {"select": [
        {"source_key": "question", "quote": "Keep all rows."}]}, confirmed=True, expected_revision=1)
    record = load_problem(tmp_path, selected, PROJECT)
    data = discussion(tmp_path, record, selected)[2]
    assert data["current_run"] == selected.name and data["state"]["issues"][0]["issue_id"] == issue
    respond(tmp_path, PROJECT, selected, issue_id=issue, mode="answer", answer="Include missing rows.", expected_revision=1)
    updated = confirm_discussion(tmp_path, PROJECT, selected, kind="supplement", reason="Clarify missingness",
        next_action="Return the small sample", expected_revision=2)
    assert load_problem(tmp_path, updated, PROJECT).requirements[0].status == "needs_reconfirmation"
