import hashlib
import json
import threading
from concurrent.futures import ThreadPoolExecutor

from click.utils import strip_ansi
import pytest
from typer.testing import CliRunner

import problem_bridge.revision_governance as governance
from problem_bridge.cli import app
from problem_bridge.revision_governance import (
    MAX_REVISION_ROUNDS,
    REVISION_SCHEMA_VERSION,
    RevisionConflictError,
    RevisionLimitReached,
    initialize_project_record,
    load_revision_history,
    migrate_legacy_revision_history,
    record_revision,
    revision_history_sha256,
    snapshot_project_governance,
    verify_revision_history,
)


def _initialize(path):
    initialize_project_record(
        path,
        project_name="demo",
        project_goal="Keep claims reviewable.",
        boundaries=["No autonomous decision."],
        artifacts=["claim_table.csv"],
        created_at="2026-07-11T00:00:00+00:00",
    )


def _payload_sha256(payload):
    unsigned = dict(payload)
    unsigned.pop("record_sha256", None)
    canonical = json.dumps(
        unsigned,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _write_v1_history(path):
    payload = {
        "target": "loader",
        "round_number": 1,
        "diagnosis": "local_execution_problem",
        "summary": "Legacy correction.",
        "verification": "Old test passed.",
        "status": "needs_revision",
        "changed_files": ["loader.py"],
        "created_at": "2026-07-01T00:00:00+00:00",
    }
    (path / "revision_history.jsonl").write_text(
        json.dumps(payload) + "\n", encoding="utf-8"
    )
    return payload


def test_reinitializing_project_preserves_original_created_at(tmp_path):
    _initialize(tmp_path)
    initialize_project_record(
        tmp_path,
        project_name="renamed demo",
        project_goal="Updated goal.",
        artifacts=["project_summary_log.md"],
    )

    payload = json.loads((tmp_path / "project_record.json").read_text(encoding="utf-8"))
    assert payload["created_at"] == "2026-07-11T00:00:00+00:00"
    assert payload["updated_at"]
    assert payload["project_name"] == "renamed demo"


def test_revision_atomic_temp_never_removes_unknown_collision(tmp_path, monkeypatch):
    class FixedUuid:
        hex = "deadbeef" * 4

    monkeypatch.setattr(governance.uuid, "uuid4", lambda: FixedUuid())
    unknown = tmp_path / ".g-deadbeef"
    unknown.write_text("user-owned", encoding="utf-8")

    with pytest.raises(RevisionConflictError, match="temporary file"):
        governance._atomic_write_text(tmp_path / "project_record.json", "system")

    assert unknown.read_text(encoding="utf-8") == "user-owned"
    assert not (tmp_path / "project_record.json").exists()


def test_colocated_lifecycle_and_revision_atomic_domains_do_not_collide(
    tmp_path, monkeypatch
):
    import problem_bridge.project_lifecycle as lifecycle

    class FixedUuid:
        hex = "cafebabe" * 4

    monkeypatch.setattr(governance.uuid, "uuid4", lambda: FixedUuid())

    with ThreadPoolExecutor(max_workers=2) as executor:
        lifecycle_write = executor.submit(
            lifecycle._atomic_write_json,
            tmp_path / "run_complete.json",
            {"schema_version": 2, "project_id": "project-a", "run_id": "run-a"},
        )
        revision_write = executor.submit(
            governance._atomic_write_text,
            tmp_path / "project_summary_log.md",
            "# summary\n",
        )
        lifecycle_write.result()
        revision_write.result()

    assert json.loads((tmp_path / "run_complete.json").read_text(encoding="utf-8"))[
        "run_id"
    ] == "run-a"
    assert (tmp_path / "project_summary_log.md").read_text(encoding="utf-8") == "# summary\n"


@pytest.mark.parametrize(
    "tamper, message",
    [
        (lambda payload: payload.__setitem__("schema_version", 1), "schema_version"),
        (lambda payload: payload.pop("updated_at"), "missing fields"),
        (lambda payload: payload.__setitem__("unexpected", True), "unexpected fields"),
        (lambda payload: payload.__setitem__("artifacts", "claim_table.csv"), "list of text"),
    ],
)
def test_public_history_verification_rejects_invalid_project_record_schema(
    tmp_path, tamper, message
):
    _initialize(tmp_path)
    record_revision(
        tmp_path,
        target="record-schema",
        diagnosis="local_execution_problem",
        summary="Create a valid history.",
        verification="Initial verification passed.",
        status="accepted",
    )
    record_path = tmp_path / "project_record.json"
    payload = json.loads(record_path.read_text(encoding="utf-8"))
    tamper(payload)
    record_path.write_text(json.dumps(payload) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match=message):
        verify_revision_history(tmp_path)


def test_committed_revision_recovers_summary_without_consuming_retry_round(
    tmp_path, monkeypatch
):
    _initialize(tmp_path)
    original_writer = governance._write_project_summary_unlocked

    def fail_summary(*args, **kwargs):
        raise OSError("simulated summary interruption")

    monkeypatch.setattr(governance, "_write_project_summary_unlocked", fail_summary)
    request = {
        "target": "crash-recovery",
        "diagnosis": "local_execution_problem",
        "summary": "Commit the history before rebuilding the summary.",
        "verification": "Fault injection interrupted the summary write.",
        "status": "needs_revision",
    }
    committed = record_revision(tmp_path, **request)

    assert len((tmp_path / "revision_history.jsonl").read_text(encoding="utf-8").splitlines()) == 1
    assert "Commit the history" not in (
        tmp_path / "project_summary_log.md"
    ).read_text(encoding="utf-8")
    pending = governance.pending_revision_recovery(tmp_path)
    assert pending is not None
    assert pending["revision_id"] == committed.revision_id
    assert pending["phase"] in {"planned", "history_committed"}

    monkeypatch.setattr(governance, "_write_project_summary_unlocked", original_writer)
    recovered = load_revision_history(tmp_path)
    retry = record_revision(tmp_path, **request)

    assert [record.revision_id for record in recovered] == [committed.revision_id]
    assert retry.revision_id == committed.revision_id
    assert retry.round_number == 1
    assert len(load_revision_history(tmp_path)) == 1
    assert governance.pending_revision_recovery(tmp_path) is None
    assert "Commit the history" in (
        tmp_path / "project_summary_log.md"
    ).read_text(encoding="utf-8")


def test_revision_history_stops_after_three_rounds(tmp_path):
    _initialize(tmp_path)
    record_revision(
        tmp_path,
        target="claim-linking",
        diagnosis="local_execution_problem",
        summary="Remove self links.",
        verification="Targeted regression added.",
        status="needs_revision",
        created_at="2026-07-11T01:00:00+00:00",
    )
    record_revision(
        tmp_path,
        target="claim-linking",
        diagnosis="local_execution_problem",
        summary="Require source distinction.",
        verification="Contradiction test still fails.",
        status="needs_revision",
        created_at="2026-07-11T02:00:00+00:00",
    )
    third = record_revision(
        tmp_path,
        target="claim-linking",
        diagnosis="structural_mismatch",
        summary="Escalate evidence semantics.",
        verification="The local rule remains insufficient.",
        status="needs_revision",
        created_at="2026-07-11T03:00:00+00:00",
    )

    assert third.round_number == MAX_REVISION_ROUNDS
    assert third.status == "escalated"
    with pytest.raises(RevisionLimitReached, match="already escalated"):
        record_revision(
            tmp_path,
            target="claim-linking",
            diagnosis="structural_mismatch",
            summary="Forbidden fourth patch.",
            verification="Not run.",
            status="needs_revision",
        )

    with pytest.raises(RevisionLimitReached, match="already escalated"):
        record_revision(
            tmp_path,
            target="  Claim_Linking  ",
            diagnosis="structural_mismatch",
            summary="Case and separator alias must not reopen the target.",
            verification="Not run.",
            status="needs_revision",
        )

    summary = (tmp_path / "project_summary_log.md").read_text(encoding="utf-8")
    assert "no fourth patch" in summary.lower()
    assert "round 3/3" in summary


def test_round_three_requires_escalation_diagnosis(tmp_path):
    _initialize(tmp_path)
    for index in range(2):
        record_revision(
            tmp_path,
            target="report",
            diagnosis="local_execution_problem",
            summary=f"Patch {index + 1}",
            verification="Still failing.",
            status="needs_revision",
        )


def test_cli_reports_round_three_escalation_error_without_traceback(tmp_path):
    _initialize(tmp_path)
    for index in range(2):
        record_revision(
            tmp_path,
            target="report",
            diagnosis="local_execution_problem",
            summary=f"Patch {index + 1}",
            verification="Still failing.",
            status="needs_revision",
        )

    result = CliRunner().invoke(
        app,
        [
            "record-revision",
            "--project",
            str(tmp_path),
            "--target",
            "REPORT",
            "--diagnosis",
            "local_execution_problem",
            "--summary",
            "Forbidden third local patch.",
            "--verification",
            "Still failing.",
            "--status",
            "needs_revision",
            "--no-artifact-hash-reason",
            "The rejected round must not produce an artifact.",
        ],
    )

    assert result.exit_code != 0
    assert "Round three" in result.output
    assert "Traceback" not in result.output

    with pytest.raises(ValueError, match="Round three"):
        record_revision(
            tmp_path,
            target="report",
            diagnosis="local_execution_problem",
            summary="Patch 3",
            verification="Still failing.",
            status="needs_revision",
        )


def test_revision_log_is_jsonl_and_cli_refreshes_summary(tmp_path):
    _initialize(tmp_path)
    result = CliRunner().invoke(
        app,
        [
            "record-revision",
            "--project",
            str(tmp_path),
            "--target",
            "loader",
            "--diagnosis",
            "local_execution_problem",
            "--summary",
            "Preserve source lines.",
            "--verification",
            "Loader tests pass.",
            "--status",
            "accepted",
            "--changed-file",
            "claim_harness/loader.py",
            "--output-artifact",
            "project_record.json",
        ],
    )

    assert result.exit_code == 0, result.output
    records = load_revision_history(tmp_path)
    assert records[0].status == "accepted"
    assert records[0].changed_files == ("claim_harness/loader.py",)
    assert "project_record.json" in records[0].output_artifact_sha256
    payload = json.loads((tmp_path / "revision_history.jsonl").read_text(encoding="utf-8"))
    assert payload["round_number"] == 1
    assert "Preserve source lines" in (tmp_path / "project_summary_log.md").read_text(encoding="utf-8")


def test_target_key_is_canonicalized_on_first_record(tmp_path):
    _initialize(tmp_path)

    record = record_revision(
        tmp_path,
        target=" Evidence_Contract ",
        diagnosis="evidence_gap",
        summary="Clarify source requirements.",
        verification="Focused checks pass.",
        status="accepted",
    )

    assert record.target == "evidence-contract"


def test_project_identity_is_created_preserved_and_cannot_be_rebound(tmp_path):
    initialize_project_record(
        tmp_path,
        project_id="project-alpha",
        project_name="demo",
        project_goal="Keep claims reviewable.",
    )
    initialize_project_record(
        tmp_path,
        project_id="project-alpha",
        project_name="renamed",
        project_goal="Keep the same identity.",
    )

    payload = json.loads((tmp_path / "project_record.json").read_text(encoding="utf-8"))
    assert payload["schema_version"] == 2
    assert payload["project_id"] == "project-alpha"

    with pytest.raises(RevisionConflictError, match="identity mismatch"):
        initialize_project_record(
            tmp_path,
            project_id="project-beta",
            project_name="wrong project",
            project_goal="Must not overwrite alpha.",
        )


def test_revision_records_have_parent_and_artifact_integrity_hashes(tmp_path):
    _initialize(tmp_path)
    (tmp_path / "before.md").write_text("before\n", encoding="utf-8")
    (tmp_path / "after.md").write_text("after\n", encoding="utf-8")

    first = record_revision(
        tmp_path,
        target="audit-rules",
        diagnosis="local_execution_problem",
        summary="First bounded correction.",
        verification="Focused test still identifies one gap.",
        status="needs_revision",
        base_artifacts=["before.md"],
        output_artifacts=["after.md"],
    )
    second = record_revision(
        tmp_path,
        target="audit-rules",
        diagnosis="structural_mismatch",
        summary="Consolidated rule accepted.",
        verification="All focused tests pass.",
        status="accepted",
        expected_parent_revision_id=first.revision_id,
        check_parent=True,
    )

    project_record = json.loads((tmp_path / "project_record.json").read_text(encoding="utf-8"))
    assert first.schema_version == REVISION_SCHEMA_VERSION
    assert first.project_id == project_record["project_id"]
    assert len(first.revision_id) == 36
    assert first.parent_revision_id is None
    assert len(first.base_artifact_sha256["before.md"]) == 64
    assert len(first.output_artifact_sha256["after.md"]) == 64
    assert len(first.record_sha256) == 64
    assert second.parent_revision_id == first.revision_id
    assert second.previous_record_sha256 == first.record_sha256
    assert verify_revision_history(tmp_path) is True


def test_tampered_v3_revision_history_fails_closed(tmp_path):
    _initialize(tmp_path)
    record_revision(
        tmp_path,
        target="audit-rules",
        diagnosis="local_execution_problem",
        summary="Original summary.",
        verification="Test passed.",
        status="needs_revision",
    )
    path = tmp_path / "revision_history.jsonl"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["summary"] = "Tampered summary."
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        load_revision_history(tmp_path)


@pytest.mark.parametrize(
    ("tamper", "message"),
    [
        ("schema_downgrade", "requires explicit migration"),
        ("delete_hash", "missing fields: record_sha256"),
    ],
)
def test_v3_schema_downgrade_or_deleted_hash_never_verifies(tmp_path, tamper, message):
    _initialize(tmp_path)
    record_revision(
        tmp_path,
        target="audit-rules",
        diagnosis="local_execution_problem",
        summary="Original summary.",
        verification="Test passed.",
        status="needs_revision",
    )
    path = tmp_path / "revision_history.jsonl"
    payload = json.loads(path.read_text(encoding="utf-8"))
    if tamper == "schema_downgrade":
        payload["schema_version"] = 1
    else:
        payload.pop("record_sha256")
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match=message):
        verify_revision_history(tmp_path)


