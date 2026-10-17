"""Local, attributed two-person handoffs; role labels are not authentication.

Replies and reviews stay in an append-only journal. Only A's explicit response
creates a new immutable need version. Agreement and sample checks remain separate.
"""
from __future__ import annotations

import json
import uuid
from pathlib import Path

from claim_harness.continuity_store import Journal
from .feedback import require_current, serialized
from .project_lifecycle import is_link_or_reparse
from .requirements import _artifact, record_check
from .workbench import FRAME_FIELDS, confirm_problem, load_problem


STATUSES = ("ready", "partial", "discuss")


def handoff_journal(root, record):
    return Journal(root, {"kind": "dyad_handoff", "project_id": record.project_id,
                          "problem_id": record.problem_id})


def _target(current, record):
    return {"run_name": current.name, "revision": record.revision,
            "framing_sha256": record.framing_sha256}


def _text(value, label, *, optional=False, limit=8000):
    if not isinstance(value, str) or len(value) > limit or (not optional and not value.strip()):
        raise ValueError(f"{label}: enter {'0' if optional else '1'}–{limit} characters.")
    return value.strip()


def _active(root, project_id, current, expected_revision):
    record = load_problem(root, current, project_id)
    require_current(root, record)
    journal = handoff_journal(root, record)
    history = journal.read()
    if history["revision"] != expected_revision:
        raise ValueError("Stale handoff: reload the saved discussion before submitting.")
    return record, journal, history


def handoff_state(root: Path, current: Path, record) -> dict:
    history = handoff_journal(root, record).read()
    target = _target(current, record)
    replies = [e["payload"] for e in history["events"] if e["kind"] == "recipient_reply"]
    reply = replies[-1] if replies else None
    updates = (record.continuation or {}).get("updates", [])
    response = next((u for u in reversed(updates)
                     if reply and u.get("dyad", {}).get("reply_id") == reply["reply_id"]), None)
    acknowledgements = {}
    # This also recovers a committed response whose final journal append failed.
    if response and response["to_revision"] == record.revision:
        acknowledgements["A"] = {"actor": response["dyad"]["actor"], "role": "A",
            "status": response["dyad"]["status"], "note": response["reason"], "target": target}
    for event in history["events"]:
        item = event["payload"]
        if (event["kind"] == "acknowledgement" and item["target"] == target
                and reply and response and item["reply_id"] == reply["reply_id"]):
            acknowledgements[item["role"]] = item
    drafts = {e["payload"]["role"]: e["payload"]["values"] for e in history["events"]
              if e["kind"] == "draft_saved" and e["payload"]["target"] == target}
    samples = [e["payload"] for e in history["events"]
               if e["kind"] == "sample_saved" and e["payload"]["target"] == target]
    pending = bool(reply and not response and reply["target"] == target)
    return {"history": history, "target": target, "reply": reply, "response": response,
            "pending": pending, "acknowledgements": acknowledgements, "drafts": drafts,
            "samples": samples, "both_ready": all(acknowledgements.get(r, {}).get("status") == "ready" for r in ("A", "B"))}


@serialized
def save_draft(root, project_id, current, *, role, values, expected_revision):
    record, journal, _ = _active(root, project_id, current, expected_revision)
    if role not in ("A", "B") or not isinstance(values, dict) or len(values) > 20:
        raise ValueError("Choose A or B and a bounded text draft.")
    for key, value in values.items():
        _text(key, "Draft field", limit=100)
        _text(value, key, optional=True, limit=20000)
    return journal.append("draft_saved", {"role": role, "target": _target(current, record),
                          "values": values}, expected_revision=expected_revision)


@serialized
def recipient_reply(root, project_id, current, *, actor, understanding, proposal="", questions="", expected_revision):
    record, journal, _ = _active(root, project_id, current, expected_revision)
    if handoff_state(root, current, record)["pending"]:
        raise ValueError("A reply is waiting for A. Review it before starting another round.")
    payload = {"reply_id": "reply-" + uuid.uuid4().hex[:12], "role": "B",
        "actor": _text(actor, "B's name", limit=500), "target": _target(current, record),
        "understanding": _text(understanding, "My understanding"),
        "proposal": _text(proposal, "Approach and limits", optional=True),
        "questions": _text(questions, "Open questions", optional=True),
        "authority": "collaborator_proposal_not_adopted"}
    return journal.append("recipient_reply", payload, expected_revision=expected_revision)


