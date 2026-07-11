import hashlib
import json
import threading

import pytest
import problem_bridge.project_lifecycle as lifecycle

from problem_bridge.project_lifecycle import (
    ProjectIdentityMismatch,
    RunConflictError,
    UnsafeArtifactPath,
    allocate_run_directory,
    delete_run_directory,
    is_run_complete,
    load_run_completion,
    load_run_identity,
    prepare_run_directory,
)


OWNED = ("claim_table.csv", "audit_report.md")


def test_allocated_run_directories_are_unique_and_identified(tmp_path):
    first = allocate_run_directory(
        tmp_path, project_id="project-alpha", prefix="audit", owned_artifacts=OWNED
    )
    second = allocate_run_directory(
        tmp_path, project_id="project-alpha", prefix="audit", owned_artifacts=OWNED
    )

    assert first.path != second.path
    assert first.path.is_dir() and second.path.is_dir()
    assert first.project_id == second.project_id == "project-alpha"
    assert first.run_id != second.run_id
    assert load_run_identity(first.path)["run_id"] == first.run_id


def test_new_mode_rejects_nonempty_or_previously_owned_directory(tmp_path):
    nonempty = tmp_path / "nonempty"
    nonempty.mkdir()
    (nonempty / "user_notes.txt").write_text("keep me", encoding="utf-8")

    with pytest.raises(RunConflictError, match="requires an empty directory"):
        prepare_run_directory(
            nonempty, project_id="project-alpha", mode="new", owned_artifacts=OWNED
        )

    owned = tmp_path / "owned"
    prepare_run_directory(owned, project_id="project-alpha", mode="new", owned_artifacts=OWNED)
    with pytest.raises(RunConflictError, match="requires an empty directory"):
        prepare_run_directory(
            owned, project_id="project-alpha", mode="new", owned_artifacts=OWNED
        )


def test_resume_and_replace_verify_identity_and_preserve_unknown_files(tmp_path):
    root = tmp_path / "run"
    original = prepare_run_directory(
        root,
        project_id="project-alpha",
        mode="new",
        run_id="run-original",
        owned_artifacts=OWNED,
    )
    (root / "claim_table.csv").write_text("old generated output", encoding="utf-8")
    (root / "user_notes.txt").write_text("user-owned", encoding="utf-8")

    resumed = prepare_run_directory(
        root,
        project_id="project-alpha",
        mode="resume",
        expected_run_id="run-original",
        run_id="run-original",
        owned_artifacts=OWNED,
    )
    assert resumed.run_id == original.run_id
    assert (root / "claim_table.csv").exists()

    with pytest.raises(ProjectIdentityMismatch, match="Project identity mismatch"):
        prepare_run_directory(
            root,
            project_id="project-beta",
            mode="replace",
            expected_run_id="run-original",
            owned_artifacts=OWNED,
        )
    with pytest.raises(ProjectIdentityMismatch, match="Run identity mismatch"):
        prepare_run_directory(
            root,
            project_id="project-alpha",
            mode="replace",
            expected_run_id="run-not-current",
            owned_artifacts=OWNED,
        )

    replaced = prepare_run_directory(
        root,
        project_id="project-alpha",
        mode="replace",
        expected_run_id="run-original",
        run_id="run-replacement",
        owned_artifacts=OWNED,
    )
    assert replaced.run_id == "run-replacement"
    assert replaced.previous_run_id == "run-original"
    assert not (root / "claim_table.csv").exists()
    assert (root / "user_notes.txt").read_text(encoding="utf-8") == "user-owned"


def test_resume_and_replace_require_independent_expected_run_id(tmp_path):
    root = tmp_path / "run"
    context = prepare_run_directory(root, project_id="project-alpha", owned_artifacts=OWNED)
    (root / "audit_report.md").write_text("preserve", encoding="utf-8")

    for mode in ("resume", "replace"):
        with pytest.raises(ProjectIdentityMismatch, match="expected_run_id is required"):
            prepare_run_directory(
                root,
                project_id=context.project_id,
                mode=mode,
                owned_artifacts=OWNED,
            )

    assert (root / "audit_report.md").read_text(encoding="utf-8") == "preserve"