def test_downgraded_v3_line_cannot_be_accepted_as_legacy_migration(tmp_path):
    _initialize(tmp_path)
    record_revision(
        tmp_path,
        target="audit-rules",
        diagnosis="local_execution_problem",
        summary="Original summary.",
        verification="Test passed.",
        status="needs_revision",
    )
    path = tmp_path / "revision_history.jsonl"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["schema_version"] = 1
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    project_id = json.loads(
        (tmp_path / "project_record.json").read_text(encoding="utf-8")
    )["project_id"]

    with pytest.raises(ValueError, match="unexpected fields"):
        migrate_legacy_revision_history(tmp_path, expected_project_id=project_id)


def test_revision_history_cannot_be_copied_between_projects(tmp_path):
    project_a = tmp_path / "project-a"
    project_b = tmp_path / "project-b"
    initialize_project_record(
        project_a,
        project_id="project-a",
        project_name="A",
        project_goal="Alpha project.",
    )
    initialize_project_record(
        project_b,
        project_id="project-b",
        project_name="B",
        project_goal="Beta project.",
    )
    record_revision(
        project_a,
        target="audit-rules",
        diagnosis="local_execution_problem",
        summary="Alpha-only change.",
        verification="Alpha test passed.",
        status="accepted",
    )
    copied = (project_a / "revision_history.jsonl").read_text(encoding="utf-8")
    (project_b / "revision_history.jsonl").write_text(copied, encoding="utf-8")

    with pytest.raises(ValueError, match="project_id mismatch"):
        verify_revision_history(project_b)


