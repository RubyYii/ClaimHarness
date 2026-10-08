"""Clarification decisions grounded in public execution previews, with bounded updates.

The module makes no model calls and never accepts hidden acceptance answers.
Preview equality is finite evidence, not a proof that a requirement is irrelevant.
"""
from __future__ import annotations

import hashlib
import json
import math
from itertools import combinations
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .handoff import NeedBrief
from .workbench import FRAME_FIELDS, ProblemRecord, confirm_problem, load_problem


class FrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Interpretation(FrozenModel):
    interpretation_id: str = Field(min_length=1, max_length=100)
    instruction: str = Field(min_length=1, max_length=4000)


class OpenIssue(FrozenModel):
    issue_id: str = Field(min_length=1, max_length=100)
    description: str = Field(min_length=1, max_length=4000)
    question: str = Field(min_length=1, max_length=4000)
    alternatives: tuple[Interpretation, ...] = Field(default=(), max_length=6)
    origin: Literal["model_proposal", "author_proposal", "collaborator_proposal"] = "model_proposal"

    @model_validator(mode="after")
    def unique_alternatives(self):
        if len(self.alternatives) == 1:
            raise ValueError("Use an open question or at least two genuinely different interpretations.")
        ids = [a.interpretation_id for a in self.alternatives]
        if len(ids) != len(set(ids)):
            raise ValueError("Interpretation IDs must be unique within an issue.")
        return self


class Preview(FrozenModel):
    issue_id: str
    interpretation_id: str
    case_id: str
    status: Literal["executed", "error", "missing", "not_run"]
    kind: Literal["execution", "example", "inference"] = "execution"
    input_description: str = ""
    execution_method: str = ""
    scope: str = ""
    outcome: object = None
    known_requirements_passed: bool = False
    error: str = ""

    @model_validator(mode="after")
    def json_outcome(self):
        # Refuse nonfinite/non-JSON values before hashing or comparing them.
        json.dumps(self.outcome, ensure_ascii=False, allow_nan=False)
        return self


class Resolution(FrozenModel):
    issue_id: str
    answer: str = Field(min_length=1, max_length=8000)
    interpretation_id: str | None = None
    actor: Literal["user", "simulated_user"] = "user"


class Event(FrozenModel):
    revision: int
    kind: Literal["answer", "correction"]
    issue_id: str
    answer: str
    actor: Literal["user", "simulated_user"]
    previous_answer: str = ""
    reason: str = ""


class ClarificationState(FrozenModel):
    schema_version: Literal[1] = 1
    problem_id: str
    project_id: str
    base_framing_sha256: str
    base_revision: int
    budget: int = Field(ge=0, le=20)
    turns_used: int = Field(default=0, ge=0)
    revision: int = Field(default=0, ge=0)
    issues: tuple[OpenIssue, ...] = Field(max_length=20)
    resolutions: tuple[Resolution, ...] = ()
    events: tuple[Event, ...] = ()

    @model_validator(mode="after")
    def coherent(self):
        ids = [issue.issue_id for issue in self.issues]
        resolved = [item.issue_id for item in self.resolutions]
        if len(ids) != len(set(ids)) or len(resolved) != len(set(resolved)):
            raise ValueError("Issue and resolution IDs must be unique.")
        if not set(resolved).issubset(ids):
            raise ValueError("A resolution refers to an unknown issue.")
        for resolution in self.resolutions:
            issue = next(i for i in self.issues if i.issue_id == resolution.issue_id)
            if resolution.interpretation_id is not None and resolution.interpretation_id not in {
                a.interpretation_id for a in issue.alternatives
            }:
                raise ValueError("Unknown interpretation in a resolution.")
        if self.turns_used > self.budget or self.turns_used != len(self.resolutions):
            raise ValueError("Reply count and budget do not agree.")
        if self.revision != len(self.events) or [e.revision for e in self.events] != list(range(1, self.revision + 1)):
            raise ValueError("Revision events must form a consecutive history.")
        latest = {}
        for event in self.events:
            if event.issue_id not in ids:
                raise ValueError("Unknown issue in event history.")
            if event.kind == "answer" and event.issue_id in latest:
                raise ValueError("An existing answer requires an explicit correction.")
            if event.kind == "correction" and (event.issue_id not in latest or not event.reason.strip()
                    or event.previous_answer != latest[event.issue_id]):
                raise ValueError("Correction must reference the previous answer and a reason.")
            latest[event.issue_id] = event.answer
        if latest != {r.issue_id: r.answer for r in self.resolutions}:
            raise ValueError("Resolution state does not match event history.")
        return self


class ImpactAssessment(FrozenModel):
    issue_id: str
    status: Literal["observed_difference", "no_observed_difference", "incomplete_preview"]
    compared_pairs: int
    differing_pairs: int
    witness_fraction: float
    complete: bool
    reason: str


class QuestionDecision(FrozenModel):
    state_sha256: str
    revision: int
    action: Literal["ask", "ready", "budget_exhausted"]
    issue_id: str | None
    question: str
    policy: Literal["impact", "generic"]
    assessments: tuple[ImpactAssessment, ...] = ()
    reason: str


