from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import tempfile
import time
import unicodedata
import uuid
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import IO, Iterable, Iterator, Mapping


MAX_REVISION_ROUNDS = 3
REVISION_SCHEMA_VERSION = 3
PROJECT_RECORD_SCHEMA_VERSION = 2
REVISION_RECOVERY_SCHEMA_VERSION = 1
REVISION_MIGRATION_RECEIPT_SCHEMA_VERSION = 2
REVISION_LOG_NAME = "revision_history.jsonl"
REVISION_MIGRATION_RECEIPT_NAME = "revision_history_migration.json"
REVISION_RECOVERY_NAME = "revision_summary_recovery.json"
PROJECT_RECORD_NAME = "project_record.json"
PROJECT_SUMMARY_NAME = "project_summary_log.md"
REVISION_LOCK_NAME = ".revision_history.lock"

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

_REVISION_COMMON_FIELDS = {
    "target",
    "round_number",
    "diagnosis",
    "summary",
    "verification",
    "status",
    "changed_files",
    "created_at",
}
_REVISION_INTEGRITY_FIELDS = {
    "revision_id",
    "parent_revision_id",
    "base_artifact_sha256",
    "output_artifact_sha256",
    "previous_record_sha256",
    "record_sha256",
}
_REVISION_V1_FIELDS = _REVISION_COMMON_FIELDS | {"schema_version"}
_REVISION_V2_FIELDS = _REVISION_V1_FIELDS | _REVISION_INTEGRITY_FIELDS
_REVISION_V3_FIELDS = _REVISION_V2_FIELDS | {"project_id"}
_PROJECT_RECORD_FIELDS = {
    "schema_version",
    "project_id",
    "project_name",
    "project_goal",
    "boundaries",
    "artifacts",
    "created_at",
    "updated_at",
    "max_revision_rounds",
}
_REVISION_RECOVERY_FIELDS = {
    "schema_version",
    "project_id",
    "phase",
    "request_sha256",
    "revision_id",
    "previous_history_sha256",
    "committed_history_sha256",
    "created_at",
    "updated_at",
}
_REVISION_RECOVERY_PHASES = {"planned", "history_committed", "complete"}
_MIGRATION_RECEIPT_FIELDS = {
    "schema_version",
    "phase",
    "project_id",
    "from_revision_schema",
    "to_revision_schema",
    "source_sha256",
    "migrated_sha256",
    "migrated_record_count",
    "migrated_tip_record_sha256",
    "backup_file",
    "started_at",
    "updated_at",
    "completed_at",
}
_MIGRATION_PHASES = {"planned", "history_committed", "complete"}


class RevisionLimitReached(RuntimeError):
    """Raised when a target is terminal or has already used three rounds."""


class RevisionConflictError(RuntimeError):
    """Raised when another writer changed or currently owns revision state."""


@dataclass(frozen=True)
class RevisionRecord:
    project_id: str
    target: str
    round_number: int
    diagnosis: str
    summary: str
    verification: str
    status: str
    changed_files: tuple[str, ...]
    created_at: str
    schema_version: int = REVISION_SCHEMA_VERSION
    revision_id: str = ""
    parent_revision_id: str | None = None
    base_artifact_sha256: dict[str, str] = field(default_factory=dict)
    output_artifact_sha256: dict[str, str] = field(default_factory=dict)
    previous_record_sha256: str | None = None
    record_sha256: str = ""


def initialize_project_record(
    project_dir: str | Path,
    *,
    project_name: str,
    project_goal: str,
    project_id: str | None = None,
    boundaries: Iterable[str] = (),
    artifacts: Iterable[str] = (),
    created_at: str | None = None,
    lock_timeout: float = 5.0,
) -> Path:
    """Create or refresh local project metadata without erasing revision history.

    Once assigned, ``project_id`` is immutable. This prevents an existing output
    directory from being silently reused for a different project.
    """

    root = Path(project_dir)
    root.mkdir(parents=True, exist_ok=True)
    with exclusive_file_lock(project_lock_path(root, REVISION_LOCK_NAME), timeout=lock_timeout):
        existing = _load_project_record_unlocked(root) if (root / PROJECT_RECORD_NAME).exists() else {}
        existing_id = str(existing.get("project_id") or "").strip() or None
        requested_id = _validate_identifier(project_id, "project_id") if project_id else None
        if existing_id and requested_id and existing_id != requested_id:
            raise RevisionConflictError(
                f"Project identity mismatch: existing project_id={existing_id!r}, "
                f"requested project_id={requested_id!r}."
            )

        now = _utc_now()
        payload = {
            "schema_version": PROJECT_RECORD_SCHEMA_VERSION,
            "project_id": existing_id or requested_id or f"project-{uuid.uuid4().hex}",
            "project_name": _required_text(project_name, "project_name"),
            "project_goal": _required_text(project_goal, "project_goal"),
            "boundaries": _clean_items(boundaries),
            "artifacts": _clean_items(artifacts),
            "created_at": created_at or existing.get("created_at") or now,
            "updated_at": now,
            "max_revision_rounds": MAX_REVISION_ROUNDS,
        }
        _assert_colocated_run_project(root, str(payload["project_id"]))
        _atomic_write_text(
            root / PROJECT_RECORD_NAME,
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        )
        records = _load_revision_history_unlocked(root)
        return _write_project_summary_unlocked(root, payload, records)


