import csv
import json
from pathlib import Path

import pandas as pd
import pytest
from pydantic import ValidationError

from claim_harness.claim_extractor import extract_claims
from claim_harness.diagnostics import build_audit_diagnostics, write_audit_diagnostics
from claim_harness.evidence_retriever import retrieve_evidence
from claim_harness.loader import load_manuscript, load_references, load_tables
from claim_harness.report_generator import write_outputs
from claim_harness.review_queue import build_human_review_queue, write_human_review_queue
from claim_harness.schemas import Claim, EvidenceItem, EvidenceLocator, VerificationResult
from claim_harness.verifier import verify_claims


DEMO_MANUSCRIPT = Path("examples/lab_report_audit_demo/manuscript.md")
DEMO_TABLES = Path("examples/lab_report_audit_demo/tables")
DEMO_REFERENCES = Path("examples/lab_report_audit_demo/references.md")


def _claim(claim_id: str, text: str) -> Claim:
    return Claim(
        claim_id=claim_id,
        text=text,
        source_section="Results",
        source_line=1,
        claim_type="performance_claim",
        strength="strong",
        requires_evidence=["table"],
    )


def test_table_links_keep_base_row_but_narrow_each_claim_to_matched_cells(tmp_path):
    claims = [
        _claim("C001", "Alpha score reaches 0.9."),
        _claim("C002", "Alpha recall reaches 0.8."),
    ]
    frame = pd.DataFrame(
        [{"model": "Alpha", "score": 0.9, "recall": 0.8, "notes": "unrelated prose"}]
    )
    frame.attrs["source_file"] = r"C:\private\metrics.csv"

    evidence = retrieve_evidence(claims, [], {"metrics": frame}, "")
    item = evidence[0]

    assert item.locator.source_file == "metrics.csv"
    assert item.locator.row == 1
    assert [cell.cell for cell in item.locator.cells] == ["A2", "B2", "C2", "D2"]
    assert [cell.column for cell in item.claim_link_locators["C001"].cells] == [
        "model",
        "score",
    ]
    assert [cell.column for cell in item.claim_link_locators["C002"].cells] == [
        "model",
        "recall",
    ]

    results = verify_claims(claims, evidence)
    write_outputs(tmp_path, claims, evidence, results)
    with (tmp_path / "claim_table.csv").open(newline="", encoding="utf-8") as handle:
        claim_rows = list(csv.DictReader(handle))
    payload = json.loads((tmp_path / "evidence_map.json").read_text(encoding="utf-8"))
    links = {
        entry["claim_id"]: entry["evidence_links"][0]["locator"]
        for entry in payload["claims"]
    }
    assert [cell["column"] for cell in links["C001"]["cells"]] == ["model", "score"]
    assert [cell["column"] for cell in links["C002"]["cells"]] == ["model", "recall"]
    assert "claim_link_locators" not in payload["evidence"][0]
    assert all(row["human_review_required"] == "false" for row in claim_rows)
    assert all(row["release_allowed"] == "true" for row in claim_rows)
    report = (tmp_path / "audit_report.md").read_text(encoding="utf-8")
    assert "- Human review required: no" in report
    assert "- Release allowed: yes" in report


def test_loader_retains_only_share_safe_input_filenames():
    sections = load_manuscript(DEMO_MANUSCRIPT)
    tables = load_tables(DEMO_TABLES)

    assert {section.source_file for section in sections} == {"manuscript.md"}
    assert tables["table1_metrics"].attrs["source_file"] == "table1_metrics.csv"

    claim = _claim("C001", "Alpha score reaches 0.9.")
    evidence = retrieve_evidence(
        [claim],
        sections,
        {},
        "1. Reference entry.",
        references_file=r"C:\private\references.md",
    )
    reference = next(item for item in evidence if item.locator.source_kind == "references")
    assert reference.locator.source_file == "references.md"


def test_locator_extension_is_backward_compatible_and_rejects_invalid_page():
    locator = EvidenceLocator(source_kind="table", source_name="metrics", row=1)

    assert locator.source_file is None
    assert locator.page_number is None
    assert locator.cells == []
    with pytest.raises(ValidationError):
        EvidenceLocator(
            source_kind="manuscript",
            source_name="Results",
            page_number=0,
        )


