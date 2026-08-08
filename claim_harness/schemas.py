from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ManuscriptSection(BaseModel):
    name: str
    text: str
    start_line: int | None
    content_start_line: int | None = None
    source_kind: Literal["manuscript", "ocr", "derived_text"] = "manuscript"
    source_file: str | None = None


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
    source_kind: Literal["manuscript", "ocr", "derived_text"] = "manuscript"


EvidenceSourceKind = Literal[
    "table",
    "manuscript",
    "references",
    "external",
    "ocr",
    "derived_text",
]


class EvidenceCell(BaseModel):
    """One addressable table cell within an evidence locator."""

    column: str
    value: str
    cell: str | None = None


class EvidenceLocator(BaseModel):
    source_kind: EvidenceSourceKind
    source_name: str
    source_file: str | None = None
    page_number: int | None = Field(default=None, gt=0)
    line: int | None = Field(default=None, gt=0)
    row: int | None = Field(default=None, gt=0)
    cells: list[EvidenceCell] = Field(default_factory=list)


EvidenceType = Literal[
    "quantitative_result",
    "ablation_result",
    "result_text",
    "narrative_assertion",
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
    claim_link_locators: dict[str, EvidenceLocator] = Field(default_factory=dict)


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
    human_review_required: bool = False
    release_allowed: bool = False
    missing_evidence: list[str] = Field(default_factory=list)
    supporting_evidence_ids: list[str] = Field(default_factory=list)
    contradicting_evidence_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def enforce_review_and_release_boundary(self) -> "VerificationResult":
        """Keep safety gates valid even when results bypass ``verify_claims``."""

        requires_review = (
            self.human_review_required
            or self.risk_level == "high"
            or self.status in {"needs_human_review", "overclaimed"}
            or bool(self.contradicting_evidence_ids)
            or any(
                requirement in {"human_review", "source_inspection"}
                or requirement.startswith("human_review_role=")
                for requirement in self.missing_evidence
            )
        )
        self.human_review_required = requires_review
        self.release_allowed = (
            self.release_allowed
            and self.risk_level == "low"
            and self.status == "supported"
            and not requires_review
        )
        return self


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
