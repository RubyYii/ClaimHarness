import json
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

import pytest

import apps.problem_bridge_wizard as ui
from problem_bridge.project_lifecycle import prepare_run_directory


@pytest.fixture(autouse=True)
def _trust_each_test_temp_as_ui_run_root(tmp_path, monkeypatch):
    monkeypatch.setattr(ui, "RUN_ROOT", tmp_path)


def test_download_archive_is_refreshed_and_does_not_include_itself(tmp_path):
    out = tmp_path / "run"
    out.mkdir()
    (out / "extracted_text.md").write_text("first", encoding="utf-8")
    (out / ".env").write_text("SECRET=value", encoding="utf-8")

    archive = ui._make_archive(out)
    (out / "extraction_warnings.md").write_text("second", encoding="utf-8")
    refreshed = ui._make_archive(out)

    assert archive != refreshed
    with ZipFile(BytesIO(refreshed)) as package:
        names = package.namelist()
    assert names == ["extracted_text.md", "extraction_warnings.md", "share_manifest.json"]
    assert ".env" not in names
    assert all(not name.endswith(".zip") for name in names)


def test_download_archive_excludes_original_sources_by_default(tmp_path):
    out = tmp_path / "run"
    sources = out / "source_files"
    sources.mkdir(parents=True)
    (sources / "private.pdf").write_bytes(b"private")
    (out / "extracted_text.md").write_text("derived", encoding="utf-8")

    archive = ui._make_archive(out)

    with ZipFile(BytesIO(archive)) as package:
        names = package.namelist()
        manifest = json.loads(package.read("share_manifest.json"))
    assert "source_files/private.pdf" not in names
    assert "extracted_text.md" in names
    assert manifest["original_source_files_included"] is False
    assert manifest["excluded_original_source_file_count"] == 1
    assert manifest["excluded_unknown_entry_count"] == 0
    assert "private.pdf" not in json.dumps(manifest)
    assert manifest["included_files"][0]["path"] == "extracted_text.md"
    assert str(tmp_path) not in json.dumps(manifest)


def test_download_archive_includes_original_sources_only_by_explicit_choice(tmp_path):
    out = tmp_path / "run"
    sources = out / "source_files"
    sources.mkdir(parents=True)
    (sources / "source.txt").write_text("original", encoding="utf-8")
    (out / "extracted_text.md").write_text("derived", encoding="utf-8")

    archive = ui._make_archive(out, include_source_files=True)

    with ZipFile(BytesIO(archive)) as package:
        assert "source_files/source.txt" in package.namelist()
        manifest = json.loads(package.read("share_manifest.json"))
    assert manifest["original_source_files_included"] is True
    assert manifest["excluded_original_source_file_count"] == 0


def test_legacy_archive_excludes_workbench_memory_and_marks_unverified(tmp_path):
    out = tmp_path / "legacy-intake"
    out.mkdir()
    (out / "extracted_text.md").write_text("derived", encoding="utf-8")
    (out / "workbench_memory.json").write_text(
        '{"drafts":{"private":"do not share"}}', encoding="utf-8"
    )

    with ZipFile(BytesIO(ui._make_archive(out))) as package:
        names = package.namelist()
        manifest = json.loads(package.read("share_manifest.json"))

    assert "extracted_text.md" in names
    assert "workbench_memory.json" not in names
    assert "private" not in json.dumps(manifest)
    assert manifest["verification_status"] == "legacy-unverified"
    assert manifest["source_package_type"] == "document-intake"


def test_legacy_archive_refuses_mixed_or_unknown_packages(tmp_path):
    mixed = tmp_path / "mixed"
    mixed.mkdir()
    (mixed / "extracted_text.md").write_text("intake", encoding="utf-8")
    (mixed / "claim_table.csv").write_text("claim", encoding="utf-8")
    with pytest.raises(ValueError, match="exactly one"):
        ui._make_archive(mixed)

    unknown = tmp_path / "unknown"
    unknown.mkdir()
    (unknown / "notes.txt").write_text("private", encoding="utf-8")
    with pytest.raises(ValueError, match="exactly one"):
        ui._make_archive(unknown)


def test_archive_rejects_pending_deletion_even_without_run_identity(tmp_path):
    out = tmp_path / "pending"
    out.mkdir()
    (out / "extracted_text.md").write_text("residual", encoding="utf-8")
    (out / ui.RUN_DELETE_MARKER_NAME).write_text(
        '{"schema_version":2,"project_id":"project-a","run_id":"run-a"}',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="pending deletion"):
        ui._make_archive(out)


