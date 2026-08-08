from pathlib import Path

import pandas as pd
import pytest

from claim_harness.claim_extractor import extract_claims
from claim_harness.evidence_retriever import retrieve_evidence
from claim_harness.loader import load_manuscript
from claim_harness.schemas import (
    Claim,
    EvidenceItem,
    EvidenceLocator,
    ManuscriptSection,
    VerificationResult,
)
from claim_harness.verifier import verify_claims


def test_result_claim_cannot_support_itself():
    section = ManuscriptSection(
        name="Results",
        text="The Alpha system improves macro score.",
        start_line=1,
        content_start_line=2,
    )
    claims = extract_claims([section])

    evidence = retrieve_evidence(claims, [section], {}, "")
    result = verify_claims(claims, evidence)[0]

    assert all(claims[0].claim_id not in item.linked_claim_ids for item in evidence)
    assert result.status == "unsupported"
    assert result.missing_evidence == ["table"]


def test_repeated_result_assertions_cannot_support_each_other():
    section = ManuscriptSection(
        name="Results",
        text=(
            "The Alpha system improves macro score.\n"
            "The Alpha system improves macro score."
        ),
        start_line=1,
        content_start_line=2,
    )
    claims = extract_claims([section])

    evidence = retrieve_evidence(claims, [section], {}, "")
    results = verify_claims(claims, evidence)

    assert len(claims) == 2
    assert all(not item.linked_claim_ids for item in evidence)
    assert [result.status for result in results] == ["unsupported", "unsupported"]
    assert all(result.missing_evidence == ["table"] for result in results)


def test_same_source_location_is_rejected_even_when_text_is_not_identical():
    section = ManuscriptSection(
        name="Results",
        text="The Alpha system improves macro score.",
        start_line=1,
        content_start_line=2,
    )
    claim = Claim(
        claim_id="C001",
        text="The Alpha system improves macro score substantially.",
        source_section="Results",
        source_line=2,
        claim_type="performance_claim",
        strength="strong",
        requires_evidence=["table"],
    )

    evidence = retrieve_evidence([claim], [section], {}, "")

    assert evidence
    assert all("C001" not in item.linked_claim_ids for item in evidence)


def test_distinct_sentence_on_same_source_line_can_remain_candidate_evidence():
    section = ManuscriptSection(
        name="Results",
        text=(
            "The Alpha system improves macro score. "
            "A separate ablation shows Alpha improves score without a review gate."
        ),
        start_line=1,
        content_start_line=2,
    )
    claim = Claim(
        claim_id="C001",
        text="The Alpha system improves macro score.",
        source_section="Results",
        source_line=2,
        claim_type="performance_claim",
        strength="strong",
        requires_evidence=["table"],
    )

    evidence = retrieve_evidence([claim], [section], {}, "")

    linked_text = [item.text for item in evidence if "C001" in item.linked_claim_ids]
    assert linked_text == [
        "A separate ablation shows Alpha improves score without a review gate."
    ]


def test_direct_verifier_rejects_exact_claim_text_from_another_location():
    claim = Claim(
        claim_id="C001",
        text="The workflow records an auditable trace.",
        source_section="Results",
        source_line=2,
        claim_type="workflow_claim",
        strength="moderate",
        requires_evidence=["trace"],
    )
    duplicate = EvidenceItem(
        evidence_id="E001",
        source="Discussion",
        locator=EvidenceLocator(
            source_kind="manuscript", source_name="Discussion", line=9
        ),
        evidence_type="workflow_trace",
        text=claim.text,
        linked_claim_ids=[claim.claim_id],
        claim_link_relations={claim.claim_id: "supports"},
    )

    result = verify_claims([claim], [duplicate])[0]

    assert result.supporting_evidence_ids == []
    assert result.missing_evidence == ["trace"]


def test_verification_result_enforces_review_and_release_invariants():
    high_risk = VerificationResult(
        claim_id="C001",
        status="supported",
        reason="Constructed outside verify_claims.",
        risk_level="high",
        suggested_revision="Route to review.",
        release_allowed=True,
    )
    review_status = VerificationResult(
        claim_id="C002",
        status="needs_human_review",
        reason="Review required.",
        risk_level="low",
        suggested_revision="Review it.",
        human_review_required=False,
        release_allowed=True,
    )

    assert high_risk.human_review_required is True
    assert high_risk.release_allowed is False
    assert review_status.human_review_required is True
    assert review_status.release_allowed is False


