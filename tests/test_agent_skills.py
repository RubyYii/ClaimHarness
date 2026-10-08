"""Portable client installation and real headless workflows with synthetic inputs."""
import json
from pathlib import Path
import subprocess
import sys

import pytest
from typer.testing import CliRunner

from claim_harness.cli import app as claim_app
from problem_bridge.cli import app as bridge_app
from problem_bridge.project_lifecycle import snapshot_completed_run
import scripts.install_agent_skills as installer
from scripts.run_agent_skills_demo import run_demo


ROOT = Path(__file__).resolve().parents[1]
runner = CliRunner()


def invoke(tmp_path, action, data=None, run=None, confirmed=False, success=True):
    args = ["task", action, "--workspace", str(tmp_path / "runs"), "--project-id", "skill-test"]
    if data is not None:
        request = tmp_path / "requests" / "request.json"
        request.parent.mkdir(exist_ok=True)
        request.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        args += ["--request", str(request)]
    if run:
        args += ["--run", run]
    if confirmed:
        args += ["--confirmed"]
    result = runner.invoke(bridge_app, args)
    if success:
        assert result.exit_code == 0, result.output
        return json.loads(result.output)
    assert result.exit_code != 0, result.output
    return result


def create(tmp_path):
    return invoke(tmp_path, "create", {"fields": {"question": "解释合成结果差异"}}, confirmed=True)


def feedback_payload(revision=0):
    return {"expected_revision": revision, "sender": "Synthetic AI", "sender_kind": "ai",
            "original": "Build a predictor. Clarify the averaging unit.", "selected": "averaging unit",
            "interpretation": "Explain only the unit", "category": "terminology", "question": "Which unit?"}


def test_headless_cli_preserves_intent_history_and_stale_writes(tmp_path):
    first = create(tmp_path)
    path = Path(first["run_path"])
    original = snapshot_completed_run(path)
    saved = invoke(tmp_path, "feedback", feedback_payload(), first["run_name"])
    assert saved["discussion"]["feedback"][0]["status"] == "proposal_not_adopted"
    assert "predictor" in saved["discussion"]["feedback"][0]["original"]
    invoke(tmp_path, "feedback", feedback_payload(), first["run_name"], success=False)
    issue = saved["discussion"]["feedback"][0]["feedback_id"]
    answered = invoke(tmp_path, "respond", {"expected_revision": 1, "issue_id": issue,
                      "mode": "answer", "answer": "按设备平均"}, first["run_name"])
    decision = {"expected_revision": answered["journal_revision"], "kind": "supplement",
                "reason": "确认单位", "next_action": "请合作者复述"}
    invoke(tmp_path, "confirm", decision, first["run_name"], success=False)
    revised = invoke(tmp_path, "confirm", decision, first["run_name"], confirmed=True)
    assert revised["record"]["question"] == first["record"]["question"]
    assert revised["journal_revision"] == 4
    assert not invoke(tmp_path, "show", run=first["run_name"])["is_current"]
    invoke(tmp_path, "feedback", feedback_payload(4), first["run_name"], success=False)
    assert snapshot_completed_run(path) == original
    for filename in revised["handoffs"].values():
        assert "按设备平均" in Path(filename).read_text(encoding="utf-8")
    next_round = invoke(tmp_path, "next-round", {"expected_revision": 4, "budget": 2}, revised["run_name"])
    assert next_round["journal_revision"] == 5


@pytest.mark.parametrize("data,confirmed", [
    ({"fields": {"question": "Q"}}, False),
    ({"fields": {"question": "Q", "invented": "value"}}, True),
    ({"fields": {"question": "Q"}, "previous": "old"}, True),
    ({"fields": {"question": 42}}, True),
    ({"fields": {"question": " "}}, True),
])
def test_create_rejects_unconfirmed_or_malformed_request_without_run(tmp_path, data, confirmed):
    invoke(tmp_path, "create", data, confirmed=confirmed, success=False)
    assert not (tmp_path / "runs").exists()


def test_unknown_and_duplicate_fields_and_run_traversal_are_rejected(tmp_path):
    first = create(tmp_path)
    bad = feedback_payload()
    bad.pop("expected_revision")
    invoke(tmp_path, "feedback", bad, first["run_name"], success=False)
    bad["expected_revision"] = True
    invoke(tmp_path, "feedback", bad, first["run_name"], success=False)
    for name in ("../" + first["run_name"], "..\\" + first["run_name"], first["run_path"]):
        invoke(tmp_path, "show", run=name, success=False)
    request = tmp_path / "duplicate.json"
    request.write_text('{"fields":{"question":"first","question":"second"}}', encoding="utf-8")
    result = runner.invoke(bridge_app, ["task", "create", "--workspace", str(tmp_path / "runs"),
                           "--project-id", "skill-test", "--request", str(request), "--confirmed"])
    assert result.exit_code == 1 and "Duplicate JSON field" in result.output