@serialized
def confirm_response(root, project_id, current, *, reply_id, actor, answer, reason,
                     next_action, remaining="", no_open_questions=False, status="ready",
                     fields=None, expected_revision):
    record, journal, history = _active(root, project_id, current, expected_revision)
    state = handoff_state(root, current, record)
    reply = state["reply"]
    if not state["pending"] or reply["reply_id"] != reply_id:
        raise ValueError("Review the latest pending B reply before responding.")
    actor = _text(actor, "A's name", limit=500)
    answer, reason = _text(answer, "A's response"), _text(reason, "Reason")
    next_action = _text(next_action, "Next action")
    remaining = _text(remaining, "Unresolved points", optional=True)
    if not remaining and not no_open_questions:
        raise ValueError("Keep unresolved points, or explicitly confirm none remain in this round.")
    if status not in STATUSES or (status != "ready" and not remaining):
        raise ValueError("A partial/discussion response must describe what remains unresolved.")
    before = {k: getattr(record, k) for k in FRAME_FIELDS}
    after = dict(before)
    if fields is not None:
        if not isinstance(fields, dict) or any(k not in FRAME_FIELDS for k in fields):
            raise ValueError("Unknown need field.")
        after.update({k: _text(v, k, optional=k != "question", limit=20000) for k, v in fields.items()})
    original = json.dumps({k: reply[k] for k in ("understanding", "proposal", "questions")}, ensure_ascii=False, indent=2)
    previous_updates = list((record.continuation or {}).get("updates", []))
    update = {"kind": "goal_change" if before != after else "supplement",
        "from_revision": record.revision, "to_revision": record.revision + 1,
        "reason": reason, "next_action": next_action, "decision": "user_confirmed",
        "before": before, "after": after,
        "feedback": [{"feedback_id": reply_id, "sender": reply["actor"], "sender_kind": "collaborator",
                      "target": reply["target"], "original": original, "selected": original}],
        "answers": [{"issue_id": reply_id, "answer": answer, "interpretation_id": None}],
        "answer_history": [],
        "open_questions": [{"issue_id": f"{reply_id}-open-{i + 1}", "question": line.strip(),
                            "disposition": {"status": "unresolved"}}
                           for i, line in enumerate(remaining.splitlines()) if line.strip()],
        "audit_effect": "Earlier checks remain historical. Check this version's requirements separately.",
        "dyad": {"reply_id": reply_id, "actor": actor, "role": "A", "status": status,
                 "no_open_questions_explicit": bool(no_open_questions and not remaining)}}
    reserved = journal.append("response_requested", {"reply_id": reply_id, "target": state["target"]},
                              expected_revision=history["revision"])
    update["dyad"]["request_sha256"] = reserved["events"][-1]["sha256"]
    try:
        out = confirm_problem(root, project_id, after, previous=current,
            continuation={"schema_version": 1, "updates": [*previous_updates, update]})
    except (OSError, ValueError, RuntimeError):
        journal.append("response_failed", {"reply_id": reply_id, "target": state["target"]},
                       expected_revision=reserved["revision"])
        raise ValueError("Response not confirmed. Your saved discussion remains; reload before retrying.") from None
    # The immutable version is authoritative if this supplementary receipt fails.
    try:
        journal.append("response_confirmed", {"reply_id": reply_id, "run_name": out.name},
                       expected_revision=reserved["revision"])
    except OSError:
        pass
    return out


@serialized
def acknowledge(root, project_id, current, *, role, actor, status, note="", expected_revision):
    record, journal, _ = _active(root, project_id, current, expected_revision)
    state = handoff_state(root, current, record)
    if role not in ("A", "B") or status not in STATUSES:
        raise ValueError("Choose A/B and a review status.")
    if state["pending"] or not state["response"]:
        raise ValueError("A must respond before this working version can be reviewed.")
    payload = {"role": role, "actor": _text(actor, "Reviewer", limit=500), "status": status,
               "note": _text(note, "Review note", optional=status == "ready"),
               "target": state["target"], "reply_id": state["reply"]["reply_id"]}
    return journal.append("acknowledgement", payload, expected_revision=expected_revision)


@serialized
def save_sample(root, project_id, current, *, actor, title, content, expected_revision):
    record, journal, _ = _active(root, project_id, current, expected_revision)
    actor, title = _text(actor, "Contributor", limit=500), _text(title, "Sample title", limit=500)
    if not isinstance(content, str) or not content.strip() or len(content.encode("utf-8")) > 2 * 1024 * 1024:
        raise ValueError("Paste a non-empty text sample of at most 2 MB.")
    directory = root.absolute() / "handoff_samples" / record.problem_id
    for part in (directory, *directory.parents):
        if (part.exists() or part.is_symlink()) and is_link_or_reparse(part):
            raise ValueError("Linked sample directories are not allowed.")
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / ("sample-" + uuid.uuid4().hex + ".txt")
    with path.open("x", encoding="utf-8", newline="") as stream:
        stream.write(content)
    evidence = _artifact(root, path.relative_to(root.absolute()).as_posix())
    return journal.append("sample_saved", {"role": "B", "actor": actor, "title": title,
        "target": _target(current, record), "evidence": evidence}, expected_revision=expected_revision)


def read_sample(root, sample):
    actual = _artifact(root, sample["evidence"]["path"])
    if actual["sha256"] != sample["evidence"]["sha256"]:
        raise ValueError("This saved sample has changed; its earlier checks no longer apply.")
    return (root / actual["path"]).read_text(encoding="utf-8")


@serialized
def check_sample(root, project_id, current, *, sample_path, requirement_id, role, actor,
                 result, method, note, location, expected_revision, expected_handoff_revision):
    record, _, _ = _active(root, project_id, current, expected_handoff_revision)
    if role not in ("A", "B"):
        raise ValueError("Choose the person recording the check.")
    sample = next((s for s in handoff_state(root, current, record)["samples"]
                   if s["evidence"]["path"] == sample_path), None)
    if sample is None:
        raise ValueError("Select a sample saved against this exact need version.")
    read_sample(root, sample)
    return record_check(root, project_id, current, requirement_id=requirement_id, result=result,
        actor=f"{role} · {_text(actor, 'Reviewer', limit=500)}", method=method, note=note,
        artifact=sample_path, location=location, expected_revision=expected_revision)
