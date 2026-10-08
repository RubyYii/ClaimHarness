"""Feedback is discussion input until the user explicitly confirms a new version."""
from __future__ import annotations

import json
import uuid
from functools import wraps
from pathlib import Path

from claim_harness.continuity_store import Journal
from .revision_governance import exclusive_file_lock
from .clarification import (ClarificationState, Interpretation, OpenIssue, answer_question,
                            choose_question, correct_answer, start_clarification)
from .workbench import FRAME_FIELDS, confirm_problem, load_problem


CATEGORIES = ("goal_meaning", "terminology", "missing_condition", "method_proposal", "new_goal")


def serialized(function):
    @wraps(function)
    def wrapped(root, project_id, current, *args, **kwargs):
        record = load_problem(root, current, project_id)
        journal = discussion_journal(root, record)
        journal._safe()
        journal.directory.mkdir(parents=True, exist_ok=True)
        with exclusive_file_lock(journal.path.with_suffix(".transaction.lock")):
            return function(root, project_id, current, *args, **kwargs)
    return wrapped


def discussion_journal(root: Path, record) -> Journal:
    return Journal(root, {"kind": "feedback_discussion", "project_id": record.project_id, "problem_id": record.problem_id})


def discussion(root: Path, record, current: Path | None = None) -> tuple[Journal, dict, dict | None]:
    journal = discussion_journal(root, record)
    history = journal.read()
    latest = history["events"][-1]["payload"] if history["events"] else None
    if latest and current is not None and latest["current_run"] != current.name:
        prior = load_problem(root, root / latest["current_run"], record.project_id)
        update = (record.continuation or {}).get("updates", [{}])[-1]
        recovered = (history["events"][-1]["kind"] == "confirmation_requested" and
                     update.get("confirmation_request_sha256") == history["events"][-1]["sha256"])
        if prior.framing_sha256 == record.framing_sha256 or recovered:
            # Audit/follow-up revisions do not change the confirmed meaning. A
            # committed confirmation can also recover after its final journal write failed.
            latest = {**latest, "current_run": current.name}
            if recovered:
                latest["last_confirmed_state_revision"] = latest["state"]["revision"]
    return journal, history, latest


def require_current(root: Path, record) -> None:
    """Reject a form based on an older confirmed version, including another tab."""
    if not root.exists():
        return
    for path in root.iterdir():
        candidate = path / "problem_record.json"
        if not candidate.is_file():
            continue
        raw = json.loads(candidate.read_text(encoding="utf-8"))
        if (raw.get("project_id"), raw.get("problem_id")) == (record.project_id, record.problem_id) and raw.get("revision", 0) > record.revision:
            # Incomplete runs are not newer confirmed state.
            try:
                newer = load_problem(root, path, record.project_id)
            except (ValueError, RuntimeError, OSError):
                continue
            if newer.revision > record.revision:
                raise ValueError("Stale page: a newer confirmed version exists. Open it before continuing.")


def _active(root: Path, current: Path, project_id: str, expected_revision: int):
    record = load_problem(root, current, project_id)
    require_current(root, record)
    journal, history, data = discussion(root, record, current)
    if history["revision"] != expected_revision:
        raise ValueError("Stale page: newer discussion changes exist. Reload before submitting.")
    if data and data["current_run"] != current.name:
        raise ValueError("Discussion is attached to another confirmed version; start a new discussion round.")
    return record, journal, data


