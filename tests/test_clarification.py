"""Meaningful invariants for selecting information and preserving task revisions."""
import json
from pathlib import Path

import pytest
from pydantic import ValidationError
from typer.testing import CliRunner

from problem_bridge.clarification import (ClarificationState, Interpretation, OpenIssue, Preview,
    answer_question, assess_impacts, choose_question, commit_clarification, correct_answer,
    render_clarification, start_clarification)
from problem_bridge.clarification_demo import ANSWERS, check_known_requirements, make_record, public_data, run_demo, scripted_issue, summarize
from problem_bridge.cli import app
from problem_bridge.project_lifecycle import snapshot_completed_run
from problem_bridge.workbench import FRAME_FIELDS, confirm_problem, load_problem


def setup_state(tmp_path, *, budget=1, extra=False):
    root = tmp_path / "runs"
    original = make_record(root, "test-clarification")
    record = load_problem(root, original, "test-clarification")
    issues = [scripted_issue()]
    if extra:
        issues.insert(0, OpenIssue(issue_id="other", description="Unresolved presentation preference", question="Short or detailed notes?",
            alternatives=(Interpretation(interpretation_id="short", instruction="Brief note."), Interpretation(interpretation_id="long", instruction="Detailed note."))))
    return root, original, record, start_clarification(record, issues, budget=budget)


def evidence(issue, outputs, *, passed=True):
    return [Preview(issue_id=issue.issue_id, interpretation_id=a.interpretation_id, case_id="same-public-case",
        status="executed", outcome=value, known_requirements_passed=passed) for a, value in zip(issue.alternatives, outputs)]


def test_real_public_executions_reveal_weighting_but_keep_missingness(tmp_path):
    _, _, _, state = setup_state(tmp_path)
    data = public_data()
    outputs = [summarize(data, p) for p in ANSWERS]
    assert outputs[0][0]["mean"] == 18 and outputs[1][0]["mean"] == 22
    assert outputs[0][2]["mean"] == 13.33 and outputs[1][2]["mean"] == 11
    assert all(check_known_requirements(data, x) for x in outputs)
    assert all(row["mean"] is None for result in outputs for row in result if row["site"] == "West")
    decision = choose_question(state, evidence(state.issues[0], outputs))
    assert decision.issue_id == "averaging_unit" and decision.assessments[0].status == "observed_difference"


def test_impact_prefers_witness_over_first_issue_but_equal_previews_remain_open(tmp_path):
    _, _, _, state = setup_state(tmp_path, extra=True)
    previews = evidence(state.issues[0], [[1.0], [1]]) + evidence(state.issues[1], [[18], [22]])
    decision = choose_question(state, previews)
    assert decision.issue_id == "averaging_unit"
    assert decision.assessments[0].status == "no_observed_difference"
    answered = answer_question(state, decision, ANSWERS["sensors"], expected_revision=0)
    assert choose_question(answered, previews).action == "budget_exhausted"
    assert "UNRESOLVED" in render_clarification(answered)
    assert "other" not in {r.issue_id for r in answered.resolutions}


def test_failed_or_incomplete_preview_is_unknown_not_irrelevant(tmp_path):
    _, _, _, state = setup_state(tmp_path)
    values = evidence(state.issues[0], [[1], [2]], passed=False)
    assert assess_impacts(state, values)[0].status == "incomplete_preview"
    assert choose_question(state, []).action == "ask"
    assert choose_question(state, []).assessments[0].compared_pairs == 0


def test_preview_identity_duplicates_nonfinite_and_unknown_options_rejected(tmp_path):
    _, _, _, state = setup_state(tmp_path)
    preview = evidence(state.issues[0], [[1], [2]])
    with pytest.raises(ValueError, match="Duplicate"):
        choose_question(state, preview + preview[:1])
    with pytest.raises(ValueError, match="unknown"):
        choose_question(state, [preview[0].model_copy(update={"issue_id": "invented"})])
    with pytest.raises((ValueError, ValidationError)):
        Preview(issue_id="x", interpretation_id="a", case_id="c", status="executed", outcome=float("nan"))


def test_zero_budget_and_no_issues_do_not_invent_answers(tmp_path):
    _, _, record, state = setup_state(tmp_path, budget=0)
    assert choose_question(state, []).action == "budget_exhausted"
    empty = start_clarification(record, [], budget=1)
    assert choose_question(empty, []).action == "ready"
    assert "No issues were proposed" in render_clarification(empty)
    with pytest.raises(ValidationError):
        start_clarification(record, [scripted_issue()], budget=-1)


