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


def test_atomic_records_and_delete_use_short_internal_names_in_deep_projects(tmp_path):
    deep_root = tmp_path
    segment = "n" * 10
    while len(str(deep_root)) < 175:
        deep_root = deep_root / segment
    deep_root.mkdir(parents=True, exist_ok=True)

    context = allocate_run_directory(
        deep_root,
        project_id="project-deep-path",
        prefix="document_intake",
        owned_artifacts=(),
        snapshot_directories=("source_files",),
    )
    source_dir = context.path / "source_files"
    source_dir.mkdir()
    nested_source = source_dir / "manual_upload_fallback.md"
    nested_source.write_text("deep source\n", encoding="utf-8")
    with context.transaction():
        pass
    assert load_run_completion(context.path)["run_id"] == context.run_id
    assert nested_source.read_text(encoding="utf-8") == "deep source\n"

    run_path = context.path
    delete_run_directory(
        run_path,
        project_id=context.project_id,
        run_id=context.run_id,
    )
    assert not run_path.exists()
    assert not list(deep_root.glob(".delete-*"))


def test_lifecycle_atomic_temp_never_removes_unknown_collision(tmp_path, monkeypatch):
    class FixedUuid:
        hex = "deadbeef" * 4

    monkeypatch.setattr(lifecycle.uuid, "uuid4", lambda: FixedUuid())
    unknown = tmp_path / ".l-deadbeef"
    unknown.write_text("user-owned", encoding="utf-8")

    with pytest.raises(RunConflictError, match="temporary file"):
        lifecycle._atomic_write_json(tmp_path / "record.json", {"safe": True})

    assert unknown.read_text(encoding="utf-8") == "user-owned"
    assert not (tmp_path / "record.json").exists()


def test_cleanup_failure_releases_lock_and_next_writer_recovers_staging(
    tmp_path, monkeypatch
):
    context = prepare_run_directory(tmp_path / "run", project_id="project-alpha")
    interrupted = context.transaction(lock_timeout=0.1)

    def fail_cleanup():
        raise OSError("simulated staging cleanup failure")

    monkeypatch.setattr(interrupted, "_cleanup_staging", fail_cleanup)
    with pytest.raises(OSError, match="cleanup failure"):
        with interrupted:
            raise RuntimeError("original operation failed")

    stale = interrupted._staging
    assert stale is not None and stale.is_dir()
    with context.transaction(lock_timeout=0.1):
        pass

    assert is_run_complete(context.path)
    assert not stale.exists()


def test_delete_removes_only_staging_owned_by_the_same_run(tmp_path):
    context = prepare_run_directory(tmp_path / "run", project_id="project-alpha")
    prefix = lifecycle._staging_prefix_for(context.path)
    staging = context.path.parent / f"{prefix}dead"
    staging.mkdir()
    (staging / lifecycle.RUN_STAGING_OWNER_NAME).write_text(
        json.dumps(
            {
                "schema_version": lifecycle.LIFECYCLE_SCHEMA_VERSION,
                "project_id": context.project_id,
                "run_id": context.run_id,
            }
        ),
        encoding="utf-8",
    )
    (staging / "sensitive-draft.md").write_text("private", encoding="utf-8")

    delete_run_directory(
        context.path,
        project_id=context.project_id,
        run_id=context.run_id,
        allow_incomplete=True,
    )

    assert not context.path.exists()
    assert not staging.exists()


def test_replace_recovers_old_staging_before_publishing_new_identity(tmp_path):
    first = prepare_run_directory(
        tmp_path / "run",
        project_id="project-alpha",
        run_id="run-a",
    )
    prefix = lifecycle._staging_prefix_for(first.path)
    stale = first.path.parent / f"{prefix}crashed"
    stale.mkdir()
    (stale / lifecycle.RUN_STAGING_OWNER_NAME).write_text(
        json.dumps(
            {
                "schema_version": lifecycle.LIFECYCLE_SCHEMA_VERSION,
                "project_id": first.project_id,
                "run_id": first.run_id,
            }
        ),
        encoding="utf-8",
    )
    (stale / "sensitive-draft.md").write_text("private", encoding="utf-8")

    replacement = prepare_run_directory(
        first.path,
        project_id=first.project_id,
        mode="replace",
        expected_run_id=first.run_id,
        run_id="run-b",
    )

    assert not stale.exists()
    with replacement.transaction():
        pass
    delete_run_directory(
        replacement.path,
        project_id=replacement.project_id,
        run_id=replacement.run_id,
    )
    assert not replacement.path.exists()


def test_replace_staging_identity_conflict_is_zero_write(tmp_path):
    first = prepare_run_directory(
        tmp_path / "run",
        project_id="project-alpha",
        run_id="run-a",
        owned_artifacts=OWNED,
    )
    (first.path / "audit_report.md").write_text("preserve", encoding="utf-8")
    prefix = lifecycle._staging_prefix_for(first.path)
    matching = first.path.parent / f"{prefix}matching"
    conflicting = first.path.parent / f"{prefix}conflicting"
    for staging, owner_run_id in ((matching, "run-a"), (conflicting, "run-other")):
        staging.mkdir()
        (staging / lifecycle.RUN_STAGING_OWNER_NAME).write_text(
            json.dumps(
                {
                    "schema_version": lifecycle.LIFECYCLE_SCHEMA_VERSION,
                    "project_id": first.project_id,
                    "run_id": owner_run_id,
                }
            ),
            encoding="utf-8",
        )

    with pytest.raises(ProjectIdentityMismatch, match="Run identity mismatch"):
        prepare_run_directory(
            first.path,
            project_id=first.project_id,
            mode="replace",
            expected_run_id=first.run_id,
            run_id="run-b",
            owned_artifacts=OWNED,
        )

    assert load_run_identity(first.path)["run_id"] == "run-a"
    assert (first.path / "audit_report.md").read_text(encoding="utf-8") == "preserve"
    assert matching.is_dir()
    assert conflicting.is_dir()


def test_owner_bootstrap_crashes_never_block_resume_or_delete(tmp_path):
    first = prepare_run_directory(tmp_path / "run-1", project_id="project-alpha")
    empty_bootstrap = first.path.parent / (
        f"{lifecycle._staging_bootstrap_prefix_for(first.path)}empty"
    )
    empty_bootstrap.mkdir()

    with first.transaction():
        pass

    assert is_run_complete(first.path)
    assert not empty_bootstrap.exists()

    second = prepare_run_directory(tmp_path / "run-2", project_id="project-alpha")
    partial_bootstrap = second.path.parent / (
        f"{lifecycle._staging_bootstrap_prefix_for(second.path)}partial"
    )
    partial_bootstrap.mkdir()
    (partial_bootstrap / f"{lifecycle.LIFECYCLE_TEMP_PREFIX}deadbeef").write_text(
        '{"schema_version":2,"project_id":"project-alpha"',
        encoding="utf-8",
    )

    delete_run_directory(
        second.path,
        project_id=second.project_id,
        run_id=second.run_id,
        allow_incomplete=True,
    )

    assert not second.path.exists()
    assert not partial_bootstrap.exists()
    assert lifecycle.is_internal_staging_name(empty_bootstrap.name)
    assert lifecycle.is_internal_staging_name(partial_bootstrap.name)


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
    assert not list(context.path.parent.glob(".t-*"))


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
