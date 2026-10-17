"""Local handoff acceptance checks use synthetic inputs only."""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

from claim_harness.cli import app as claim_app
from claim_harness.comparison import load_audit_run
from claim_harness.handling import annotate, audit_journal, record_handling
from claim_harness.handoff_export import evidence_brief, export_audit, export_problem, render_evidence_brief
from problem_bridge.cli import app as bridge_app
from problem_bridge.feedback import add_feedback, discussion
from problem_bridge.handoff import ConceptNote, NeedBrief
from problem_bridge.project_lifecycle import prepare_run_directory, snapshot_completed_run
from problem_bridge.workbench import answer_follow_up, audit_problem, confirm_problem, load_problem


PROJECT = "local-handoff-test"
TEXT = "# Results\nThe triage_reviewer achieves precision of 0.95.\n这个条件尚未核实 😀。\n"
TABLE = b"model,precision\ntriage_reviewer,0.85\n"


def problem(tmp_path, **kwargs):
    root = tmp_path / "runs"
    run = confirm_problem(root, PROJECT, {"question": "解释差异，不改成预测。"}, **kwargs)
    return root, run


def audit(tmp_path, text=TEXT):
    root, first = problem(tmp_path)
    return audit_problem(root, PROJECT, first, manuscript=text, tables={"results.csv": TABLE})


def exported(result, name):
    return json.loads(Path(result["files"][name]).read_text(encoding="utf-8"))


@pytest.mark.parametrize("language", ["zh", "en"])
def test_problem_preserves_all_saved_conditions_and_answers(tmp_path, language):
    root = tmp_path / "runs"
    fields = {"question": "保留我的问题。", "observation": "某次合成测量不一致。",
              "observation_source": "合成演示日志。", "desired_change": "解释条件差异。",
              "hypothesis": "可能与设备设置有关，未验证。", "human_boundary": "是否改变目标由我决定。"}
    brief = NeedBrief(background="领域研究者。", collaborator="协助查明设备条件。",
                      materials="只有合成表格，其他材料尚未获得。", success_check="能够定位一次差异。",
                      concepts=[ConceptNote(term="差异", meaning="同一条件下测量值不同。",
                                            example="设备甲与乙不同。", non_example="不要自动改成预测任务。")])
    initial = confirm_problem(root, PROJECT, fields, brief=brief, interview_answers={"limits": "先不用模型。"})
    checked = audit_problem(root, PROJECT, initial, manuscript=TEXT, tables={"results.csv": TABLE})
    current = answer_follow_up(root, PROJECT, checked, "coverage-review", "还需要核查中文条件。")
    before = snapshot_completed_run(current)
    result = export_problem(root, current, PROJECT, tmp_path / "带 空格的导出", language=language)
    value = exported(result, "problem_context.json")
    text = Path(result["files"]["problem_context.md"]).read_text(encoding="utf-8")
    assert value["record"] == json.loads(before["problem_record.json"])
    assert value["source"]["record_sha256"] == hashlib.sha256(before["problem_record.json"]).hexdigest()
    assert value["source"]["completion_sha256"] == hashlib.sha256(before["run_complete.json"]).hexdigest()
    assert value["is_current_at_export"] is True
    for word in [*fields.values(), brief.background, brief.collaborator, brief.materials, brief.success_check,
                 *brief.concepts[0].model_dump().values(), "先不用模型。", "还需要核查中文条件。"]:
        assert word in text
    assert "user_reported_not_verified" in text
    assert value["record"]["previous"]["run_name"] == checked.name
    assert snapshot_completed_run(current) == before
    assert {"problem_context.md", "problem_context.json"} <= snapshot_completed_run(Path(result["export_path"])).keys()


