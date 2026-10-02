"""The published pilot must restore its ignored cache without changing evidence."""
import importlib.util
import io
import json
from pathlib import Path

import pytest


@pytest.fixture
def snapshot(tmp_path, monkeypatch):
    source = Path(__file__).resolve().parents[1] / "research/requirements_data_check_2026-10-02/inspect_sources.py"
    spec = importlib.util.spec_from_file_location("requirements_data_snapshot", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "ROOT", tmp_path)
    commit = "a" * 40
    monkeypatch.setattr(module, "SOURCES", {"example": {
        "repo": "example/public-data", "commit": commit, "files": {"data.json": "data.json"}}})
    data = b'{"rows": [1, 2]}\n'
    record = {"dataset": "example", "path": "raw/example/data.json",
              "url": f"https://raw.githubusercontent.com/example/public-data/{commit}/data.json",
              "commit": commit, "bytes": len(data), "sha256": module.digest(data)}
    manifest = tmp_path / "source_manifest.json"
    manifest.write_text(json.dumps({"files": [record], "created_at_utc": "original-snapshot"}), encoding="utf-8")
    return module, data, manifest


def test_fresh_checkout_restores_cache_without_rewriting_manifest(snapshot, monkeypatch):
    module, data, manifest = snapshot
    original_manifest = manifest.read_bytes()
    monkeypatch.setattr(module, "urlopen", lambda *args, **kwargs: io.BytesIO(data))
    module.fetch()
    assert (module.ROOT / "raw/example/data.json").read_bytes() == data
    assert manifest.read_bytes() == original_manifest
    module.verify()


def test_changed_download_is_rejected_before_cache_write(snapshot, monkeypatch):
    module, _, manifest = snapshot
    original_manifest = manifest.read_bytes()
    monkeypatch.setattr(module, "urlopen", lambda *args, **kwargs: io.BytesIO(b'{"rows": [9]}\n'))
    with pytest.raises(ValueError, match="Source mismatch"):
        module.fetch()
    assert not (module.ROOT / "raw/example/data.json").exists()
    assert manifest.read_bytes() == original_manifest


def test_changed_cache_is_preserved_and_rejected_without_network(snapshot, monkeypatch):
    module, _, manifest = snapshot
    original_manifest = manifest.read_bytes()
    cached = module.ROOT / "raw/example/data.json"
    cached.parent.mkdir(parents=True)
    cached.write_bytes(b'{"rows": [9]}\n')
    def unexpected_network(*args, **kwargs):
        pytest.fail("Existing cache verification must not access the network.")
    monkeypatch.setattr(module, "urlopen", unexpected_network)
    with pytest.raises(ValueError, match="Source mismatch"):
        module.fetch()
    assert cached.read_bytes() == b'{"rows": [9]}\n'
    assert manifest.read_bytes() == original_manifest


def test_incomplete_manifest_is_rejected(snapshot):
    module, _, manifest = snapshot
    manifest.write_text('{"files": []}', encoding="utf-8")
    with pytest.raises(ValueError, match="source list differ"):
        module.fetch()


def test_initial_download_creates_portable_lf_manifest(snapshot, monkeypatch):
    module, data, manifest = snapshot
    manifest.unlink()
    monkeypatch.setattr(module, "urlopen", lambda *args, **kwargs: io.BytesIO(data))
    module.fetch()
    saved = manifest.read_bytes()
    assert b"\r\n" not in saved
    assert json.loads(saved)["files"][0]["sha256"] == module.digest(data)
    assert (module.ROOT / "raw/example/data.json").read_bytes() == data