def record_revision(
    project_dir: str | Path,
    *,
    target: str,
    diagnosis: str,
    summary: str,
    verification: str,
    status: str,
    changed_files: Iterable[str] = (),
    base_artifacts: Iterable[str | Path] = (),
    output_artifacts: Iterable[str | Path] = (),
    created_at: str | None = None,
    expected_history_sha256: str | None = None,
    expected_parent_revision_id: str | None = None,
    check_parent: bool = False,
    lock_timeout: float = 5.0,
) -> RevisionRecord:
    """Append one bounded, integrity-linked revision round.

    ``expected_history_sha256`` provides optimistic concurrency control. A UI
    can read :func:`revision_history_sha256`, let a user review the current
    state, and reject the write if that state changed before acceptance.

    ``check_parent`` makes ``expected_parent_revision_id`` authoritative. It is
    separate from the ID so callers can explicitly require a target with no
    existing parent.
    """

    root = Path(project_dir)
    root.mkdir(parents=True, exist_ok=True)
    normalized_target = _canonical_target(target)
    normalized_diagnosis = _choice(diagnosis, DIAGNOSIS_CATEGORIES, "diagnosis")
    normalized_status = _choice(status, REVISION_STATUSES, "status")
    requested_status = normalized_status
    normalized_summary = _required_text(summary, "summary")
    normalized_verification = _required_text(verification, "verification")
    normalized_changed_files = tuple(_clean_items(changed_files))

    with exclusive_file_lock(project_lock_path(root, REVISION_LOCK_NAME), timeout=lock_timeout):
        metadata = _load_project_record_unlocked(root, require_exists=True)
        project_id = _project_id_from_metadata(metadata)
        _assert_colocated_run_project(root, project_id)
        records = _load_revision_history_unlocked(root)
        base_artifact_sha256 = compute_artifact_sha256(root, base_artifacts)
        output_artifact_sha256 = compute_artifact_sha256(root, output_artifacts)
        request_sha256 = _revision_request_sha256(
            target=normalized_target,
            diagnosis=normalized_diagnosis,
            summary=normalized_summary,
            verification=normalized_verification,
            requested_status=requested_status,
            changed_files=normalized_changed_files,
            base_artifact_sha256=base_artifact_sha256,
            output_artifact_sha256=output_artifact_sha256,
            explicit_created_at=created_at,
            expected_parent_revision_id=expected_parent_revision_id,
            check_parent=check_parent,
        )
        recovery = _load_revision_recovery_unlocked(root, required=False)
        if recovery and recovery["phase"] == "complete" and _constant_time_equal(
            str(recovery["request_sha256"]), request_sha256
        ):
            existing = next(
                (
                    item
                    for item in records
                    if item.revision_id == str(recovery["revision_id"])
                ),
                None,
            )
            if existing is None:
                raise RevisionConflictError(
                    "Completed revision recovery state references a missing revision."
                )
            return existing

        current_history_hash = _history_file_sha256(root)
        if expected_history_sha256 is not None and not _constant_time_equal(
            current_history_hash, expected_history_sha256
        ):
            raise RevisionConflictError(
                "Revision history changed after it was reviewed; reload it before writing."
            )

        target_records = [
            record for record in records if _canonical_target(record.target) == normalized_target
        ]
        current_parent_id = target_records[-1].revision_id if target_records else None
        if check_parent and current_parent_id != expected_parent_revision_id:
            raise RevisionConflictError(
                "Revision parent changed after it was reviewed; reload it before writing."
            )

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

        parent_revision_id = (
            next(
                (
                    record.revision_id
                    for record in reversed(records)
                    if record.target == normalized_target
                ),
                None,
            )
        )
        record = RevisionRecord(
            project_id=project_id,
            target=normalized_target,
            round_number=round_number,
            diagnosis=normalized_diagnosis,
            summary=normalized_summary,
            verification=normalized_verification,
            status=normalized_status,
            changed_files=normalized_changed_files,
            created_at=created_at or _utc_now(),
            revision_id=str(uuid.uuid4()),
            parent_revision_id=parent_revision_id,
            base_artifact_sha256=base_artifact_sha256,
            output_artifact_sha256=output_artifact_sha256,
            previous_record_sha256=(records[-1].record_sha256 if records else None),
        )
        record = replace(record, record_sha256=_record_sha256(record))
        updated_records = [*records, record]
        history_text = _render_revision_history(updated_records)
        committed_history_sha256 = hashlib.sha256(history_text.encode("utf-8")).hexdigest()
        now = _utc_now()
        recovery = {
            "schema_version": REVISION_RECOVERY_SCHEMA_VERSION,
            "project_id": project_id,
            "phase": "planned",
            "request_sha256": request_sha256,
            "revision_id": record.revision_id,
            "previous_history_sha256": current_history_hash,
            "committed_history_sha256": committed_history_sha256,
            "created_at": now,
            "updated_at": now,
        }
        _write_revision_recovery_unlocked(root, recovery)
        try:
            _atomic_write_text(root / REVISION_LOG_NAME, history_text)
        except Exception as exc:
            actual_history_sha256 = _history_file_sha256(root)
            if _constant_time_equal(actual_history_sha256, committed_history_sha256):
                return record
            if _constant_time_equal(actual_history_sha256, current_history_hash):
                try:
                    (root / REVISION_RECOVERY_NAME).unlink(missing_ok=True)
                except OSError:
                    pass
                raise
            raise RevisionConflictError(
                "Revision history write ended in an unknown state; inspect recovery metadata."
            ) from exc

        try:
            recovery = _set_recovery_phase(recovery, "history_committed")
            _write_revision_recovery_unlocked(root, recovery)
            _write_project_summary_unlocked(root, metadata, updated_records)
            recovery = _set_recovery_phase(recovery, "complete")
            _write_revision_recovery_unlocked(root, recovery)
        except Exception:
            # The hash-chained history is the committed fact. A pending marker
            # makes summary repair observable and prevents an exact retry from
            # consuming another revision round.
            return record
        return record


def load_revision_history(
    project_dir: str | Path, *, lock_timeout: float = 5.0
) -> list[RevisionRecord]:
    root = Path(project_dir)
    root.mkdir(parents=True, exist_ok=True)
    with exclusive_file_lock(project_lock_path(root, REVISION_LOCK_NAME), timeout=lock_timeout):
        return _load_revision_history_unlocked(root)


def revision_history_sha256(project_dir: str | Path, *, lock_timeout: float = 5.0) -> str:
    """Return a snapshot token suitable for optimistic write checks."""

    root = Path(project_dir)
    root.mkdir(parents=True, exist_ok=True)
    with exclusive_file_lock(project_lock_path(root, REVISION_LOCK_NAME), timeout=lock_timeout):
        # Loading first makes a corrupt/tampered current history fail before its hash
        # can be presented as an acceptable snapshot token.
        _load_revision_history_unlocked(root)
        return _history_file_sha256(root)


def verify_revision_history(project_dir: str | Path, *, lock_timeout: float = 5.0) -> bool:
    """Validate the current JSONL schema, project binding, links, and hash chain."""

    load_revision_history(project_dir, lock_timeout=lock_timeout)
    return True