def test_problem_export_excludes_unconfirmed_feedback_and_preserves_legacy_schema(tmp_path):
    root, run = problem(tmp_path)
    old = snapshot_completed_run(run)
    history = add_feedback(root, PROJECT, run, target=run, sender="AI helper", sender_kind="ai",
                           original="Replace this with a predictor", selected="predictor", interpretation="not adopted",
                           category="new_goal", question="Change the goal?", expected_revision=0)
    record = load_problem(root, run, PROJECT)
    result = export_problem(root, run, PROJECT, tmp_path / "export")
    value = exported(result, "problem_context.json")
    text = Path(result["files"]["problem_context.md"]).read_text(encoding="utf-8")
    assert value["record"] == json.loads(old["problem_record.json"])
    assert "Replace this with a predictor" not in text
    assert "尚未明确" in text and value["record"]["observation"] == ""
    assert discussion(root, record)[1] == history
    assert snapshot_completed_run(run) == old


def test_historical_problem_is_explicitly_labelled(tmp_path):
    root, old = problem(tmp_path)
    confirm_problem(root, PROJECT, {"question": "用户确认的另一个目标。"}, previous=old)
    result = export_problem(root, old, PROJECT, tmp_path / "historical")
    value = exported(result, "problem_context.json")
    assert value["is_current_at_export"] is False
    assert "newer confirmed version" in value["current_warning"]
    assert value["record"]["question"] == "解释差异，不改成预测。"
    assert "历史版本" in Path(result["files"]["problem_context.md"]).read_text(encoding="utf-8")


@pytest.mark.parametrize("payload,confirmed,ok", [
    ({"out": "导出 目录"}, False, True),
    ({"out": "导出 目录", "language": "fr"}, False, False),
    ({"out": "导出 目录", "adopt_feedback": True}, False, False),
    ({"out": "导出 目录"}, True, False),
])
def test_problem_export_cli_validates_requests_and_rebases_output(tmp_path, payload, confirmed, ok):
    root, run = problem(tmp_path)
    base = tmp_path / "requests"
    base.mkdir()
    request = base / "export.json"
    request.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    args = ["task", "export", "--workspace", str(root), "--project-id", PROJECT,
            "--run", run.name, "--request", str(request)]
    result = CliRunner().invoke(bridge_app, [*args, "--confirmed"] if confirmed else args)
    assert (result.exit_code == 0) is ok, result.output
    if ok:
        assert Path(json.loads(result.output)["export_path"]) == base / "导出 目录"
    else:
        assert not (base / "导出 目录").exists()


def test_single_audit_retains_verdicts_evidence_and_separate_user_records(tmp_path):
    run = audit(tmp_path)
    before = snapshot_completed_run(run)
    workspace = tmp_path / "handling"
    start = TEXT.index("这个")
    annotate(workspace, run, start=start, end=len(TEXT.rstrip()), question="条件是否有依据？")
    record_handling(workspace, run, claim_id="C001", layer="user_action", action="done",
                    note="用户说已修改，尚未重新核查。", expected_revision=1)
    record_handling(workspace, run, claim_id="M001", layer="human_review", action="request_review",
                    note="请核实条件。", actor="合作者", source="合成演示意见", expected_revision=2)
    original = load_audit_run(run)
    journal = audit_journal(workspace, original).read()
    result = export_audit(run, tmp_path / "export", workspace)
    value = exported(result, "evidence_brief.json")
    text = Path(result["files"]["evidence_brief.md"]).read_text(encoding="utf-8")
    assert value["claims"] == original.claims and value["evidence"] == original.evidence
    assert value["inputs"] == original.manifest["inputs"]
    assert value["rules"] == original.snapshot["rules"]
    assert value["source"] == original.ref
    assert any(item["claim_id"] == "C001" for item in value["pending_findings"])
    assert value["manual_annotations"][0]["evaluation"] == "not_evaluated"
    assert value["manual_annotations"][0]["text"] == TEXT[start:].rstrip()
    assert value["user_records"] == journal and value["user_records"]["revision"] == 3
    assert value["user_records_included"] is True
    claim = value["claims"][0]
    assert claim["text"] in text and claim["reason"] in text
    assert claim["evidence_links"]
    for link in claim["evidence_links"]:
        assert link["evidence_id"] in text and "locator" in text
    assert "not_evaluated" in text and "用户说已修改" in text
    assert snapshot_completed_run(run) == before
    assert audit_journal(workspace, original).read() == journal
    assert {"evidence_brief.md", "evidence_brief.json"} <= snapshot_completed_run(Path(result["export_path"])).keys()


