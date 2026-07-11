from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import stat
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from .revision_governance import (
    RevisionConflictError,
    exclusive_file_lock,
    project_lock_path,
)


LIFECYCLE_SCHEMA_VERSION = 2
RUN_IDENTITY_NAME = "run_identity.json"
RUN_COMPLETION_NAME = "run_complete.json"
RUN_LOCK_NAME = ".run_lifecycle.lock"
RUN_DELETE_MARKER_NAME = ".run_delete_pending"

# Only these flat, generated files may be removed by ``replace`` or written by
# the transactional interface. User notes, source uploads, tables, and arbitrary
# directories are intentionally outside this allow-list.
SYSTEM_OWNED_ARTIFACTS = frozenset(
    {
        "agent_trace.json",
        "agent_trace.jsonl",
        "ai_task_spec.yaml",
        "alignment_trace.jsonl",
        "applied_evidence_contract.json",
        "annotation_map.json",
        "audit_report.md",
        "claim_table.csv",
        "comment_threads.md",
        "concept_alignment_table.csv",
        "discussion_plan.md",
        "evaluation_protocol.md",
        "evidence_contract.yaml",
        "evidence_map.json",
        "expert_interview_guide.md",
        "extracted_text.md",
        "extraction_warnings.md",
        "highlighted_spans.csv",
        "human_in_loop_plan.md",
        "implementation_routes.md",
        "llm_review.json",
        "manual_upload_fallback.md",
        "misalignment_risk_report.md",
        "ocr_quality_report.json",
        "painpoint_opportunity_matrix.csv",
        "priority_marks.md",
        "problem_card.md",
        "question_brief.md",
        "revision_suggestions.md",
        "run_manifest.json",
        "source_manifest.json",
        "stakeholder_map.md",
        "unknowns_to_validate.md",
        "workflow_map.md",
        "workbench_memory.json",
    }
)

# These directory names are narrow, project-owned snapshot boundaries. They
# are never accepted from arbitrary user input, and the lifecycle layer never
# follows symlinks while hashing them.
SYSTEM_SNAPSHOT_DIRECTORIES = frozenset({"extracted_tables", "source_files"})


class ProjectLifecycleError(RuntimeError):
    """Base class for safe run-directory errors."""


class ProjectIdentityMismatch(ProjectLifecycleError):
    """Raised when a directory belongs to another project or run."""


class RunConflictError(ProjectLifecycleError):
    """Raised when requested lifecycle mode conflicts with existing state."""


class UnsafeArtifactPath(ProjectLifecycleError):
    """Raised when a path is not a known, project-owned artifact."""


@dataclass(frozen=True)
class RunContext:
    path: Path
    project_id: str
    run_id: str
    mode: str
    owned_artifacts: tuple[str, ...]
    required_artifacts: tuple[str, ...] = ()
    snapshot_directories: tuple[str, ...] = ()
    workflow_type: str = "generic"
    run_spec_sha256: str = ""
    previous_run_id: str | None = None

    def transaction(self, *, lock_timeout: float = 5.0) -> "RunTransaction":
        return RunTransaction(self, lock_timeout=lock_timeout)


def allocate_run_directory(
    base_dir: str | Path,
    *,
    project_id: str,
    prefix: str | None = None,
    owned_artifacts: Iterable[str] = SYSTEM_OWNED_ARTIFACTS,
    required_artifacts: Iterable[str] = (),
    snapshot_directories: Iterable[str] = (),
    workflow_type: str = "generic",
    run_spec_sha256: str | None = None,
    lock_timeout: float = 5.0,
) -> RunContext:
    """Atomically allocate a unique, explicitly identified run directory."""

    clean_project_id = _validate_identifier(project_id, "project_id")
    clean_prefix = _validate_prefix(prefix) if prefix else clean_project_id
    base = Path(base_dir)
    base.mkdir(parents=True, exist_ok=True)
    for _ in range(100):
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        candidate = base / f"{clean_prefix}-{stamp}-{uuid.uuid4().hex[:8]}"
        try:
            candidate.mkdir()
        except FileExistsError:
            continue
        return prepare_run_directory(
            candidate,
            project_id=clean_project_id,
            mode="new",
            owned_artifacts=owned_artifacts,
            required_artifacts=required_artifacts,
            snapshot_directories=snapshot_directories,
            workflow_type=workflow_type,
            run_spec_sha256=run_spec_sha256,
            lock_timeout=lock_timeout,
        )
    raise RunConflictError("Could not allocate a unique run directory after 100 attempts.")


