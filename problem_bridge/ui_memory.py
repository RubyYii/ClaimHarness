from __future__ import annotations

import json
from pathlib import Path
from typing import Any


DEFAULT_MEMORY_PATH = Path("outputs/ui_memory/workbench_memory.json")
SENSITIVE_KEY_PARTS = ("api_key", "apikey", "token", "secret", "password")


def sanitize_memory_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Return a JSON-safe copy with API keys and other secrets removed."""

    return {
        key: _sanitize_value(value)
        for key, value in payload.items()
        if not _is_sensitive_key(key)
    }


def load_workbench_memory(path: Path = DEFAULT_MEMORY_PATH) -> dict[str, Any]:
    if not path.exists():
        return {}

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}

    if not isinstance(data, dict):
        return {}
    return sanitize_memory_payload(data)


def save_workbench_memory(
    payload: dict[str, Any],
    path: Path = DEFAULT_MEMORY_PATH,
) -> Path:
    sanitized = sanitize_memory_payload(payload)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(sanitized, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return path


def clear_workbench_memory(path: Path = DEFAULT_MEMORY_PATH) -> None:
    if path.exists():
        path.unlink()


def _sanitize_value(value: Any) -> Any:
    if isinstance(value, dict):
        return sanitize_memory_payload(value)
    if isinstance(value, list):
        return [_sanitize_value(item) for item in value]
    return value


def _is_sensitive_key(key: str) -> bool:
    normalized = key.lower().replace("-", "_").replace(" ", "_")
    return any(part in normalized for part in SENSITIVE_KEY_PARTS)