def test_discussion_assertions_are_not_promoted_to_workflow_traces():
    sections = [
        ManuscriptSection(
            name="Methods",
            text="The workflow records each audit step.",
            start_line=1,
            content_start_line=2,
        ),
        ManuscriptSection(
            name="Discussion",
            text=(
                "The workflow appears useful for audit teams. "
                "It does not establish deployment readiness."
            ),
            start_line=3,
            content_start_line=4,
        ),
    ]

    evidence = retrieve_evidence([], sections, {}, "")
    types_by_source = {
        item.source: [entry.evidence_type for entry in evidence if entry.source == item.source]
        for item in evidence
    }

    assert types_by_source["Methods"] == ["workflow_trace"]
    assert types_by_source["Discussion"] == [
        "narrative_assertion",
        "limitation_statement",
    ]


def test_source_locations_preserve_original_coordinates(tmp_path: Path):
    manuscript = tmp_path / "manuscript.md"
    manuscript.write_text(
        "# Title\n\nContext.\n\n## Results\nThe Alpha system improves score.\n",
        encoding="utf-8",
    )
    sections = load_manuscript(manuscript)
    claims = extract_claims(sections)
    evidence = retrieve_evidence(
        claims,
        sections,
        {"metrics": pd.DataFrame([{"model": "Alpha", "score": 0.9}, {"model": "Beta", "score": 0.7}])},
        "# References\n\n1. Alpha score study.\n",
    )

    assert claims[0].source_line == 6
    table_items = [item for item in evidence if item.locator.source_kind == "table"]
    assert [item.locator.row for item in table_items] == [1, 2]
    reference = next(item for item in evidence if item.locator.source_kind == "references")
    assert reference.locator.line == 3


def test_verifier_enforces_required_evidence():
    claim = Claim(
        claim_id="C001",
        text="The workflow enables auditable tracing.",
        source_section="Discussion",
        source_line=1,
        claim_type="workflow_claim",
        strength="moderate",
        requires_evidence=["ablation", "trace"],
    )
    ablation = EvidenceItem(
        evidence_id="E001",
        source="ablation",
        locator=EvidenceLocator(source_kind="table", source_name="ablation", row=1),
        evidence_type="ablation_result",
        text="setting=full; success_rate=0.9",
        numeric_values={"success_rate": 0.9},
        linked_claim_ids=["C001"],
        claim_link_relations={"C001": "supports"},
    )
    trace = EvidenceItem(
        evidence_id="S001",
        source="Methods",
        locator=EvidenceLocator(source_kind="manuscript", source_name="Methods", line=3),
        evidence_type="workflow_trace",
        text="The workflow records a trace for audit.",
        linked_claim_ids=["C001"],
        claim_link_relations={"C001": "supports"},
    )

    missing_trace = verify_claims([claim], [ablation])[0]
    complete = verify_claims([claim], [ablation, trace])[0]

    assert missing_trace.status == "weakly_supported"
    assert missing_trace.missing_evidence == ["trace"]
    assert complete.status == "supported"
    assert complete.human_review_required is False
    assert complete.release_allowed is True


def test_high_risk_claims_route_to_review_or_overclaim():
    clinical = Claim(
        claim_id="C001",
        text="The method clinically improves outcomes.",
        source_section="Discussion",
        source_line=1,
        claim_type="clinical_claim",
        strength="high",
        requires_evidence=["external_validation", "human_review"],
    )
    deployment = clinical.model_copy(
        update={
            "claim_id": "C002",
            "text": "The method is ready for real-world clinical deployment.",
            "claim_type": "deployment_claim",
        }
    )
    internal = EvidenceItem(
        evidence_id="E001",
        source="metrics",
        locator=EvidenceLocator(source_kind="table", source_name="metrics", row=1),
        evidence_type="quantitative_result",
        text="metric=0.9",
        numeric_values={"metric": 0.9},
        linked_claim_ids=["C001", "C002"],
        claim_link_relations={"C001": "supports", "C002": "supports"},
    )

    results = verify_claims([clinical, deployment], [internal])

    assert results[0].status == "needs_human_review"
    assert results[1].status == "overclaimed"
    assert all(result.human_review_required for result in results)
    assert all(not result.release_allowed for result in results)