def prepare_run_directory(
    run_dir: str | Path,
    *,
    project_id: str,
    mode: str = "new",
    run_id: str | None = None,
    expected_run_id: str | None = None,
    owned_artifacts: Iterable[str] = SYSTEM_OWNED_ARTIFACTS,
    required_artifacts: Iterable[str] = (),
    snapshot_directories: Iterable[str] = (),
    workflow_type: str = "generic",
    run_spec_sha256: str | None = None,
    lock_timeout: float = 5.0,
) -> RunContext:
    """Prepare ``new``, ``resume``, or ``replace`` state safely.

    ``resume`` retains the existing run ID and is valid only for an incomplete
    run. ``replace`` verifies the existing identity, removes only allow-listed
    generated artifacts, and starts a new run ID. Unknown files are preserved.
    """

    clean_project_id = _validate_identifier(project_id, "project_id")
    clean_mode = str(mode).strip().lower()
    if clean_mode not in {"new", "resume", "replace"}:
        raise ValueError("mode must be one of: new, resume, replace.")
    requested_run_id = _validate_identifier(run_id, "run_id") if run_id else None
    clean_expected_run_id = (
        _validate_identifier(expected_run_id, "expected_run_id") if expected_run_id else None
    )
    if clean_mode in {"resume", "replace"} and clean_expected_run_id is None:
        raise ProjectIdentityMismatch(
            "expected_run_id is required for resume or replace; supply an independently "
            "reviewed run identity before reusing a directory."
        )
    requested_owned = _validate_owned_artifacts(owned_artifacts)
    requested_required = _validate_required_artifacts(required_artifacts)
    requested_snapshot_dirs = _validate_snapshot_directories(snapshot_directories)
    clean_workflow_type = _validate_workflow_type(workflow_type)
    clean_run_spec_sha256 = _validate_run_spec_sha256(
        run_spec_sha256 or _default_run_spec_sha256(clean_workflow_type)
    )

    root = Path(run_dir)
    root.mkdir(parents=True, exist_ok=True)
    try:
        with exclusive_file_lock(project_lock_path(root, RUN_LOCK_NAME), timeout=lock_timeout):
            delete_marker = root / RUN_DELETE_MARKER_NAME
            if delete_marker.exists() or delete_marker.is_symlink():
                raise RunConflictError(f"Run is pending deletion and cannot be reused: {root}")
            identity_path = root / RUN_IDENTITY_NAME
            if clean_mode == "new":
                non_lock_entries = [entry for entry in root.iterdir() if entry.name != RUN_LOCK_NAME]
                if non_lock_entries:
                    raise RunConflictError(
                        f"New mode requires an empty directory: {root}. "
                        "Use resume or replace only after verifying its identity."
                    )
                current_run_id = requested_run_id or _new_run_id()
                payload = _identity_payload(
                    project_id=clean_project_id,
                    run_id=current_run_id,
                    mode=clean_mode,
                    owned_artifacts=requested_owned,
                    required_artifacts=requested_required,
                    snapshot_directories=requested_snapshot_dirs,
                    workflow_type=clean_workflow_type,
                    run_spec_sha256=clean_run_spec_sha256,
                )
                _atomic_write_json(identity_path, payload)
                return _context_from_identity(root, payload)

            if not identity_path.is_file():
                raise RunConflictError(
                    f"Cannot {clean_mode} an unowned directory without {RUN_IDENTITY_NAME}: {root}"
                )
            existing = _load_identity_unlocked(root)
            _assert_identity(existing, project_id=clean_project_id, run_id=clean_expected_run_id)
            existing_run_id = str(existing["run_id"])

            if clean_mode == "resume":
                _assert_run_spec(
                    existing,
                    workflow_type=clean_workflow_type,
                    run_spec_sha256=clean_run_spec_sha256,
                )
                if requested_run_id and requested_run_id != existing_run_id:
                    raise ProjectIdentityMismatch(
                        f"Run identity mismatch: existing run_id={existing_run_id!r}, "
                        f"requested run_id={requested_run_id!r}."
                    )
                existing_owned = _validate_owned_artifacts(
                    existing.get("owned_artifacts", [])
                )
                if requested_owned != existing_owned:
                    raise RunConflictError(
                        "Resume requires the exact original owned-artifact declaration."
                    )
                if (root / RUN_COMPLETION_NAME).exists():
                    raise RunConflictError("Completed runs cannot be resumed; use replace explicitly.")
                effective_required = _validate_required_artifacts(
                    existing.get("required_artifacts", [])
                )
                if requested_required != effective_required:
                    raise RunConflictError(
                        "Resume requires the exact original required-artifact declaration."
                    )
                existing_snapshot_dirs = tuple(existing.get("snapshot_directories", []))
                if requested_snapshot_dirs != existing_snapshot_dirs:
                    raise RunConflictError(
                        "Resume requires the same snapshot directories as the original run."
                    )
                return RunContext(
                    path=root,
                    project_id=clean_project_id,
                    run_id=existing_run_id,
                    mode=clean_mode,
                    owned_artifacts=tuple(existing["owned_artifacts"]),
                    required_artifacts=effective_required,
                    snapshot_directories=existing_snapshot_dirs,
                    workflow_type=str(existing["workflow_type"]),
                    run_spec_sha256=str(existing["run_spec_sha256"]),
                    previous_run_id=_optional_string(existing.get("previous_run_id")),
                )

            existing_owned = _validate_owned_artifacts(existing.get("owned_artifacts", []))
            clearable = tuple(sorted(set(existing_owned) | set(requested_owned)))
            existing_snapshot_dirs = _validate_snapshot_directories(
                existing.get("snapshot_directories", [])
            )
            clearable_snapshot_dirs = tuple(
                sorted(set(existing_snapshot_dirs) | set(requested_snapshot_dirs))
            )
            next_run_id = requested_run_id or _new_run_id()
            if next_run_id == existing_run_id:
                raise RunConflictError("Replace mode requires a new run_id.")
            _preflight_owned_artifacts(root, clearable)
            _preflight_snapshot_directories(root, clearable_snapshot_dirs)
            (root / RUN_COMPLETION_NAME).unlink(missing_ok=True)
            _clear_owned_artifacts(root, clearable)
            _clear_snapshot_directories(root, clearable_snapshot_dirs)
            payload = _identity_payload(
                project_id=clean_project_id,
                run_id=next_run_id,
                mode=clean_mode,
                owned_artifacts=requested_owned,
                required_artifacts=requested_required,
                snapshot_directories=requested_snapshot_dirs,
                workflow_type=clean_workflow_type,
                run_spec_sha256=clean_run_spec_sha256,
                previous_run_id=existing_run_id,
                directory_created_at=_optional_string(existing.get("directory_created_at")),
            )
            _atomic_write_json(identity_path, payload)
            return _context_from_identity(root, payload)
    except RevisionConflictError as exc:
        raise RunConflictError(str(exc)) from exc


