import hashlib
import json
import csv
from pathlib import Path

import pytest
from typer.testing import CliRunner

from claim_harness.cli import app
from claim_harness.claim_extractor import extract_claims
from claim_harness.evidence_contract import (
    EVIDENCE_CONTRACT_SCHEMA_VERSION,
    EvidenceContract,
    EvidenceContractError,
    default_evidence_contract,
    evidence_contract_id,
    load_evidence_contract,
)
from claim_harness.schemas import Claim, EvidenceItem, EvidenceLocator
from claim_harness.evidence_retriever import retrieve_evidence
from claim_harness.loader import load_manuscript
from claim_harness.report_generator import write_outputs
from claim_harness.verifier import verify_claims
from problem_bridge.generator import build_alignment_package
from problem_bridge.mock_profiles import (
    cultural_archive_profile,
    generic_profile,
    quality_inspection_profile,
    training_policy_profile,
)
from problem_bridge.writer import _to_yaml, write_alignment_package


DEMO_MANUSCRIPT = Path("examples/lab_report_audit_demo/manuscript.md")
DEMO_TABLES = Path("examples/lab_report_audit_demo/tables")
DEMO_REFERENCES = Path("examples/lab_report_audit_demo/references.md")


def _write_contract(path: Path, data: dict | None = None) -> Path:
    payload = data or default_evidence_contract().model_dump(mode="json")
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def _contract_with(mutator) -> EvidenceContract:
    payload = default_evidence_contract().model_dump(mode="json")
    mutator(payload)
    payload["contract_id"] = evidence_contract_id(payload)
    return EvidenceContract.model_validate(payload)


def _performance_fixture() -> tuple[Claim, list[EvidenceItem]]:
    claim = Claim(
        claim_id="C001",
        text="Alpha outperforms Beta on score.",
        source_section="Results",
        source_line=1,
        claim_type="performance_claim",
        strength="strong",
        requires_evidence=["table"],
    )
    evidence = [
        EvidenceItem(
            evidence_id="E001",
            source="metrics",
            locator=EvidenceLocator(source_kind="table", source_name="metrics", row=1),
            evidence_type="quantitative_result",
            text="model=Alpha; score=0.9",
            numeric_values={"score": 0.9},
            categorical_values=["Alpha"],
            linked_claim_ids=["C001"],
            claim_link_relations={"C001": "supports"},
        ),
        EvidenceItem(
            evidence_id="E002",
            source="metrics",
            locator=EvidenceLocator(source_kind="table", source_name="metrics", row=2),
            evidence_type="quantitative_result",
            text="model=Beta; score=0.7",
            numeric_values={"score": 0.7},
            categorical_values=["Beta"],
            linked_claim_ids=["C001"],
            claim_link_relations={"C001": "supports"},
        ),
    ]
    return claim, evidence


def test_committed_problembridge_samples_use_executable_versioned_contracts():
    for sample in (
        "quality_inspection_alignment",
        "cultural_archive_alignment",
        "training_policy_alignment",
    ):
        loaded = load_evidence_contract(
            Path("docs/sample_outputs") / sample / "evidence_contract.yaml"
        )
        assert loaded.contract.schema_version == EVIDENCE_CONTRACT_SCHEMA_VERSION
        assert loaded.sha256


def test_problem_bridge_writes_a_versioned_loadable_contract(tmp_path):
    package = build_alignment_package(
        "I want to evaluate whether AI can support cultural archive interpretation from catalog notes."
    )
    write_alignment_package(package, tmp_path)

    loaded = load_evidence_contract(tmp_path / "evidence_contract.yaml")

    assert loaded.contract.schema_version == EVIDENCE_CONTRACT_SCHEMA_VERSION
    assert set(loaded.contract.claim_rules) == {
        "clinical_claim",
        "deployment_claim",
        "performance_claim",
        "novelty_claim",
        "robustness_claim",
        "workflow_claim",
        "general_claim",
    }
    assert loaded.contract.claim_rules["general_claim"].minimum_evidence_count >= 1
    assert "domain_reviewer" in loaded.contract.human_review_roles
    assert "derived_text" in loaded.contract.source_kinds


@pytest.mark.parametrize(
    "profile_builder",
    [
        quality_inspection_profile,
        cultural_archive_profile,
        training_policy_profile,
        generic_profile,
    ],
)
def test_every_builtin_profile_writes_an_executable_contract(tmp_path, profile_builder):
    out = tmp_path / profile_builder.__name__
    write_alignment_package(profile_builder("Synthetic non-sensitive workflow."), out)
    loaded = load_evidence_contract(out / "evidence_contract.yaml")
    assert loaded.contract.schema_version == EVIDENCE_CONTRACT_SCHEMA_VERSION