def test_high_risk_supported_claim_still_requires_review_and_blocks_release():
    claim = Claim(
        claim_id="C001",
        text="The method clinically improves outcomes.",
        source_section="Discussion",
        source_line=1,
        claim_type="clinical_claim",
        strength="high",
        requires_evidence=["external_validation", "human_review"],
    )
    external_validation = EvidenceItem(
        evidence_id="E001",
        source="independent-study",
        locator=EvidenceLocator(
            source_kind="external", source_name="independent-study", line=1
        ),
        evidence_type="external_validation",
        text="An independent validation reports improved outcomes.",
        linked_claim_ids=["C001"],
        claim_link_relations={"C001": "supports"},
    )
    human_review = EvidenceItem(
        evidence_id="E002",
        source="review-record",
        locator=EvidenceLocator(source_kind="external", source_name="review-record", line=1),
        evidence_type="human_review",
        text="A qualified reviewer inspected the claim boundary.",
        linked_claim_ids=["C001"],
        claim_link_relations={"C001": "supports"},
    )

    result = verify_claims([claim], [external_validation, human_review])[0]

    assert result.status == "supported"
    assert result.risk_level == "high"
    assert result.human_review_required is True
    assert result.release_allowed is False


def test_negation_meta_language_and_word_boundaries():
    section = ManuscriptSection(
        name="Discussion",
        text=(
            "The input is already normalized. Firstly, values are listed. "
            "The estimate is unreliable. The device is not clinically ready. "
            "The manuscript warns against claiming deployment-ready status."
        ),
        start_line=1,
        content_start_line=2,
    )

    claims = extract_claims([section])

    assert len(claims) == 1
    assert claims[0].text == "The device is not clinically ready."
    assert claims[0].polarity == "negative"
    assert verify_claims(claims, [])[0].status == "needs_human_review"


def test_numeric_table_relation_checks_direction_and_comparator():
    claim = Claim(
        claim_id="C001",
        text="Alpha outperforms Beta on score.",
        source_section="Results",
        source_line=1,
        claim_type="performance_claim",
        strength="strong",
        requires_evidence=["table"],
    )

    def status(rows):
        evidence = retrieve_evidence([claim], [], {"metrics": pd.DataFrame(rows)}, "")
        return verify_claims([claim], evidence)[0].status

    assert status([{"model": "Alpha", "score": 0.9}, {"model": "Beta", "score": 0.7}]) == "supported"
    assert status([{"model": "Alpha", "score": 0.7}, {"model": "Beta", "score": 0.9}]) != "supported"
    assert status([{"model": "Alpha", "score": 0.9}]) != "supported"


def _comparison_status(text: str, rows: list[dict[str, object]]) -> str:
    claim = Claim(
        claim_id="C001",
        text=text,
        source_section="Results",
        source_line=1,
        claim_type="performance_claim",
        strength="strong",
        requires_evidence=["table"],
    )
    evidence = retrieve_evidence([claim], [], {"metrics": pd.DataFrame(rows)}, "")
    return verify_claims([claim], evidence)[0].status


@pytest.mark.parametrize(
    ("text", "rows"),
    [
        (
            "Alpha outperforms Beta and Gamma on score.",
            [
                {"model": "Alpha", "score": 0.8},
                {"model": "Beta", "score": 0.9},
                {"model": "Gamma", "score": 0.7},
            ],
        ),
        (
            "Alpha outperforms Beta on score and accuracy.",
            [
                {"model": "Alpha", "score": 0.9, "accuracy": 0.5},
                {"model": "Beta", "score": 0.8, "accuracy": 0.6},
            ],
        ),
        (
            "Alpha outperforms Beta on score: 0.9 versus 0.8.",
            [
                {"model": "Alpha", "score": 0.8},
                {"model": "Beta", "score": 0.7},
            ],
        ),
        (
            "Alpha outperforms Beta on score by 0.2.",
            [
                {"model": "Alpha", "score": 0.8},
                {"model": "Beta", "score": 0.7},
            ],
        ),
        (
            "Alpha improves score from 70% to 90%.",
            [
                {"model": "Alpha", "score": 0.8},
                {"model": "Beta", "score": 0.7},
            ],
        ),
        (
            "Alpha outperforms Beta on error rate.",
            [
                {"model": "Alpha", "error_rate": 0.2},
                {"model": "Beta", "error_rate": 0.1},
            ],
        ),
        (
            "Alpha outperforms Beta with lower error rate and higher accuracy.",
            [
                {"model": "Alpha", "error_rate": 0.1, "accuracy": 0.7},
                {"model": "Beta", "error_rate": 0.2, "accuracy": 0.8},
            ],
        ),
        (
            "Alpha Pro outperforms Alpha Base on score.",
            [
                {"model": "Alpha Pro", "score": 0.7},
                {"model": "Alpha Base", "score": 0.9},
            ],
        ),
    ],
)
def test_comparison_claim_requires_every_explicit_constraint(text, rows):
    assert _comparison_status(text, rows) != "supported"