def pending_revision_recovery(
    project_dir: str | Path, *, lock_timeout: float = 5.0
) -> dict[str, object] | None:
    """Return validated pending summary-recovery state without repairing it."""

    root = Path(project_dir)
    with exclusive_file_lock(project_lock_path(root, REVISION_LOCK_NAME), timeout=lock_timeout):
        metadata = _load_project_record_unlocked(root, require_exists=True)
        project_id = _project_id_from_metadata(metadata)
        _assert_colocated_run_project(root, project_id)
        recovery = _load_revision_recovery_unlocked(root, required=False)
        if recovery is None or recovery["phase"] == "complete":
            return None
        if not _constant_time_equal(str(recovery["project_id"]), project_id):
            raise RevisionConflictError("Revision recovery project_id does not match this project.")
        return dict(recovery)


def migrate_legacy_revision_history(
    project_dir: str | Path,
    *,
    expected_project_id: str,
    lock_timeout: float = 5.0,
) -> list[RevisionRecord]:
    """Explicitly bind one homogeneous v1/v2 history to its project as v3.

    Migration is deliberately separate from reading and appending. A phased
    receipt makes the operation re-entrant after interruption at any write.
    """

    root = Path(project_dir)
    with exclusive_file_lock(project_lock_path(root, REVISION_LOCK_NAME), timeout=lock_timeout):
        metadata = _load_project_record_unlocked(root, require_exists=True)
        project_id = _project_id_from_metadata(metadata)
        _assert_colocated_run_project(root, project_id)
        confirmed_project_id = _validate_identifier(expected_project_id, "expected_project_id")
        if not _constant_time_equal(project_id, confirmed_project_id):
            raise RevisionConflictError(
                "Project identity mismatch: legacy history migration requires the exact "
                f"project_id from {PROJECT_RECORD_NAME}."
            )

        receipt = _load_migration_receipt_unlocked(root, required=False)
        if receipt is None:
            path = root / REVISION_LOG_NAME
            entries = _read_history_payloads(path)
            if not entries:
                raise ValueError("No legacy revision history is available to migrate.")
            schema_versions = {schema_version for _, _, schema_version in entries}
            if len(schema_versions) != 1:
                raise ValueError("Mixed revision history schema versions cannot be migrated.")
            source_schema = next(iter(schema_versions))
            if source_schema == REVISION_SCHEMA_VERSION:
                raise ValueError(
                    "Revision history is already current and has no migration receipt to resume."
                )
            if source_schema not in {1, 2}:
                raise ValueError(f"Unsupported legacy revision schema_version {source_schema}.")

            records = _load_revision_history_unlocked(
                root,
                allow_legacy=True,
                allow_pending_migration=True,
            )
            upgraded = _upgrade_legacy_records(records, project_id=project_id)
            with path.open("r", encoding="utf-8", newline="") as handle:
                source_text = handle.read()
            source_sha256 = hashlib.sha256(source_text.encode("utf-8")).hexdigest()
            migrated_text = _render_revision_history(upgraded)
            migrated_sha256 = hashlib.sha256(migrated_text.encode("utf-8")).hexdigest()
            backup_name = f"revision_history.legacy-v{source_schema}.jsonl"
            if (root / backup_name).exists():
                raise ValueError(
                    "A legacy backup exists without a migration receipt; manual review is required."
                )
            now = _utc_now()
            receipt = {
                "schema_version": REVISION_MIGRATION_RECEIPT_SCHEMA_VERSION,
                "phase": "planned",
                "project_id": project_id,
                "from_revision_schema": source_schema,
                "to_revision_schema": REVISION_SCHEMA_VERSION,
                "source_sha256": source_sha256,
                "migrated_sha256": migrated_sha256,
                "migrated_record_count": len(upgraded),
                "migrated_tip_record_sha256": upgraded[-1].record_sha256,
                "backup_file": backup_name,
                "started_at": now,
                "updated_at": now,
                "completed_at": None,
            }
            _write_migration_receipt_unlocked(root, receipt)
        elif not _constant_time_equal(str(receipt["project_id"]), project_id):
            raise RevisionConflictError("Migration receipt project_id does not match this project.")

        return _resume_legacy_migration_unlocked(root, metadata, receipt)


def compute_artifact_sha256(
    project_dir: str | Path, artifacts: Iterable[str | Path]
) -> dict[str, str]:
    """Hash project-local files without following paths outside the project."""

    root = Path(project_dir).resolve()
    result: dict[str, str] = {}
    for value in artifacts:
        raw = Path(value)
        path = raw.resolve() if raw.is_absolute() else (root / raw).resolve()
        try:
            relative = path.relative_to(root)
        except ValueError as exc:
            raise ValueError(f"Artifact path must stay inside the project directory: {value}") from exc
        if not path.is_file():
            raise ValueError(f"Artifact file not found: {value}")
        label = relative.as_posix()
        result[label] = _file_sha256(path)
    return dict(sorted(result.items()))


def write_project_summary(project_dir: str | Path, *, lock_timeout: float = 5.0) -> Path:
    root = Path(project_dir)
    root.mkdir(parents=True, exist_ok=True)
    with exclusive_file_lock(project_lock_path(root, REVISION_LOCK_NAME), timeout=lock_timeout):
        metadata = _load_project_record_unlocked(root)
        records = _load_revision_history_unlocked(root)
        return _write_project_summary_unlocked(root, metadata, records)


def snapshot_project_governance(
    project_dir: str | Path, *, lock_timeout: float = 5.0
) -> dict[str, bytes]:
    """Return one verified, lock-consistent snapshot of governance artifacts.

    The summary is checked against the project metadata and revision history
    while the revision lock is held. Callers therefore cannot accidentally
    package an old summary with a newer history through cooperating writers.
    """

    root = Path(project_dir)
    with exclusive_file_lock(project_lock_path(root, REVISION_LOCK_NAME), timeout=lock_timeout):
        metadata = _load_project_record_unlocked(root, require_exists=True)
        project_id = _project_id_from_metadata(metadata)
        _assert_colocated_run_project(root, project_id)
        records = _load_revision_history_unlocked(root)
        record_path = root / PROJECT_RECORD_NAME
        summary_path = root / PROJECT_SUMMARY_NAME
        for path in (record_path, summary_path):
            if path.is_symlink() or not path.is_file():
                raise ValueError(f"Governance artifact is missing or unsafe: {path}")

        summary_bytes = summary_path.read_bytes()
        expected_summary = _render_summary(metadata, records).encode("utf-8")
        if not hmac.compare_digest(summary_bytes, expected_summary):
            raise ValueError(
                f"{PROJECT_SUMMARY_NAME} is out of sync with the verified project history."
            )

        snapshot = {
            PROJECT_RECORD_NAME: record_path.read_bytes(),
            PROJECT_SUMMARY_NAME: summary_bytes,
        }
        history_path = root / REVISION_LOG_NAME
        if history_path.exists():
            if history_path.is_symlink() or not history_path.is_file():
                raise ValueError(f"Governance artifact is unsafe: {history_path}")
            snapshot[REVISION_LOG_NAME] = history_path.read_bytes()
        return snapshot


