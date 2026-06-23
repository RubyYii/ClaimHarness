from typing import Any

from pydantic import BaseModel, Field


class ManuscriptSection(BaseModel):
    name: str
    text: str
    start_line: int | None


class Claim(BaseModel):
    claim_id: str
    text: str
    source_section: str
    claim_type: str
    strength: str
    requires_evidence: list[str]


class EvidenceItem(BaseModel):
    evidence_id: str
    source: str
    evidence_type: str
    text: str
    linked_claim_ids: list[str] = Field(default_factory=list)


class VerificationResult(BaseModel):
    claim_id: str
    status: str
    reason: str
    risk_level: str
    suggested_revision: str


class AuditEvent(BaseModel):
    step: int
    module: str
    message: str
    data: dict[str, Any]
