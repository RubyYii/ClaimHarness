from pydantic import BaseModel, Field


class PainpointOpportunity(BaseModel):
    workflow_step: str
    pain_point: str
    ai_opportunity: str
    risk: str
    human_role: str


class ConceptAlignment(BaseModel):
    domain_concept: str
    ai_representation: str
    alignment_status: str
    misalignment_risk: str


class AlignmentPackage(BaseModel):
    profile: str
    project_name: str
    title: str
    source_problem: str
    domain_goal: str
    not_allowed_goal: str
    meaningful_outputs: list[str] = Field(default_factory=list)
    non_meaningful_outputs: list[str] = Field(default_factory=list)
    workflow_steps: list[str] = Field(default_factory=list)
    painpoints: list[PainpointOpportunity] = Field(default_factory=list)
    concepts: list[ConceptAlignment] = Field(default_factory=list)
    ai_task_type: list[str] = Field(default_factory=list)
    inputs: list[str] = Field(default_factory=list)
    outputs: list[str] = Field(default_factory=list)
    required_evidence: dict[str, list[str]] = Field(default_factory=dict)
    forbidden_without: dict[str, list[str]] = Field(default_factory=dict)
    evaluation_protocol: list[str] = Field(default_factory=list)
    insufficient_metrics: list[str] = Field(default_factory=list)
    misalignment_risks: list[str] = Field(default_factory=list)
    human_review_required: list[str] = Field(default_factory=list)
    implementation_routes: list[str] = Field(default_factory=list)