def _assert_colocated_run_project(root: Path, project_id: str) -> None:
    """Reject a mutable project ledger copied beside another run identity."""

    identity_path = root / "run_identity.json"
    if not identity_path.exists():
        return
    if identity_path.is_symlink() or not identity_path.is_file():
        raise RevisionConflictError(f"Co-located run identity is unsafe: {identity_path}")
    try:
        payload = json.loads(identity_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RevisionConflictError(f"Co-located run identity is invalid: {identity_path}") from exc
    if not isinstance(payload, dict) or str(payload.get("project_id", "")) != project_id:
        raise RevisionConflictError(
            "Project ledger does not match the co-located run_identity.json project_id."
        )


@contextmanager
def exclusive_file_lock(lock_path: str | Path, *, timeout: float = 5.0) -> Iterator[None]:
    """Hold a crash-safe advisory file lock on Windows or POSIX.

    The file itself may remain after a process exits; the operating-system lock
    is released automatically, so a crashed writer cannot leave a permanent
    false lock.
    """

    lock = _CrossProcessFileLock(Path(lock_path), timeout=timeout)
    lock.acquire()
    try:
        yield
    finally:
        lock.release()


def project_lock_path(project_dir: str | Path, purpose: str) -> Path:
    """Return a stable external lock path without polluting project artifacts."""

    root_key = str(Path(project_dir).resolve())
    if os.name == "nt":
        root_key = root_key.casefold()
    digest = hashlib.sha256(root_key.encode("utf-8")).hexdigest()
    clean_purpose = re.sub(r"[^A-Za-z0-9_.-]+", "-", purpose).strip(".-") or "project"
    return Path(tempfile.gettempdir()) / "claimharness-locks" / f"{digest}-{clean_purpose}.lock"


class _CrossProcessFileLock:
    def __init__(self, path: Path, *, timeout: float) -> None:
        if timeout < 0:
            raise ValueError("lock timeout must be non-negative.")
        self.path = path
        self.timeout = timeout
        self._handle: IO[bytes] | None = None

    def acquire(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        handle = self.path.open("a+b")
        handle.seek(0, os.SEEK_END)
        if handle.tell() == 0:
            handle.write(b"\0")
            handle.flush()
        deadline = time.monotonic() + self.timeout
        while True:
            try:
                _lock_handle(handle)
                self._handle = handle
                return
            except (BlockingIOError, OSError):
                if time.monotonic() >= deadline:
                    handle.close()
                    raise RevisionConflictError(
                        f"Timed out waiting for project lock: {self.path}"
                    ) from None
                time.sleep(min(0.05, max(0.0, deadline - time.monotonic())))

    def release(self) -> None:
        if self._handle is None:
            return
        try:
            _unlock_handle(self._handle)
        finally:
            self._handle.close()
            self._handle = None


def _lock_handle(handle: IO[bytes]) -> None:
    handle.seek(0)
    if os.name == "nt":
        import msvcrt

        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
    else:
        import fcntl

        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)


def _unlock_handle(handle: IO[bytes]) -> None:
    handle.seek(0)
    if os.name == "nt":
        import msvcrt

        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
    else:
        import fcntl

        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _read_history_payloads(path: Path) -> list[tuple[int, dict[str, object], int]]:
    if not path.is_file():
        raise ValueError(f"Revision history not found: {path}")
    entries: list[tuple[int, dict[str, object], int]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid revision history at {path}:{line_number}") from exc
        if not isinstance(payload, dict):
            raise ValueError(f"Invalid revision history at {path}:{line_number}")
        try:
            schema_version = _payload_schema_version(payload)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Invalid revision history at {path}:{line_number}: {exc}") from exc
        entries.append((line_number, payload, schema_version))
    return entries


def _payload_schema_version(payload: Mapping[str, object]) -> int:
    value = payload.get("schema_version", 1)
    if type(value) is not int:
        raise TypeError("schema_version must be an integer")
    if value not in {1, 2, REVISION_SCHEMA_VERSION}:
        raise ValueError(f"unsupported schema_version {value}")
    return value


def _validate_revision_payload_fields(
    payload: Mapping[str, object], *, schema_version: int
) -> None:
    expected = {
        1: _REVISION_V1_FIELDS,
        2: _REVISION_V2_FIELDS,
        REVISION_SCHEMA_VERSION: _REVISION_V3_FIELDS,
    }[schema_version]
    actual = set(payload)
    required = _REVISION_COMMON_FIELDS if schema_version == 1 else expected
    missing = sorted(required - actual)
    unexpected = sorted(actual - expected)
    if missing:
        raise ValueError(f"schema v{schema_version} record is missing fields: {', '.join(missing)}")
    if unexpected:
        raise ValueError(
            f"schema v{schema_version} record has unexpected fields: {', '.join(unexpected)}"
        )


def _load_revision_history_unlocked(
    root: Path,
    *,
    allow_legacy: bool = False,
    allow_pending_migration: bool = False,
) -> list[RevisionRecord]:
    path = root / REVISION_LOG_NAME
    if not path.exists():
        recovery = _load_revision_recovery_unlocked(root, required=False)
        if recovery is not None:
            metadata = _load_project_record_unlocked(root, require_exists=True)
            project_id = _project_id_from_metadata(metadata)
            _assert_colocated_run_project(root, project_id)
            _recover_revision_summary_unlocked(root, metadata, [])
        return []

    metadata = _load_project_record_unlocked(root, require_exists=True)
    project_id = _project_id_from_metadata(metadata)
    _assert_colocated_run_project(root, project_id)
    migration_receipt = _load_migration_receipt_unlocked(root, required=False)
    if migration_receipt is not None:
        if not _constant_time_equal(str(migration_receipt["project_id"]), project_id):
            raise RevisionConflictError("Migration receipt project_id does not match this project.")
        if migration_receipt["phase"] != "complete" and not allow_pending_migration:
            raise RevisionConflictError(
                "Revision migration is incomplete; rerun migrate-revision-history before continuing."
            )
    entries = _read_history_payloads(path)
    schema_versions = {schema_version for _, _, schema_version in entries}
    if len(schema_versions) > 1:
        raise ValueError(f"Invalid revision history at {path}: mixed schema versions are forbidden")
    history_schema = next(iter(schema_versions), REVISION_SCHEMA_VERSION)
    if history_schema != REVISION_SCHEMA_VERSION and not allow_legacy:
        raise ValueError(
            f"Legacy revision history schema v{history_schema} requires explicit migration; "
            "run migrate-revision-history before reading or appending."
        )
    if history_schema not in {1, 2, REVISION_SCHEMA_VERSION}:
        raise ValueError(f"Unsupported revision history schema_version {history_schema}")

    records: list[RevisionRecord] = []
    previous_hash: str | None = None
    latest_by_target: dict[str, str] = {}
    latest_status_by_target: dict[str, str] = {}
    rounds_by_target: dict[str, int] = {}
    seen_ids: set[str] = set()
    for line_number, payload, schema_version in entries:
        try:
            record = _record_from_payload(
                payload,
                line_number=line_number,
                previous_hash=previous_hash,
                parent_revision_id=latest_by_target.get(
                    _canonical_target(str(payload.get("target", "")))
                ),
                project_id=project_id,
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"Invalid revision history at {path}:{line_number}: {exc}") from exc

        if record.revision_id in seen_ids:
            raise ValueError(f"Invalid revision history at {path}:{line_number}: duplicate revision_id")
        seen_ids.add(record.revision_id)

        prior_rounds = rounds_by_target.get(record.target, 0)
        if latest_status_by_target.get(record.target) in TERMINAL_STATUSES:
            raise ValueError(
                f"Invalid revision history at {path}:{line_number}: revision follows terminal status"
            )
        if record.round_number != prior_rounds + 1 or record.round_number > MAX_REVISION_ROUNDS:
            raise ValueError(
                f"Invalid revision history at {path}:{line_number}: non-sequential round number"
            )
        if record.round_number == MAX_REVISION_ROUNDS:
            if record.status == "needs_revision":
                raise ValueError(
                    f"Invalid revision history at {path}:{line_number}: round three must be terminal"
                )
            if record.status == "escalated" and record.diagnosis not in ESCALATION_CATEGORIES:
                raise ValueError(
                    f"Invalid revision history at {path}:{line_number}: invalid escalation diagnosis"
                )

        if schema_version >= 2:
            expected_parent = latest_by_target.get(record.target)
            if record.parent_revision_id != expected_parent:
                raise ValueError(
                    f"Invalid revision history at {path}:{line_number}: parent revision mismatch"
                )
            if record.previous_record_sha256 != previous_hash:
                raise ValueError(
                    f"Invalid revision history at {path}:{line_number}: hash-chain predecessor mismatch"
                )
            if schema_version == REVISION_SCHEMA_VERSION:
                if not _constant_time_equal(record.project_id, project_id):
                    raise ValueError(
                        f"Invalid revision history at {path}:{line_number}: project_id mismatch"
                    )
                expected_hash = _record_sha256(record)
            else:
                expected_hash = _legacy_v2_payload_sha256(payload)
            if not _constant_time_equal(record.record_sha256, expected_hash):
                raise ValueError(
                    f"Invalid revision history at {path}:{line_number}: record SHA-256 mismatch"
                )

        records.append(record)
        previous_hash = record.record_sha256
        latest_by_target[record.target] = record.revision_id
        latest_status_by_target[record.target] = record.status
        rounds_by_target[record.target] = record.round_number
    if not allow_legacy:
        _recover_revision_summary_unlocked(root, metadata, records)
    if migration_receipt is not None and migration_receipt["phase"] == "complete":
        _validate_migration_artifacts_unlocked(root, migration_receipt)
    return records


def _record_from_payload(
    payload: Mapping[str, object],
    *,
    line_number: int,
    previous_hash: str | None,
    parent_revision_id: str | None,
    project_id: str,
) -> RevisionRecord:
    target = _canonical_target(str(payload["target"]))
    schema_version = _payload_schema_version(payload)
    _validate_revision_payload_fields(payload, schema_version=schema_version)
    changed_files_value = payload.get("changed_files", [])
    if not isinstance(changed_files_value, list):
        raise TypeError("changed_files must be a list")

    common = dict(
        target=target,
        round_number=int(payload["round_number"]),
        diagnosis=_choice(str(payload["diagnosis"]), DIAGNOSIS_CATEGORIES, "diagnosis"),
        summary=_required_text(str(payload["summary"]), "summary"),
        verification=_required_text(str(payload["verification"]), "verification"),
        status=_choice(str(payload["status"]), REVISION_STATUSES, "status"),
        changed_files=tuple(_clean_items(changed_files_value)),
        created_at=_required_text(str(payload["created_at"]), "created_at"),
    )
    if schema_version >= 2:
        base_hashes = _validate_digest_map(payload.get("base_artifact_sha256", {}))
        output_hashes = _validate_digest_map(payload.get("output_artifact_sha256", {}))
        return RevisionRecord(
            **common,
            schema_version=schema_version,
            project_id=(
                _validate_identifier(str(payload["project_id"]), "project_id")
                if schema_version == REVISION_SCHEMA_VERSION
                else project_id
            ),
            revision_id=_required_text(str(payload["revision_id"]), "revision_id"),
            parent_revision_id=_optional_text(payload.get("parent_revision_id")),
            base_artifact_sha256=base_hashes,
            output_artifact_sha256=output_hashes,
            previous_record_sha256=_optional_digest(payload.get("previous_record_sha256")),
            record_sha256=_required_digest(payload.get("record_sha256"), "record_sha256"),
        )

    # Explicit v1 migration assigns deterministic in-memory IDs before the
    # records are rebound and rehashed as v3. Normal reads never reach here.
    legacy_payload = {key: payload[key] for key in sorted(payload)}
    seed = f"{line_number}:" + _canonical_json(legacy_payload)
    legacy_id = f"legacy-{hashlib.sha256(seed.encode('utf-8')).hexdigest()[:24]}"
    legacy_record = RevisionRecord(
        **common,
        project_id=project_id,
        schema_version=1,
        revision_id=legacy_id,
        parent_revision_id=parent_revision_id,
        previous_record_sha256=previous_hash,
    )
    return replace(legacy_record, record_sha256=_record_sha256(legacy_record))


def _upgrade_legacy_records(
    records: Iterable[RevisionRecord], *, project_id: str
) -> list[RevisionRecord]:
    upgraded: list[RevisionRecord] = []
    latest_by_target: dict[str, str] = {}
    previous_hash: str | None = None
    for record in records:
        current = replace(
            record,
            project_id=project_id,
            schema_version=REVISION_SCHEMA_VERSION,
            parent_revision_id=latest_by_target.get(record.target),
            previous_record_sha256=previous_hash,
            record_sha256="",
        )
        current = replace(current, record_sha256=_record_sha256(current))
        upgraded.append(current)
        latest_by_target[current.target] = current.revision_id
        previous_hash = current.record_sha256
    return upgraded


def _record_sha256(record: RevisionRecord) -> str:
    payload = asdict(record)
    payload.pop("record_sha256", None)
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def _legacy_v2_payload_sha256(payload: Mapping[str, object]) -> str:
    hash_payload = dict(payload)
    hash_payload.pop("record_sha256", None)
    return hashlib.sha256(_canonical_json(hash_payload).encode("utf-8")).hexdigest()


def _revision_request_sha256(
    *,
    target: str,
    diagnosis: str,
    summary: str,
    verification: str,
    requested_status: str,
    changed_files: tuple[str, ...],
    base_artifact_sha256: Mapping[str, str],
    output_artifact_sha256: Mapping[str, str],
    explicit_created_at: str | None,
    expected_parent_revision_id: str | None,
    check_parent: bool,
) -> str:
    payload = {
        "target": target,
        "diagnosis": diagnosis,
        "summary": summary,
        "verification": verification,
        "requested_status": requested_status,
        "changed_files": list(changed_files),
        "base_artifact_sha256": dict(base_artifact_sha256),
        "output_artifact_sha256": dict(output_artifact_sha256),
        "explicit_created_at": explicit_created_at,
        "expected_parent_revision_id": expected_parent_revision_id,
        "check_parent": check_parent,
    }
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def _load_revision_recovery_unlocked(
    root: Path, *, required: bool
) -> dict[str, object] | None:
    path = root / REVISION_RECOVERY_NAME
    if not path.exists():
        if required:
            raise ValueError(f"Revision recovery state not found: {path}")
        return None
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"Revision recovery state is unsafe: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Invalid revision recovery state: {path}") from exc
    if not isinstance(payload, dict) or set(payload) != _REVISION_RECOVERY_FIELDS:
        raise ValueError(f"Invalid revision recovery state fields: {path}")
    if payload["schema_version"] != REVISION_RECOVERY_SCHEMA_VERSION:
        raise ValueError(f"Unsupported revision recovery schema: {path}")
    if payload["phase"] not in _REVISION_RECOVERY_PHASES:
        raise ValueError(f"Invalid revision recovery phase: {path}")
    _validate_identifier(str(payload["project_id"]), "project_id")
    _required_text(str(payload["revision_id"]), "revision_id")
    for field_name in (
        "request_sha256",
        "previous_history_sha256",
        "committed_history_sha256",
    ):
        _required_digest(payload[field_name], field_name)
    _required_text(str(payload["created_at"]), "created_at")
    _required_text(str(payload["updated_at"]), "updated_at")
    return payload


def _write_revision_recovery_unlocked(root: Path, payload: Mapping[str, object]) -> None:
    _atomic_write_text(
        root / REVISION_RECOVERY_NAME,
        json.dumps(dict(payload), indent=2, ensure_ascii=False) + "\n",
    )


def _set_recovery_phase(
    recovery: Mapping[str, object], phase: str
) -> dict[str, object]:
    if phase not in _REVISION_RECOVERY_PHASES:
        raise ValueError(f"Unsupported revision recovery phase: {phase}")
    updated = dict(recovery)
    updated["phase"] = phase
    updated["updated_at"] = _utc_now()
    return updated


def _recover_revision_summary_unlocked(
    root: Path,
    metadata: dict[str, object],
    records: list[RevisionRecord],
) -> dict[str, object] | None:
    recovery = _load_revision_recovery_unlocked(root, required=False)
    if recovery is None:
        return None
    project_id = _project_id_from_metadata(metadata)
    if not _constant_time_equal(str(recovery["project_id"]), project_id):
        raise RevisionConflictError("Revision recovery project_id does not match this project.")
    actual_history_sha256 = _history_file_sha256(root)
    previous_sha256 = str(recovery["previous_history_sha256"])
    committed_sha256 = str(recovery["committed_history_sha256"])
    if recovery["phase"] == "planned" and _constant_time_equal(
        actual_history_sha256, previous_sha256
    ):
        (root / REVISION_RECOVERY_NAME).unlink(missing_ok=True)
        return None
    if not _constant_time_equal(actual_history_sha256, committed_sha256):
        raise RevisionConflictError(
            "Revision recovery does not match the current history; refusing automatic repair."
        )
    if not any(record.revision_id == recovery["revision_id"] for record in records):
        raise RevisionConflictError("Revision recovery references a missing committed revision.")
    if recovery["phase"] == "complete":
        return recovery
    _write_project_summary_unlocked(root, metadata, records)
    recovery = _set_recovery_phase(recovery, "complete")
    _write_revision_recovery_unlocked(root, recovery)
    return recovery


def _load_migration_receipt_unlocked(
    root: Path, *, required: bool
) -> dict[str, object] | None:
    path = root / REVISION_MIGRATION_RECEIPT_NAME
    if not path.exists():
        if required:
            raise ValueError(f"Migration receipt not found: {path}")
        return None
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"Migration receipt is unsafe: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Invalid migration receipt: {path}") from exc
    if not isinstance(payload, dict) or set(payload) != _MIGRATION_RECEIPT_FIELDS:
        raise ValueError(f"Invalid migration receipt fields: {path}")
    if payload["schema_version"] != REVISION_MIGRATION_RECEIPT_SCHEMA_VERSION:
        raise ValueError(f"Unsupported migration receipt schema: {path}")
    if payload["phase"] not in _MIGRATION_PHASES:
        raise ValueError(f"Invalid migration receipt phase: {path}")
    _validate_identifier(str(payload["project_id"]), "project_id")
    if payload["from_revision_schema"] not in {1, 2}:
        raise ValueError(f"Invalid migration source schema: {path}")
    if payload["to_revision_schema"] != REVISION_SCHEMA_VERSION:
        raise ValueError(f"Invalid migration destination schema: {path}")
    expected_backup = f"revision_history.legacy-v{payload['from_revision_schema']}.jsonl"
    if payload["backup_file"] != expected_backup:
        raise ValueError(f"Invalid migration backup name: {path}")
    _required_digest(payload["source_sha256"], "source_sha256")
    _required_digest(payload["migrated_sha256"], "migrated_sha256")
    if type(payload["migrated_record_count"]) is not int or payload["migrated_record_count"] < 1:
        raise ValueError(f"Invalid migrated record count: {path}")
    _required_digest(payload["migrated_tip_record_sha256"], "migrated_tip_record_sha256")
    _required_text(str(payload["started_at"]), "started_at")
    _required_text(str(payload["updated_at"]), "updated_at")
    if payload["phase"] == "complete":
        _required_text(str(payload["completed_at"]), "completed_at")
    elif payload["completed_at"] is not None:
        raise ValueError(f"Incomplete migration receipt has completed_at: {path}")
    return payload