def test_archive_rejects_reparse_or_non_child_output_directory(tmp_path, monkeypatch):
    trusted = tmp_path / "trusted"
    trusted.mkdir()
    monkeypatch.setattr(ui, "RUN_ROOT", trusted)
    linked = trusted / "linked"
    linked.mkdir()
    (linked / "extracted_text.md").write_text("external", encoding="utf-8")
    original = ui.is_link_or_reparse
    monkeypatch.setattr(
        ui,
        "is_link_or_reparse",
        lambda path: Path(path) == linked or original(path),
    )

    with pytest.raises(ValueError, match="linked, or unsafe"):
        ui._make_archive(linked)

    monkeypatch.setattr(ui, "is_link_or_reparse", original)
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "extracted_text.md").write_text("outside", encoding="utf-8")
    with pytest.raises(ValueError, match="direct child"):
        ui._make_archive(outside)

    for internal_name in (".t-deadbeef", ".b-deadbeef"):
        staging = trusted / internal_name
        staging.mkdir()
        (staging / "extracted_text.md").write_text("uncommitted", encoding="utf-8")
        with pytest.raises(ValueError, match="linked, or unsafe"):
            ui._make_archive(staging)


def test_delete_ui_run_is_scoped_to_run_root(tmp_path, monkeypatch):
    run_root = tmp_path / "ui_runs"
    run = run_root / "one-run"
    context = prepare_run_directory(run, project_id="project-ui-test")
    (run / "artifact.txt").write_text("result", encoding="utf-8")
    with context.transaction():
        pass
    archive = run_root / "one-run.zip"
    archive.write_bytes(b"archive")
    outside = tmp_path / "outside"
    outside.mkdir()
    monkeypatch.setattr(ui, "RUN_ROOT", run_root)

    with pytest.raises(ValueError, match="outside"):
        ui._delete_ui_run(outside)

    ui._delete_ui_run(run)
    assert not run.exists()
    assert not archive.exists()


def test_ui_run_allocation_has_stable_project_and_unique_run_identity(tmp_path, monkeypatch):
    monkeypatch.setattr(ui, "RUN_ROOT", tmp_path / "ui_runs")

    first = ui._allocate_ui_run(
        "document_intake",
        project_id="project-ui-test",
        owned_artifacts=("source_manifest.json",),
        required_artifacts=("source_manifest.json",),
    )
    second = ui._allocate_ui_run("document_intake", project_id="project-ui-test")
    (first.path / "source_manifest.json").write_text("{}\n", encoding="utf-8")
    ui._complete_ui_run(first)

    first_identity = json.loads((first.path / "run_identity.json").read_text(encoding="utf-8"))
    completion = json.loads((first.path / "run_complete.json").read_text(encoding="utf-8"))
    assert first.path != second.path
    assert first.project_id == second.project_id == "project-ui-test"
    assert first.run_id != second.run_id
    assert first_identity["project_id"] == "project-ui-test"
    assert completion["run_id"] == first.run_id
    assert "source_manifest.json" in completion["artifact_sha256"]


def test_project_delete_removes_matching_complete_and_incomplete_runs_only(tmp_path, monkeypatch):
    run_root = tmp_path / "ui_runs"
    monkeypatch.setattr(ui, "RUN_ROOT", run_root)
    complete = prepare_run_directory(run_root / "complete", project_id="project-alpha")
    incomplete = prepare_run_directory(run_root / "incomplete", project_id="project-alpha")
    other = prepare_run_directory(run_root / "other", project_id="project-beta")
    with complete.transaction():
        pass
    with other.transaction():
        pass

    deleted = ui._delete_ui_project("project-alpha")

    assert deleted == 2
    assert not complete.path.exists()
    assert not incomplete.path.exists()
    assert other.path.exists()


def test_project_delete_clears_matching_persisted_workbench_memory(tmp_path, monkeypatch):
    run_root = tmp_path / "ui_runs"
    memory_path = tmp_path / "ui_memory" / "workbench_memory.json"
    monkeypatch.setattr(ui, "RUN_ROOT", run_root)
    monkeypatch.setattr(ui, "MEMORY_PATH", memory_path)
    context = prepare_run_directory(run_root / "run", project_id="project-alpha")
    with context.transaction():
        pass
    ui.save_workbench_memory(
        {
            "schema_version": 3,
            "active_project_id": "project-alpha",
            "drafts": {"private": "sensitive draft"},
        },
        memory_path,
    )

    assert ui._delete_ui_project("project-alpha") == 1
    assert not memory_path.exists()


def test_all_ui_run_root_read_write_and_delete_paths_reject_reparse_root(
    tmp_path, monkeypatch
):
    run_root = tmp_path / "junction-root"
    context = prepare_run_directory(
        run_root / "run",
        project_id="project-alpha",
        run_id="run-alpha",
    )
    with context.transaction():
        pass
    monkeypatch.setattr(ui, "RUN_ROOT", run_root)
    original = ui.is_link_or_reparse
    marked_root = run_root.absolute()
    monkeypatch.setattr(
        ui,
        "is_link_or_reparse",
        lambda path: Path(path).absolute() == marked_root or original(path),
    )

    operations = [
        lambda: ui._project_run_paths("project-alpha"),
        ui._pending_run_records,
        lambda: ui._allocate_ui_run("document_intake", project_id="project-alpha"),
        lambda: ui._delete_ui_run(context.path),
        lambda: ui._delete_ui_project("project-alpha"),
    ]
    for operation in operations:
        with pytest.raises(ValueError, match="linked or unsafe"):
            operation()

    assert context.path.is_dir()
    assert (context.path / "run_identity.json").is_file()