def test_public_verify_rejects_complete_ledger_copied_beside_another_run(tmp_path):
    from problem_bridge.project_lifecycle import prepare_run_directory

    project_a = tmp_path / "run-a"
    project_b = tmp_path / "run-b"
    prepare_run_directory(project_a, project_id="project-a")
    prepare_run_directory(project_b, project_id="project-b")
    initialize_project_record(
        project_a,
        project_id="project-a",
        project_name="A",
        project_goal="Alpha project.",
    )
    initialize_project_record(
        project_b,
        project_id="project-b",
        project_name="B",
        project_goal="Beta project.",
    )
    record_revision(
        project_b,
        target="audit-rules",
        diagnosis="local_execution_problem",
        summary="Beta-only change.",
        verification="Beta test passed.",
        status="accepted",
    )
    for name in (
        "project_record.json",
        "project_summary_log.md",
        "revision_history.jsonl",
        "revision_summary_recovery.json",
    ):
        source = project_b / name
        if source.exists():
            (project_a / name).write_bytes(source.read_bytes())

    with pytest.raises(RevisionConflictError, match="co-located run_identity"):
        verify_revision_history(project_a)


def test_migration_rejects_colocated_project_mismatch_before_rewrite(tmp_path):
    from problem_bridge.project_lifecycle import prepare_run_directory

    project = tmp_path / "run-a"
    prepare_run_directory(project, project_id="project-a")
    initialize_project_record(
        project,
        project_id="project-a",
        project_name="A",
        project_goal="Alpha project.",
    )
    record_path = project / "project_record.json"
    metadata = json.loads(record_path.read_text(encoding="utf-8"))
    metadata["project_id"] = "project-b"
    record_path.write_text(json.dumps(metadata) + "\n", encoding="utf-8")
    legacy = _write_v1_history(project)
    before = (project / "revision_history.jsonl").read_bytes()

    with pytest.raises(RevisionConflictError, match="co-located run_identity"):
        migrate_legacy_revision_history(project, expected_project_id="project-b")

    assert (project / "revision_history.jsonl").read_bytes() == before
    assert json.loads(before)["summary"] == legacy["summary"]
    assert not (project / "revision_history_migration.json").exists()


