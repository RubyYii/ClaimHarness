import re
from collections import defaultdict

from .claim_extractor import contains_term, term_is_negated
from .claim_language import high_risk_claim_type
from .evidence_contract import DERIVED_SOURCE_KINDS, EvidenceContract
from .evidence_retriever import is_claim_self_evidence
from .schemas import Claim, EvidenceItem, VerificationResult
from .table_relations import assess_table_relation, has_verifiable_table_relation as _has_verifiable_table_relation


STRONG_EVIDENCE_TYPES = {
    "quantitative_result",
    "ablation_result",
    "external_validation",
    "robustness_test",
}
OVERCLAIM_TERMS = {
    "clinically ready",
    "clinical deployment",
    "diagnosis",
    "real-world clinical deployment",
    "ready for real-world deployment",
    "ready for real-world operational deployment",
    "real-world operational deployment",
    "deployment-ready",
    "operationally ready",
}

def verify_claims(
    claims: list[Claim],
    evidence: list[EvidenceItem],
    evidence_contract: EvidenceContract | None = None,
) -> list[VerificationResult]:
    evidence_by_claim: dict[str, list[EvidenceItem]] = defaultdict(list)
    for item in evidence:
        for claim_id in item.linked_claim_ids:
            evidence_by_claim[claim_id].append(item)

    results: list[VerificationResult] = []
    for claim in claims:
        result = _verify_claim(
            claim,
            evidence_by_claim.get(claim.claim_id, []),
            evidence_contract,
            table_context=[item for item in evidence if item.locator.source_kind == 'table'],
        )
        human_review_required = result.human_review_required
        release_allowed = (
            result.risk_level == "low"
            and result.status == "supported"
            and not human_review_required
        )
        results.append(
            result.model_copy(
                update={
                    "human_review_required": human_review_required,
                    "release_allowed": release_allowed,
                }
            )
        )
    return results


