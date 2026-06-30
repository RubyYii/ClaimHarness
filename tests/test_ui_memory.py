from pathlib import Path

from problem_bridge.ui_memory import (
    clear_workbench_memory,
    load_workbench_memory,
    save_workbench_memory,
    sanitize_memory_payload,
)


def test_sanitize_memory_payload_removes_api_keys_and_tokens():
    payload = {
        "provider": "qwen",
        "api_key": "secret-key",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "model": "qwen-plus",
        "domain_draft": {"repeated_work": "review reports"},
        "nested": {
            "DEEPSEEK_API_KEY": "secret-deepseek",
            "token": "secret-token",
            "safe_note": "keep me",
        },
    }

    sanitized = sanitize_memory_payload(payload)

    assert sanitized["provider"] == "qwen"
    assert sanitized["model"] == "qwen-plus"
    assert sanitized["domain_draft"]["repeated_work"] == "review reports"
    assert "api_key" not in sanitized
    assert "DEEPSEEK_API_KEY" not in sanitized["nested"]
    assert "token" not in sanitized["nested"]
    assert sanitized["nested"]["safe_note"] == "keep me"


def test_save_load_and_clear_workbench_memory_round_trip(tmp_path):
    memory_path = tmp_path / "workbench_memory.json"

    saved_path = save_workbench_memory(
        {
            "provider": "deepseek",
            "api_key": "do-not-save",
            "model": "deepseek-chat",
            "last_output_dir": "outputs/ui_runs/demo",
        },
        memory_path,
    )

    assert saved_path == memory_path
    loaded = load_workbench_memory(memory_path)
    assert loaded == {
        "provider": "deepseek",
        "model": "deepseek-chat",
        "last_output_dir": "outputs/ui_runs/demo",
    }
    assert "do-not-save" not in memory_path.read_text(encoding="utf-8")

    clear_workbench_memory(memory_path)

    assert not memory_path.exists()
    assert load_workbench_memory(memory_path) == {}
