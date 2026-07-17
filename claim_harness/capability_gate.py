from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


CapabilityStatus = Literal[
    "supported",
    "weakly_supported",
    "unsupported",
    "overclaimed",
    "needs_human_review",
]
CapabilityAction = Literal["retain", "downgrade", "remove", "abstain"]
RiskLevel = Literal["low", "medium", "high"]


class CapabilityClaim(BaseModel):
    """A proposed product capability and the workflow evidence cited for it."""

    model_config = ConfigDict(extra="forbid")

    claim_id: str = Field(pattern=r"^BC\d{3}$")
    statement: str = Field(min_length=12, max_length=700)
    evidence_refs: list[str] = Field(default_factory=list, max_length=12)
    risk_level: RiskLevel
    rationale: str = Field(min_length=8, max_length=700)
    safe_fallback: str = Field(min_length=12, max_length=700)


class CapabilityDecision(BaseModel):
    """Deterministic evidence-gate result for one proposed capability claim."""

    model_config = ConfigDict(extra="forbid")

    claim_id: str
    original_statement: str
    status: CapabilityStatus
    action: CapabilityAction
    final_statement: str
    reason: str
    accepted_evidence_refs: list[str]
    rejected_evidence_refs: list[str]
    human_review_required: bool


_AUTONOMY_OR_GUARANTEE = re.compile(
    r"\b(automatically\s+(approve(s|d)?|reject(s|ed)?|decide(s|d)?|"
    r"diagnos(e|es|ed)|grade(s|d)?|determine(s|d)?)|"
    r"replace(s|d)?\s+(a\s+)?(human|expert|reviewer)|"
    r"without\s+human\s+(review|oversight|confirmation)|"
    r"guarantee(s|d)?|always\s+(correct|accurate)|zero\s+errors?)\b",
    re.IGNORECASE,
)
_HIGH_STAKES = re.compile(
    r"\b(clinical|patient|diagnos(e|is|tic)|treat(ment)?|legal|eligibility|"
    r"approve|reject|grade|disciplinary|safety[- ]critical)\b",
    re.IGNORECASE,
)
_EXPLICIT_HUMAN_AUTHORITY = re.compile(
    r"\b(human|expert|reviewer|qualified\s+person)\b.{0,80}"
    r"\b(review|decid(e|es)|decision|authorit(y|ies)|confirm(s|ed)?|"
    r"approv(e|es|al)|responsib(le|ility))\b|"
    r"\b(final\s+(decision|authority)|human\s+review)\b",
    re.IGNORECASE,
)


def audit_capability_claims(
    claims: list[CapabilityClaim],
    *,
    allowed_evidence_refs: set[str],
    human_boundaries: list[str],
) -> list[CapabilityDecision]:
    """Gate product claims against traceable workflow evidence and human boundaries.

    ``supported`` here means supported as a bounded design requirement by the
    supplied workflow artifacts. It is not empirical performance validation.
    """

    decisions: list[CapabilityDecision] = []
    for claim in claims:
        accepted = [ref for ref in claim.evidence_refs if ref in allowed_evidence_refs]
        rejected = [ref for ref in claim.evidence_refs if ref not in allowed_evidence_refs]
        statement = claim.statement.strip()
        fallback = _bounded_fallback(claim.safe_fallback, human_boundaries)

        if _AUTONOMY_OR_GUARANTEE.search(statement):
            decisions.append(
                CapabilityDecision(
                    claim_id=claim.claim_id,
                    original_statement=statement,
                    status="overclaimed",
                    action="downgrade" if accepted else "remove",
                    final_statement=fallback if accepted else "",
                    reason=(
                        "The proposal asserts autonomous authority or guaranteed "
                        "performance that workflow artifacts cannot establish."
                    ),
                    accepted_evidence_refs=accepted,
                    rejected_evidence_refs=rejected,
                    human_review_required=True,
                )
            )
            continue

        if not accepted:
            decisions.append(
                CapabilityDecision(
                    claim_id=claim.claim_id,
                    original_statement=statement,
                    status="unsupported",
                    action="abstain",
                    final_statement="",
                    reason="No cited evidence reference belongs to the approved workflow package.",
                    accepted_evidence_refs=[],
                    rejected_evidence_refs=rejected,
                    human_review_required=True,
                )
            )
            continue

        if claim.risk_level == "high" or _HIGH_STAKES.search(statement):
            decisions.append(
                CapabilityDecision(
                    claim_id=claim.claim_id,
                    original_statement=statement,
                    status="needs_human_review",
                    action="downgrade",
                    final_statement=fallback,
                    reason=(
                        "The claim affects a high-stakes judgement and must remain "
                        "bounded to decision support with explicit human review."
                    ),
                    accepted_evidence_refs=accepted,
                    rejected_evidence_refs=rejected,
                    human_review_required=True,
                )
            )
            continue

        status: CapabilityStatus = (
            "supported"
            if claim.risk_level == "low" and len(set(accepted)) >= 2 and not rejected
            else "weakly_supported"
        )
        decisions.append(
            CapabilityDecision(
                claim_id=claim.claim_id,
                original_statement=statement,
                status=status,
                action="retain",
                final_statement=statement,
                reason=(
                    "The bounded assistive claim is traceable to approved workflow artifacts."
                    if status == "supported"
                    else "The claim has partial workflow support and still requires evaluation."
                ),
                accepted_evidence_refs=accepted,
                rejected_evidence_refs=rejected,
                human_review_required=status != "supported",
            )
        )
    return decisions


def _bounded_fallback(candidate: str, human_boundaries: list[str]) -> str:
    clean = " ".join(candidate.split()).strip()
    if (
        clean
        and not _AUTONOMY_OR_GUARANTEE.search(clean)
        and _EXPLICIT_HUMAN_AUTHORITY.search(clean)
    ):
        return clean
    boundary = next((" ".join(item.split()) for item in human_boundaries if item.strip()), "")
    suffix = f" Boundary: {boundary}" if boundary else ""
    return (
        "The assistant may surface relevant material, uncertainty, and review cues; "
        "a qualified human must make the final decision." + suffix
    )