def load_run_identity(run_dir: str | Path, *, lock_timeout: float = 5.0) -> dict[str, object]:
    root = Path(run_dir)
    if not root.is_dir():
        raise RunConflictError(f"Run directory not found: {root}")
    try:
        with exclusive_file_lock(project_lock_path(root, RUN_LOCK_NAME), timeout=lock_timeout):
            return _load_identity_unlocked(root)
    except RevisionConflictError as exc:
        raise RunConflictError(str(exc)) from exc


def load_run_completion(run_dir: str | Path, *, lock_timeout: float = 5.0) -> dict[str, object]:
    root = Path(run_dir)
    try:
        with exclusive_file_lock(project_lock_path(root, RUN_LOCK_NAME), timeout=lock_timeout):
            delete_marker = root / RUN_DELETE_MARKER_NAME
            if delete_marker.exists() or delete_marker.is_symlink():
                raise RunConflictError(f"Run is pending deletion: {root}")
            identity = _load_identity_unlocked(root)
            path = root / RUN_COMPLETION_NAME
            if not path.is_file():
                raise RunConflictError(f"Run is incomplete: {root}")
            payload = _load_json_object(path)
            if int(payload.get("schema_version", 0)) != LIFECYCLE_SCHEMA_VERSION:
                raise RunConflictError(f"Unsupported run completion schema at {path}")
            _assert_identity(
                payload,
                project_id=str(identity["project_id"]),
                run_id=str(identity["run_id"]),
            )
            _verify_completion_artifacts(root, identity, payload)
            return payload
    except RevisionConflictError as exc:
        raise RunConflictError(str(exc)) from exc


def is_run_complete(run_dir: str | Path) -> bool:
    try:
        load_run_completion(run_dir)
    except (OSError, ProjectLifecycleError, ValueError):
        return False
    return True


def snapshot_completed_run(
    run_dir: str | Path, *, lock_timeout: float = 5.0
) -> dict[str, bytes]:
    """Return one lock-protected, hash-verified byte snapshot for sharing.

    Only files committed in ``run_complete.json`` plus the two lifecycle
    records are returned. Unknown notes, credentials, and post-run exports are
    deliberately outside this allow-list.
    """

    root = Path(run_dir)
    try:
        with exclusive_file_lock(project_lock_path(root, RUN_LOCK_NAME), timeout=lock_timeout):
            delete_marker = root / RUN_DELETE_MARKER_NAME
            if delete_marker.exists() or delete_marker.is_symlink():
                raise RunConflictError(f"Run is pending deletion: {root}")
            identity = _load_identity_unlocked(root)
            completion_path = root / RUN_COMPLETION_NAME
            if not completion_path.is_file():
                raise RunConflictError(f"Run is incomplete: {root}")
            completion = _load_json_object(completion_path)
            if int(completion.get("schema_version", 0)) != LIFECYCLE_SCHEMA_VERSION:
                raise RunConflictError(
                    f"Unsupported run completion schema at {completion_path}"
                )
            _assert_identity(
                completion,
                project_id=str(identity["project_id"]),
                run_id=str(identity["run_id"]),
            )
            _verify_completion_artifacts(root, identity, completion)

            hashes = completion["artifact_sha256"]
            assert isinstance(hashes, dict)
            snapshot: dict[str, bytes] = {}
            for raw_name, raw_digest in sorted(hashes.items()):
                name = str(raw_name)
                data = (root / Path(name)).read_bytes()
                digest = hashlib.sha256(data).hexdigest()
                if digest != str(raw_digest):
                    raise RunConflictError(
                        f"Completed artifact changed while creating snapshot: {name}"
                    )
                snapshot[name] = data
            snapshot[RUN_IDENTITY_NAME] = (root / RUN_IDENTITY_NAME).read_bytes()
            snapshot[RUN_COMPLETION_NAME] = completion_path.read_bytes()
            return snapshot
    except RevisionConflictError as exc:
        raise RunConflictError(str(exc)) from exc