def test_legacy_history_requires_explicit_one_time_migration(tmp_path):
    _initialize(tmp_path)
    legacy = {
        "target": "loader",
        "round_number": 1,
        "diagnosis": "local_execution_problem",
        "summary": "Legacy correction.",
        "verification": "Old test passed.",
        "status": "needs_revision",
        "changed_files": ["loader.py"],
        "created_at": "2026-07-01T00:00:00+00:00",
    }
    path = tmp_path / "revision_history.jsonl"
    path.write_text(json.dumps(legacy) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="requires explicit migration"):
        load_revision_history(tmp_path)
    with pytest.raises(ValueError, match="requires explicit migration"):
        record_revision(
            tmp_path,
            target="loader",
            diagnosis="local_execution_problem",
            summary="Silent upgrade must be refused.",
            verification="Not run.",
            status="accepted",
        )

    project_record = json.loads((tmp_path / "project_record.json").read_text(encoding="utf-8"))
    migrated = migrate_legacy_revision_history(
        tmp_path,
        expected_project_id=project_record["project_id"],
    )
    assert migrated[0].schema_version == REVISION_SCHEMA_VERSION
    assert migrated[0].project_id == project_record["project_id"]
    assert migrated[0].revision_id.startswith("legacy-")
    assert (tmp_path / "revision_history.legacy-v1.jsonl").is_file()
    assert (tmp_path / "revision_history_migration.json").is_file()

    appended = record_revision(
        tmp_path,
        target="loader",
        diagnosis="local_execution_problem",
        summary="Current correction.",
        verification="Current test passed.",
        status="accepted",
    )
    lines = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert [line["schema_version"] for line in lines] == [3, 3]
    assert appended.parent_revision_id == migrated[0].revision_id
    assert verify_revision_history(tmp_path) is True

    resumed = migrate_legacy_revision_history(
        tmp_path,
        expected_project_id=project_record["project_id"],
    )
    assert [record.revision_id for record in resumed] == [
        record.revision_id for record in load_revision_history(tmp_path)
    ]