def test_generic_selection_uses_same_candidates_without_impact_ranking(tmp_path):
    _, _, _, state = setup_state(tmp_path, extra=True)
    result = choose_question(state, [], policy="generic", generic_issue_id="other")
    assert result.issue_id == "other" and not result.assessments
    with pytest.raises(ValueError):
        choose_question(state, [], policy="generic", generic_issue_id="unknown")


def test_answer_updates_one_issue_rejects_stale_question_and_preserves_old_state(tmp_path):
    _, _, _, state = setup_state(tmp_path, extra=True)
    before = state.model_dump(mode="json")
    decision = choose_question(state, [], policy="generic", generic_issue_id="averaging_unit")
    result = answer_question(state, decision, ANSWERS["sensors"], expected_revision=0, interpretation_id="sensors")
    assert state.model_dump(mode="json") == before
    assert result.issues == state.issues and result.resolutions[0].issue_id == "averaging_unit"
    with pytest.raises(ValueError, match="Stale"):
        answer_question(result, decision, "another", expected_revision=0)
    with pytest.raises(ValueError, match="stale"):
        answer_question(result, decision, "another", expected_revision=1)
    with pytest.raises(ValueError, match="Unknown interpretation"):
        answer_question(state, decision, "invented", expected_revision=0, interpretation_id="other")


def test_history_forgery_and_cross_task_question_are_rejected(tmp_path):
    _, _, _, state = setup_state(tmp_path)
    decision = choose_question(state, [])
    other = state.model_copy(update={"project_id": "another-project"})
    with pytest.raises(ValueError, match="different"):
        answer_question(other, decision, "answer", expected_revision=0)
    result = answer_question(state, decision, ANSWERS["sensors"], expected_revision=0)
    forged = result.model_dump()
    forged["events"][0]["answer"] = "changed history"
    with pytest.raises(ValueError, match="history"):
        ClarificationState.model_validate(forged)


def test_committed_reply_and_explicit_correction_preserve_original_requirements(tmp_path):
    root, original, record, state = setup_state(tmp_path)
    old_files = snapshot_completed_run(original)
    decision = choose_question(state, [])
    answered = answer_question(state, decision, ANSWERS["sensors"], expected_revision=0, interpretation_id="sensors")
    second = commit_clarification(root, original, answered)
    second_files = snapshot_completed_run(second)
    corrected = correct_answer(answered, "averaging_unit", ANSWERS["observations"], reason="User changes weighting.", expected_revision=1)
    third = commit_clarification(root, second, corrected, original=original, previous_state=answered)
    final = load_problem(root, third, state.project_id)
    assert final.revision == 3 and final.previous.run_name == second.name
    assert all(getattr(final, k) == getattr(record, k) for k in FRAME_FIELDS)
    assert final.brief.concepts == record.brief.concepts and final.brief.materials == record.brief.materials
    assert final.brief.success_check.startswith(record.brief.success_check)
    assert ANSWERS["observations"] in final.brief.success_check and ANSWERS["sensors"] not in final.brief.success_check
    assert corrected.turns_used == 1 and corrected.events[-1].previous_answer == ANSWERS["sensors"]
    assert snapshot_completed_run(original) == old_files and snapshot_completed_run(second) == second_files
    with pytest.raises(ValueError):
        correct_answer(answered, "averaging_unit", "new", reason="", expected_revision=1)


def test_export_refuses_rebase_over_unrelated_user_edit(tmp_path):
    root, original, record, state = setup_state(tmp_path)
    answered = answer_question(state, choose_question(state, []), ANSWERS["sensors"], expected_revision=0)
    second = commit_clarification(root, original, answered)
    fields = {k: getattr(record, k) for k in FRAME_FIELDS}
    fields["question"] = "An explicitly different task"
    changed = confirm_problem(root, state.project_id, fields, previous=second)
    corrected = correct_answer(answered, "averaging_unit", ANSWERS["observations"], reason="Changed weighting", expected_revision=1)
    with pytest.raises(ValueError, match="outside"):
        commit_clarification(root, changed, corrected, original=original, previous_state=answered)


def test_cli_demo_runs_without_models_and_refuses_to_overwrite(tmp_path):
    out = tmp_path / "demo"
    runner = CliRunner()
    result = runner.invoke(app, ["clarify-demo", "--out", str(out), "--answer", "sensors", "--correct-to", "observations"])
    assert result.exit_code == 0, result.output
    verification = json.loads((out / "verification.json").read_text(encoding="utf-8"))
    assert verification["model_calls"] == 0 and verification["problem_revisions"] == 3
    assert verification["known_requirements_passed"]
    assert (out / "result.csv").read_text().splitlines()[1].endswith(",18.0")
    manifest = (out / "demo_manifest.json").read_bytes()
    assert runner.invoke(app, ["clarify-demo", "--out", str(out)]).exit_code != 0
    assert (out / "demo_manifest.json").read_bytes() == manifest