def test_optional_workspace_is_distinct_from_empty_workspace_and_zero_claims(tmp_path):
    run = audit(tmp_path, "# Notes\n这个条件尚未核实。\n")
    value = evidence_brief(run)
    assert value["claims"] == [] and value["coverage"] == "unknown"
    assert value["user_records_included"] is False and value["user_records"] is None
    assert "No claims were extracted" in render_evidence_brief(value)
    assert "Not included" in render_evidence_brief(value)
    workspace = tmp_path / "absent notes"
    included = evidence_brief(run, workspace)
    assert included["user_records_included"] is True
    assert included["user_records"]["revision"] == 0
    assert not workspace.exists()


@pytest.mark.parametrize("damage", ["tampered", "incomplete", "legacy"])
def test_invalid_or_unverified_audit_fails_without_export(tmp_path, damage):
    run = audit(tmp_path)
    if damage == "tampered":
        (run / "claim_table.csv").write_text("altered", encoding="utf-8")
    elif damage == "incomplete":
        (run / "run_complete.json").unlink()
    else:
        legacy = tmp_path / "legacy"
        legacy.mkdir()
        for name in ("run_manifest.json", "claim_table.csv", "evidence_map.json"):
            (legacy / name).write_bytes((run / name).read_bytes())
        run = legacy
    out = tmp_path / "export"
    result = CliRunner().invoke(claim_app, ["handoff", "--run", str(run), "--out", str(out)])
    assert result.exit_code == 1 and "verified complete audit" in result.output
    assert not out.exists()


def test_verified_older_audit_keeps_missing_snapshot_limitation(tmp_path):
    run = audit(tmp_path)
    legacy = tmp_path / "verified-old"
    names = ("run_manifest.json", "claim_table.csv", "evidence_map.json")
    context = prepare_run_directory(legacy, project_id=PROJECT, required_artifacts=names)
    manifest = json.loads((run / "run_manifest.json").read_text(encoding="utf-8"))
    manifest.update(run_id=context.run_id, schema_version=1)
    with context.transaction():
        (legacy / "run_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        for name in names[1:]:
            (legacy / name).write_bytes((run / name).read_bytes())
    result = export_audit(legacy, tmp_path / "export")
    value = exported(result, "evidence_brief.json")
    assert value["source"]["integrity"] == "verified" and value["rules"] is None
    assert any("snapshot is missing" in note for note in value["limitations"])


def test_destinations_cannot_modify_sources_or_existing_material(tmp_path):
    run = audit(tmp_path)
    before = snapshot_completed_run(run)
    result = export_audit(run, tmp_path / "first")
    existing = tmp_path / "existing"
    existing.mkdir()
    (existing / "user.txt").write_text("keep me", encoding="utf-8")
    for out in (run, run / "nested" / "export", Path(result["export_path"]) / "nested", existing):
        with pytest.raises((ValueError, RuntimeError)):
            export_audit(run, out)
    assert snapshot_completed_run(run) == before
    assert not (run / "nested").exists()
    assert (existing / "user.txt").read_text(encoding="utf-8") == "keep me"


def test_export_rejects_linked_destination(tmp_path):
    run = audit(tmp_path)
    real = tmp_path / "real"
    real.mkdir()
    link = tmp_path / "linked"
    try:
        link.symlink_to(real, target_is_directory=True)
    except OSError:
        if sys.platform != "win32":
            raise
        result = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(real)], capture_output=True)
        assert result.returncode == 0, result.stderr
    with pytest.raises(ValueError, match="Linked"):
        export_audit(run, link / "export")
    assert not list(real.iterdir())


def test_failed_export_has_no_completion_record(tmp_path, monkeypatch):
    run = audit(tmp_path)
    out = tmp_path / "export"
    original = Path.write_text

    def fail_markdown(path, *args, **kwargs):
        if path.name == "evidence_brief.md":
            raise OSError("simulated full disk")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", fail_markdown)
    with pytest.raises(OSError, match="simulated full disk"):
        export_audit(run, out)
    assert not (out / "run_complete.json").exists()
    with pytest.raises((ValueError, RuntimeError, OSError)):
        snapshot_completed_run(out)