def test_audit_json_paths_inspection_unicode_offsets_and_read_only_state(tmp_path):
    first = create(tmp_path)
    base = tmp_path / "requests"
    text = "# Results\n前言 😀\nThe model achieves precision of 0.95.\n"
    (base / "稿件.md").write_bytes(text.replace("\n", "\r\n").encode("utf-8"))
    (base / "scores.csv").write_text("model,precision\nmodel,0.85\n", encoding="utf-8")
    audited = invoke(tmp_path, "audit", {"manuscript": "稿件.md", "tables": ["scores.csv"]}, first["run_name"])
    before = snapshot_completed_run(Path(audited["run_path"]))
    workspace = tmp_path / "manual"
    args = ["inspect", "--run", audited["run_path"], "--workspace", str(workspace)]
    result = runner.invoke(claim_app, args)
    assert result.exit_code == 0, result.output
    inspected = json.loads(result.output)
    assert inspected["manuscript"]["text"] == text
    assert inspected["journal_revision"] == 0
    assert not workspace.exists()
    start = text.index("The model")
    result = runner.invoke(claim_app, ["annotate", "--run", audited["run_path"], "--workspace", str(workspace),
                           "--start", str(start), "--end", str(len(text.rstrip())), "--question", "Check this span",
                           "--expected-revision", "0"])
    assert result.exit_code == 0, result.output
    inspected = json.loads(runner.invoke(claim_app, args).output)
    assert inspected["journal_revision"] == 1
    assert inspected["history"]["events"][0]["payload"]["text"] == text[start:].rstrip()
    assert snapshot_completed_run(Path(audited["run_path"])) == before
    assert runner.invoke(claim_app, ["inspect", "--run", str(tmp_path / "missing")]).exit_code == 1


def test_installer_dry_run_collision_upgrade_and_modified_file(tmp_path, capsys):
    args = ["--client", "both", "--scope", "project", "--project", str(tmp_path)]
    assert installer.main([*args, "--dry-run"]) == 0
    assert not list(tmp_path.iterdir())
    unmanaged = tmp_path / ".claude" / "skills" / "claim-harness"
    unmanaged.mkdir(parents=True)
    (unmanaged / "mine.txt").write_text("keep me")
    assert installer.main(args) == 1
    assert not (tmp_path / ".agents").exists()  # All destinations preflighted.
    assert (unmanaged / "mine.txt").read_text() == "keep me"
    destination = tmp_path / "managed"
    files = installer.payload("problem-bridge", Path(sys.executable))
    installer.install(destination, files, False)
    before = installer.inventory(destination)
    installer.install(destination, files, True)
    assert installer.inventory(destination) == before
    (destination / "SKILL.md").write_text("user customization")
    with pytest.raises(ValueError, match="local changes"):
        installer.install(destination, files, True)
    assert (destination / "SKILL.md").read_text() == "user customization"


def test_installer_rolls_back_a_failed_replacement(tmp_path, monkeypatch):
    destination = tmp_path / "managed"
    files = installer.payload("problem-bridge", Path(sys.executable))
    installer.install(destination, files, False)
    before = installer.inventory(destination)
    original_rename = Path.rename

    def fail_stage(path, target):
        if path.name.startswith(".claimharness-stage-"):
            raise OSError("simulated interrupted replacement")
        return original_rename(path, target)

    monkeypatch.setattr(Path, "rename", fail_stage)
    with pytest.raises(OSError, match="simulated"):
        installer.install(destination, {**files, "SKILL.md": b"replacement"}, True)
    assert installer.inventory(destination) == before
    assert sorted(p.name for p in tmp_path.iterdir()) == ["managed"]


def test_installer_refuses_links(tmp_path):
    real = tmp_path / "real"
    real.mkdir()
    link = tmp_path / "link"
    try:
        link.symlink_to(real, target_is_directory=True)
    except OSError:
        if sys.platform == "win32":
            # Junctions need no Windows symlink privilege.
            result = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(real)], capture_output=True)
            assert result.returncode == 0, result.stderr
        else:
            raise
    with pytest.raises(ValueError, match="Linked"):
        installer.verify_destination(link / "problem-bridge", True)


def test_installed_workflow_runs_from_another_unicode_project(tmp_path):
    summary = run_demo(tmp_path / "独立项目 with spaces")
    comparison = json.loads((Path(summary["comparison"]) / "audit_changes.json").read_text(encoding="utf-8"))
    assert comparison["comparability"] == "comparable"
    assert len(comparison["changes"]) > 0
    assert Path(summary["original"]).is_dir()
    assert Path(summary["confirmed"]).is_dir()
    assert (Path(summary["standalone_audit"]) / "audit_report.md").is_file()
    assert not (ROOT / "runs").exists()  # Runner never redirected outputs into backend cwd.
    helper = Path(summary["project"]) / ".agents/skills/claim-harness/scripts/run.py"
    failed = subprocess.run([sys.executable, "-X", "utf8", str(helper), "inspect", "--run=missing"],
                            cwd=summary["project"], capture_output=True, text=True, encoding="utf-8")
    assert failed.returncode == 1  # Preserve backend failure, including --flag=value paths.


def test_agent_modules_do_not_require_streamlit():
    code = """
import importlib.abc
import sys
class NoUI(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path, target=None):
        if fullname == 'streamlit' or fullname.startswith('streamlit.'):
            raise RuntimeError('UI imported in headless workflow')
sys.meta_path.insert(0, NoUI())
import problem_bridge.agent_cli
import claim_harness.agent_inspect
assert 'streamlit' not in sys.modules
"""
    result = subprocess.run([sys.executable, "-X", "utf8", "-c", code], cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