def _write_migration_receipt_unlocked(root: Path, payload: Mapping[str, object]) -> None:
    _atomic_write_text(
        root / REVISION_MIGRATION_RECEIPT_NAME,
        json.dumps(dict(payload), indent=2, ensure_ascii=False) + "\n",
    )


def _set_migration_phase(
    receipt: Mapping[str, object], phase: str
) -> dict[str, object]:
    if phase not in _MIGRATION_PHASES:
        raise ValueError(f"Unsupported migration phase: {phase}")
    updated = dict(receipt)
    now = _utc_now()
    updated["phase"] = phase
    updated["updated_at"] = now
    updated["completed_at"] = now if phase == "complete" else None
    return updated


def _validate_migration_artifacts_unlocked(
    root: Path, receipt: Mapping[str, object]
) -> None:
    backup_path = root / str(receipt["backup_file"])
    if backup_path.is_symlink() or not backup_path.is_file():
        raise ValueError("Migration backup is missing or unsafe.")
    if not _constant_time_equal(_file_sha256(backup_path), str(receipt["source_sha256"])):
        raise ValueError("Migration backup SHA-256 does not match the receipt.")
    history_path = root / REVISION_LOG_NAME
    if history_path.is_symlink() or not history_path.is_file():
        raise ValueError("Migrated history is missing or unsafe.")
    lines = history_path.read_text(encoding="utf-8").splitlines()
    count = int(receipt["migrated_record_count"])
    if len(lines) < count:
        raise ValueError("Migrated history is shorter than the receipt prefix.")
    migrated_prefix = "".join(line + "\n" for line in lines[:count])
    if not _constant_time_equal(
        hashlib.sha256(migrated_prefix.encode("utf-8")).hexdigest(),
        str(receipt["migrated_sha256"]),
    ):
        raise ValueError("Migrated history prefix SHA-256 does not match the receipt.")
    try:
        tip_payload = json.loads(lines[count - 1])
    except json.JSONDecodeError as exc:
        raise ValueError("Migrated history receipt tip is invalid JSON.") from exc
    if not isinstance(tip_payload, dict) or not _constant_time_equal(
        str(tip_payload.get("record_sha256", "")),
        str(receipt["migrated_tip_record_sha256"]),
    ):
        raise ValueError("Migrated history tip does not match the receipt.")


