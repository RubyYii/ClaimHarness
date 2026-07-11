from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


MAX_REVISION_ROUNDS = 3
REVISION_LOG_NAME = "revision_history.jsonl"
PROJECT_RECORD_NAME = "project_record.json"
PROJECT_SUMMARY_NAME = "project_summary_log.md"

DIAGNOSIS_CATEGORIES = {
    "underspecified_request",
    "ambiguous_feedback",
    "local_execution_problem",
    "structural_mismatch",
    "evidence_gap",
    "version_contamination",
}
ESCALATION_CATEGORIES = DIAGNOSIS_CATEGORIES - {"local_execution_problem"}
REVISION_STATUSES = {"accepted", "needs_revision", "escalated"}
TERMINAL_STATUSES = {"accepted", "escalated"}


class RevisionLimitReached(RuntimeError):
    """Raised when a target is terminal or has already used three rounds."""


@dataclass(frozen=True)
class RevisionRecord:
    target: str
    round_number: int
    diagnosis: str
    summary: str
    verification: str
    status: str
    changed_files: tuple[str, ...]
    created_at: str


def initialize_project_record(
    project_dir: str | Path,
    *,
    project_name: str,
    project_goal: str,
    boundaries: Iterable[str] = (),
    artifacts: Iterable[str] = (),
    created_at: str | None = None,
) -> Path:
    """Create or refresh local project metadata without erasing revision history."""

    root = Path(project_dir)
    root.mkdir(parents=True, exist_ok=True)
    existing = _load_project_record(root) if (root / PROJECT_RECORD_NAME).exists() else {}
    now = _utc_now()
    payload = {
        "project_name": _required_text(project_name, "project_name"),
        "project_goal": _required_text(project_goal, "project_goal"),
        "boundaries": _clean_items(boundaries),
        "artifacts": _clean_items(artifacts),
        "created_at": created_at or existing.get("created_at") or now,
        "updated_at": now,
        "max_revision_rounds": MAX_REVISION_ROUNDS,
    }
    _atomic_write_text(
        root / PROJECT_RECORD_NAME,
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
    )
    return write_project_summary(root)


def record_revision(
    project_dir: str | Path,
    *,
    target: str,
    diagnosis: str,
    summary: str,
    verification: str,
    status: str,
    changed_files: Iterable[str] = (),
    created_at: str | None = None,
) -> RevisionRecord:
    """Append one bounded revision round and refresh the human-readable summary.

    A target may be revised at most three times. Round three must either be
    accepted or escalated with a non-local diagnosis. A fourth patch is never
    appended to the same target; callers must open a new, explicitly scoped
    target after resolving the specification or structure problem.
    """

    root = Path(project_dir)
    root.mkdir(parents=True, exist_ok=True)
    normalized_target = _canonical_target(target)
    normalized_diagnosis = _choice(diagnosis, DIAGNOSIS_CATEGORIES, "diagnosis")
    normalized_status = _choice(status, REVISION_STATUSES, "status")
    records = load_revision_history(root)
    target_records = [
        record for record in records if _canonical_target(record.target) == normalized_target
    ]

    if target_records and target_records[-1].status in TERMINAL_STATUSES:
        raise RevisionLimitReached(
            f"Revision target '{normalized_target}' is already {target_records[-1].status}. "
            "Open a new target only after writing a consolidated specification."
        )
    if len(target_records) >= MAX_REVISION_ROUNDS:
        raise RevisionLimitReached(
            f"Revision target '{normalized_target}' already used {MAX_REVISION_ROUNDS} rounds. "
            "Do not apply a fourth patch; diagnose the specification or structure first."
        )

    round_number = len(target_records) + 1
    if round_number == MAX_REVISION_ROUNDS:
        if normalized_status == "needs_revision":
            normalized_status = "escalated"
        if normalized_status == "escalated" and normalized_diagnosis not in ESCALATION_CATEGORIES:
            allowed = ", ".join(sorted(ESCALATION_CATEGORIES))
            raise ValueError(
                "Round three cannot remain a local execution problem. "
                f"Use an escalation diagnosis: {allowed}."
            )

    record = RevisionRecord(
        target=normalized_target,
        round_number=round_number,
        diagnosis=normalized_diagnosis,
        summary=_required_text(summary, "summary"),
        verification=_required_text(verification, "verification"),
        status=normalized_status,
        changed_files=tuple(_clean_items(changed_files)),
        created_at=created_at or _utc_now(),
    )
    _write_revision_history(root, [*records, record])
    write_project_summary(root)
    return record


