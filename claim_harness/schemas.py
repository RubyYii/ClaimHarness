from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ManuscriptSection(BaseModel):
    name: str
    text: str
    start_line: int | None
    content_start_line: int | None = None


ClaimType = Literal[
    "clinical_claim",
    "deployment_claim",
    "performance_claim",
    "novelty_claim",
    "robustness_claim",
    "workflow_claim",
    "general_claim",
]
ClaimStrength = Literal["high", "strong", "moderate", "weak"]
ClaimPolarity = Literal["positive", "negative"]


class Claim(BaseModel):
    claim_id: str
    text: str
    source_section: str
    source_line: int | None = None
    claim_type: ClaimType
    strength: ClaimStrength
    polarity: ClaimPolarity = "positive"
    requires_evidence: list[str]


class EvidenceLocator(BaseModel):
    source_kind: Literal["table", "manuscript", "references", "external"]
    source_name: str
    line: int | None = Field(default=None, gt=0)
    row: int | None = Field(default=None, gt=0)


EvidenceType = Literal[
    "quantitative_result",
    "ablation_result",
    "result_text",
    "workflow_trace",
    "limitation_statement",
    "citation",
    "external_validation",
    "human_review",
    "robustness_test",
]
EvidencePolarity = Literal["positive", "negative", "neutral"]
EvidenceRelation = Literal["supports", "contradicts", "related"]


class EvidenceItem(BaseModel):
    evidence_id: str
    source: str
    locator: EvidenceLocator
    evidence_type: EvidenceType
    text: str
    polarity: EvidencePolarity = "neutral"
    numeric_values: dict[str, float] = Field(default_factory=dict)
    table_columns: list[str] = Field(default_factory=list)
    categorical_values: list[str] = Field(default_factory=list)
    linked_claim_ids: list[str] = Field(default_factory=list)
    claim_link_reasons: dict[str, str] = Field(default_factory=dict)
    claim_link_relations: dict[str, EvidenceRelation] = Field(default_factory=dict)


VerificationStatus = Literal[
    "supported",
    "weakly_supported",
    "unsupported",
    "overclaimed",
    "needs_human_review",
]
RiskLevel = Literal["low", "high"]


class VerificationResult(BaseModel):
    claim_id: str
    status: VerificationStatus
    reason: str
    risk_level: RiskLevel
    suggested_revision: str
    missing_evidence: list[str] = Field(default_factory=list)
    supporting_evidence_ids: list[str] = Field(default_factory=list)
    contradicting_evidence_ids: list[str] = Field(default_factory=list)


class AuditEvent(BaseModel):
    step: int
    module: str
    message: str
    data: dict[str, Any]
    run_id: str | None = None
    created_at: str | None = None


class LLMAuditReview(BaseModel):
    """Strict schema for the optional advisory provider output."""

    model_config = ConfigDict(extra="forbid", strict=True)

    summary: str = Field(min_length=1, max_length=20_000)
    highest_risk_claims: list[str] = Field(max_length=100)
    recommended_next_actions: list[str] = Field(max_length=100)
    limitations: list[str] = Field(max_length=100)