def test_unknown_problembridge_requirement_fails_closed():
    from problem_bridge.writer import _contract_requirement

    with pytest.raises(ValueError, match="Cannot map domain evidence requirement"):
        _contract_requirement("chain_of_custody_typo")


def test_loader_accepts_safe_indented_yaml_subset(tmp_path):
    contract = default_evidence_contract(
        human_review_roles={"domain_reviewer": "Review the domain boundary."},
        role_claim_types={"general_claim"},
    )
    path = tmp_path / "indented.yaml"
    path.write_text(_to_yaml(contract.model_dump(mode="json")), encoding="utf-8")

    loaded = load_evidence_contract(path)

    assert loaded.contract == contract


@pytest.mark.parametrize(
    "mutator",
    [
        lambda payload: payload.update(schema_version=99),
        lambda payload: payload["source_kinds"].append("webcam"),
        lambda payload: payload["claim_rules"].update(
            {"unknown_claim": payload["claim_rules"]["general_claim"]}
        ),
        lambda payload: payload["claim_rules"]["general_claim"].update(
            {"required_evidence": ["unknown_requirement"]}
        ),
        lambda payload: payload["claim_rules"]["general_claim"].update(
            {"unknown_rule_field": True}
        ),
    ],
)
def test_contract_fails_closed_for_unknown_schema_rule_or_source(tmp_path, mutator):
    payload = default_evidence_contract().model_dump(mode="json")
    mutator(payload)
    path = _write_contract(tmp_path / "invalid.yaml", payload)

    with pytest.raises(EvidenceContractError):
        load_evidence_contract(path)


@pytest.mark.parametrize(
    "mutator",
    [
        lambda payload: payload.update(strong_evidence_types=["result_text"]),
        lambda payload: payload["claim_rules"]["clinical_claim"].update(
            required_evidence=["external_validation"],
            forbidden_without=["external_validation"],
        ),
        lambda payload: payload["claim_rules"]["deployment_claim"].update(
            minimum_evidence_count=1
        ),
    ],
)
def test_contract_cannot_promote_narrative_evidence_or_weaken_high_risk_baseline(
    tmp_path, mutator
):
    payload = default_evidence_contract(project_id="project-safety").model_dump(mode="json")
    mutator(payload)
    payload["contract_id"] = evidence_contract_id(payload)
    path = _write_contract(tmp_path / "unsafe-contract.yaml", payload)

    with pytest.raises(EvidenceContractError):
        load_evidence_contract(path)


def test_invalid_contract_fails_before_output_directory_is_created(tmp_path):
    payload = default_evidence_contract().model_dump(mode="json")
    payload["schema_version"] = 999
    contract_path = _write_contract(tmp_path / "invalid.yaml", payload)
    output_dir = tmp_path / "must_not_exist"

    result = CliRunner().invoke(
        app,
        [
            "run",
            "--manuscript",
            str(DEMO_MANUSCRIPT),
            "--tables",
            str(DEMO_TABLES),
            "--references",
            str(DEMO_REFERENCES),
            "--evidence-contract",
            str(contract_path),
            "--out",
            str(output_dir),
            "--llm",
            "mock",
        ],
    )

    assert result.exit_code != 0
    assert "evidence contract" in result.output.lower()
    assert not output_dir.exists()