def test_replace_removes_old_and_requested_snapshot_trees(tmp_path):
    root = tmp_path / "run"
    original = prepare_run_directory(
        root,
        project_id="project-alpha",
        snapshot_directories=("extracted_tables", "source_files"),
    )
    (root / "extracted_tables").mkdir()
    (root / "extracted_tables" / "old.csv").write_text("old\n", encoding="utf-8")
    (root / "source_files").mkdir()
    (root / "source_files" / "old.md").write_text("old\n", encoding="utf-8")
    with original.transaction():
        pass

    replacement = prepare_run_directory(
        root,
        project_id=original.project_id,
        mode="replace",
        expected_run_id=original.run_id,
        snapshot_directories=("extracted_tables",),
    )

    assert not (root / "extracted_tables").exists()
    assert not (root / "source_files").exists()
    with replacement.transaction():
        pass
    completion = load_run_completion(root)
    assert not any(
        name.startswith(("extracted_tables/", "source_files/"))
        for name in completion["artifact_sha256"]
    )


def test_replace_refuses_recursive_delete_at_owned_file_path(tmp_path):
    root = tmp_path / "run"
    context = prepare_run_directory(root, project_id="project-alpha", owned_artifacts=OWNED)
    (root / "claim_table.csv").mkdir()
    (root / "audit_report.md").write_text("must survive failed preflight", encoding="utf-8")

    with pytest.raises(UnsafeArtifactPath, match="Refusing to recursively remove"):
        prepare_run_directory(
            root,
            project_id="project-alpha",
            mode="replace",
            expected_run_id=context.run_id,
            owned_artifacts=OWNED,
        )
    assert (root / "claim_table.csv").is_dir()
    assert (root / "audit_report.md").read_text(encoding="utf-8") == "must survive failed preflight"


def test_replace_rejects_reused_run_id_before_deleting_outputs(tmp_path):
    root = tmp_path / "run"
    prepare_run_directory(
        root,
        project_id="project-alpha",
        run_id="run-original",
        owned_artifacts=OWNED,
    )
    (root / "audit_report.md").write_text("preserve on conflict", encoding="utf-8")

    with pytest.raises(RunConflictError, match="requires a new run_id"):
        prepare_run_directory(
            root,
            project_id="project-alpha",
            mode="replace",
            expected_run_id="run-original",
            run_id="run-original",
            owned_artifacts=OWNED,
        )
    assert (root / "audit_report.md").read_text(encoding="utf-8") == "preserve on conflict"


def test_transaction_publishes_completion_marker_last_with_hashes(tmp_path):
    context = prepare_run_directory(
        tmp_path / "run", project_id="project-alpha", owned_artifacts=OWNED
    )
    with context.transaction() as transaction:
        transaction.write_text("claim_table.csv", "claim_id,status\nc1,supported\n")
        transaction.write_bytes("audit_report.md", b"# Audit\n")
        assert not is_run_complete(context.path)
        assert not (context.path / "claim_table.csv").exists()

    assert is_run_complete(context.path)
    completion = load_run_completion(context.path)
    expected = hashlib.sha256(b"claim_id,status\nc1,supported\n").hexdigest()
    assert completion["project_id"] == context.project_id
    assert completion["run_id"] == context.run_id
    assert completion["artifact_sha256"]["claim_table.csv"] == expected

    with pytest.raises(RunConflictError, match="cannot be resumed"):
        prepare_run_directory(
            context.path,
            project_id=context.project_id,
            mode="resume",
            expected_run_id=context.run_id,
            run_id=context.run_id,
            owned_artifacts=OWNED,
        )


