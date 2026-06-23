import json
from pathlib import Path
from typing import Any

from .schemas import AuditEvent


class AuditLogger:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._step = 0
        self.path.write_text("", encoding="utf-8")

    def log(self, module: str, message: str, data: dict[str, Any] | None = None) -> AuditEvent:
        self._step += 1
        event = AuditEvent(
            step=self._step,
            module=module,
            message=message,
            data=data or {},
        )
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event.model_dump(), ensure_ascii=False) + "\n")
        return event