def delete_run_directory(
    run_dir: str | Path,
    *,
    project_id: str,
    run_id: str | None = None,
    allow_incomplete: bool = False,
    trusted_parent: str | Path | None = None,
    lock_timeout: float = 5.0,
) -> None:
    """Identity-check, fence future writers, then delete one explicit run.

    The deletion marker is written while holding the same lifecycle lock used
    by writers. If deletion is interrupted, later writers fail closed instead
    of reviving a partially deleted run.
    """

    root = Path(run_dir)
    tombstone: Path | None = None
    try:
        with exclusive_file_lock(project_lock_path(root, RUN_LOCK_NAME), timeout=lock_timeout):
            if not root.is_dir() or _is_link_or_reparse(root):
                raise RunConflictError(f"Run directory is missing or unsafe: {root}")
            marker_path = root / RUN_DELETE_MARKER_NAME
            marker_present = marker_path.exists() or marker_path.is_symlink()
            if marker_present:
                if _is_link_or_reparse(marker_path) or not marker_path.is_file():
                    raise RunConflictError(
                        f"Pending deletion marker is not a safe regular file: {marker_path}"
                    )
                marker = _load_json_object(marker_path)
                if int(marker.get("schema_version", 0)) != LIFECYCLE_SCHEMA_VERSION:
                    raise RunConflictError(f"Unsupported deletion marker schema at {marker_path}")
                _assert_identity(marker, project_id=project_id, run_id=run_id)
                identity_path = root / RUN_IDENTITY_NAME
                identity_present = identity_path.exists() or identity_path.is_symlink()
                if identity_present:
                    if _is_link_or_reparse(identity_path) or not identity_path.is_file():
                        raise RunConflictError(f"Run identity is unsafe: {identity_path}")
                    identity = _load_identity_unlocked(root)
                    _assert_identity(
                        identity,
                        project_id=str(marker["project_id"]),
                        run_id=str(marker["run_id"]),
                    )
                else:
                    if trusted_parent is None:
                        raise RunConflictError(
                            "Marker-only deletion retry requires an explicitly trusted parent directory."
                        )
                    expected_parent = Path(trusted_parent).resolve()
                    if root.resolve().parent != expected_parent:
                        raise RunConflictError(
                            "Marker-only deletion retry is outside the trusted parent directory."
                        )
                    identity = marker
            else:
                identity = _load_identity_unlocked(root)
                _assert_identity(identity, project_id=project_id, run_id=run_id)
            completion_path = root / RUN_COMPLETION_NAME
            if not marker_present and not allow_incomplete:
                if not completion_path.is_file():
                    raise RunConflictError(f"Run is incomplete: {root}")
                completion = _load_json_object(completion_path)
                if int(completion.get("schema_version", 0)) != LIFECYCLE_SCHEMA_VERSION:
                    raise RunConflictError(
                        f"Unsupported run completion schema at {completion_path}"
                    )
                _assert_identity(
                    completion,
                    project_id=str(identity["project_id"]),
                    run_id=str(identity["run_id"]),
                )
                _verify_completion_artifacts(root, identity, completion)
            if not marker_present:
                _atomic_write_json(
                    marker_path,
                    {
                        "schema_version": LIFECYCLE_SCHEMA_VERSION,
                        "project_id": str(identity["project_id"]),
                        "run_id": str(identity["run_id"]),
                        "marked_at": _utc_now(),
                    },
                )
            tombstone = root.parent / (
                f".{root.name}.{identity['run_id']}.{uuid.uuid4().hex}.delete-tombstone"
            )
            if tombstone.exists() or tombstone.is_symlink():
                raise RunConflictError(f"Deletion tombstone already exists: {tombstone}")
            # Renaming is the delete commit point. A later process may create a
            # new run at the original path, but cleanup below can only remove
            # this uniquely named, identity-checked directory.
            os.replace(root, tombstone)
    except RevisionConflictError as exc:
        raise RunConflictError(str(exc)) from exc
    assert tombstone is not None
    try:
        shutil.rmtree(tombstone)
    except Exception:
        # Preserve the old retry path where possible. If another run already
        # occupies it, leave the uniquely named marker-fenced tombstone for an
        # explicit trusted-parent cleanup instead of touching the new run.
        try:
            if tombstone.exists() and not root.exists():
                os.replace(tombstone, root)
        except OSError:
            pass
        raise


