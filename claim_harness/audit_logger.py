import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from .schemas import AuditEvent


class AuditLogger:
    def __init__(self, path: str | Path, *, run_id: str | None = None) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._step = 0
        self.run_id = run_id or uuid4().hex
        self.started_at = _utc_now()
        self.path.write_text("", encoding="utf-8")

    def log(self, module: str, message: str, data: dict[str, Any] | None = None) -> AuditEvent:
        self._step += 1
        event = AuditEvent(
            step=self._step,
            module=module,
            message=message,
            data=data or {},
            run_id=self.run_id,
            created_at=_utc_now(),
        )
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event.model_dump(), ensure_ascii=False) + "\n")
        return event


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