def _resume_legacy_migration_unlocked(
    root: Path,
    metadata: dict[str, object],
    receipt: dict[str, object],
) -> list[RevisionRecord]:
    project_id = _project_id_from_metadata(metadata)
    if not _constant_time_equal(str(receipt["project_id"]), project_id):
        raise RevisionConflictError("Migration receipt project_id does not match this project.")
    history_path = root / REVISION_LOG_NAME
    backup_path = root / str(receipt["backup_file"])
    source_sha256 = str(receipt["source_sha256"])
    migrated_sha256 = str(receipt["migrated_sha256"])

    if not backup_path.exists():
        if receipt["phase"] != "planned" or not _constant_time_equal(
            _history_file_sha256(root), source_sha256
        ):
            raise ValueError("Migration backup is missing and cannot be reconstructed safely.")
        with history_path.open("r", encoding="utf-8", newline="") as handle:
            source_text = handle.read()
        if not _constant_time_equal(
            hashlib.sha256(source_text.encode("utf-8")).hexdigest(), source_sha256
        ):
            raise ValueError("Legacy source changed before backup creation.")
        _atomic_write_text(backup_path, source_text)
    if backup_path.is_symlink() or not backup_path.is_file() or not _constant_time_equal(
        _file_sha256(backup_path), source_sha256
    ):
        raise ValueError("Migration backup SHA-256 does not match the receipt.")

    actual_history_sha256 = _history_file_sha256(root)
    if receipt["phase"] == "planned":
        if _constant_time_equal(actual_history_sha256, source_sha256):
            legacy_records = _load_revision_history_unlocked(
                root,
                allow_legacy=True,
                allow_pending_migration=True,
            )
            upgraded = _upgrade_legacy_records(legacy_records, project_id=project_id)
            migrated_text = _render_revision_history(upgraded)
            if not _constant_time_equal(
                hashlib.sha256(migrated_text.encode("utf-8")).hexdigest(),
                migrated_sha256,
            ):
                raise ValueError("Deterministic migrated history does not match the receipt.")
            _atomic_write_text(history_path, migrated_text)
            records = upgraded
        elif _constant_time_equal(actual_history_sha256, migrated_sha256):
            records = _load_revision_history_unlocked(
                root,
                allow_pending_migration=True,
            )
        else:
            raise ValueError("Revision history matches neither migration source nor destination.")
        if not _constant_time_equal(_history_file_sha256(root), migrated_sha256):
            raise ValueError("Migrated history SHA-256 does not match the planned receipt.")
        receipt = _set_migration_phase(receipt, "history_committed")
        _write_migration_receipt_unlocked(root, receipt)
    else:
        _validate_migration_artifacts_unlocked(root, receipt)
        records = _load_revision_history_unlocked(
            root,
            allow_pending_migration=True,
        )

    if receipt["phase"] == "history_committed":
        _write_project_summary_unlocked(root, metadata, records)
        receipt = _set_migration_phase(receipt, "complete")
        _write_migration_receipt_unlocked(root, receipt)
    else:
        expected_summary = _render_summary(metadata, records).encode("utf-8")
        summary_path = root / PROJECT_SUMMARY_NAME
        if not summary_path.is_file() or not hmac.compare_digest(
            summary_path.read_bytes(), expected_summary
        ):
            _write_project_summary_unlocked(root, metadata, records)
    _validate_migration_artifacts_unlocked(root, receipt)
    return records


