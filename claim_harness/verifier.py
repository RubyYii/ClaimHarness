from collections import defaultdict

from .schemas import Claim, EvidenceItem, VerificationResult


STRONG_EVIDENCE_TYPES = {"quantitative_result", "ablation_result"}
WEAK_EVIDENCE_TYPES = {"workflow_trace", "citation", "limitation_statement"}
HIGH_RISK_TERMS = {"clinical", "clinically", "deployment", "diagnosis", "oocyte", "biomedical"}
OVERCLAIM_TERMS = {"clinically ready", "clinical deployment", "diagnosis", "real-world clinical deployment"}


def verify_claims(claims: list[Claim], evidence: list[EvidenceItem]) -> list[VerificationResult]:
    evidence_by_claim: dict[str, list[EvidenceItem]] = defaultdict(list)
    for item in evidence:
        for claim_id in item.linked_claim_ids:
            evidence_by_claim[claim_id].append(item)

    return [_verify_claim(claim, evidence_by_claim.get(claim.claim_id, [])) for claim in claims]


def _verify_claim(claim: Claim, evidence_items: list[EvidenceItem]) -> VerificationResult:
    lowered = claim.text.lower()
    strong = [item for item in evidence_items if item.evidence_type in STRONG_EVIDENCE_TYPES]
    weak = [item for item in evidence_items if item.evidence_type in WEAK_EVIDENCE_TYPES]
    risk_level = "high" if any(term in lowered for term in HIGH_RISK_TERMS) else "low"

    if any(term in lowered for term in OVERCLAIM_TERMS):
        return VerificationResult(
            claim_id=claim.claim_id,
            status="overclaimed",
            reason="Clinical deployment language appears without external validation or safety evidence.",
            risk_level="high",
            suggested_revision="Reframe as a synthetic benchmark observation and route to human review.",
        )

    if strong:
        return VerificationResult(
            claim_id=claim.claim_id,
            status="supported",
            reason=f"Linked to {len(strong)} structured table or results evidence item(s).",
            risk_level=risk_level,
            suggested_revision="No revision needed for the synthetic benchmark scope.",
        )

    if weak:
        return VerificationResult(
            claim_id=claim.claim_id,
            status="weakly_supported",
            reason=f"Linked only to narrative, citation, trace, or limitation evidence ({len(weak)} item(s)).",
            risk_level=risk_level,
            suggested_revision="Add quantitative evidence or narrow the wording.",
        )

    return VerificationResult(
        claim_id=claim.claim_id,
        status="unsupported",
        reason="No matching evidence was found in the provided manuscript, tables, or references.",
        risk_level=risk_level,
        suggested_revision="Remove the claim or add explicit supporting evidence.",
    )
