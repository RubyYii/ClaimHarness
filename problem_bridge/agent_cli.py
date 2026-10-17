"""Small JSON adapter over the existing workbench; no UI or model service."""
from __future__ import annotations

import json
from enum import Enum
from pathlib import Path
from typing import Literal, Optional

import typer
from pydantic import BaseModel, ConfigDict, Field

from . import feedback
from .handoff import HANDOFF_ARTIFACTS, NeedBrief
from .workbench import MAX_FILE_BYTES, audit_problem, confirm_problem, load_problem


class Request(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, str_max_length=20000)


class Frame(Request):
    question: str = Field(min_length=1)
    observation: str = ""
    observation_source: str = ""
    desired_change: str = ""
    hypothesis: str = ""
    human_boundary: str = ""


class CreateRequest(Request):
    fields: Frame
    brief: NeedBrief | None = None


class FeedbackRequest(Request):
    expected_revision: int = Field(ge=0)
    sender: str
    sender_kind: Literal["collaborator", "ai", "user"]
    original: str
    selected: str
    interpretation: str
    category: Literal["goal_meaning", "terminology", "missing_condition", "method_proposal", "new_goal"]
    question: str
    target: str | None = None
    alternatives: list[str] = Field(default_factory=list, max_length=10)
    consequence: str = ""
    budget: int = Field(default=5, ge=1, le=20)


class RespondRequest(Request):
    expected_revision: int = Field(ge=0)
    issue_id: str
    mode: Literal["unknown", "defer", "correct", "answer", "none_accurate"]
    answer: str = ""
    interpretation_id: str | None = None
    reason: str = ""


class ConfirmRequest(Request):
    expected_revision: int = Field(ge=0)
    kind: Literal["supplement", "correction", "goal_change"]
    reason: str
    next_action: str
    fields: Frame | None = None


class NextRoundRequest(Request):
    expected_revision: int = Field(ge=0)
    budget: int = Field(default=5, ge=1, le=20)


class AuditRequest(Request):
    manuscript: str
    tables: list[str] = Field(min_length=1, max_length=20)
    references: str | None = None


class ExportRequest(Request):
    out: str = Field(min_length=1)
    language: Literal["zh", "en"] = "zh"


class Action(str, Enum):
    create = "create"
    show = "show"
    feedback = "feedback"
    respond = "respond"
    confirm = "confirm"
    next_round = "next-round"
    audit = "audit"
    export = "export"


MODELS = {Action.create: CreateRequest, Action.feedback: FeedbackRequest,
          Action.respond: RespondRequest, Action.confirm: ConfirmRequest,
          Action.next_round: NextRoundRequest, Action.audit: AuditRequest, Action.export: ExportRequest}


def read_bounded(path: Path) -> bytes:
    with path.open("rb") as handle:
        value = handle.read(MAX_FILE_BYTES + 1)
    if len(value) > MAX_FILE_BYTES:
        raise ValueError(f"Input exceeds 2 MiB: {path.name}")
    return value


def unique_keys(pairs: list) -> dict:
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError(f"Duplicate JSON field: {key}")
        value[key] = item
    return value


def read_text(path: Path) -> str:
    # Match normal text-file reading before passing strings to the workbench.
    # Keeping CRLF here would cause double newlines when Windows writes it again.
    return read_bounded(path).decode("utf-8-sig").replace("\r\n", "\n").replace("\r", "\n")


def run_path(workspace: Path, name: str) -> Path:
    # Reject both OS separators even on POSIX; a run is a direct child name.
    if not name or name in {".", ".."} or any(c in name for c in '/\\:') or Path(name).name != name:
        raise ValueError("Use a run_name returned by this workspace, not a path.")
    return workspace / name


