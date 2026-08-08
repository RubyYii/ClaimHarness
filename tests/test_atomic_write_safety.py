from pathlib import Path

import pytest

import claim_harness.report_viewer as viewer
import claim_harness.run_records as run_records
import problem_bridge.project_lifecycle as lifecycle
import problem_bridge.revision_governance as governance


class _FixedUuid:
    hex = "deadbeef" * 4


def _recreate_source_after_publish(monkeypatch, module, content="other-owner"):
    original_replace = module.os.replace

    def replace_then_recreate(source, destination):
        original_replace(source, destination)
        Path(source).write_text(content, encoding="utf-8")

    monkeypatch.setattr(module.os, "replace", replace_then_recreate)


@pytest.mark.parametrize(
    ("module", "prefix", "writer", "target", "expected"),
    [
        (
            lifecycle,
            ".l-",
            lambda path: lifecycle._atomic_write_json(path, {"safe": True}),
            "run_identity.json",
            '{\n  "safe": true\n}\n',
        ),
        (
            governance,
            ".g-",
            lambda path: governance._atomic_write_text(path, "governed\n"),
            "project_record.json",
            "governed\n",
        ),
        (
            run_records,
            ".r-",
            lambda path: run_records._atomic_write(path, "recorded\n"),
            "run_manifest.json",
            "recorded\n",
        ),
    ],
)
def test_atomic_publish_does_not_unlink_recreated_source_name(
    tmp_path, monkeypatch, module, prefix, writer, target, expected
):
    monkeypatch.setattr(module.uuid, "uuid4", lambda: _FixedUuid())
    _recreate_source_after_publish(monkeypatch, module)

    destination = tmp_path / target
    writer(destination)

    assert destination.read_text(encoding="utf-8") == expected
    assert (tmp_path / f"{prefix}deadbeef").read_text(encoding="utf-8") == "other-owner"


def test_viewer_publish_does_not_unlink_recreated_source_name(tmp_path, monkeypatch):
    monkeypatch.setattr(viewer.uuid, "uuid4", lambda: _FixedUuid())
    monkeypatch.setattr(viewer, "_load_audit_package", lambda _path: {})
    monkeypatch.setattr(viewer, "_render_html", lambda _payload, _path: "<p>safe</p>")
    _recreate_source_after_publish(monkeypatch, viewer)

    output = viewer.render_report_viewer(tmp_path / "run")

    assert output.read_text(encoding="utf-8") == "<p>safe</p>"
    assert (output.parent / ".v-deadbeef").read_text(encoding="utf-8") == "other-owner"
