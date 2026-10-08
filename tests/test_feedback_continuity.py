"""PB-01–06 feedback ownership, clarification persistence and version boundaries."""
import pytest

from problem_bridge.clarification import (ClarificationState, OpenIssue, Preview, assess_impacts, choose_question,
                                         start_clarification)
from problem_bridge.feedback import add_feedback, confirm_discussion, discussion, respond
from problem_bridge.handoff import build_handoffs, build_research_input
from problem_bridge.project_lifecycle import snapshot_completed_run
from problem_bridge.workbench import confirm_problem, load_problem


def setup(tmp_path):
    root = tmp_path / "runs"
    current = confirm_problem(root, "feedback-test", {"question": "我想解释差异，不想预测。"})
    return root, current


def add(root, current, *, target=None, revision=0, category="terminology", budget=5):
    return add_feedback(root, "feedback-test", current, target=target or current, sender="AI helper", sender_kind="ai",
                        original="建议增加一个预测模型。也请解释平均值的口径。", selected="解释平均值的口径",
                        interpretation="我只想讨论平均口径", category=category, question="平均值在这里指什么？",
                        expected_revision=revision, budget=budget)


def test_feedback_preserves_original_and_does_not_adopt_ai_goal(tmp_path):
    root, current = setup(tmp_path)
    old = snapshot_completed_run(current)
    value = add(root, current)
    item = value["events"][-1]["payload"]["feedback"][0]
    assert item["original"].startswith("建议增加一个预测模型")
    assert item["status"] == "proposal_not_adopted"
    assert item["sender_kind"] == "ai"
    assert snapshot_completed_run(current) == old
    assert load_problem(root, current, "feedback-test").question == "我想解释差异，不想预测。"


def test_open_question_unknown_defer_answer_correction_and_reopen(tmp_path):
    root, current = setup(tmp_path)
    value = add(root, current)
    issue = value["events"][-1]["payload"]["feedback"][0]["feedback_id"]
    record = load_problem(root, current, "feedback-test")
    _, history, data = discussion(root, record)
    state = ClarificationState.model_validate(data["state"])
    assert state.issues[0].alternatives == ()
    assert choose_question(state, []).action == "ask"
    respond(root, "feedback-test", current, issue_id=issue, mode="unknown", expected_revision=1)
    respond(root, "feedback-test", current, issue_id=issue, mode="defer", expected_revision=2)
    respond(root, "feedback-test", current, issue_id=issue, mode="none_accurate", answer="先按设备平均", expected_revision=3)
    respond(root, "feedback-test", current, issue_id=issue, mode="correct", answer="先按观测平均", reason="纠正刚才口径", expected_revision=4)
    data = discussion(root, record)[2]
    assert data["state"]["events"][-1]["previous_answer"] == "先按设备平均"
    assert data["state"]["resolutions"][0]["interpretation_id"] is None
    with pytest.raises(ValueError, match="Stale"):
        respond(root, "feedback-test", current, issue_id=issue, mode="correct", answer="旧页面", reason="old", expected_revision=1)


def test_confirmed_update_and_goal_change_keep_full_history_and_handoffs(tmp_path):
    root, current = setup(tmp_path)
    before = snapshot_completed_run(current)
    value = add(root, current, category="new_goal")
    issue = value["events"][-1]["payload"]["feedback"][0]["feedback_id"]
    respond(root, "feedback-test", current, issue_id=issue, mode="answer", answer="先保持解释目标", expected_revision=1)
    new = confirm_discussion(root, "feedback-test", current, kind="supplement", reason="明确口径", next_action="请对方确认理解", expected_revision=2)
    record = load_problem(root, new, "feedback-test")
    assert record.question == load_problem(root, current, "feedback-test").question
    assert record.schema_version == 3
    assert snapshot_completed_run(current) == before
    for content in build_handoffs(record).values():
        assert "先保持解释目标" in content and "请对方确认理解" in content
    assert record.framing_sha256 in build_research_input(record)
    # Feedback can explicitly refer to an old version without replacing the current version.
    result = add(root, new, target=current, revision=4)
    assert result["events"][-1]["payload"]["feedback"][-1]["target"]["revision"] == 1
    changed = confirm_discussion(root, "feedback-test", new, kind="goal_change", reason="用户决定试一个新方向",
                                 next_action="只做合成样例", fields={"question": "我决定研究预测"}, expected_revision=5)
    revised = load_problem(root, changed, "feedback-test")
    assert revised.question == "我决定研究预测" and revised.audit is None
    assert revised.continuation["updates"][-1]["open_questions"]
    with pytest.raises(ValueError, match="Stale"):
        add(root, new, revision=7)