def _verify_claim(
    claim: Claim,
    evidence_items: list[EvidenceItem],
    evidence_contract: EvidenceContract | None = None,
    *,
    table_context: list[EvidenceItem] | None = None,
) -> VerificationResult:
    allowed_source_kinds = (
        set(evidence_contract.source_kinds) if evidence_contract is not None else None
    )
    evidence_items = [
        item for item in evidence_items if not is_claim_self_evidence(claim, item)
    ]
    table_assessment = assess_table_relation(claim, [
        item for item in (table_context if table_context is not None else evidence_items)
        if item.locator.source_kind == 'table'
        and (allowed_source_kinds is None or 'table' in allowed_source_kinds)
    ])
    supporting = [
        item
        for item in evidence_items
        if item.claim_link_relations.get(claim.claim_id, "supports") == "supports"
        and item.evidence_id not in table_assessment.contradictions
        and (
            allowed_source_kinds is None
            or item.locator.source_kind in allowed_source_kinds
        )
    ]
    contradicting = [
        item
        for item in evidence_items
        if item.claim_link_relations.get(claim.claim_id) == "contradicts"
        or item.evidence_id in table_assessment.contradictions
    ]
    related = [
        item
        for item in evidence_items
        if item.claim_link_relations.get(claim.claim_id) == "related"
        and (
            allowed_source_kinds is None
            or item.locator.source_kind in allowed_source_kinds
        )
    ]

    valid_table_relation = table_assessment.supported
    strong_evidence_types = (
        set(evidence_contract.strong_evidence_types)
        if evidence_contract is not None
        else STRONG_EVIDENCE_TYPES
    )
    strong = [
        item
        for item in supporting
        if item.evidence_type in strong_evidence_types
        and item.locator.source_kind not in DERIVED_SOURCE_KINDS
        and (item.locator.source_kind != "table" or valid_table_relation)
    ]
    rule = evidence_contract.claim_rules[claim.claim_type] if evidence_contract is not None else None
    requirements = list(rule.required_evidence) if rule is not None else claim.requires_evidence
    missing = _missing_requirements(
        claim,
        supporting,
        related,
        strong,
        requirements=requirements,
    )
    forbidden_missing: list[str] = []
    missing_review_roles: list[str] = []
    if rule is not None:
        supporting_count = len(
            {
                item.evidence_id
                for item in supporting
                if item.locator.source_kind not in DERIVED_SOURCE_KINDS
            }
        )
        if supporting_count < rule.minimum_evidence_count:
            missing.append(f"minimum_evidence_count={rule.minimum_evidence_count}")
        forbidden_missing = _missing_requirements(
            claim,
            supporting,
            related,
            strong,
            requirements=list(rule.forbidden_without),
        )
        completed_review_roles = {
            role_id
            for item in supporting
            if item.evidence_type == "human_review"
            and item.locator.source_kind not in DERIVED_SOURCE_KINDS
            for role_id in item.categorical_values
        }
        missing_review_roles = [
            role_id
            for role_id in rule.human_review_roles
            if role_id not in completed_review_roles
        ]
        missing.extend(
            requirement for requirement in forbidden_missing if requirement not in missing
        )
        missing.extend(
            f"human_review_role={role_id}"
            for role_id in missing_review_roles
            if f"human_review_role={role_id}" not in missing
        )
    risk_level = _risk_level(claim)
    support_ids = [item.evidence_id for item in supporting]
    contradiction_ids = [item.evidence_id for item in contradicting]

    if _has_positive_overclaim_language(claim) and missing:
        return VerificationResult(
            claim_id=claim.claim_id,
            status="overclaimed",
            reason=(
                "High-risk readiness or deployment language is missing required evidence: "
                + ", ".join(missing)
                + "."
            ),
            risk_level="high",
            suggested_revision=(
                "Remove readiness/deployment language or add independently reviewable external validation "
                "and a documented human-review decision."
            ),
            missing_evidence=missing,
            supporting_evidence_ids=support_ids,
            contradicting_evidence_ids=contradiction_ids,
        )

    if claim.source_kind in DERIVED_SOURCE_KINDS:
        derived_missing = [*missing]
        if "source_inspection" not in derived_missing:
            derived_missing.append("source_inspection")
        return VerificationResult(
            claim_id=claim.claim_id,
            status="needs_human_review",
            reason=(
                "The claim was extracted from OCR-derived text. A human must inspect the "
                "original source before this claim can be treated as supported."
            ),
            risk_level="high" if risk_level == "high" else "low",
            suggested_revision=(
                "Verify the transcription against the original page, then rerun the audit "
                "with direct source text or a documented human-review record."
            ),
            missing_evidence=derived_missing,
            supporting_evidence_ids=support_ids,
            contradicting_evidence_ids=contradiction_ids,
        )

    if forbidden_missing or missing_review_roles:
        details = []
        if forbidden_missing:
            details.append("forbidden-without conditions missing: " + ", ".join(forbidden_missing))
        if missing_review_roles:
            details.append("human review roles incomplete: " + ", ".join(missing_review_roles))
        return VerificationResult(
            claim_id=claim.claim_id,
            status="needs_human_review",
            reason="Evidence contract requires human review; " + "; ".join(details) + ".",
            risk_level="high" if risk_level == "high" else "low",
            suggested_revision=(
                "Do not present the claim as contract-compliant until the forbidden-without conditions "
                "and named human-review roles are satisfied."
            ),
            missing_evidence=missing,
            supporting_evidence_ids=support_ids,
            contradicting_evidence_ids=contradiction_ids,
        )

    if risk_level == "high" and (missing or not strong or contradicting):
        details = []
        if missing:
            details.append("missing required evidence: " + ", ".join(missing))
        if not strong:
            details.append("no independently verifiable strong evidence")
        if contradicting:
            details.append("contradictory evidence: " + ", ".join(contradiction_ids))
        return VerificationResult(
            claim_id=claim.claim_id,
            status="needs_human_review",
            reason="High-risk claim requires human review; " + "; ".join(details) + ".",
            risk_level="high",
            suggested_revision=(
                "Do not present this as validated until the missing evidence and contradiction checks are "
                "reviewed by a qualified human."
            ),
            missing_evidence=missing,
            supporting_evidence_ids=support_ids,
            contradicting_evidence_ids=contradiction_ids,
        )

    if contradicting:
        details = [table_assessment.contradictions.get(
            item.evidence_id, item.claim_link_reasons.get(claim.claim_id, item.evidence_id)
        ) for item in contradicting]
        return VerificationResult(
            claim_id=claim.claim_id,
            status="needs_human_review",
            reason="Provided evidence conflicts with the claim: " + "; ".join(dict.fromkeys(details)) + ".",
            risk_level=risk_level,
            suggested_revision="Resolve the conflicting evidence or narrow the claim before publication.",
            missing_evidence=missing,
            supporting_evidence_ids=support_ids,
            contradicting_evidence_ids=contradiction_ids,
        )

    if table_assessment.review_reason:
        return VerificationResult(
            claim_id=claim.claim_id,
            status='needs_human_review',
            reason=table_assessment.review_reason,
            risk_level=risk_level,
            suggested_revision='Identify the model, comparator, experiment and units in the original table, then rerun the audit.',
            missing_evidence=missing,
            supporting_evidence_ids=support_ids,
            contradicting_evidence_ids=[],
        )

    if missing:
        return VerificationResult(
            claim_id=claim.claim_id,
            status="weakly_supported" if supporting or related else "unsupported",
            reason="Required evidence is missing: " + ", ".join(missing) + ".",
            risk_level=risk_level,
            suggested_revision="Add the missing evidence or narrow the wording to the evidence available.",
            missing_evidence=missing,
            supporting_evidence_ids=support_ids,
            contradicting_evidence_ids=contradiction_ids,
        )

    if strong:
        return VerificationResult(
            claim_id=claim.claim_id,
            status="supported",
            reason=(
                f"All evidence requirements are met with {len(strong)} independently verifiable strong "
                "evidence item(s)."
            ),
            risk_level=risk_level,
            suggested_revision="No revision needed within the evidenced scope.",
            missing_evidence=[],
            supporting_evidence_ids=support_ids,
            contradicting_evidence_ids=[],
        )

    if supporting or related:
        return VerificationResult(
            claim_id=claim.claim_id,
            status="weakly_supported",
            reason="Only narrative or topically related evidence is available; no strong relation was verified.",
            risk_level=risk_level,
            suggested_revision="Add verifiable evidence or narrow the wording.",
            missing_evidence=[],
            supporting_evidence_ids=support_ids,
            contradicting_evidence_ids=[],
        )

    return VerificationResult(
        claim_id=claim.claim_id,
        status="unsupported",
        reason="No supporting evidence was found in the provided manuscript, tables, or references.",
        risk_level=risk_level,
        suggested_revision="Remove the claim or add explicit supporting evidence.",
        missing_evidence=[],
        supporting_evidence_ids=[],
        contradicting_evidence_ids=[],
    )


