"""Append-only, hash-linked local notes outside immutable audit packages."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from problem_bridge.project_lifecycle import is_link_or_reparse
from problem_bridge.revision_governance import exclusive_file_lock
from .run_records import _atomic_write


def digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     allow_nan=False).encode("utf-8")).hexdigest()


class Journal:
    """One explicit context, monotonically numbered events, optimistic writes.

    Hashes detect accidental edits, not malicious rewriting or actor identity.
    Callers must retain the revision displayed by the form until it is submitted.
    """

    def __init__(self, workspace: Path, context: dict):
        self.context = context
        self.directory = workspace.absolute() / ".continuity"
        self.path = self.directory / (digest(context) + ".json")

    def _safe(self) -> None:
        for path in (self.path, self.directory, *self.directory.parents):
            if (path.exists() or path.is_symlink()) and is_link_or_reparse(path):
                raise ValueError("Linked continuity paths are not allowed.")

    def read(self) -> dict:
        self._safe()
        if not self.path.exists():
            return {"schema_version": 1, "context": self.context, "revision": 0, "events": []}
        value = json.loads(self.path.read_text(encoding="utf-8"))
        if value.get("schema_version") != 1 or value.get("context") != self.context:
            raise ValueError("Unknown or mismatched continuity record.")
        previous = ""
        for number, item in enumerate(value["events"], 1):
            body = {k: v for k, v in item.items() if k != "sha256"}
            if item["revision"] != number or item["previous_sha256"] != previous or digest(body) != item["sha256"]:
                raise ValueError("Continuity history failed integrity checks.")
            previous = item["sha256"]
        if value["revision"] != len(value["events"]):
            raise ValueError("Continuity revision does not match its history.")
        return value

    def append(self, kind: str, payload: dict, *, expected_revision: int) -> dict:
        self._safe()
        self.directory.mkdir(parents=True, exist_ok=True)
        lock = self.path.with_suffix(".lock")
        if (lock.exists() or lock.is_symlink()) and is_link_or_reparse(lock):
            raise ValueError("Linked continuity locks are not allowed.")
        with exclusive_file_lock(lock):
            value = self.read()
            if value["revision"] != expected_revision:
                raise ValueError("Stale page: newer changes exist. Reload and review them before submitting.")
            event = {"revision": expected_revision + 1, "kind": kind, "payload": payload,
                     "recorded_at": datetime.now(timezone.utc).isoformat(),
                     "previous_sha256": value["events"][-1]["sha256"] if value["events"] else ""}
            event["sha256"] = digest(event)
            value["events"].append(event)
            value["revision"] += 1
            _atomic_write(self.path, json.dumps(value, ensure_ascii=False, indent=2) + "\n")
            return value