def test_failed_transaction_leaves_no_output_or_false_completion(tmp_path):
    context = prepare_run_directory(
        tmp_path / "run", project_id="project-alpha", owned_artifacts=OWNED
    )

    with pytest.raises(RuntimeError, match="simulated failure"):
        with context.transaction() as transaction:
            transaction.write_text("audit_report.md", "partial")
            raise RuntimeError("simulated failure")

    assert not is_run_complete(context.path)
    assert not (context.path / "audit_report.md").exists()
    assert not list(context.path.glob(".run-txn-*"))


def test_completion_requires_every_declared_artifact(tmp_path):
    context = prepare_run_directory(
        tmp_path / "run",
        project_id="project-alpha",
        owned_artifacts=OWNED,
        required_artifacts=("audit_report.md", "project_summary_log.md"),
    )
    (context.path / "audit_report.md").write_text("audit", encoding="utf-8")

    with pytest.raises(RunConflictError, match="project_summary_log.md"):
        with context.transaction():
            pass

    assert not is_run_complete(context.path)


def test_real_writer_lease_blocks_concurrent_replace(tmp_path):
    context = prepare_run_directory(
        tmp_path / "run",
        project_id="project-alpha",
        owned_artifacts=OWNED,
        required_artifacts=("audit_report.md",),
    )
    entered = threading.Event()
    release = threading.Event()

    def hold_writer_lock():
        with context.transaction():
            (context.path / "audit_report.md").write_text("complete", encoding="utf-8")
            entered.set()
            release.wait(timeout=5)

    thread = threading.Thread(target=hold_writer_lock)
    thread.start()
    assert entered.wait(timeout=5)
    try:
        with pytest.raises(RunConflictError, match="Timed out"):
            prepare_run_directory(
                context.path,
                project_id=context.project_id,
                mode="replace",
                expected_run_id=context.run_id,
                owned_artifacts=OWNED,
                required_artifacts=("audit_report.md",),
                lock_timeout=0.05,
            )
    finally:
        release.set()
        thread.join(timeout=5)

    assert is_run_complete(context.path)


def test_transaction_rejects_unowned_and_nested_paths(tmp_path):
    context = prepare_run_directory(
        tmp_path / "run", project_id="project-alpha", owned_artifacts=OWNED
    )

    with pytest.raises(UnsafeArtifactPath, match="not owned by this run"):
        with context.transaction() as transaction:
            transaction.write_text("user_notes.txt", "must not be overwritten")

    with pytest.raises(UnsafeArtifactPath):
        prepare_run_directory(
            tmp_path / "unsafe",
            project_id="project-alpha",
            owned_artifacts=("../claim_table.csv",),
        )


def test_lifecycle_records_fail_closed_when_identity_is_tampered(tmp_path):
    root = tmp_path / "run"
    context = prepare_run_directory(root, project_id="project-alpha", owned_artifacts=OWNED)
    path = root / "run_identity.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["project_id"] = "project-beta"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ProjectIdentityMismatch):
        prepare_run_directory(
            root,
            project_id="project-alpha",
            mode="resume",
            expected_run_id=context.run_id,
            owned_artifacts=OWNED,
        )


def test_completed_artifact_tampering_is_detected(tmp_path):
    context = prepare_run_directory(
        tmp_path / "run", project_id="project-alpha", owned_artifacts=OWNED
    )
    with context.transaction() as transaction:
        transaction.write_text("audit_report.md", "original")
    (context.path / "audit_report.md").write_text("tampered", encoding="utf-8")

    assert not is_run_complete(context.path)

    with pytest.raises(RunConflictError, match="SHA-256 mismatch"):
        load_run_completion(context.path)