def test_budget_retains_questions_and_examples_are_not_execution_differences(tmp_path):
    root, current = setup(tmp_path)
    first = add(root, current, budget=1)
    first_id = first["events"][-1]["payload"]["feedback"][0]["feedback_id"]
    add(root, current, revision=1)
    respond(root, "feedback-test", current, issue_id=first_id, mode="answer", answer="一个回答", expected_revision=2)
    record = load_problem(root, current, "feedback-test")
    state = ClarificationState.model_validate(discussion(root, record)[2]["state"])
    assert choose_question(state, []).action == "budget_exhausted"
    from problem_bridge.clarification import Interpretation
    state = start_clarification(record, [OpenIssue(issue_id="x", description="compare", question="which?",
        alternatives=(Interpretation(interpretation_id="a", instruction="A"), Interpretation(interpretation_id="b", instruction="B")))])
    example = [Preview(issue_id="x", interpretation_id=i, case_id="toy", status="executed", kind="example", outcome=n,
                       known_requirements_passed=True) for i, n in [("a", 1), ("b", 99)]]
    assert assess_impacts(state, example)[0].compared_pairs == 0
    assert assess_impacts(state, example)[0].status == "incomplete_preview"
    equal = [p.model_copy(update={"kind": "execution", "outcome": 1}) for p in example]
    assert assess_impacts(state, equal)[0].status == "no_observed_difference"
    assert choose_question(state, equal).action == "ask"


def test_confirmation_failure_is_recorded_and_retry_keeps_discussion(tmp_path, monkeypatch):
    import problem_bridge.feedback as module
    root, current = setup(tmp_path)
    add(root, current)
    real = module.confirm_problem
    monkeypatch.setattr(module, "confirm_problem", lambda *a, **k: (_ for _ in ()).throw(OSError("test failure")))
    with pytest.raises(ValueError, match="preserved"):
        confirm_discussion(root, "feedback-test", current, kind="supplement", reason="explain", next_action="clarify", expected_revision=1)
    record = load_problem(root, current, "feedback-test")
    assert discussion(root, record)[1]["events"][-1]["kind"] == "confirmation_failed"
    monkeypatch.setattr(module, "confirm_problem", real)
    newer = confirm_discussion(root, "feedback-test", current, kind="supplement", reason="explain", next_action="clarify", expected_revision=3)
    assert load_problem(root, newer, "feedback-test").revision == 2


def test_auditing_same_framing_keeps_discussion_and_next_round_retains_unknowns(tmp_path):
    from problem_bridge.workbench import audit_problem
    from problem_bridge.feedback import start_next_round
    root, current = setup(tmp_path)
    history = add(root, current, budget=1)
    first = history["events"][-1]["payload"]["feedback"][0]["feedback_id"]
    add(root, current, revision=1)
    respond(root, "feedback-test", current, issue_id=first, mode="answer", answer="Known answer", expected_revision=2)
    newer = confirm_discussion(root, "feedback-test", current, kind="supplement", reason="preserve unknowns", next_action="clarify remaining question", expected_revision=3)
    audited = audit_problem(root, "feedback-test", newer, manuscript="# Results\nThe model achieves precision of 0.85.", tables={"scores.csv": b"model,precision\nmodel,0.85\n"})
    record = load_problem(root, audited, "feedback-test")
    assert discussion(root, record, audited)[2]["current_run"] == audited.name
    result = start_next_round(root, "feedback-test", audited, budget=2, expected_revision=5)
    state = ClarificationState.model_validate(result["events"][-1]["payload"]["state"])
    assert len(state.issues) == 1 and not state.resolutions and state.turns_used == 0
    assert state.issues[0].issue_id != first
