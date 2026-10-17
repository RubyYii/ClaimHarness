"""Selected user requirements and attributed checks, without semantic grading."""
from __future__ import annotations

import hashlib
import json
import uuid
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, ConfigDict, Field

from claim_harness.continuity_store import Journal
from .project_lifecycle import is_link_or_reparse

if TYPE_CHECKING:
    from .workbench import ProblemRecord


TRACE_ARTIFACTS = ("requirement_trace.json", "requirement_trace.md")


class RequirementSource(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    run_name: str
    revision: int = Field(ge=1)
    framing_sha256: str
    record_sha256: str
    key: str
    start: int = Field(ge=0)
    end: int = Field(gt=0)


class TrackedRequirement(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    requirement_id: str = Field(pattern=r"^R-[a-f0-9]{12}$")
    text: str = Field(min_length=1, max_length=8000)
    source: RequirementSource
    acceptance: str = Field(default="", max_length=4000)
    status: Literal["confirmed", "needs_reconfirmation", "retired"] = "confirmed"
    confirmed_revision: int = Field(ge=1)
    retirement_reason: str = Field(default="", max_length=4000)


class Selection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    requirement_id: str | None = None
    source_key: str
    quote: str = Field(min_length=1, max_length=8000)
    start: int | None = Field(default=None, ge=0)
    acceptance: str = Field(default="", max_length=4000)


class RequirementChanges(BaseModel):
    model_config = ConfigDict(extra="forbid")
    select: list[Selection] = Field(default_factory=list, max_length=30)
    retire: dict[str, str] = Field(default_factory=dict, max_length=30)


def source_catalog(record: ProblemRecord) -> dict[str, str]:
    """Only confirmed wording; feedback proposals are deliberately excluded."""
    from .workbench import FRAME_FIELDS
    sources = {key: getattr(record, key) for key in FRAME_FIELDS}
    if record.brief:
        for key in ("background", "collaborator", "materials", "success_check"):
            sources[f"brief.{key}"] = getattr(record.brief, key)
        for index, concept in enumerate(record.brief.concepts):
            for key in ("term", "meaning", "example", "non_example"):
                sources[f"brief.concepts.{index}.{key}"] = getattr(concept, key)
    if record.continuation:
        # Historical, superseded answers are not offered as current sources.
        update = record.continuation["updates"][-1]
        for answer in update["answers"]:
            sources[f"answer.{answer['issue_id']}"] = answer["answer"]
    return {key: value for key, value in sources.items() if value.strip()}


def confirm_requirements(root: Path, project_id: str, current: Path, changes: dict, *,
                         confirmed: bool, expected_revision: int) -> Path:
    """Select exact source spans into a new immutable, user-confirmed revision."""
    from .feedback import discussion_journal, require_current
    from .revision_governance import exclusive_file_lock
    from .workbench import FRAME_FIELDS, _snapshot, confirm_problem, load_problem

    if not confirmed:
        raise ValueError("Explicit confirmation is required; suggestions are not requirements.")
    change = RequirementChanges.model_validate(changes)
    if not change.select and not change.retire:
        raise ValueError("Select or explicitly retire at least one requirement.")
    record = load_problem(root, current, project_id)
    journal = discussion_journal(root, record)
    journal._safe()
    journal.directory.mkdir(parents=True, exist_ok=True)
    # Share the confirmation lock with feedback updates to this same problem.
    with exclusive_file_lock(journal.path.with_suffix(".transaction.lock")):
        require_current(root, record)
        if record.revision != expected_revision:
            raise ValueError("Stale requirement selection: review the current problem revision.")
        files, reference = _snapshot(root, current, project_id)
        sources = source_catalog(record)
        items = {r.requirement_id: r for r in record.requirements or []}
        touched = set()
        for selected in change.select:
            text = sources.get(selected.source_key, "")
            if not selected.quote.strip() or selected.quote not in text:
                raise ValueError("A requirement must quote the selected confirmed source exactly.")
            if selected.start is None:
                start = text.find(selected.quote)
                if text.find(selected.quote, start + 1) != -1:
                    raise ValueError("Repeated wording needs an explicit start offset.")
            else:
                start = selected.start
            end = start + len(selected.quote)
            if text[start:end] != selected.quote:
                raise ValueError("The selected source offset does not match the quote.")
            rid = selected.requirement_id or f"R-{uuid.uuid4().hex[:12]}"
            if rid in touched or rid in change.retire:
                raise ValueError("A requirement can be changed only once per confirmation.")
            if selected.requirement_id:
                old = items.get(rid)
                if old is None or old.status == "retired" or old.text != selected.quote:
                    raise ValueError("Reconfirmation keeps the same text; retire and add changed wording explicitly.")
            elif any(r.text == selected.quote and r.status != "retired" for r in items.values()):
                raise ValueError("This wording is already tracked; use its requirement_id to reconfirm it.")
            touched.add(rid)
            items[rid] = TrackedRequirement(requirement_id=rid, text=selected.quote,
                source=RequirementSource(run_name=reference.run_name, revision=record.revision,
                    framing_sha256=record.framing_sha256,
                    record_sha256=hashlib.sha256(files["problem_record.json"]).hexdigest(),
                    key=selected.source_key, start=start, end=end),
                acceptance=selected.acceptance, confirmed_revision=record.revision + 1)
        for rid, reason in change.retire.items():
            if rid not in items or items[rid].status == "retired" or not reason.strip() or len(reason) > 4000:
                raise ValueError("Retirement needs an active requirement and a reason of 1–4,000 characters.")
            items[rid] = items[rid].model_copy(update={"status": "retired", "retirement_reason": reason.strip()})
        if len(items) > 100:
            raise ValueError("A problem can retain at most 100 selected requirements, including retired ones.")
        return confirm_problem(root, project_id, {k: getattr(record, k) for k in FRAME_FIELDS},
                               previous=current, _requirements=list(items.values()))


def render_requirements(record: ProblemRecord, language: str) -> str:
    if record.requirements is None:
        return ""
    zh = language == "zh"
    lines = ["## 已选关键要求" if zh else "## Selected key requirements",
             "仅包含用户明确选取的要求，不代表需求覆盖完整。验收记录另存，不改变证据核查结论。" if zh else
             "Only explicitly selected requirements are listed; completeness is unknown. Checks are recorded separately from evidence verdicts.",
             "只有已确认条目作为当前约束；待重新确认和已撤回条目保留供核对。" if zh else
             "Only confirmed entries apply as current constraints; entries needing reconfirmation or retired entries remain for reference."]
    labels = {"confirmed": "已确认", "needs_reconfirmation": "需要重新确认", "retired": "已撤回"}
    for item in record.requirements:
        lines += [f"\n<!-- requirement:{item.requirement_id} -->",
                  f"### {item.requirement_id} · {labels[item.status] if zh else item.status}",
                  "\n".join("> " + line for line in item.text.splitlines()),
                  f"Source: {item.source.run_name} / revision {item.source.revision} / {item.source.key} [{item.source.start}:{item.source.end}]",
                  ("验收方法：" if zh else "Acceptance method: ") + (item.acceptance or ("尚未明确" if zh else "Not specified"))]
        if item.status == "retired":
            lines += [("撤回理由：" if zh else "Retirement reason: ") + item.retirement_reason]
        lines += [f"<!-- /requirement:{item.requirement_id} -->"]
    return "\n\n".join(lines) + "\n"


def build_trace(record: ProblemRecord, handoffs: dict[str, str]) -> dict:
    rows = []
    for item in record.requirements or []:
        locations = []
        for name, content in handoffs.items():
            lines = content.splitlines()
            first, last = f"<!-- requirement:{item.requirement_id} -->", f"<!-- /requirement:{item.requirement_id} -->"
            if lines.count(first) != 1 or lines.count(last) != 1:
                raise ValueError("A handoff lost or duplicated a selected requirement marker.")
            locations.append({"file": name, "start_line": lines.index(first) + 1,
                              "end_line": lines.index(last) + 1,
                              "sha256": hashlib.sha256(content.encode("utf-8")).hexdigest()})
        rows.append({**item.model_dump(mode="json"), "handoff_locations": locations, "check": None})
    return {"schema_version": 1, "problem_id": record.problem_id, "project_id": record.project_id,
            "problem_revision": record.revision, "framing_sha256": record.framing_sha256,
            "scope": "selected_requirements_only", "completeness": "unknown",
            "requirements": rows}


def render_trace(value: dict) -> str:
    lines = ["# 要求、交接与验收 / Requirements, handoff and checks", "",
        f"Problem: {value['problem_id']} · Revision: {value['problem_revision']}",
        f"Framing SHA-256: {value['framing_sha256']}", "",
        "仅检查已选要求；需求覆盖完整性未知。验收是注明来源的记录，不自动改变 ClaimHarness 判断。",
        "Selected requirements only; completeness is unknown. Checks are attributed reports, not automatic ClaimHarness verdicts.", ""]
    if "journal_revision" in value:
        lines.append(f"Check journal revision: {value['journal_revision']}")
    for item in value["requirements"]:
        lines += [f"\n## {item['requirement_id']} · {item['status']}",
                  "\n".join("> " + line for line in item["text"].splitlines()),
                  f"Source: {item['source']['run_name']} / {item['source']['key']} [{item['source']['start']}:{item['source']['end']}]",
                  f"Acceptance / 验收方法: {item['acceptance'] or 'Unknown / 未明确'}"]
        if item["retirement_reason"]:
            lines.append(f"Retirement / 撤回理由: {item['retirement_reason']}")
        for loc in item["handoff_locations"]:
            lines.append(f"- {loc['file']}:{loc['start_line']}–{loc['end_line']} (SHA-256: {loc['sha256']})")
        check = item.get("check")
        if check:
            lines += [f"Check / 验收记录: {check['result']} · user_reported_not_verified",
                      f"Actor: {check['actor']} · Method: {check['method']}", f"Note: {check['note']}",
                      f"Evidence state: {check['evidence_state']} · applicable: {check['applicable']}"]
            if check["evidence"]:
                lines += [f"Evidence: {check['evidence']['path']} · {check['evidence']['location']}",
                          f"Recorded SHA-256: {check['evidence']['sha256']}"]
        else:
            lines.append("Check / 验收记录: not_checked / 尚未检查")
    return "\n\n".join(lines) + "\n"


def _check_journal(root: Path, current: Path, record: ProblemRecord) -> Journal:
    return Journal(root, {"kind": "requirement_checks", "project_id": record.project_id,
        "problem_id": record.problem_id, "run_name": current.name,
        "problem_revision": record.revision, "framing_sha256": record.framing_sha256})


def _artifact(root: Path, name: str) -> dict:
    path = Path(name)
    if path.is_absolute() or path.drive or ".." in path.parts or ":" in name:
        raise ValueError("Evidence must be a relative file within the workspace.")
    root = root.absolute()
    target = root / path
    for part in (target, *target.parents):
        if (part.exists() or part.is_symlink()) and is_link_or_reparse(part):
            raise ValueError("Linked evidence paths are not allowed.")
    if not target.resolve().is_relative_to(root.resolve()) or not target.is_file():
        raise ValueError("Evidence file is missing or outside the workspace.")
    with target.open("rb") as stream:
        content = stream.read(10 * 1024 * 1024 + 1)
    if len(content) > 10 * 1024 * 1024:
        raise ValueError("Evidence files must be at most 10 MB.")
    return {"path": path.as_posix(), "sha256": hashlib.sha256(content).hexdigest()}


def record_check(root: Path, project_id: str, current: Path, *, requirement_id: str, result: str,
                 actor: str, method: str, note: str, expected_revision: int,
                 artifact: str = "", location: str = "") -> dict:
    from .workbench import load_problem
    record = load_problem(root, current, project_id)
    item = next((r for r in record.requirements or [] if r.requirement_id == requirement_id), None)
    if item is None or item.status != "confirmed":
        raise ValueError("Choose a confirmed requirement in this exact problem revision.")
    if result not in {"met", "not_met", "not_checked"}:
        raise ValueError("Check result must be met, not_met or not_checked.")
    if any(not v.strip() or len(v) > 4000 for v in (actor, method, note)):
        raise ValueError("Actor, method and note must contain 1–4,000 characters.")
    if len(location) > 4000 or (result != "not_checked" and (not artifact or not location.strip())):
        raise ValueError("A met/not_met report needs an evidence file and an explicit location.")
    evidence = {**_artifact(root, artifact), "location": location} if artifact else None
    payload = {"requirement_id": requirement_id, "result": result, "actor": actor,
        "method": method, "note": note, "evidence": evidence, "authority": "user_reported_not_verified"}
    return _check_journal(root, current, record).append("requirement_check", payload, expected_revision=expected_revision)


def current_trace(root: Path, project_id: str, current: Path) -> dict:
    from .handoff import HANDOFF_ARTIFACTS
    from .workbench import _snapshot, load_problem
    record = load_problem(root, current, project_id)
    files, _ = _snapshot(root, current, project_id)
    if record.requirements is None:
        raise ValueError("No requirements have been explicitly selected for this version.")
    trace = build_trace(record, {name: files[name].decode("utf-8") for name in HANDOFF_ARTIFACTS})
    history = _check_journal(root, current, record).read()
    latest = {event["payload"]["requirement_id"]: event["payload"] for event in history["events"]}
    trace["journal_revision"] = history["revision"]
    trace["check_history"] = history["events"]
    for item in trace["requirements"]:
        if item["requirement_id"] not in latest:
            continue
        check = dict(latest[item["requirement_id"]])
        evidence = check["evidence"]
        state = "not_supplied"
        if evidence:
            try:
                state = "unchanged" if _artifact(root, evidence["path"])["sha256"] == evidence["sha256"] else "changed"
            except (OSError, ValueError):
                state = "missing_or_unreadable"
        check.update(evidence_state=state, applicable=item["status"] == "confirmed"
                     and check["result"] != "not_checked" and state == "unchanged")
        item["check"] = check
    return trace


def export_trace(root: Path, project_id: str, current: Path, out: Path) -> dict:
    value = current_trace(root, project_id, current)
    # A fresh workspace child cannot overwrite or sit inside an immutable run.
    if out.absolute().parent != root.absolute() or out.exists() or out.is_symlink():
        raise ValueError("Use a fresh direct child of the workspace for the export.")
    out.mkdir()
    (out / TRACE_ARTIFACTS[0]).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out / TRACE_ARTIFACTS[1]).write_text(render_trace(value), encoding="utf-8")
    return value