def test_migration_resumes_after_summary_write_interruption(tmp_path, monkeypatch):
    _initialize(tmp_path)
    _write_v1_history(tmp_path)
    project_id = json.loads(
        (tmp_path / "project_record.json").read_text(encoding="utf-8")
    )["project_id"]
    original_writer = governance._write_project_summary_unlocked

    def fail_summary(*args, **kwargs):
        raise OSError("simulated migration summary interruption")

    monkeypatch.setattr(governance, "_write_project_summary_unlocked", fail_summary)
    with pytest.raises(OSError, match="summary interruption"):
        migrate_legacy_revision_history(tmp_path, expected_project_id=project_id)

    receipt_path = tmp_path / "revision_history_migration.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    migrated_payload = json.loads(
        (tmp_path / "revision_history.jsonl").read_text(encoding="utf-8")
    )
    assert receipt["phase"] == "history_committed"
    assert migrated_payload["schema_version"] == REVISION_SCHEMA_VERSION
    assert (tmp_path / receipt["backup_file"]).is_file()

    monkeypatch.setattr(governance, "_write_project_summary_unlocked", original_writer)
    records = migrate_legacy_revision_history(tmp_path, expected_project_id=project_id)
    completed = json.loads(receipt_path.read_text(encoding="utf-8"))

    assert len(records) == 1
    assert completed["phase"] == "complete"
    assert verify_revision_history(tmp_path) is True