def load_revision_history(project_dir: str | Path) -> list[RevisionRecord]:
    path = Path(project_dir) / REVISION_LOG_NAME
    if not path.exists():
        return []

    records: list[RevisionRecord] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
            payload["changed_files"] = tuple(payload.get("changed_files", []))
            records.append(RevisionRecord(**payload))
        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            raise ValueError(f"Invalid revision history at {path}:{line_number}") from exc
    return records


def write_project_summary(project_dir: str | Path) -> Path:
    root = Path(project_dir)
    metadata = _load_project_record(root)
    records = load_revision_history(root)
    path = root / PROJECT_SUMMARY_NAME
    _atomic_write_text(path, _render_summary(metadata, records))
    return path


def _write_revision_history(root: Path, records: list[RevisionRecord]) -> None:
    text = "".join(json.dumps(asdict(record), ensure_ascii=False) + "\n" for record in records)
    _atomic_write_text(root / REVISION_LOG_NAME, text)


def _load_project_record(root: Path) -> dict[str, object]:
    path = root / PROJECT_RECORD_NAME
    if not path.exists():
        return {
            "project_name": root.name,
            "project_goal": "Project goal has not been recorded yet.",
            "boundaries": [],
            "artifacts": [],
            "max_revision_rounds": MAX_REVISION_ROUNDS,
        }
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid project record: {path}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"Invalid project record: {path}")
    return payload


def _render_summary(metadata: dict[str, object], records: list[RevisionRecord]) -> str:
    project_name = str(metadata.get("project_name") or "Unnamed project")
    project_goal = str(metadata.get("project_goal") or "Not recorded")
    boundaries = [str(item) for item in metadata.get("boundaries", [])]
    artifacts = [str(item) for item in metadata.get("artifacts", [])]
    lines = [
        "# Project Summary Log",
        "",
        "## Project",
        "",
        f"- Name: {project_name}",
        f"- Goal: {project_goal}",
        f"- Revision rule: maximum {MAX_REVISION_ROUNDS} rounds per target; no fourth patch.",
        "",
        "## Boundaries",
        "",
        *(_bullets(boundaries) or ["- No boundaries recorded."]),
        "",
        "## Artifact Index",
        "",
        *(_bullets(artifacts) or ["- No artifacts recorded."]),
        "",
        "## Revision History",
        "",
    ]
    if not records:
        lines.append("- No revision rounds recorded yet.")
    else:
        for record in records:
            lines.extend(
                [
                    f"### {record.target} — round {record.round_number}/{MAX_REVISION_ROUNDS}",
                    "",
                    f"- Time: {record.created_at}",
                    f"- Diagnosis: {record.diagnosis}",
                    f"- Status: {record.status}",
                    f"- Change: {record.summary}",
                    f"- Verification: {record.verification}",
                    "- Changed files:",
                    *(_bullets(record.changed_files, indent="  ") or ["  - None recorded."]),
                    "",
                ]
            )
        latest_by_target = {record.target: record for record in records}
        escalated = [record for record in latest_by_target.values() if record.status == "escalated"]
        if escalated:
            lines.extend(
                [
                    "## Escalated Targets",
                    "",
                    "Do not make a fourth local patch for these targets. Consolidate the specification, evidence, or structure first.",
                    "",
                    *[f"- {record.target}: {record.diagnosis}" for record in escalated],
                    "",
                ]
            )
    return "\n".join(lines).rstrip() + "\n"


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(text, encoding="utf-8")
    temporary.replace(path)


def _required_text(value: str, field: str) -> str:
    cleaned = str(value).strip()
    if not cleaned:
        raise ValueError(f"{field} must not be empty.")
    return cleaned


def _canonical_target(value: str) -> str:
    """Return a stable target key so case and separator aliases share one limit."""

    cleaned = unicodedata.normalize("NFKC", _required_text(value, "target")).casefold()
    canonical = re.sub(r"[\s_-]+", "-", cleaned).strip("-")
    if not canonical:
        raise ValueError("target must contain a letter or number.")
    return canonical


def _choice(value: str, choices: set[str], field: str) -> str:
    cleaned = _required_text(value, field).lower()
    if cleaned not in choices:
        allowed = ", ".join(sorted(choices))
        raise ValueError(f"Unsupported {field} '{value}'. Choose one of: {allowed}.")
    return cleaned


def _clean_items(values: Iterable[str]) -> list[str]:
    return [cleaned for value in values if (cleaned := str(value).strip())]


def _bullets(values: Iterable[str], *, indent: str = "") -> list[str]:
    return [f"{indent}- {value}" for value in values]


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