@pytest.mark.parametrize(
    ("text", "rows"),
    [
        (
            "Alpha outperforms Beta and Gamma on score.",
            [
                {"model": "Alpha", "score": 0.9},
                {"model": "Beta", "score": 0.8},
                {"model": "Gamma", "score": 0.7},
            ],
        ),
        (
            "Alpha outperforms Beta on score and accuracy.",
            [
                {"model": "Alpha", "score": 0.9, "accuracy": 0.8},
                {"model": "Beta", "score": 0.8, "accuracy": 0.7},
            ],
        ),
        (
            "Alpha outperforms Beta on score: 0.9 versus 0.8.",
            [
                {"model": "Alpha", "score": 0.9},
                {"model": "Beta", "score": 0.8},
            ],
        ),
        (
            "Alpha outperforms Beta on score by 0.2.",
            [
                {"model": "Alpha", "score": 0.9},
                {"model": "Beta", "score": 0.7},
            ],
        ),
        (
            "Alpha improves score from 70% to 90%.",
            [
                {"model": "Alpha", "score": 0.9},
                {"model": "Beta", "score": 0.7},
            ],
        ),
        (
            "Alpha outperforms Beta on error rate.",
            [
                {"model": "Alpha", "error_rate": 0.1},
                {"model": "Beta", "error_rate": 0.2},
            ],
        ),
        (
            "Alpha outperforms Beta with lower error rate and higher accuracy.",
            [
                {"model": "Alpha", "error_rate": 0.1, "accuracy": 0.9},
                {"model": "Beta", "error_rate": 0.2, "accuracy": 0.8},
            ],
        ),
        (
            "Alpha Pro outperforms Alpha Base on score.",
            [
                {"model": "Alpha Pro", "score": 0.9},
                {"model": "Alpha Base", "score": 0.7},
            ],
        ),
    ],
)
def test_comparison_claim_supports_only_when_every_constraint_matches(text, rows):
    assert _comparison_status(text, rows) == "supported"


def test_noncomparison_quantitative_claim_binds_every_metric_and_value():
    text = "Alpha supports Dice 0.9 and recall 0.8."

    assert _comparison_status(
        text,
        [{"model": "Alpha", "dice": 0.9, "recall": 0.1}],
    ) != "supported"
    assert _comparison_status(
        text,
        [{"model": "Alpha", "dice": 0.9, "recall": 0.8}],
    ) == "supported"


def test_percent_delta_is_relative_unless_percentage_points_are_explicit():
    relative = "Alpha outperforms Beta on score by 10%."
    percentage_points = "Alpha outperforms Beta on score by 10 percentage points."

    assert _comparison_status(
        relative,
        [{"model": "Alpha", "score": 0.9}, {"model": "Beta", "score": 0.8}],
    ) != "supported"
    assert _comparison_status(
        relative,
        [{"model": "Alpha", "score": 0.88}, {"model": "Beta", "score": 0.8}],
    ) == "supported"
    assert _comparison_status(
        percentage_points,
        [{"model": "Alpha", "score": 0.9}, {"model": "Beta", "score": 0.8}],
    ) == "supported"
    assert _comparison_status(
        percentage_points,
        [{"model": "Alpha", "score": 0.88}, {"model": "Beta", "score": 0.8}],
    ) != "supported"