def state_digest(state: ClarificationState) -> str:
    raw = json.dumps(state.model_dump(mode="json"), sort_keys=True, ensure_ascii=False, allow_nan=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def start_clarification(record: ProblemRecord, issues: list[OpenIssue], *, budget: int = 1) -> ClarificationState:
    return ClarificationState(problem_id=record.problem_id, project_id=record.project_id,
        base_framing_sha256=record.framing_sha256, base_revision=record.revision,
        budget=budget, issues=tuple(issues))


def _same_output(a, b) -> bool:
    if isinstance(a, bool) or isinstance(b, bool):
        return type(a) is type(b) and a == b
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-9)
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(_same_output(x, y) for x, y in zip(a, b))
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(_same_output(a[k], b[k]) for k in a)
    return type(a) is type(b) and a == b


def assess_impacts(state: ClarificationState, previews: list[Preview]) -> tuple[ImpactAssessment, ...]:
    issue_map = {issue.issue_id: issue for issue in state.issues}
    index = {}
    for preview in previews:
        if preview.issue_id not in issue_map or preview.interpretation_id not in {
            a.interpretation_id for a in issue_map[preview.issue_id].alternatives
        }:
            raise ValueError("Preview refers to an unknown issue or interpretation.")
        key = (preview.issue_id, preview.interpretation_id, preview.case_id)
        if key in index:
            raise ValueError("Duplicate public preview.")
        index[key] = preview
    assessments = []
    for issue in state.issues:
        cases = sorted({p.case_id for p in previews if p.issue_id == issue.issue_id and p.kind == "execution"})
        compared = different = 0
        complete = bool(cases) and len(issue.alternatives) >= 2
        for case in cases:
            values = [index.get((issue.issue_id, a.interpretation_id, case)) for a in issue.alternatives]
            valid = [p for p in values if p is not None and p.kind == "execution" and p.status == "executed" and p.known_requirements_passed]
            complete = complete and len(valid) == len(values)
            for a, b in combinations(valid, 2):
                compared += 1
                different += not _same_output(a.outcome, b.outcome)
        status = "observed_difference" if different else ("no_observed_difference" if complete else "incomplete_preview")
        reason = ("Valid public executions differ; the choice can affect the delivered result."
                  if different else "Public executions agree; this does not prove equivalence on untested inputs."
                  if complete else "Missing or invalid executions leave the effect unknown.")
        assessments.append(ImpactAssessment(issue_id=issue.issue_id, status=status, compared_pairs=compared,
            differing_pairs=different, witness_fraction=different / compared if compared else 0.0,
            complete=complete, reason=reason))
    return tuple(assessments)


def choose_question(state: ClarificationState, previews: list[Preview], *, policy: Literal["impact", "generic"] = "impact",
                    generic_issue_id: str | None = None) -> QuestionDecision:
    if policy not in ("impact", "generic"):
        raise ValueError("Unknown selection policy.")
    resolved = {r.issue_id for r in state.resolutions}
    remaining = [i for i in state.issues if i.issue_id not in resolved]
    common = dict(state_sha256=state_digest(state), revision=state.revision, policy=policy)
    if not remaining:
        return QuestionDecision(**common, action="ready", issue_id=None, question="", reason="All proposed issues have answers; candidate coverage is not guaranteed.")
    if state.turns_used >= state.budget:
        return QuestionDecision(**common, action="budget_exhausted", issue_id=None, question="", reason="Keep unanswered issues explicit; do not invent an answer.")
    if policy == "generic":
        if generic_issue_id not in {i.issue_id for i in remaining}:
            raise ValueError("Generic selection must name one unanswered issue.")
        selected = next(i for i in remaining if i.issue_id == generic_issue_id)
        return QuestionDecision(**common, action="ask", issue_id=selected.issue_id, question=selected.question,
            reason="The caller's generic selector chose this issue; no impact ranking was applied.")
    assessments = assess_impacts(state, previews)
    by_id = {a.issue_id: a for a in assessments}
    # Unknown effects precede observed agreement; input order breaks exact ties.
    priority = {"observed_difference": 2, "incomplete_preview": 1, "no_observed_difference": 0}
    selected = max(remaining, key=lambda i: (priority[by_id[i.issue_id].status], by_id[i.issue_id].witness_fraction))
    return QuestionDecision(**common, action="ask", issue_id=selected.issue_id, question=selected.question,
        assessments=assessments, reason=by_id[selected.issue_id].reason)


def _check_revision(state, expected_revision):
    if expected_revision != state.revision:
        raise ValueError("Stale clarification revision.")