def describe(workspace: Path, current: Path, project_id: str) -> dict:
    record = load_problem(workspace, current, project_id)
    _, history, latest = feedback.discussion(workspace, record, current)
    current_error = None
    try:
        feedback.require_current(workspace, record)
    except ValueError as exc:
        current_error = str(exc)
    return {"schema_version": 1, "run_name": current.name, "run_path": str(current),
            "record": record.model_dump(mode="json"), "is_current": current_error is None,
            "current_error": current_error, "journal_revision": history["revision"],
            "discussion": latest, "history": history,
            "handoffs": {name: str(current / name) for name in HANDOFF_ARTIFACTS},
            "follow_up": json.loads((current / "follow_up.json").read_text(encoding="utf-8"))}


def execute(action: Action, workspace: Path, project_id: str, run: str | None,
            request: Path | None, confirmed: bool) -> dict:
    workspace = workspace.absolute()
    if not project_id.strip():
        raise ValueError("An explicit non-empty project ID is required.")
    if action in {Action.create, Action.confirm} and not confirmed:
        raise ValueError("Review the proposed meaning with the user, then pass --confirmed once authorized.")
    if confirmed and action not in {Action.create, Action.confirm}:
        raise ValueError("--confirmed applies only to create and confirm.")
    if action == Action.create:
        if run is not None:
            raise ValueError("create starts a new problem; use confirm to continue an existing one.")
        current = None
    else:
        if not run:
            raise ValueError("--run is required; use the saved run_name.")
        current = run_path(workspace, run)
        load_problem(workspace, current, project_id)
    if action == Action.show:
        if request is not None:
            raise ValueError("show does not accept --request.")
        return describe(workspace, current, project_id)
    if request is None:
        raise ValueError("--request must name a UTF-8 JSON file.")
    raw = json.loads(read_bounded(request).decode("utf-8-sig"), object_pairs_hook=unique_keys)
    payload = MODELS[action].model_validate(raw)
    values = payload.model_dump()
    if action == Action.create:
        current = confirm_problem(workspace, project_id, payload.fields.model_dump(), brief=payload.brief)
    elif action == Action.feedback:
        target = values.pop("target")
        feedback.add_feedback(workspace, project_id, current,
                              target=run_path(workspace, target) if target else None, **values)
    elif action == Action.respond:
        feedback.respond(workspace, project_id, current, **values)
    elif action == Action.confirm:
        values["fields"] = payload.fields.model_dump(exclude_unset=True) if payload.fields else None
        current = feedback.confirm_discussion(workspace, project_id, current, **values)
    elif action == Action.next_round:
        feedback.start_next_round(workspace, project_id, current, **values)
    elif action == Action.export:
        from claim_harness.handoff_export import export_problem
        return export_problem(workspace, current, project_id, request.absolute().parent / payload.out,
                              language=payload.language)
    elif action == Action.audit:
        feedback.require_current(workspace, load_problem(workspace, current, project_id))
        # Paths inside JSON are relative to that request, not the backend checkout.
        base = request.absolute().parent
        paths = [base / path for path in payload.tables]
        if len({p.name.casefold() for p in paths}) != len(paths):
            raise ValueError("Table filenames must be unique, ignoring case.")
        current = audit_problem(workspace, project_id, current,
                                manuscript=read_text(base / payload.manuscript),
                                tables={p.name: read_bounded(p) for p in paths},
                                references=read_text(base / payload.references) if payload.references else "")
    return describe(workspace, current, project_id)


def task_command(
    action: Action = typer.Argument(...),
    workspace: Path = typer.Option(..., "--workspace"),
    project_id: str = typer.Option(..., "--project-id"),
    run: Optional[str] = typer.Option(None, "--run", help="Saved run_name, not a filesystem path."),
    request: Optional[Path] = typer.Option(None, "--request", help="UTF-8 JSON request; unknown fields are rejected."),
    confirmed: bool = typer.Option(False, "--confirmed", help="Caller asserts that the user authorized this exact meaning."),
) -> None:
    """Continue a confirmed problem from an agent or terminal without the web UI."""
    try:
        value = execute(action, workspace, project_id, run, request, confirmed)
        typer.echo(json.dumps(value, ensure_ascii=False, indent=2))
    except (OSError, ValueError, RuntimeError) as exc:
        typer.echo(json.dumps({"error": str(exc)}, ensure_ascii=False), err=True)
        raise typer.Exit(code=1) from exc