def test_migration_resumes_when_history_committed_before_receipt_phase(
    tmp_path, monkeypatch
):
    _initialize(tmp_path)
    _write_v1_history(tmp_path)
    project_id = json.loads(
        (tmp_path / "project_record.json").read_text(encoding="utf-8")
    )["project_id"]
    original_writer = governance._write_migration_receipt_unlocked

    def fail_history_committed_receipt(root, payload):
        if payload["phase"] == "history_committed":
            raise OSError("simulated receipt interruption")
        return original_writer(root, payload)

    monkeypatch.setattr(
        governance,
        "_write_migration_receipt_unlocked",
        fail_history_committed_receipt,
    )
    with pytest.raises(OSError, match="receipt interruption"):
        migrate_legacy_revision_history(tmp_path, expected_project_id=project_id)

    receipt_path = tmp_path / "revision_history_migration.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    migrated_payload = json.loads(
        (tmp_path / "revision_history.jsonl").read_text(encoding="utf-8")
    )
    assert receipt["phase"] == "planned"
    assert migrated_payload["schema_version"] == REVISION_SCHEMA_VERSION

    monkeypatch.setattr(governance, "_write_migration_receipt_unlocked", original_writer)
    records = migrate_legacy_revision_history(tmp_path, expected_project_id=project_id)

    assert len(records) == 1
    assert json.loads(receipt_path.read_text(encoding="utf-8"))["phase"] == "complete"
    assert verify_revision_history(tmp_path) is True


