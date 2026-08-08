from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from .schemas import Claim, EvidenceItem, VerificationResult


DIAGNOSTICS_SCHEMA_VERSION = 2
DIAGNOSTICS_BOUNDARY = (
    "Derived only from this run's deterministic links and verifier outputs. "
    "These structural diagnostics do not establish factual correctness, scientific "
    "validity, clinical safety, model accuracy, faithfulness, or hallucination rates."
)


def build_audit_diagnostics(
    claims: list[Claim],
    evidence: list[EvidenceItem],
    results: list[VerificationResult],
) -> dict[str, Any]:
    """Build deterministic, gold-label-free diagnostics for one audit run."""

    claim_ids = {claim.claim_id for claim in claims}
    linked_claim_ids = {
        claim_id
        for item in evidence
        for claim_id in item.linked_claim_ids
        if claim_id in claim_ids
    }
    support_relation_claim_ids = {
        result.claim_id
        for result in results
        if result.claim_id in claim_ids and result.supporting_evidence_ids
    }
    missing_requirement_claim_ids = {
        result.claim_id
        for result in results
        if result.claim_id in claim_ids and result.missing_evidence
    }
    high_risk_claim_ids = {
        result.claim_id
        for result in results
        if result.claim_id in claim_ids and result.risk_level == "high"
    }
    needs_human_review_status_claim_ids = {
        result.claim_id
        for result in results
        if result.claim_id in claim_ids and result.status == "needs_human_review"
    }
    human_review_claim_ids = {
        result.claim_id
        for result in results
        if result.claim_id in claim_ids and result.human_review_required
    }
    release_allowed_claim_ids = {
        result.claim_id
        for result in results
        if result.claim_id in claim_ids and result.release_allowed
    }
    release_blocked_claim_ids = claim_ids - release_allowed_claim_ids
    contradiction_claim_ids = {
        result.claim_id
        for result in results
        if result.claim_id in claim_ids and result.contradicting_evidence_ids
    }
    high_risk_blocked_ids = {
        result.claim_id
        for result in results
        if result.claim_id in claim_ids
        and result.risk_level == "high"
        and not result.release_allowed
    }
    unlinked_evidence_ids = {
        item.evidence_id
        for item in evidence
        if not (set(item.linked_claim_ids) & claim_ids)
    }

    governed_results = [result for result in results if result.claim_id in claim_ids]
    status_counts = Counter(result.status for result in governed_results)
    relation_counts = Counter(
        item.claim_link_relations.get(claim_id, "related")
        for item in evidence
        for claim_id in item.linked_claim_ids
        if claim_id in claim_ids
    )
    requirement_gap_counts = Counter(
        requirement
        for result in governed_results
        for requirement in result.missing_evidence
    )
    total_claims = len(claims)
    total_evidence = len(evidence)

    metrics = {
        "support_relation_coverage": _ratio(
            len(support_relation_claim_ids), total_claims
        ),
        "any_link_coverage": _ratio(len(linked_claim_ids), total_claims),
        "contradiction_claims": _ratio(len(contradiction_claim_ids), total_claims),
        "high_risk_blocked_or_reviewed": _ratio(
            len(high_risk_blocked_ids), len(high_risk_claim_ids)
        ),
        "high_risk_claims": _ratio(len(high_risk_claim_ids), total_claims),
        "missing_requirement_claims": _ratio(
            len(missing_requirement_claim_ids), total_claims
        ),
        "needs_human_review": _ratio(
            len(needs_human_review_status_claim_ids), total_claims
        ),
        "human_review_required": _ratio(len(human_review_claim_ids), total_claims),
        "release_allowed": _ratio(len(release_allowed_claim_ids), total_claims),
        "release_blocked": _ratio(len(release_blocked_claim_ids), total_claims),
        "no_support_relation": _ratio(
            total_claims - len(support_relation_claim_ids), total_claims
        ),
        "no_linked_evidence": _ratio(
            total_claims - len(linked_claim_ids), total_claims
        ),
        "unlinked_evidence_items": _ratio(
            len(unlinked_evidence_ids), total_evidence
        ),
    }

    return {
        "schema_version": DIAGNOSTICS_SCHEMA_VERSION,
        "artifact_type": "single_run_structural_diagnostics",
        "boundary": DIAGNOSTICS_BOUNDARY,
        "totals": {
            "claims": total_claims,
            "evidence_items": total_evidence,
            "claim_evidence_links": sum(relation_counts.values()),
        },
        "status_counts": dict(sorted(status_counts.items())),
        "relation_link_counts": dict(sorted(relation_counts.items())),
        "metrics": metrics,
        "requirement_gap_counts": dict(sorted(requirement_gap_counts.items())),
        "release_boundary_by_claim": {
            result.claim_id: {
                "human_review_required": result.human_review_required,
                "release_allowed": result.release_allowed,
            }
            for result in sorted(governed_results, key=lambda item: item.claim_id)
        },
        "attention": {
            "claims_needing_human_review": sorted(human_review_claim_ids),
            "release_allowed_claims": sorted(release_allowed_claim_ids),
            "release_blocked_claims": sorted(release_blocked_claim_ids),
            "claims_with_contradictions": sorted(contradiction_claim_ids),
            "claims_with_missing_requirements": sorted(missing_requirement_claim_ids),
            "claims_without_support_relation": sorted(
                claim_ids - support_relation_claim_ids
            ),
            "claims_without_any_link": sorted(claim_ids - linked_claim_ids),
            "high_risk_claims": sorted(high_risk_claim_ids),
            "high_risk_not_blocked_or_reviewed": sorted(
                high_risk_claim_ids - high_risk_blocked_ids
            ),
            "unlinked_evidence_items": sorted(unlinked_evidence_ids),
        },
        "definitions": {
            "support_relation_coverage": (
                "Claims with at least one deterministic supports relation. This can include "
                "weakly_supported claims whose evidence requirements remain unmet."
            ),
            "any_link_coverage": (
                "Claims with at least one deterministic supports, related, or contradicts link."
            ),
            "high_risk_blocked_or_reviewed": (
                "High-risk claims whose explicit release_allowed flag is false."
            ),
            "human_review_required": (
                "Claims whose explicit verifier boundary requires pending human review."
            ),
            "release_allowed": (
                "Low-risk supported claims with no human-review requirement."
            ),
            "unlinked_evidence_items": (
                "Evidence items not linked to any claim in this run."
            ),
        },
    }


def write_audit_diagnostics(
    path: Path,
    claims: list[Claim],
    evidence: list[EvidenceItem],
    results: list[VerificationResult],
) -> None:
    payload = build_audit_diagnostics(claims, evidence, results)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _ratio(numerator: int, denominator: int) -> dict[str, int | float | None]:
    return {
        "numerator": numerator,
        "denominator": denominator,
        "rate": round(numerator / denominator, 6) if denominator else None,
    }