def _render_revision_history(records: Iterable[RevisionRecord]) -> str:
    return "".join(_canonical_json(asdict(record)) + "\n" for record in records)


def _write_revision_history(root: Path, records: list[RevisionRecord]) -> None:
    _atomic_write_text(root / REVISION_LOG_NAME, _render_revision_history(records))


def _load_project_record_unlocked(
    root: Path, *, require_exists: bool = False
) -> dict[str, object]:
    path = root / PROJECT_RECORD_NAME
    if not path.exists():
        if require_exists:
            raise ValueError(
                f"Revision history requires an existing {PROJECT_RECORD_NAME} with an immutable project_id."
            )
        return {
            "schema_version": PROJECT_RECORD_SCHEMA_VERSION,
            "project_id": _derived_project_id(root),
            "project_name": root.name,
            "project_goal": "Project goal has not been recorded yet.",
            "boundaries": [],
            "artifacts": [],
            "max_revision_rounds": MAX_REVISION_ROUNDS,
        }
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Invalid project record: {path}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"Invalid project record: {path}")
    _validate_project_record_payload(payload, path=path)
    return payload


def _project_id_from_metadata(metadata: Mapping[str, object]) -> str:
    if "project_id" not in metadata:
        raise ValueError(f"{PROJECT_RECORD_NAME} is missing project_id.")
    if not isinstance(metadata["project_id"], str):
        raise ValueError(f"{PROJECT_RECORD_NAME} project_id must be a string.")
    return _validate_identifier(metadata["project_id"], "project_id")