def test_valid_v2_history_can_only_be_migrated_explicitly(tmp_path):
    _initialize(tmp_path)
    record_revision(
        tmp_path,
        target="loader",
        diagnosis="local_execution_problem",
        summary="Version two correction.",
        verification="Old test passed.",
        status="needs_revision",
    )
    path = tmp_path / "revision_history.jsonl"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["schema_version"] = 2
    payload.pop("project_id")
    payload["record_sha256"] = _payload_sha256(payload)
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    project_id = json.loads(
        (tmp_path / "project_record.json").read_text(encoding="utf-8")
    )["project_id"]

    with pytest.raises(ValueError, match="requires explicit migration"):
        load_revision_history(tmp_path)
    migrated = migrate_legacy_revision_history(tmp_path, expected_project_id=project_id)

    assert migrated[0].schema_version == REVISION_SCHEMA_VERSION
    assert migrated[0].project_id == project_id
    assert verify_revision_history(tmp_path) is True


def test_mixed_legacy_schemas_are_rejected_without_rewrite(tmp_path):
    _initialize(tmp_path)
    v1 = {
        "target": "loader",
        "round_number": 1,
        "diagnosis": "local_execution_problem",
        "summary": "Legacy correction.",
        "verification": "Old test passed.",
        "status": "needs_revision",
        "changed_files": ["loader.py"],
        "created_at": "2026-07-01T00:00:00+00:00",
    }
    v2 = dict(v1, schema_version=2, round_number=2)
    path = tmp_path / "revision_history.jsonl"
    path.write_text(json.dumps(v1) + "\n" + json.dumps(v2) + "\n", encoding="utf-8")
    project_id = json.loads(
        (tmp_path / "project_record.json").read_text(encoding="utf-8")
    )["project_id"]

    with pytest.raises(ValueError, match="Mixed revision history schema versions"):
        migrate_legacy_revision_history(tmp_path, expected_project_id=project_id)
    assert path.read_text(encoding="utf-8").splitlines() == [json.dumps(v1), json.dumps(v2)]