@serialized
def add_feedback(root: Path, project_id: str, current: Path, *, target: Path | None, sender: str,
                 sender_kind: str, original: str, selected: str, interpretation: str, category: str,
                 question: str, alternatives: list[str] | None = None, consequence: str = "",
                 budget: int = 5, expected_revision: int = 0) -> dict:
    record = load_problem(root, current, project_id)
    require_current(root, record)
    journal, history, data = discussion(root, record, current)
    if history["revision"] != expected_revision:
        raise ValueError("Stale page: newer discussion changes exist. Reload before submitting.")
    if category not in CATEGORIES or sender_kind not in {"collaborator", "ai", "user"}:
        raise ValueError("Choose a feedback category and sender type.")
    if not sender.strip() or not original.strip() or not selected.strip() or selected not in original or not question.strip():
        raise ValueError("Record a sender, verbatim feedback, an exact selected excerpt and a question.")
    if max(len(original), len(interpretation), len(consequence)) > 20000:
        raise ValueError("Feedback fields must be at most 20,000 characters.")
    target_record = load_problem(root, target, project_id) if target else None
    if target_record and target_record.problem_id != record.problem_id:
        raise ValueError("Feedback target belongs to another problem.")
    if data is None or data["current_run"] != current.name:
        # A new user-confirmed goal may start a fresh discussion. Earlier rounds remain in the journal.
        data = {"current_run": current.name, "base_run": current.name, "feedback": [],
                "state": start_clarification(record, [], budget=budget).model_dump(mode="json"),
                "dispositions": {}, "last_confirmed_state_revision": -1}
    state = ClarificationState.model_validate(data["state"])
    issue_id = "feedback-" + uuid.uuid4().hex[:12]
    options = tuple(Interpretation(interpretation_id=f"option-{i + 1}", instruction=s.strip()) for i, s in enumerate(alternatives or []) if s.strip())
    issue = OpenIssue(issue_id=issue_id, description=interpretation.strip() or selected,
                      question=question.strip(), alternatives=options,
                      origin={"ai": "model_proposal", "collaborator": "collaborator_proposal", "user": "author_proposal"}[sender_kind])
    state = ClarificationState.model_validate({**state.model_dump(), "issues": (*state.issues, issue)})
    item = {"feedback_id": issue_id, "sender": sender.strip(), "sender_kind": sender_kind,
            "original": original, "selected": selected, "selected_start": original.index(selected),
            "interpretation": interpretation, "category": category, "consequence": consequence,
            "target": {"run_name": target.name, "revision": target_record.revision, "framing_sha256": target_record.framing_sha256} if target else None,
            "received_against_revision": record.revision, "status": "proposal_not_adopted"}
    data = {**data, "feedback": [*data["feedback"], item], "state": state.model_dump(mode="json")}
    return journal.append("feedback_added", data, expected_revision=expected_revision)


@serialized
def respond(root: Path, project_id: str, current: Path, *, issue_id: str, mode: str,
            answer: str = "", interpretation_id: str | None = None, reason: str = "",
            expected_revision: int) -> dict:
    _, journal, data = _active(root, current, project_id, expected_revision)
    if data is None:
        raise ValueError("There is no active discussion.")
    state = ClarificationState.model_validate(data["state"])
    if issue_id not in {i.issue_id for i in state.issues}:
        raise ValueError("Unknown discussion issue.")
    dispositions = dict(data["dispositions"])
    if mode in {"unknown", "defer"}:
        if issue_id in {r.issue_id for r in state.resolutions}:
            raise ValueError("An existing answer needs an explicit correction before deferral.")
        dispositions[issue_id] = {"status": mode, "note": answer}
    elif mode == "correct":
        state = correct_answer(state, issue_id, answer, reason=reason, expected_revision=state.revision, interpretation_id=interpretation_id)
        dispositions.pop(issue_id, None)
    elif mode in {"answer", "none_accurate"}:
        decision = choose_question(state, [], policy="generic", generic_issue_id=issue_id)
        state = answer_question(state, decision, answer, expected_revision=state.revision,
                                interpretation_id=None if mode == "none_accurate" else interpretation_id)
        dispositions.pop(issue_id, None)
    else:
        raise ValueError("Unknown discussion action.")
    return journal.append("discussion_response", {**data, "state": state.model_dump(mode="json"),
                          "dispositions": dispositions}, expected_revision=expected_revision)