def test_resume_rejects_different_workflow_or_run_spec(tmp_path):
    root = tmp_path / "run"
    spec_a = hashlib.sha256(b"spec-a").hexdigest()
    context = prepare_run_directory(
        root,
        project_id="project-alpha",
        workflow_type="claim_harness.audit",
        run_spec_sha256=spec_a,
        owned_artifacts=OWNED,
    )

    with pytest.raises(ProjectIdentityMismatch, match="Workflow mismatch"):
        prepare_run_directory(
            root,
            project_id="project-alpha",
            mode="resume",
            expected_run_id=context.run_id,
            workflow_type="problem_bridge.alignment",
            run_spec_sha256=spec_a,
            owned_artifacts=OWNED,
        )
    with pytest.raises(ProjectIdentityMismatch, match="specification mismatch"):
        prepare_run_directory(
            root,
            project_id="project-alpha",
            mode="resume",
            expected_run_id=context.run_id,
            workflow_type="claim_harness.audit",
            run_spec_sha256=hashlib.sha256(b"spec-b").hexdigest(),
            owned_artifacts=OWNED,
        )


def test_completion_binds_identity_schema_and_exact_owned_snapshot(tmp_path):
    context = prepare_run_directory(tmp_path / "run", project_id="project-alpha")
    with context.transaction():
        pass

    identity_path = context.path / "run_identity.json"
    identity = json.loads(identity_path.read_text(encoding="utf-8"))
    identity["workflow_type"] = "tampered.workflow"
    identity_path.write_text(json.dumps(identity), encoding="utf-8")
    assert not is_run_complete(context.path)

    # Restore by creating a separate valid run, then test completion schema and
    # exact-set protection against injected declared artifacts.
    second = prepare_run_directory(tmp_path / "run-2", project_id="project-alpha")
    with second.transaction():
        pass
    completion_path = second.path / "run_complete.json"
    completion = json.loads(completion_path.read_text(encoding="utf-8"))
    completion["schema_version"] = 999
    completion_path.write_text(json.dumps(completion), encoding="utf-8")
    assert not is_run_complete(second.path)

    third = prepare_run_directory(tmp_path / "run-3", project_id="project-alpha")
    with third.transaction():
        pass
    (third.path / "llm_review.json").write_text("{}", encoding="utf-8")
    assert not is_run_complete(third.path)


def test_nested_snapshot_directories_are_hashed_and_tamper_evident(tmp_path):
    context = prepare_run_directory(
        tmp_path / "run",
        project_id="project-alpha",
        snapshot_directories=("extracted_tables",),
    )
    with context.transaction():
        tables = context.path / "extracted_tables"
        tables.mkdir()
        (tables / "table_1.csv").write_text("a,b\n1,2\n", encoding="utf-8")

    completion = load_run_completion(context.path)
    assert "extracted_tables/table_1.csv" in completion["artifact_sha256"]
    (context.path / "extracted_tables" / "table_1.csv").write_text(
        "a,b\n9,9\n", encoding="utf-8"
    )
    assert not is_run_complete(context.path)


def test_workflow_completion_rejects_other_generated_artifacts(tmp_path):
    context = prepare_run_directory(
        tmp_path / "run",
        project_id="project-alpha",
        owned_artifacts=("audit_report.md",),
        required_artifacts=("audit_report.md",),
    )
    (context.path / "audit_report.md").write_text("audit", encoding="utf-8")
    (context.path / "ai_task_spec.yaml").write_text("stale: true\n", encoding="utf-8")

    with pytest.raises(RunConflictError, match="outside this workflow declaration"):
        with context.transaction():
            pass
    assert not is_run_complete(context.path)


def test_snapshot_tree_rejects_reparse_directories_before_traversal(tmp_path, monkeypatch):
    context = prepare_run_directory(
        tmp_path / "run",
        project_id="project-alpha",
        owned_artifacts=(),
        snapshot_directories=("source_files",),
    )
    source = context.path / "source_files"
    linked = source / "linked"
    linked.mkdir(parents=True)
    (linked / "outside.txt").write_text("must not be read", encoding="utf-8")
    original = lifecycle._is_link_or_reparse
    monkeypatch.setattr(
        lifecycle,
        "_is_link_or_reparse",
        lambda path: path == linked or original(path),
    )

    with pytest.raises(UnsafeArtifactPath, match="junctions"):
        with context.transaction():
            pass


