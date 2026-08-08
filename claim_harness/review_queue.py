from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .schemas import Claim, VerificationResult


REVIEW_QUEUE_SCHEMA_VERSION = 2
REVIEW_QUEUE_BOUNDARY = (
    "Every item is pending. This artifact is a deterministic review-work snapshot, "
    "not a reviewer identity check, decision, approval, scientific evidence, or permission "
    "to change a verification status."
)


def build_human_review_queue(
    claims: list[Claim],
    results: list[VerificationResult],
) -> dict[str, Any]:
    """Create one pending work item per actionable claim and required role."""

    result_by_claim = {result.claim_id: result for result in results}
    items: list[dict[str, Any]] = []
    for claim in sorted(claims, key=lambda item: item.claim_id):
        result = result_by_claim[claim.claim_id]
        if not _requires_review_work(result):
            continue
        contract_roles = sorted(
            {
                entry.split("=", 1)[1]
                for entry in result.missing_evidence
                if entry.startswith("human_review_role=") and entry.split("=", 1)[1]
            }
        )
        roles = contract_roles or ["domain_reviewer"]
        triggers = _trigger_codes(result, bool(contract_roles))
        for role in roles:
            items.append(
                {
                    "review_item_id": f"HR-{claim.claim_id}-{role}",
                    "claim_id": claim.claim_id,
                    "required_role": role,
                    "role_origin": "evidence_contract" if contract_roles else "built_in_route",
                    "trigger_codes": triggers,
                    "verification_status": result.status,
                    "risk_level": result.risk_level,
                    "human_review_required": result.human_review_required,
                    "release_allowed": result.release_allowed,
                    "claim_text": claim.text,
                    "claim_source": {
                        "section": claim.source_section,
                        "line": claim.source_line,
                        "source_kind": claim.source_kind,
                    },
                    "candidate_supporting_evidence_ids": sorted(
                        result.supporting_evidence_ids
                    ),
                    "candidate_contradicting_evidence_ids": sorted(
                        result.contradicting_evidence_ids
                    ),
                    "missing_evidence": sorted(result.missing_evidence),
                    "state": "pending",
                }
            )

    return {
        "schema_version": REVIEW_QUEUE_SCHEMA_VERSION,
        "artifact_type": "pending_human_review_queue",
        "boundary": REVIEW_QUEUE_BOUNDARY,
        "role_boundary": (
            "ClaimHarness routes work to named roles but does not verify a reviewer's "
            "identity, qualifications, independence, or authority."
        ),
        "counts": {
            "pending_items": len(items),
            "claims_routed": len({item["claim_id"] for item in items}),
        },
        "items": items,
    }


def write_human_review_queue(
    path: Path,
    claims: list[Claim],
    results: list[VerificationResult],
) -> None:
    payload = build_human_review_queue(claims, results)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _requires_review_work(result: VerificationResult) -> bool:
    return result.human_review_required


def _trigger_codes(
    result: VerificationResult,
    has_contract_role: bool,
) -> list[str]:
    codes: list[str] = []
    if not result.release_allowed:
        codes.append("release_not_allowed")
    if has_contract_role:
        codes.append("contract_role_required")
    if result.contradicting_evidence_ids:
        codes.append("contradiction_detected")
    if result.risk_level == "high":
        codes.append("high_risk_claim")
    if "human_review" in result.missing_evidence:
        codes.append("missing_human_review")
    if result.status == "overclaimed":
        codes.append("overclaim_detected")
    if "source_inspection" in result.missing_evidence:
        codes.append("source_inspection_required")
    if result.status == "needs_human_review":
        codes.append("verification_requires_human_review")
    return codes