def load_pending_deletion(
    run_dir: str | Path, *, lock_timeout: float = 5.0
) -> dict[str, object]:
    """Load and validate a pending-deletion marker without trusting it globally."""

    root = Path(run_dir)
    try:
        with exclusive_file_lock(project_lock_path(root, RUN_LOCK_NAME), timeout=lock_timeout):
            marker_path = root / RUN_DELETE_MARKER_NAME
            marker_present = marker_path.exists() or marker_path.is_symlink()
            if not marker_present:
                raise RunConflictError(f"Pending deletion marker not found: {root}")
            if _is_link_or_reparse(marker_path) or not marker_path.is_file():
                raise RunConflictError(
                    f"Pending deletion marker is not a safe regular file: {marker_path}"
                )
            marker = _load_json_object(marker_path)
            if int(marker.get("schema_version", 0)) != LIFECYCLE_SCHEMA_VERSION:
                raise RunConflictError(f"Unsupported deletion marker schema at {marker_path}")
            marker["project_id"] = _validate_identifier(
                str(marker.get("project_id", "")), "project_id"
            )
            marker["run_id"] = _validate_identifier(
                str(marker.get("run_id", "")), "run_id"
            )
            identity_path = root / RUN_IDENTITY_NAME
            if identity_path.exists() or identity_path.is_symlink():
                if _is_link_or_reparse(identity_path) or not identity_path.is_file():
                    raise RunConflictError(f"Run identity is unsafe: {identity_path}")
                identity = _load_identity_unlocked(root)
                _assert_identity(
                    identity,
                    project_id=str(marker["project_id"]),
                    run_id=str(marker["run_id"]),
                )
            return marker
    except RevisionConflictError as exc:
        raise RunConflictError(str(exc)) from exc


class RunTransaction:
    """Stage generated files and publish a completion marker last."""

    def __init__(self, context: RunContext, *, lock_timeout: float = 5.0) -> None:
        self.context = context
        self.lock_timeout = lock_timeout
        self._lock_manager = None
        self._staging: Path | None = None
        self._staged_names: set[str] = set()
        self._committed = False

    def __enter__(self) -> "RunTransaction":
        self._lock_manager = exclusive_file_lock(
            project_lock_path(self.context.path, RUN_LOCK_NAME), timeout=self.lock_timeout
        )
        try:
            self._lock_manager.__enter__()
        except RevisionConflictError as exc:
            raise RunConflictError(str(exc)) from exc
        try:
            delete_marker = self.context.path / RUN_DELETE_MARKER_NAME
            if delete_marker.exists() or delete_marker.is_symlink():
                raise RunConflictError("Run is pending deletion and cannot be written.")
            identity = _load_identity_unlocked(self.context.path)
            _assert_identity(
                identity,
                project_id=self.context.project_id,
                run_id=self.context.run_id,
            )
            if (self.context.path / RUN_COMPLETION_NAME).exists():
                raise RunConflictError("Run is already complete; use replace before writing again.")
            self._staging = self.context.path / f".run-txn-{uuid.uuid4().hex}"
            self._staging.mkdir()
            return self
        except Exception:
            self._release_lock()
            raise

    def stage_path(self, artifact_name: str) -> Path:
        self._ensure_active()
        name = _validate_artifact_name(artifact_name, self.context.owned_artifacts)
        assert self._staging is not None
        self._staged_names.add(name)
        return self._staging / name

    def write_text(self, artifact_name: str, content: str, *, encoding: str = "utf-8") -> Path:
        path = self.stage_path(artifact_name)
        # Keep byte-level hashes reproducible across Windows and POSIX.
        with path.open("w", encoding=encoding, newline="") as handle:
            handle.write(content)
        return path

    def write_bytes(self, artifact_name: str, content: bytes) -> Path:
        path = self.stage_path(artifact_name)
        path.write_bytes(content)
        return path

    def commit(self) -> dict[str, object]:
        self._ensure_active()
        if self._committed:
            raise RunConflictError("Transaction was already committed.")
        assert self._staging is not None

        for name in sorted(self._staged_names):
            staged = self._staging / name
            if staged.is_symlink() or not staged.is_file():
                raise RunConflictError(f"Staged artifact was not written: {name}")
            destination = self.context.path / name
            if destination.exists() and destination.is_dir():
                raise UnsafeArtifactPath(f"Owned artifact destination is a directory: {name}")
            os.replace(staged, destination)

        artifact_hashes = _hash_present_artifacts(
            self.context.path,
            {*self.context.owned_artifacts, *self.context.required_artifacts},
            snapshot_directories=self.context.snapshot_directories,
        )
        _reject_undeclared_system_artifacts(
            self.context.path,
            declared={*self.context.owned_artifacts, *self.context.required_artifacts},
        )
        missing_required = [
            name for name in self.context.required_artifacts if name not in artifact_hashes
        ]
        if missing_required:
            raise RunConflictError(
                "Required run artifacts were not written: " + ", ".join(missing_required)
            )
        completion: dict[str, object] = {
            "schema_version": LIFECYCLE_SCHEMA_VERSION,
            "project_id": self.context.project_id,
            "run_id": self.context.run_id,
            "completed_at": _utc_now(),
            "run_identity_sha256": _file_sha256(
                self.context.path / RUN_IDENTITY_NAME
            ),
            "artifact_sha256": artifact_hashes,
        }
        # This marker is the commit point. Any exception before this atomic
        # replace leaves the run observably incomplete.
        _atomic_write_json(self.context.path / RUN_COMPLETION_NAME, completion)
        self._committed = True
        return completion

    def __exit__(self, exc_type, exc, traceback) -> bool:
        try:
            if exc_type is None and not self._committed:
                self.commit()
        finally:
            self._cleanup_staging()
            self._release_lock()
        return False

    def _ensure_active(self) -> None:
        if self._staging is None or self._lock_manager is None:
            raise RunConflictError("Transaction is not active.")

    def _cleanup_staging(self) -> None:
        if self._staging is not None and self._staging.exists():
            shutil.rmtree(self._staging)
        self._staging = None

    def _release_lock(self) -> None:
        if self._lock_manager is not None:
            self._lock_manager.__exit__(None, None, None)
            self._lock_manager = None