def test_cli_migrates_legacy_history_only_with_matching_project_id(tmp_path):
    initialize_project_record(
        tmp_path,
        project_id="project-cli",
        project_name="CLI",
        project_goal="Test explicit migration.",
    )
    legacy = {
        "target": "loader",
        "round_number": 1,
        "diagnosis": "local_execution_problem",
        "summary": "Legacy correction.",
        "verification": "Old test passed.",
        "status": "accepted",
        "changed_files": ["loader.py"],
        "created_at": "2026-07-01T00:00:00+00:00",
    }
    (tmp_path / "revision_history.jsonl").write_text(
        json.dumps(legacy) + "\n", encoding="utf-8"
    )

    wrong = CliRunner().invoke(
        app,
        [
            "migrate-revision-history",
            "--project",
            str(tmp_path),
            "--project-id",
            "project-wrong",
        ],
    )
    assert wrong.exit_code != 0
    assert "identity mismatch" in wrong.output.lower()

    result = CliRunner().invoke(
        app,
        [
            "migrate-revision-history",
            "--project",
            str(tmp_path),
            "--project-id",
            "project-cli",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "schema=v3" in strip_ansi(result.output)
    assert verify_revision_history(tmp_path) is True


def test_stale_history_snapshot_is_rejected(tmp_path):
    _initialize(tmp_path)
    snapshot = revision_history_sha256(tmp_path)
    record_revision(
        tmp_path,
        target="report",
        diagnosis="local_execution_problem",
        summary="First writer.",
        verification="Focused test passed.",
        status="needs_revision",
        expected_history_sha256=snapshot,
    )

    with pytest.raises(RevisionConflictError, match="changed after it was reviewed"):
        record_revision(
            tmp_path,
            target="report",
            diagnosis="local_execution_problem",
            summary="Stale second writer.",
            verification="Must not overwrite.",
            status="needs_revision",
            expected_history_sha256=snapshot,
        )


def test_concurrent_writers_with_same_snapshot_have_one_explicit_conflict(tmp_path):
    _initialize(tmp_path)
    snapshot = revision_history_sha256(tmp_path)

    def write(index):
        try:
            return record_revision(
                tmp_path,
                target="concurrent-target",
                diagnosis="local_execution_problem",
                summary=f"Writer {index}.",
                verification="Concurrency test.",
                status="needs_revision",
                expected_history_sha256=snapshot,
            )
        except RevisionConflictError as exc:
            return exc

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(write, [1, 2]))

    assert sum(not isinstance(result, Exception) for result in results) == 1
    assert sum(isinstance(result, RevisionConflictError) for result in results) == 1
    assert len(load_revision_history(tmp_path)) == 1


def test_interleaved_targets_keep_target_parent_and_global_hash_chain_separate(tmp_path):
    _initialize(tmp_path)
    alpha_one = record_revision(
        tmp_path,
        target="alpha",
        diagnosis="local_execution_problem",
        summary="Alpha first pass.",
        verification="Needs another pass.",
        status="needs_revision",
    )
    beta_one = record_revision(
        tmp_path,
        target="beta",
        diagnosis="local_execution_problem",
        summary="Beta first pass.",
        verification="Needs another pass.",
        status="needs_revision",
    )
    alpha_two = record_revision(
        tmp_path,
        target="alpha",
        diagnosis="structural_mismatch",
        summary="Alpha accepted.",
        verification="All alpha checks pass.",
        status="accepted",
    )

    assert beta_one.parent_revision_id is None
    assert beta_one.previous_record_sha256 == alpha_one.record_sha256
    assert alpha_two.parent_revision_id == alpha_one.revision_id
    assert alpha_two.previous_record_sha256 == beta_one.record_sha256


def test_governance_snapshot_returns_verified_consistent_bytes(tmp_path):
    _initialize(tmp_path)
    record_revision(
        tmp_path,
        target="snapshot-target",
        diagnosis="local_execution_problem",
        summary="Create one coherent snapshot.",
        verification="Snapshot test.",
        status="accepted",
    )

    snapshot = snapshot_project_governance(tmp_path)

    assert set(snapshot) == {
        "project_record.json",
        "project_summary_log.md",
        "revision_history.jsonl",
    }
    project = json.loads(snapshot["project_record.json"])
    history = json.loads(snapshot["revision_history.jsonl"])
    assert history["project_id"] == project["project_id"]
    assert "Create one coherent snapshot." in snapshot["project_summary_log.md"].decode("utf-8")


def test_governance_snapshot_rejects_stale_summary(tmp_path):
    _initialize(tmp_path)
    (tmp_path / "project_summary_log.md").write_text("# stale\n", encoding="utf-8")

    with pytest.raises(ValueError, match="out of sync"):
        snapshot_project_governance(tmp_path)


def test_governance_snapshot_is_coherent_during_concurrent_revision(tmp_path):
    _initialize(tmp_path)
    record_revision(
        tmp_path,
        target="coherent-target",
        diagnosis="local_execution_problem",
        summary="First pass.",
        verification="Needs another pass.",
        status="needs_revision",
    )
    barrier = threading.Barrier(2)

    def write_second_round():
        barrier.wait()
        return record_revision(
            tmp_path,
            target="coherent-target",
            diagnosis="structural_mismatch",
            summary="Second pass accepted.",
            verification="All checks pass.",
            status="accepted",
        )

    def read_snapshot():
        barrier.wait()
        return snapshot_project_governance(tmp_path)

    with ThreadPoolExecutor(max_workers=2) as executor:
        writer = executor.submit(write_second_round)
        reader = executor.submit(read_snapshot)
        snapshot = reader.result()
        writer.result()

    history_lines = snapshot["revision_history.jsonl"].decode("utf-8").splitlines()
    summary = snapshot["project_summary_log.md"].decode("utf-8")
    assert len(history_lines) in {1, 2}
    assert summary.count("### coherent-target") == len(history_lines)