def test_interrupted_delete_fences_future_writers(tmp_path, monkeypatch):
    context = prepare_run_directory(tmp_path / "run", project_id="project-alpha")
    with context.transaction():
        pass

    def fail_delete(path):
        raise OSError("simulated delete interruption")

    real_rmtree = lifecycle.shutil.rmtree
    monkeypatch.setattr(lifecycle.shutil, "rmtree", fail_delete)
    with pytest.raises(OSError, match="interruption"):
        delete_run_directory(
            context.path,
            project_id=context.project_id,
            run_id=context.run_id,
        )

    assert (context.path / lifecycle.RUN_DELETE_MARKER_NAME).is_file()
    with pytest.raises(RunConflictError, match="pending deletion"):
        with context.transaction():
            pass

    # The marker remains sufficient authority for an idempotent retry even if
    # the first recursive deletion already removed the identity file.
    (context.path / "run_identity.json").unlink()
    monkeypatch.setattr(lifecycle.shutil, "rmtree", real_rmtree)
    delete_run_directory(
        context.path,
        project_id=context.project_id,
        run_id=context.run_id,
        trusted_parent=tmp_path,
    )
    assert not context.path.exists()


def test_delete_rejects_marker_that_does_not_match_live_identity(tmp_path):
    context = prepare_run_directory(
        tmp_path / "run",
        project_id="project-beta",
        run_id="run-beta",
    )
    marker = {
        "schema_version": lifecycle.LIFECYCLE_SCHEMA_VERSION,
        "project_id": "project-alpha",
        "run_id": "run-alpha",
        "marked_at": "2026-07-11T00:00:00+00:00",
    }
    (context.path / lifecycle.RUN_DELETE_MARKER_NAME).write_text(
        json.dumps(marker), encoding="utf-8"
    )

    with pytest.raises(ProjectIdentityMismatch, match="Project identity mismatch"):
        delete_run_directory(
            context.path,
            project_id="project-alpha",
            run_id="run-alpha",
            allow_incomplete=True,
        )
    with pytest.raises(ProjectIdentityMismatch, match="Project identity mismatch"):
        lifecycle.load_pending_deletion(context.path)

    assert context.path.is_dir()
    assert load_run_identity(context.path)["project_id"] == "project-beta"


def test_delete_rejects_non_file_marker_without_deleting_incomplete_run(tmp_path):
    context = prepare_run_directory(tmp_path / "run", project_id="project-alpha")
    (context.path / lifecycle.RUN_DELETE_MARKER_NAME).mkdir()

    with pytest.raises(RunConflictError, match="safe regular file"):
        delete_run_directory(
            context.path,
            project_id=context.project_id,
            run_id=context.run_id,
        )

    assert context.path.is_dir()
    assert (context.path / lifecycle.RUN_IDENTITY_NAME).is_file()


def test_delete_cleanup_cannot_remove_new_run_at_reused_path(tmp_path, monkeypatch):
    root = tmp_path / "run"
    old = prepare_run_directory(
        root,
        project_id="project-old",
        run_id="run-old",
    )
    with old.transaction():
        pass
    real_rmtree = lifecycle.shutil.rmtree

    def create_new_run_then_remove_tombstone(path):
        prepare_run_directory(
            root,
            project_id="project-new",
            run_id="run-new",
        )
        real_rmtree(path)

    monkeypatch.setattr(lifecycle.shutil, "rmtree", create_new_run_then_remove_tombstone)
    delete_run_directory(
        root,
        project_id=old.project_id,
        run_id=old.run_id,
    )

    identity = load_run_identity(root)
    assert identity["project_id"] == "project-new"
    assert identity["run_id"] == "run-new"