def _identity_payload(
    *,
    project_id: str,
    run_id: str,
    mode: str,
    owned_artifacts: tuple[str, ...],
    required_artifacts: tuple[str, ...],
    snapshot_directories: tuple[str, ...],
    workflow_type: str,
    run_spec_sha256: str,
    previous_run_id: str | None = None,
    directory_created_at: str | None = None,
) -> dict[str, object]:
    now = _utc_now()
    return {
        "schema_version": LIFECYCLE_SCHEMA_VERSION,
        "project_id": project_id,
        "run_id": run_id,
        "previous_run_id": previous_run_id,
        "mode": mode,
        "directory_created_at": directory_created_at or now,
        "run_created_at": now,
        "owned_artifacts": list(owned_artifacts),
        "required_artifacts": list(required_artifacts),
        "snapshot_directories": list(snapshot_directories),
        "workflow_type": workflow_type,
        "run_spec_sha256": run_spec_sha256,
    }


def _context_from_identity(root: Path, payload: dict[str, object]) -> RunContext:
    return RunContext(
        path=root,
        project_id=str(payload["project_id"]),
        run_id=str(payload["run_id"]),
        mode=str(payload["mode"]),
        owned_artifacts=tuple(str(item) for item in payload["owned_artifacts"]),
        required_artifacts=tuple(str(item) for item in payload.get("required_artifacts", [])),
        snapshot_directories=tuple(
            str(item) for item in payload.get("snapshot_directories", [])
        ),
        workflow_type=str(payload["workflow_type"]),
        run_spec_sha256=str(payload["run_spec_sha256"]),
        previous_run_id=_optional_string(payload.get("previous_run_id")),
    )


def _load_identity_unlocked(root: Path) -> dict[str, object]:
    path = root / RUN_IDENTITY_NAME
    if not path.is_file():
        raise RunConflictError(f"Run identity not found: {path}")
    payload = _load_json_object(path)
    if int(payload.get("schema_version", 0)) != LIFECYCLE_SCHEMA_VERSION:
        raise RunConflictError(f"Unsupported run identity schema at {path}")
    payload["project_id"] = _validate_identifier(str(payload.get("project_id", "")), "project_id")
    payload["run_id"] = _validate_identifier(str(payload.get("run_id", "")), "run_id")
    payload["owned_artifacts"] = list(
        _validate_owned_artifacts(payload.get("owned_artifacts", []))
    )
    payload["required_artifacts"] = list(
        _validate_required_artifacts(payload.get("required_artifacts", []))
    )
    payload["snapshot_directories"] = list(
        _validate_snapshot_directories(payload.get("snapshot_directories", []))
    )
    payload["workflow_type"] = _validate_workflow_type(
        str(payload.get("workflow_type", ""))
    )
    payload["run_spec_sha256"] = _validate_run_spec_sha256(
        str(payload.get("run_spec_sha256", ""))
    )
    return payload


def _assert_run_spec(
    payload: dict[str, object], *, workflow_type: str, run_spec_sha256: str
) -> None:
    existing_workflow = str(payload.get("workflow_type", ""))
    existing_spec = str(payload.get("run_spec_sha256", ""))
    if existing_workflow != workflow_type:
        raise ProjectIdentityMismatch(
            f"Workflow mismatch: existing workflow_type={existing_workflow!r}, "
            f"requested workflow_type={workflow_type!r}. Use replace for a new workflow."
        )
    if existing_spec != run_spec_sha256:
        raise ProjectIdentityMismatch(
            "Run specification mismatch. Resume may only continue the exact original inputs "
            "and configuration; use replace for a changed specification."
        )


def _assert_identity(
    payload: dict[str, object], *, project_id: str, run_id: str | None = None
) -> None:
    actual_project_id = str(payload.get("project_id", ""))
    actual_run_id = str(payload.get("run_id", ""))
    if actual_project_id != project_id:
        raise ProjectIdentityMismatch(
            f"Project identity mismatch: existing project_id={actual_project_id!r}, "
            f"requested project_id={project_id!r}."
        )
    if run_id is not None and actual_run_id != run_id:
        raise ProjectIdentityMismatch(
            f"Run identity mismatch: existing run_id={actual_run_id!r}, requested run_id={run_id!r}."
        )


