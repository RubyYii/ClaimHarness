import json

import pytest
from typer.testing import CliRunner

from problem_bridge.cli import app
from problem_bridge.revision_governance import (
    MAX_REVISION_ROUNDS,
    RevisionLimitReached,
    initialize_project_record,
    load_revision_history,
    record_revision,
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
        ],
    )

    assert result.exit_code == 0, result.output
    records = load_revision_history(tmp_path)
    assert records[0].status == "accepted"
    assert records[0].changed_files == ("claim_harness/loader.py",)
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
