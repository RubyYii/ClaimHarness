from claim_harness.schemas import (
    AuditEvent,
    Claim,
    EvidenceItem,
    ManuscriptSection,
    VerificationResult,
)


def test_schema_models_accept_expected_fields():
    section = ManuscriptSection(name="Results", text="Metrics improved.", start_line=12)
    claim = Claim(
        claim_id="C001",
        text="The method improves Dice.",
        source_section="Results",
        claim_type="performance_claim",
        strength="strong",
        requires_evidence=["table"],
    )
    evidence = EvidenceItem(
        evidence_id="E001",
        source="table1_metrics",
        evidence_type="quantitative_result",
        text="Dice increased to 0.89.",
        linked_claim_ids=["C001"],
    )
    result = VerificationResult(
        claim_id="C001",
        status="supported",
        reason="The metric table reports the improvement.",
        risk_level="low",
        suggested_revision="No revision needed.",
    )
    event = AuditEvent(step=1, module="loader", message="Loaded inputs", data={"tables": 2})

    assert section.name == "Results"
    assert claim.requires_evidence == ["table"]
    assert evidence.linked_claim_ids == ["C001"]
    assert result.status == "supported"
    assert event.data["tables"] == 2


def test_evidence_linked_claim_ids_default_isolated():
    first = EvidenceItem(
        evidence_id="E001",
        source="references",
        evidence_type="citation",
        text="Reference note.",
    )
    second = EvidenceItem(
        evidence_id="E002",
        source="references",
        evidence_type="citation",
        text="Another reference note.",
    )

    first.linked_claim_ids.append("C001")

    assert first.linked_claim_ids == ["C001"]
    assert second.linked_claim_ids == []
