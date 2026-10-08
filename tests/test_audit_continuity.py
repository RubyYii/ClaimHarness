"""Adversarial acceptance cases for CH-01–06, using only synthetic material."""
import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path

import pytest
from typer.testing import CliRunner

from claim_harness.cli import app
from claim_harness.comparison import compare_runs, export_comparison, load_audit_run, normalize
from claim_harness.continuity_store import Journal
from claim_harness.handling import annotate, audit_journal, record_handling
from problem_bridge.project_lifecycle import snapshot_completed_run
from problem_bridge.workbench import audit_problem, confirm_problem


TEXT = "# Results\nThe model achieves precision of 0.95.\nThe model improves recall to 0.80.\n"
CSV = b"model,precision,recall\nmodel,0.85,0.80\n"


def make_audit(tmp_path, text=TEXT, csv=CSV, previous=None):
    root = tmp_path / "runs"
    if previous is None:
        previous = confirm_problem(root, "continuity-test", {"question": "Check synthetic scores"})
    return audit_problem(root, "continuity-test", previous, manuscript=text, tables={"results.csv": csv})


def test_identical_input_and_inserted_sentence_do_not_shift_claim_identity(tmp_path):
    old = make_audit(tmp_path)
    same = make_audit(tmp_path, previous=old)
    value = compare_runs(old, same, same_task=True)
    assert value["comparability"] == "comparable"
    assert {c["kind"] for c in value["changes"]} == {"unchanged"}
    inserted = make_audit(tmp_path, "# Intro\nA novel method enables review.\n" + TEXT, previous=same)
    result = compare_runs(old, inserted, same_task=True)
    matches = [c for c in result["changes"] if c.get("match_method") == "unique_exact"]
    assert len(matches) == 2
    assert all(c["previous"][0]["text"] == c["current"][0]["text"] for c in matches)
    assert any(c["previous"][0]["claim_id"] != c["current"][0]["claim_id"] for c in matches)


def test_deleted_and_unextracted_claims_are_not_repaired(tmp_path, monkeypatch):
    import claim_harness.cli as cli
    old = make_audit(tmp_path)
    deleted = make_audit(tmp_path, "# Results\nThe model improves recall to 0.80.\n", previous=old)
    value = compare_runs(old, deleted, same_task=True)
    assert any(c["kind"] == "text_removed" for c in value["changes"])
    assert not any(c["resolved"] for c in value["changes"])
    extractor = cli.extract_claims
    monkeypatch.setattr(cli, "extract_claims", lambda *args: extractor(*args)[1:])
    missed = make_audit(tmp_path, previous=deleted)
    assert any(c["kind"] == "not_extracted" for c in compare_runs(old, missed, same_task=True)["changes"])


def test_negation_numeric_units_and_duplicate_context_stay_conservative(tmp_path):
    old = make_audit(tmp_path)
    new = make_audit(tmp_path, TEXT.replace("improves", "does not improve").replace("0.95", "95%"), previous=old)
    value = compare_runs(old, new, same_task=True)
    assert not any(c.get("match_method") == "unique_exact" for c in value["changes"])
    assert normalize("95 % not improved") != normalize("95% improved")
    assert normalize("a\n b") == normalize("a b")
    repeated = "# Repeated\n" + "The model achieves precision of 0.95.\n" * 4
    a = make_audit(tmp_path / "duplicates", repeated)
    b = make_audit(tmp_path / "duplicates", repeated, previous=a)
    report = compare_runs(a, b, same_task=True)
    assert any(c["kind"] == "correspondence_pending" for c in report["changes"])
    assert len([c for c in report["changes"] if c.get("match_method") == "unique_context"]) == 2


def test_explicit_rewrite_split_merge_and_bad_mappings(tmp_path):
    old = make_audit(tmp_path)
    new = make_audit(tmp_path, TEXT.replace("0.95", "0.85"), previous=old)
    value = compare_runs(old, new, same_task=True, mappings=[{"previous_ids": ["C001", "C002"], "current_ids": ["C001", "C002"], "reason": "User confirms reworded grouped finding"}])
    assert value["changes"][0]["kind"] == "split_or_merge"
    assert "text_modified" in value["changes"][0]["tags"]
    with pytest.raises(ValueError):
        compare_runs(old, new, same_task=True, mappings=[{"previous_ids": ["C999"], "current_ids": ["C001"], "reason": "x"}])