def _clear_owned_artifacts(root: Path, names: Iterable[str]) -> None:
    _preflight_owned_artifacts(root, names)
    for name in names:
        path = root / name
        if path.is_symlink() or path.is_file():
            path.unlink()


def _preflight_owned_artifacts(root: Path, names: Iterable[str]) -> None:
    for name in names:
        path = root / name
        if path.exists() and not path.is_symlink() and not path.is_file():
            raise UnsafeArtifactPath(
                f"Refusing to recursively remove directory at owned artifact path: {name}"
            )


def _preflight_snapshot_directories(root: Path, names: Iterable[str]) -> None:
    """Verify every run-owned snapshot tree before replace removes any output."""

    for name in names:
        directory = root / name
        if not directory.exists():
            if directory.is_symlink():
                raise UnsafeArtifactPath(f"Snapshot directory is unsafe: {name}")
            continue
        # The traversal rejects root/child links, junctions, non-files, and
        # paths resolving outside the run before any prior output is removed.
        snapshot_directory_files(root, name)


def _clear_snapshot_directories(root: Path, names: Iterable[str]) -> None:
    _preflight_snapshot_directories(root, names)
    for name in names:
        directory = root / name
        if directory.exists():
            shutil.rmtree(directory)


def _verify_completion_artifacts(
    root: Path, identity: dict[str, object], completion: dict[str, object]
) -> None:
    identity_digest = str(completion.get("run_identity_sha256", "")).lower()
    if not re.fullmatch(r"[0-9a-f]{64}", identity_digest):
        raise RunConflictError("Invalid completion record: run_identity_sha256 is missing.")
    if _file_sha256(root / RUN_IDENTITY_NAME) != identity_digest:
        raise RunConflictError("Run identity SHA-256 mismatch after completion.")
    hashes = completion.get("artifact_sha256")
    if not isinstance(hashes, dict):
        raise RunConflictError("Invalid completion record: artifact_sha256 must be an object.")
    owned = set(str(item) for item in identity["owned_artifacts"])
    required = set(str(item) for item in identity.get("required_artifacts", []))
    snapshot_directories = tuple(
        str(item) for item in identity.get("snapshot_directories", [])
    )
    current_hashes = _hash_present_artifacts(
        root,
        owned | required,
        snapshot_directories=snapshot_directories,
    )
    _reject_undeclared_system_artifacts(root, declared=owned | required)
    allowed = set(current_hashes)
    for raw_name, raw_digest in hashes.items():
        name = str(raw_name)
        if name not in allowed:
            raise RunConflictError(f"Completion record contains an undeclared artifact: {name!r}")
        digest = str(raw_digest).lower()
        if not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise RunConflictError(f"Invalid completion SHA-256 for artifact: {name}")
        path = root / name
        if path.is_symlink() or not path.is_file():
            raise RunConflictError(f"Completed artifact is missing or unsafe: {name}")
        if _file_sha256(path) != digest:
            raise RunConflictError(f"Completed artifact SHA-256 mismatch: {name}")
    missing_required = sorted(required - set(str(name) for name in hashes))
    if missing_required:
        raise RunConflictError(
            "Completion record is missing required artifacts: " + ", ".join(missing_required)
        )
    recorded_names = {str(name) for name in hashes}
    if recorded_names != allowed:
        missing = sorted(allowed - recorded_names)
        unexpected = sorted(recorded_names - allowed)
        details = []
        if missing:
            details.append("unrecorded current artifacts: " + ", ".join(missing))
        if unexpected:
            details.append("recorded artifacts no longer declared: " + ", ".join(unexpected))
        raise RunConflictError("Completed run snapshot changed; " + "; ".join(details))


def _validate_owned_artifacts(values: Iterable[object]) -> tuple[str, ...]:
    names: set[str] = set()
    for value in values:
        name = str(value).strip()
        if name not in SYSTEM_OWNED_ARTIFACTS:
            raise UnsafeArtifactPath(f"Artifact is not in the system-owned allow-list: {name!r}")
        names.add(name)
    return tuple(sorted(names))


def _reject_undeclared_system_artifacts(root: Path, *, declared: set[str]) -> None:
    unexpected = sorted(
        name
        for name in SYSTEM_OWNED_ARTIFACTS - declared
        if (root / name).exists() or (root / name).is_symlink()
    )
    if unexpected:
        raise RunConflictError(
            "Run contains generated artifacts outside this workflow declaration: "
            + ", ".join(unexpected)
        )


def _validate_required_artifacts(values: Iterable[object]) -> tuple[str, ...]:
    names: set[str] = set()
    reserved = {
        RUN_IDENTITY_NAME,
        RUN_COMPLETION_NAME,
        RUN_LOCK_NAME,
        RUN_DELETE_MARKER_NAME,
    }
    for value in values:
        name = str(value).strip()
        if not name or Path(name).name != name or name in reserved:
            raise UnsafeArtifactPath(
                f"Required artifact must be a safe flat generated filename: {name!r}"
            )
        names.add(name)
    return tuple(sorted(names))