def test_cli_records_share_safe_contract_path_and_hash(tmp_path):
    contract_path = _write_contract(tmp_path / "contract.yaml")
    output_dir = tmp_path / "audit"

    result = CliRunner().invoke(
        app,
        [
            "run",
            "--manuscript",
            str(DEMO_MANUSCRIPT),
            "--tables",
            str(DEMO_TABLES),
            "--references",
            str(DEMO_REFERENCES),
            "--evidence-contract",
            str(contract_path),
            "--out",
            str(output_dir),
            "--llm",
            "mock",
        ],
    )

    assert result.exit_code == 0, result.output
    expected_hash = hashlib.sha256(contract_path.read_bytes()).hexdigest()
    manifest_text = (output_dir / "run_manifest.json").read_text(encoding="utf-8")
    manifest = json.loads(manifest_text)
    contract_record = manifest["inputs"]["evidence_contract"]
    assert contract_record == {
        "path": contract_path.name,
        "size_bytes": contract_path.stat().st_size,
        "sha256": expected_hash,
        "schema_version": EVIDENCE_CONTRACT_SCHEMA_VERSION,
        "project_id": "project-unbound",
        "contract_id": default_evidence_contract().contract_id,
    }
    assert str(tmp_path.resolve()) not in manifest_text

    trace = [
        json.loads(line)
        for line in (output_dir / "agent_trace.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    contract_event = next(event for event in trace if event["module"] == "evidence_contract")
    assert contract_event["data"] == {
        "path": contract_path.name,
        "sha256": expected_hash,
        "schema_version": EVIDENCE_CONTRACT_SCHEMA_VERSION,
        "project_id": "project-unbound",
        "contract_id": default_evidence_contract().contract_id,
    }


def test_cli_rejects_contract_from_a_different_explicit_project_before_mutation(tmp_path):
    contract = default_evidence_contract(project_id="project-alpha")
    contract_path = _write_contract(
        tmp_path / "project-alpha-contract.yaml",
        contract.model_dump(mode="json"),
    )
    output_dir = tmp_path / "must-not-exist"

    result = CliRunner().invoke(
        app,
        [
            "run",
            "--manuscript",
            str(DEMO_MANUSCRIPT),
            "--tables",
            str(DEMO_TABLES),
            "--references",
            str(DEMO_REFERENCES),
            "--evidence-contract",
            str(contract_path),
            "--project-id",
            "project-beta",
            "--out",
            str(output_dir),
        ],
    )

    assert result.exit_code != 0
    assert "project mismatch" in result.output.lower()
    assert not output_dir.exists()


def test_contract_minimum_count_and_strong_types_change_verification():
    claim, evidence = _performance_fixture()
    assert verify_claims([claim], evidence)[0].status == "supported"

    minimum_three = _contract_with(
        lambda payload: payload["claim_rules"]["performance_claim"].update(
            minimum_evidence_count=3
        )
    )
    minimum_result = verify_claims([claim], evidence, minimum_three)[0]
    assert minimum_result.status == "weakly_supported"
    assert "minimum_evidence_count=3" in minimum_result.missing_evidence

    no_table_strength = _contract_with(
        lambda payload: payload.update(strong_evidence_types=["external_validation"])
    )
    strength_result = verify_claims([claim], evidence, no_table_strength)[0]
    assert strength_result.status == "weakly_supported"
    assert "table" in strength_result.missing_evidence

    no_table_sources = _contract_with(
        lambda payload: payload.update(
            source_kinds=[kind for kind in payload["source_kinds"] if kind != "table"]
        )
    )
    source_result = verify_claims([claim], evidence, no_table_sources)[0]
    assert source_result.status == "unsupported"
    assert source_result.supporting_evidence_ids == []


def test_contract_applies_forbidden_conditions_and_human_review_roles():
    claim = Claim(
        claim_id="C001",
        text="The workflow enables auditable tracing.",
        source_section="Discussion",
        source_line=1,
        claim_type="workflow_claim",
        strength="moderate",
        requires_evidence=["trace"],
    )
    trace = EvidenceItem(
        evidence_id="S001",
        source="Methods",
        locator=EvidenceLocator(source_kind="manuscript", source_name="Methods", line=2),
        evidence_type="workflow_trace",
        text="The workflow records an auditable trace.",
        linked_claim_ids=["C001"],
        claim_link_relations={"C001": "supports"},
    )
    human_review = EvidenceItem(
        evidence_id="H001",
        source="review",
        locator=EvidenceLocator(source_kind="external", source_name="review", line=1),
        evidence_type="human_review",
        text="The audit lead approved the trace boundary.",
        categorical_values=["audit_lead"],
        linked_claim_ids=["C001"],
        claim_link_relations={"C001": "supports"},
    )

    def add_review_policy(payload):
        payload["human_review_roles"] = {"audit_lead": "Approve the trace boundary."}
        payload["claim_rules"]["workflow_claim"].update(
            forbidden_without=["human_review"],
            human_review_roles=["audit_lead"],
        )

    contract = _contract_with(add_review_policy)
    missing_review = verify_claims([claim], [trace], contract)[0]
    complete = verify_claims([claim], [trace, human_review], contract)[0]

    assert missing_review.status == "needs_human_review"
    assert "human_review" in missing_review.missing_evidence
    assert "human_review_role=audit_lead" in missing_review.missing_evidence
    assert complete.status == "weakly_supported"


@pytest.mark.parametrize("source_kind", ["ocr", "derived_text"])
def test_ocr_and_derived_text_never_count_as_strong_evidence(source_kind):
    claim = Claim(
        claim_id="C001",
        text="The method is robust.",
        source_section="Results",
        source_line=1,
        claim_type="robustness_claim",
        strength="moderate",
        requires_evidence=["robustness_test"],
    )
    ocr_evidence = EvidenceItem(
        evidence_id="O001",
        source="scan.png",
        locator=EvidenceLocator(source_kind=source_kind, source_name="scan.png", line=1),
        evidence_type="robustness_test",
        text="OCR-derived robustness test statement.",
        linked_claim_ids=["C001"],
        claim_link_relations={"C001": "supports"},
    )

    result = verify_claims([claim], [ocr_evidence], default_evidence_contract())[0]

    assert result.status == "weakly_supported"
    assert "robustness_test" in result.missing_evidence


@pytest.mark.parametrize("source_kind", ["ocr", "derived_text"])
def test_derived_human_review_cannot_approve_a_clinical_claim(source_kind):
    claim = Claim(
        claim_id="C001",
        text="The intervention reduced symptoms in the clinical cohort.",
        source_section="Conclusion",
        source_line=1,
        claim_type="clinical_claim",
        strength="strong",
        requires_evidence=["external_validation", "human_review"],
    )
    external_validation = EvidenceItem(
        evidence_id="E001",
        source="external study",
        locator=EvidenceLocator(source_kind="external", source_name="study", line=1),
        evidence_type="external_validation",
        text="Independent validation evidence.",
        linked_claim_ids=["C001"],
        claim_link_relations={"C001": "supports"},
    )
    derived_review = EvidenceItem(
        evidence_id="H001",
        source="scan.png",
        locator=EvidenceLocator(source_kind=source_kind, source_name="scan.png", line=1),
        evidence_type="human_review",
        text="OCR-derived note that appears to approve the claim.",
        linked_claim_ids=["C001"],
        claim_link_relations={"C001": "supports"},
    )

    result = verify_claims(
        [claim],
        [external_validation, derived_review],
        default_evidence_contract(),
    )[0]

    assert result.status == "needs_human_review"
    assert "human_review" in result.missing_evidence


def test_problembridge_ocr_marker_propagates_to_claim_outputs_and_requires_review(tmp_path):
    manuscript = tmp_path / "extracted_text.md"
    manuscript.write_text(
        "# Source: scan.png\n"
        "<!-- provenance: derived_text/ocr; inspect source -->\n"
        "## Methods\nThe guided workflow enables auditable review.\n"
        "## Results\nA separate trace enables auditable review of the workflow.\n",
        encoding="utf-8",
    )
    sections = load_manuscript(manuscript)
    claims = extract_claims(sections)
    evidence = retrieve_evidence(claims, sections, {}, "")
    results = verify_claims(claims, evidence)

    assert claims
    assert all(claim.source_kind == "ocr" for claim in claims)
    assert all(result.status == "needs_human_review" for result in results)
    assert all("source_inspection" in result.missing_evidence for result in results)

    out = tmp_path / "out"
    write_outputs(out, claims, evidence, results)
    with (out / "claim_table.csv").open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert rows and all(row["source_kind"] == "ocr" for row in rows)
    evidence_map = json.loads((out / "evidence_map.json").read_text(encoding="utf-8"))
    assert all(item["source_kind"] == "ocr" for item in evidence_map["claims"])
    assert "- Source kind: ocr" in (out / "audit_report.md").read_text(encoding="utf-8")


def test_no_contract_keeps_legacy_behavior_and_records_none(tmp_path):
    claim, evidence = _performance_fixture()
    assert verify_claims([claim], evidence)[0].status == "supported"

    output_dir = tmp_path / "legacy"
    result = CliRunner().invoke(
        app,
        [
            "run",
            "--manuscript",
            str(DEMO_MANUSCRIPT),
            "--tables",
            str(DEMO_TABLES),
            "--references",
            str(DEMO_REFERENCES),
            "--out",
            str(output_dir),
            "--llm",
            "mock",
        ],
    )

    assert result.exit_code == 0, result.output
    manifest = json.loads((output_dir / "run_manifest.json").read_text(encoding="utf-8"))
    assert manifest["inputs"]["evidence_contract"] is None
    assert "built-in legacy verification rules" in (
        output_dir / "project_summary_log.md"
    ).read_text(encoding="utf-8")