@serialized
def confirm_discussion(root: Path, project_id: str, current: Path, *, kind: str, reason: str,
                       next_action: str, fields: dict[str, str] | None = None, expected_revision: int) -> Path:
    record, journal, data = _active(root, current, project_id, expected_revision)
    if data is None or kind not in {"supplement", "correction", "goal_change"} or not reason.strip() or not next_action.strip():
        raise ValueError("Choose the update type, its reason and the recipient's next action.")
    state = ClarificationState.model_validate(data["state"])
    updated = {key: getattr(record, key) for key in FRAME_FIELDS}
    if kind == "goal_change":
        if not fields or not fields.get("question", "").strip():
            raise ValueError("Write the new goal explicitly.")
        if any(k not in FRAME_FIELDS for k in fields):
            raise ValueError("Unknown goal field.")
        updated.update({k: v.strip() for k, v in fields.items()})
        if updated == {key: getattr(record, key) for key in FRAME_FIELDS}:
            raise ValueError("A goal change must change the confirmed wording.")
    elif fields:
        raise ValueError("Supplement/correction does not replace the goal; use goal_change explicitly.")
    if kind == "correction" and not any(e.kind == "correction" and e.revision > data["last_confirmed_state_revision"] for e in state.events):
        raise ValueError("First record the corrected answer and its reason.")
    before = {key: getattr(record, key) for key in FRAME_FIELDS}
    open_issues = [{"issue_id": i.issue_id, "question": i.question,
                    "disposition": data["dispositions"].get(i.issue_id, {"status": "unanswered"})}
                   for i in state.issues if i.issue_id not in {r.issue_id for r in state.resolutions}]
    update = {"kind": kind, "from_revision": record.revision, "to_revision": record.revision + 1,
              "reason": reason.strip(), "next_action": next_action.strip(), "decision": "user_confirmed",
              "before": before, "after": updated, "feedback": data["feedback"],
              "answers": [r.model_dump(mode="json") for r in state.resolutions],
              "answer_history": [e.model_dump(mode="json") for e in state.events], "open_questions": open_issues,
              "audit_effect": "Earlier audits remain historical; current requirements need their own check."}
    history = list((record.continuation or {}).get("updates", []))
    continuation = {"schema_version": 1, "updates": [*history, update]}
    # Reserve the displayed discussion revision before making the immutable version.
    # Concurrent submissions cannot both pass; a failed confirmation remains a visible attempt.
    reserved = journal.append("confirmation_requested", data, expected_revision=expected_revision)
    update["confirmation_request_sha256"] = reserved["events"][-1]["sha256"]
    try:
        out = confirm_problem(root, project_id, updated, previous=current, continuation=continuation)
    except (OSError, ValueError, RuntimeError):
        journal.append("confirmation_failed", data, expected_revision=reserved["revision"])
        raise ValueError("Confirmation failed. Discussion was preserved; reload it before retrying.") from None
    journal.append("version_confirmed", {**data, "current_run": out.name,
                   "last_confirmed_state_revision": state.revision}, expected_revision=reserved["revision"])
    return out


@serialized
def start_next_round(root: Path, project_id: str, current: Path, *, budget: int, expected_revision: int) -> dict:
    record, journal, data = _active(root, current, project_id, expected_revision)
    if not data:
        raise ValueError("Record feedback before starting a further round.")
    state = ClarificationState.model_validate(data["state"])
    if state.revision != data["last_confirmed_state_revision"]:
        raise ValueError("Confirm the recorded answers before starting the next round.")
    answered = {r.issue_id for r in state.resolutions}
    unresolved = [i for i in state.issues if i.issue_id not in answered]
    next_state = start_clarification(record, unresolved, budget=budget)
    remaining = {i.issue_id for i in unresolved}
    return journal.append("next_round", {**data, "base_run": current.name,
        "state": next_state.model_dump(mode="json"), "feedback": [f for f in data["feedback"] if f["feedback_id"] in remaining],
        "dispositions": {k: v for k, v in data["dispositions"].items() if k in remaining},
        "last_confirmed_state_revision": -1}, expected_revision=expected_revision)