def _risk_level(claim: Claim) -> str:
    if claim.claim_type in {"clinical_claim", "deployment_claim"}:
        return "high"
    return "high" if high_risk_claim_type(claim.text) is not None else "low"


def _has_positive_overclaim_language(claim: Claim) -> bool:
    if claim.polarity == "negative":
        return False
    return any(
        contains_term(claim.text, term) and not term_is_negated(claim.text, term)
        for term in OVERCLAIM_TERMS
    )


def _canonical_requirement(requirement: str) -> str:
    return re.sub(r"[\s-]+", "_", requirement.strip().lower())


def _missing_requirements(
    claim: Claim,
    supporting: list[EvidenceItem],
    related: list[EvidenceItem],
    strong: list[EvidenceItem],
    *,
    requirements: list[str] | None = None,
) -> list[str]:
    missing = []
    strong_ids = {item.evidence_id for item in strong}
    eligible_supporting = [
        item for item in supporting if item.locator.source_kind not in DERIVED_SOURCE_KINDS
    ]
    eligible_related = [
        item for item in related if item.locator.source_kind not in DERIVED_SOURCE_KINDS
    ]
    for raw_requirement in claim.requires_evidence if requirements is None else requirements:
        requirement = _canonical_requirement(raw_requirement)
        if requirement == "table":
            satisfied = any(
                item.locator.source_kind == "table" and item.evidence_id in strong_ids
                for item in supporting
            )
        elif requirement == "ablation":
            satisfied = any(
                item.evidence_type == "ablation_result" and item.evidence_id in strong_ids
                for item in supporting
            )
        elif requirement == "trace":
            satisfied = any(item.evidence_type == "workflow_trace" for item in eligible_supporting)
        elif requirement == "result_text":
            satisfied = any(item.evidence_type == "result_text" for item in eligible_supporting)
        elif requirement == "external_validation":
            satisfied = any(
                item.evidence_type == "external_validation" and item.evidence_id in strong_ids
                for item in eligible_supporting
            )
        elif requirement == "human_review":
            satisfied = any(item.evidence_type == "human_review" for item in eligible_supporting)
        elif requirement == "robustness_test":
            satisfied = any(
                item.evidence_type == "robustness_test" and item.evidence_id in strong_ids
                for item in eligible_supporting
            )
        elif requirement == "citation":
            satisfied = any(
                item.evidence_type == "citation"
                for item in [*eligible_supporting, *eligible_related]
            )
        elif requirement == "manuscript_context":
            satisfied = any(
                item.locator.source_kind == "manuscript" for item in eligible_supporting
            )
        elif requirement == "source_inspection":
            satisfied = any(
                item.evidence_type == "human_review"
                and item.locator.source_kind not in DERIVED_SOURCE_KINDS
                for item in eligible_supporting
            )
        else:
            satisfied = False
        if not satisfied:
            missing.append(requirement)
    return missing