def test_demo_structural_diagnostics_match_the_deterministic_pipeline():
    sections = load_manuscript(DEMO_MANUSCRIPT)
    tables = load_tables(DEMO_TABLES)
    references = load_references(DEMO_REFERENCES)
    claims = extract_claims(sections)
    evidence = retrieve_evidence(claims, sections, tables, references)
    results = verify_claims(claims, evidence)

    diagnostics = build_audit_diagnostics(claims, evidence, results)

    assert diagnostics["schema_version"] == 2
    assert diagnostics["totals"] == {
        "claims": 16,
        "evidence_items": 26,
        "claim_evidence_links": 67,
    }
    assert diagnostics["metrics"]["any_link_coverage"] == {
        "numerator": 15,
        "denominator": 16,
        "rate": 0.9375,
    }
    assert diagnostics["metrics"]["support_relation_coverage"]["rate"] == 0.75
    assert diagnostics["metrics"]["unlinked_evidence_items"]["rate"] == 0.115385
    assert diagnostics["requirement_gap_counts"] == {
        "citation": 1,
        "external_validation": 1,
        "human_review": 1,
        "robustness_test": 3,
        "table": 1,
        "trace": 4,
    }
    assert diagnostics["metrics"]["human_review_required"]["numerator"] == 2
    assert diagnostics["metrics"]["release_allowed"]["numerator"] == 3
    assert diagnostics["release_boundary_by_claim"]["C003"] == {
        "human_review_required": True,
        "release_allowed": False,
    }
    assert "do not establish factual correctness" in diagnostics["boundary"]


def test_diagnostics_distinguish_related_links_from_support_relations_and_zero_denominators():
    claim = _claim("C001", "Alpha score improves.")
    evidence = EvidenceItem(
        evidence_id="E001",
        source="metrics",
        locator=EvidenceLocator(source_kind="table", source_name="metrics", row=1),
        evidence_type="quantitative_result",
        text="model=Alpha",
        linked_claim_ids=["C001"],
        claim_link_relations={"C001": "related"},
    )
    result = VerificationResult(
        claim_id="C001",
        status="weakly_supported",
        reason="Related only.",
        risk_level="low",
        suggested_revision="Add stronger evidence.",
    )

    diagnostics = build_audit_diagnostics([claim], [evidence], [result])
    empty = build_audit_diagnostics([], [], [])

    assert diagnostics["metrics"]["any_link_coverage"]["rate"] == 1.0
    assert diagnostics["metrics"]["support_relation_coverage"]["rate"] == 0.0
    assert all(metric["rate"] is None for metric in empty["metrics"].values())


def test_review_queue_is_pending_role_specific_and_never_an_approval():
    claim = _claim("C001", "Alpha is ready for deployment.")
    result = VerificationResult(
        claim_id="C001",
        status="needs_human_review",
        reason="Named review is required.",
        risk_level="high",
        suggested_revision="Obtain bounded review.",
        human_review_required=True,
        release_allowed=False,
        missing_evidence=["human_review", "human_review_role=audit_lead"],
        supporting_evidence_ids=["E001"],
    )

    queue = build_human_review_queue([claim], [result])

    assert queue["schema_version"] == 2
    assert queue["counts"] == {"pending_items": 1, "claims_routed": 1}
    assert queue["items"][0]["required_role"] == "audit_lead"
    assert queue["items"][0]["role_origin"] == "evidence_contract"
    assert queue["items"][0]["state"] == "pending"
    assert queue["items"][0]["human_review_required"] is True
    assert queue["items"][0]["release_allowed"] is False
    assert "release_not_allowed" in queue["items"][0]["trigger_codes"]
    assert "approval" in queue["boundary"]
    assert "decision" not in queue["items"][0]


def test_high_risk_supported_result_is_still_pending_in_review_queue():
    claim = _claim("C001", "Alpha is clinically effective.")
    result = VerificationResult(
        claim_id="C001",
        status="supported",
        reason="Requirements are met within the supplied evidence.",
        risk_level="high",
        suggested_revision="No wording revision within scope.",
        human_review_required=True,
        release_allowed=False,
        supporting_evidence_ids=["E001", "E002"],
    )

    queue = build_human_review_queue([claim], [result])

    assert queue["counts"] == {"pending_items": 1, "claims_routed": 1}
    assert queue["items"][0]["verification_status"] == "supported"
    assert "high_risk_claim" in queue["items"][0]["trigger_codes"]
    assert queue["items"][0]["release_allowed"] is False


def test_diagnostic_and_review_artifacts_are_byte_deterministic(tmp_path):
    claim = _claim("C001", "Alpha score improves.")
    result = VerificationResult(
        claim_id="C001",
        status="needs_human_review",
        reason="Review required.",
        risk_level="low",
        suggested_revision="Review it.",
        human_review_required=True,
        release_allowed=False,
    )
    first_diagnostics = tmp_path / "first-diagnostics.json"
    second_diagnostics = tmp_path / "second-diagnostics.json"
    first_queue = tmp_path / "first-queue.json"
    second_queue = tmp_path / "second-queue.json"

    write_audit_diagnostics(first_diagnostics, [claim], [], [result])
    write_audit_diagnostics(second_diagnostics, [claim], [], [result])
    write_human_review_queue(first_queue, [claim], [result])
    write_human_review_queue(second_queue, [claim], [result])

    assert first_diagnostics.read_bytes() == second_diagnostics.read_bytes()
    assert first_queue.read_bytes() == second_queue.read_bytes()