def _validate_project_record_payload(payload: Mapping[str, object], *, path: Path) -> None:
    actual = set(payload)
    missing = sorted(_PROJECT_RECORD_FIELDS - actual)
    unexpected = sorted(actual - _PROJECT_RECORD_FIELDS)
    if missing or unexpected:
        details = []
        if missing:
            details.append("missing fields: " + ", ".join(missing))
        if unexpected:
            details.append("unexpected fields: " + ", ".join(unexpected))
        raise ValueError(f"Invalid project record at {path}: {'; '.join(details)}")
    if type(payload["schema_version"]) is not int or payload["schema_version"] != PROJECT_RECORD_SCHEMA_VERSION:
        raise ValueError(
            f"Invalid project record at {path}: schema_version must be "
            f"{PROJECT_RECORD_SCHEMA_VERSION}."
        )
    if type(payload["max_revision_rounds"]) is not int or payload["max_revision_rounds"] != MAX_REVISION_ROUNDS:
        raise ValueError(
            f"Invalid project record at {path}: max_revision_rounds must be {MAX_REVISION_ROUNDS}."
        )
    for field_name in ("project_id", "project_name", "project_goal", "created_at", "updated_at"):
        value = payload[field_name]
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"Invalid project record at {path}: {field_name} must be text.")
    _validate_identifier(str(payload["project_id"]), "project_id")
    for field_name in ("boundaries", "artifacts"):
        value = payload[field_name]
        if not isinstance(value, list) or any(
            not isinstance(item, str) or not item.strip() for item in value
        ):
            raise ValueError(
                f"Invalid project record at {path}: {field_name} must be a list of text values."
            )


def _write_project_summary_unlocked(
    root: Path, metadata: dict[str, object], records: list[RevisionRecord]
) -> Path:
    path = root / PROJECT_SUMMARY_NAME
    _atomic_write_text(path, _render_summary(metadata, records))
    return path


def _render_summary(metadata: dict[str, object], records: list[RevisionRecord]) -> str:
    project_id = str(metadata.get("project_id") or "Not assigned")
    project_name = str(metadata.get("project_name") or "Unnamed project")
    project_goal = str(metadata.get("project_goal") or "Not recorded")
    boundaries = [str(item) for item in metadata.get("boundaries", [])]
    artifacts = [str(item) for item in metadata.get("artifacts", [])]
    lines = [
        "# Project Summary Log",
        "",
        "## Project",
        "",
        f"- ID: {project_id}",
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
                    f"- Revision ID: {record.revision_id}",
                    f"- Parent revision: {record.parent_revision_id or 'None'}",
                    f"- Time: {record.created_at}",
                    f"- Diagnosis: {record.diagnosis}",
                    f"- Status: {record.status}",
                    f"- Change: {record.summary}",
                    f"- Verification: {record.verification}",
                    f"- Integrity SHA-256: {record.record_sha256}",
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
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("w", encoding="utf-8", newline="") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _validate_identifier(value: str, field: str) -> str:
    cleaned = _required_text(value, field)
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", cleaned):
        raise ValueError(
            f"{field} must use 1-128 ASCII letters, numbers, dots, underscores, or hyphens."
        )
    return cleaned


def _required_text(value: str, field: str) -> str:
    cleaned = str(value).strip()
    if not cleaned:
        raise ValueError(f"{field} must not be empty.")
    return cleaned


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned or None


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


def _clean_items(values: Iterable[object]) -> list[str]:
    return [cleaned for value in values if (cleaned := str(value).strip())]


def _bullets(values: Iterable[str], *, indent: str = "") -> list[str]:
    return [f"{indent}- {value}" for value in values]


def _validate_digest_map(value: object) -> dict[str, str]:
    if not isinstance(value, dict):
        raise TypeError("artifact SHA-256 field must be an object")
    result: dict[str, str] = {}
    for key, digest in value.items():
        result[_required_text(str(key), "artifact path")] = _required_digest(
            digest, "artifact SHA-256"
        )
    return dict(sorted(result.items()))


def _required_digest(value: object, field: str) -> str:
    cleaned = _required_text(str(value), field).lower()
    if not re.fullmatch(r"[0-9a-f]{64}", cleaned):
        raise ValueError(f"{field} must be a lowercase hexadecimal SHA-256 digest")
    return cleaned


def _optional_digest(value: object) -> str | None:
    if value is None:
        return None
    return _required_digest(value, "previous_record_sha256")


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _history_file_sha256(root: Path) -> str:
    path = root / REVISION_LOG_NAME
    return _file_sha256(path) if path.exists() else hashlib.sha256(b"").hexdigest()


def _derived_project_id(root: Path) -> str:
    key = str(root.resolve())
    if os.name == "nt":
        key = key.casefold()
    return f"project-{hashlib.sha256(key.encode('utf-8')).hexdigest()[:24]}"


def _constant_time_equal(left: str, right: str) -> bool:
    return hmac.compare_digest(str(left), str(right))


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")