def answer_question(state: ClarificationState, decision: QuestionDecision, answer: str, *, expected_revision: int,
                    interpretation_id: str | None = None, actor: Literal["user", "simulated_user"] = "user") -> ClarificationState:
    _check_revision(state, expected_revision)
    if decision.state_sha256 != state_digest(state) or decision.revision != state.revision:
        raise ValueError("Question belongs to a different or stale task state.")
    if decision.action != "ask" or state.turns_used >= state.budget:
        raise ValueError("No open clarification turn is available.")
    issue = next((i for i in state.issues if i.issue_id == decision.issue_id), None)
    if issue is None or decision.question != issue.question or issue.issue_id in {r.issue_id for r in state.resolutions}:
        raise ValueError("Question does not name an unanswered issue.")
    resolution = Resolution(issue_id=issue.issue_id, answer=answer.strip(), interpretation_id=interpretation_id, actor=actor)
    event = Event(revision=state.revision + 1, kind="answer", issue_id=issue.issue_id, answer=resolution.answer, actor=actor)
    return ClarificationState.model_validate({**state.model_dump(), "turns_used": state.turns_used + 1,
        "revision": state.revision + 1, "resolutions": (*state.resolutions, resolution), "events": (*state.events, event)})


def correct_answer(state: ClarificationState, issue_id: str, answer: str, *, reason: str, expected_revision: int,
                   interpretation_id: str | None = None, actor: Literal["user", "simulated_user"] = "user") -> ClarificationState:
    """An explicit user correction replaces one answer without consuming a new question."""
    _check_revision(state, expected_revision)
    previous = next((r for r in state.resolutions if r.issue_id == issue_id), None)
    if previous is None or not reason.strip():
        raise ValueError("A correction needs a prior answer and an explicit reason.")
    replacement = Resolution(issue_id=issue_id, answer=answer.strip(), interpretation_id=interpretation_id, actor=actor)
    event = Event(revision=state.revision + 1, kind="correction", issue_id=issue_id, answer=replacement.answer,
                  previous_answer=previous.answer, reason=reason.strip(), actor=actor)
    return ClarificationState.model_validate({**state.model_dump(), "revision": state.revision + 1,
        "resolutions": tuple(replacement if r.issue_id == issue_id else r for r in state.resolutions),
        "events": (*state.events, event)})


def render_clarification(state: ClarificationState) -> str:
    lines = ["## Clarification record / 需求澄清记录", "", f"Questions used: {state.turns_used}/{state.budget}",
             "Replies below supplement the original requirements; unmentioned requirements remain in force."]
    answers = {r.issue_id: r for r in state.resolutions}
    for issue in state.issues:
        resolution = answers.get(issue.issue_id)
        lines += ["", f"### {issue.issue_id}: {issue.description}"]
        if resolution:
            lines += [f"Reply source: {resolution.actor}", "\n".join("> " + line for line in resolution.answer.splitlines())]
        else:
            lines += ["UNRESOLVED / 尚未明确: " + issue.question]
    if not state.issues:
        lines += ["No issues were proposed. This does not establish complete understanding."]
    lines += ["", "Recorded replies are requirements input, not verification of external facts."]
    return "\n".join(lines) + "\n"


def _clarified_brief(record: ProblemRecord, state: ClarificationState) -> NeedBrief:
    brief = record.brief or NeedBrief()
    updated = brief.model_copy(update={"success_check": (brief.success_check + "\n\n" + render_clarification(state)).strip()})
    return NeedBrief.model_validate(updated.model_dump())


def commit_clarification(root: Path, previous: Path, state: ClarificationState, *,
                         original: Path | None = None, previous_state: ClarificationState | None = None) -> Path:
    """Create a normal ProblemBridge revision; preserve every original frame field.

    For a correction after a prior export, pass the original snapshot and the
    previously exported state. This prevents appending obsolete answers or
    silently rebasing over an unrelated user edit. Immutable branches are
    explicit; this API does not maintain a globally mutable current pointer.
    """
    base = load_problem(root, original or previous, state.project_id)
    record = load_problem(root, previous, state.project_id)
    if (base.problem_id, base.revision, base.framing_sha256) != (
        state.problem_id, state.base_revision, state.base_framing_sha256
    ):
        raise ValueError("Clarification is not bound to this original problem snapshot.")
    if record.problem_id != base.problem_id:
        raise ValueError("Previous record belongs to a different problem.")
    if original is not None and original != previous:
        if previous_state is None or previous_state.revision >= state.revision:
            raise ValueError("A further export needs its prior clarification state.")
        if (previous_state.problem_id, previous_state.base_framing_sha256, previous_state.base_revision,
                previous_state.issues, previous_state.budget) != (
                state.problem_id, state.base_framing_sha256, state.base_revision, state.issues, state.budget):
            raise ValueError("The prior clarification state belongs to another task.")
        if state.events[:previous_state.revision] != previous_state.events:
            raise ValueError("Prior clarification history was changed.")
        if record.brief != _clarified_brief(base, previous_state):
            raise ValueError("The current brief changed outside this clarification sequence.")
        if record.interview_answers != base.interview_answers or any(
            getattr(record, key) != getattr(base, key) for key in FRAME_FIELDS
        ):
            raise ValueError("The current task changed outside this clarification sequence.")
    updated = _clarified_brief(base, state)
    fields = {key: getattr(base, key) for key in FRAME_FIELDS}
    return confirm_problem(root, state.project_id, fields, previous=previous, brief=updated)