def test_cells_rules_and_missing_snapshot_are_separate(tmp_path):
    old = make_audit(tmp_path)
    new = make_audit(tmp_path, csv=CSV.replace(b"0.85", b"0.95"), previous=old)
    value = compare_runs(old, new, same_task=True)
    material = next(m for m in value["materials"] if m["source"] == "table:results.csv")
    assert material["cells"] == [{"row": 2, "column": 2, "previous": "0.85", "current": "0.95"}]
    assert material["affected_changes"]
    a, b = load_audit_run(old), load_audit_run(new)
    b.snapshot["rules"]["components"]["verifier.py"] = "changed-rule"
    assert compare_runs(a, b, same_task=True)["rules"]["state"] == "changed"
    limited = compare_runs(replace(a, snapshot=None), b, same_task=True)
    assert limited["comparability"] == "limited"
    assert not any(c["kind"] == "text_removed" for c in limited["changes"])


def test_incomplete_identity_and_same_task_requirements(tmp_path):
    a = make_audit(tmp_path)
    assert compare_runs(a, a)["comparability"] == "blocked"
    (a / "claim_table.csv").write_text("corrupt", encoding="utf-8")
    assert compare_runs(a, a, same_task=True)["comparability"] == "blocked"
    assert not compare_runs(a, a, same_task=True)["changes"]


def test_chinese_manual_span_and_human_actions_do_not_change_verdicts(tmp_path):
    body = TEXT + "这个结果还需要考虑不同设备之间的差异。\n"
    run = make_audit(tmp_path, body)
    before = snapshot_completed_run(run)
    start = body.index("这个")
    value = annotate(tmp_path, run, start=start, end=start + len("这个结果还需要考虑不同设备之间的差异。"), question="设备条件有哪些？")
    assert value["events"][-1]["payload"]["evaluation"] == "not_evaluated"
    assert value["events"][-1]["payload"]["text"] == "这个结果还需要考虑不同设备之间的差异。"
    manual_id = value["events"][-1]["payload"]["manual_id"]
    note = record_handling(tmp_path, run, claim_id=manual_id, layer="user_action", action="done", note="User says resolved", expected_revision=1)
    assert note["events"][-1]["payload"]["actor_verified"] is False
    record_handling(tmp_path, run, claim_id="C001", layer="human_review", action="request_review", note="Check table version", actor="Colleague", source="Pasted feedback on current draft", expected_revision=2)
    assert snapshot_completed_run(run) == before
    with pytest.raises(ValueError, match="Stale"):
        record_handling(tmp_path, run, claim_id="C001", layer="user_action", action="done", note="stale", expected_revision=1)
    rerun = make_audit(tmp_path, body, previous=run)
    linked = record_handling(tmp_path, run, claim_id="C001", layer="user_action", action="done", note="Added evidence", expected_revision=3, rerun=rerun, same_task=True)
    assert linked["events"][-1]["payload"]["rerun"]["changes"][0]["resolved"] is False


def test_journal_concurrent_stale_submission_and_integrity(tmp_path):
    journal = Journal(tmp_path, {"task": "synthetic"})
    def submit(i):
        try:
            journal.append("note", {"i": i}, expected_revision=0)
            return "saved"
        except ValueError:
            return "stale"
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(submit, [1, 2])) == ["saved", "stale"]
    saved = journal.read()
    saved["events"][0]["payload"]["i"] = "tampered"
    journal.path.write_text(json.dumps(saved), encoding="utf-8")
    with pytest.raises(ValueError, match="integrity"):
        journal.read()


def test_cli_exports_readable_and_machine_reports_and_legacy_limits(tmp_path):
    a = make_audit(tmp_path)
    b = make_audit(tmp_path, previous=a)
    out = tmp_path / "comparison"
    value = CliRunner().invoke(app, ["compare", "--previous", str(a), "--current", str(b), "--same-task", "--out", str(out), "--research-questions"])
    assert value.exit_code == 0, value.output
    files = snapshot_completed_run(out)
    assert {"audit_changes.json", "audit_changes.md", "pending_questions.md", "research_questions.md"} <= files.keys()
    legacy = tmp_path / "legacy"
    legacy.mkdir()
    for name in ("run_manifest.json", "evidence_map.json", "claim_table.csv"):
        (legacy / name).write_bytes((a / name).read_bytes())
    report = compare_runs(legacy, b, same_task=True)
    assert report["comparability"] == "limited"
    assert not any(c["kind"] == "text_removed" for c in report["changes"])