def _validate_snapshot_directories(values: Iterable[object]) -> tuple[str, ...]:
    names: set[str] = set()
    for value in values:
        name = str(value).strip()
        if name not in SYSTEM_SNAPSHOT_DIRECTORIES:
            raise UnsafeArtifactPath(
                f"Snapshot directory is not in the system allow-list: {name!r}"
            )
        names.add(name)
    return tuple(sorted(names))


def _validate_artifact_name(value: str, allowed: Iterable[str]) -> str:
    name = str(value).strip()
    if name not in set(allowed) or name not in SYSTEM_OWNED_ARTIFACTS:
        raise UnsafeArtifactPath(f"Artifact is not owned by this run: {name!r}")
    if Path(name).name != name:
        raise UnsafeArtifactPath(f"Nested or absolute artifact path is forbidden: {name!r}")
    return name


def _validate_identifier(value: str, field: str) -> str:
    cleaned = str(value).strip()
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", cleaned):
        raise ValueError(
            f"{field} must use 1-128 ASCII letters, numbers, dots, underscores, or hyphens."
        )
    return cleaned


def _validate_prefix(value: str) -> str:
    cleaned = str(value).strip()
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}", cleaned):
        raise ValueError("prefix must be a filesystem-safe ASCII identifier.")
    return cleaned


def _new_run_id() -> str:
    return f"run-{uuid.uuid4().hex}"


def _hash_present_artifacts(
    root: Path,
    names: Iterable[str],
    *,
    snapshot_directories: Iterable[str] = (),
) -> dict[str, str]:
    result: dict[str, str] = {}
    for name in sorted(names):
        path = root / name
        if path.is_file() and not path.is_symlink():
            result[name] = _file_sha256(path)
    for directory_name in _validate_snapshot_directories(snapshot_directories):
        for path in snapshot_directory_files(root, directory_name):
            relative = path.relative_to(root).as_posix()
            result[relative] = _file_sha256(path)
    return result


def snapshot_directory_files(root: str | Path, directory_name: str) -> tuple[Path, ...]:
    """List one allowed snapshot tree without following symlinks or junctions."""

    base = Path(root)
    name = _validate_snapshot_directories((directory_name,))[0]
    directory = base / name
    if not directory.exists():
        return ()
    if _is_link_or_reparse(directory) or not directory.is_dir():
        raise UnsafeArtifactPath(f"Snapshot directory is missing or unsafe: {name}")

    base_resolved = base.resolve()
    files: list[Path] = []
    for current, dirnames, filenames in os.walk(directory, followlinks=False):
        current_path = Path(current)
        safe_directories: list[str] = []
        for child_name in sorted(dirnames):
            child = current_path / child_name
            if _is_link_or_reparse(child):
                raise UnsafeArtifactPath(
                    f"Links and junctions are forbidden in run snapshot directories: {child}"
                )
            safe_directories.append(child_name)
        dirnames[:] = safe_directories
        for filename in sorted(filenames):
            path = current_path / filename
            if _is_link_or_reparse(path) or not path.is_file():
                raise UnsafeArtifactPath(
                    f"Unsafe file in run snapshot directory: {path}"
                )
            try:
                path.resolve().relative_to(base_resolved)
            except ValueError as exc:
                raise UnsafeArtifactPath(
                    f"Snapshot file resolves outside the run directory: {path}"
                ) from exc
            files.append(path)
    return tuple(sorted(files))


def _is_link_or_reparse(path: Path) -> bool:
    if path.is_symlink():
        return True
    try:
        attributes = getattr(os.lstat(path), "st_file_attributes", 0)
    except OSError:
        return True
    return bool(attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))


def is_link_or_reparse(path: str | Path) -> bool:
    """Return whether a path is a symlink, junction, or other reparse point."""

    return _is_link_or_reparse(Path(path))


def _validate_workflow_type(value: str) -> str:
    cleaned = str(value).strip()
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", cleaned):
        raise ValueError(
            "workflow_type must use 1-128 ASCII letters, numbers, dots, underscores, or hyphens."
        )
    return cleaned


def _validate_run_spec_sha256(value: str) -> str:
    cleaned = str(value).strip().lower()
    if not re.fullmatch(r"[0-9a-f]{64}", cleaned):
        raise ValueError("run_spec_sha256 must be a lowercase SHA-256 digest.")
    return cleaned


def _default_run_spec_sha256(workflow_type: str) -> str:
    payload = json.dumps(
        {"workflow_type": workflow_type}, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _atomic_write_json(path: Path, payload: dict[str, object]) -> None:
    text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("w", encoding="utf-8", newline="") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _load_json_object(path: Path) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RunConflictError(f"Invalid lifecycle record: {path}") from exc
    if not isinstance(payload, dict):
        raise RunConflictError(f"Invalid lifecycle record: {path}")
    return payload


def _optional_string(value: object) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned or None


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")
