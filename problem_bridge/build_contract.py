from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from importlib import resources
from pathlib import Path
from typing import Any, Callable

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from claim_harness.capability_gate import (
    CapabilityClaim,
    CapabilityDecision,
    audit_capability_claims,
)
from claim_harness.llm import (
    DEFAULT_OPENAI_BASE_URL,
    LLMProviderConfig,
    LLMProviderError,
    StructuredProviderResult,
    call_structured_provider_json,
)

from .schemas import AlignmentPackage


BUILD_CONTRACT_RUN_ARTIFACTS = [
    "build_contract.json",
    "build_contract.md",
    "capability_claims.json",
    "claim_decisions.csv",
    "gpt_5_6_runtime.json",
    "build_record.jsonl",
]
BUILD_CONTRACT_SNAPSHOT_DIRECTORIES = ("codex_handoff",)
HANDOFF_FILES = (
    "AGENTS.md",
    "SPEC.md",
    "TASKS.md",
    "acceptance_tests.yaml",
    "evidence_contract.yaml",
    "risk_register.md",
    "demo_scenario.md",
)

ALLOWED_EVIDENCE_REFS = {
    "problem_card.md#Domain Goal",
    "problem_card.md#Not Allowed Goal",
    "workflow_map.md#Current Workflow",
    "ai_task_spec.yaml#inputs",
    "ai_task_spec.yaml#outputs",
    "evidence_contract.yaml#claim_rules",
    "evaluation_protocol.md#Evaluation Checks",
    "human_in_loop_plan.md#Required Human Review",
    "misalignment_risk_report.md#Known Risks",
}


class BuildProposal(BaseModel):
    """Structured proposal produced by mock mode or GPT-5.6."""

    model_config = ConfigDict(extra="forbid")

    problem_summary: str = Field(min_length=12, max_length=1200)
    target_user: str = Field(min_length=3, max_length=300)
    workflow_goal: str = Field(min_length=8, max_length=700)
    capability_claims: list[CapabilityClaim] = Field(min_length=3, max_length=8)
    human_boundaries: list[str] = Field(min_length=1, max_length=12)
    evaluation_signals: list[str] = Field(min_length=1, max_length=12)

    @model_validator(mode="after")
    def require_unique_claim_ids(self) -> "BuildProposal":
        claim_ids = [claim.claim_id for claim in self.capability_claims]
        if len(claim_ids) != len(set(claim_ids)):
            raise ValueError("capability claim IDs must be unique")
        return self


@dataclass(frozen=True)
class BuildContractResult:
    proposal: BuildProposal
    decisions: list[CapabilityDecision]
    runtime_record: dict[str, Any]
    output_dir: Path


def generate_evidence_gated_build(
    package: AlignmentPackage,
    out: Path,
    *,
    provider_config: LLMProviderConfig,
    project_id: str,
    structured_caller: Callable[..., StructuredProviderResult] = call_structured_provider_json,
) -> BuildContractResult:
    """Generate, gate, record, and package a Codex-ready build contract."""

    out.mkdir(parents=True, exist_ok=True)
    input_payload = _proposal_input(package)
    input_sha256 = _sha256_json(input_payload)
    if provider_config.api_style == "mock":
        proposal = _mock_proposal(package)
        provider_result = None
    else:
        _require_competition_openai_config(provider_config)
        prompt = (
            resources.files("problem_bridge")
            .joinpath("prompts")
            .joinpath("evidence_gated_build.md")
            .read_text(encoding="utf-8")
        )
        provider_result = structured_caller(
            provider_config,
            prompt,
            json.dumps(input_payload, indent=2, ensure_ascii=False),
            json_schema=BuildProposal.model_json_schema(),
            schema_name="problembridge_build_proposal",
        )
        _validate_competition_result(provider_result)
        try:
            proposal = BuildProposal.model_validate(provider_result.payload)
        except ValidationError as exc:
            raise LLMProviderError(
                "GPT-5.6 returned an invalid ProblemBridge build proposal schema."
            ) from exc

    completed_at = _utc_now()

    decisions = audit_capability_claims(
        proposal.capability_claims,
        allowed_evidence_refs=ALLOWED_EVIDENCE_REFS,
        human_boundaries=[*package.human_review_required, *proposal.human_boundaries],
    )
    runtime_record = _runtime_record(
        provider_config,
        provider_result,
        input_sha256=input_sha256,
        output_sha256=_sha256_json(proposal.model_dump(mode="json")),
        completed_at=completed_at,
    )
    contract_payload = _contract_payload(package, proposal, decisions, project_id)

    _write_json(out / "capability_claims.json", proposal.model_dump(mode="json"))
    _write_decisions_csv(out / "claim_decisions.csv", decisions)
    _write_json(out / "build_contract.json", contract_payload)
    (out / "build_contract.md").write_text(
        _build_contract_markdown(package, proposal, decisions, runtime_record),
        encoding="utf-8",
    )
    _write_json(out / "gpt_5_6_runtime.json", runtime_record)
    handoff_hashes = _write_handoff_pack(out, package, proposal, decisions, project_id)
    _write_build_record(
        out / "build_record.jsonl",
        proposal,
        decisions,
        runtime_record,
        handoff_hashes,
        timestamp=completed_at,
    )
    return BuildContractResult(
        proposal=proposal,
        decisions=decisions,
        runtime_record=runtime_record,
        output_dir=out,
    )


def _require_competition_openai_config(config: LLMProviderConfig) -> None:
    model = (config.model or "").lower()
    if config.provider != "openai" or config.api_style != "openai-responses":
        raise LLMProviderError(
            "Evidence-Gated Build remote mode requires --llm openai via the Responses API."
        )
    if not model.startswith("gpt-5.6"):
        raise LLMProviderError(
            "Evidence-Gated Build competition mode requires an OPENAI_MODEL in the GPT-5.6 family."
        )
    if (config.base_url or "").rstrip("/") != DEFAULT_OPENAI_BASE_URL:
        raise LLMProviderError(
            "Evidence-Gated Build competition mode requires the official OpenAI API "
            f"endpoint: {DEFAULT_OPENAI_BASE_URL}."
        )


def _validate_competition_result(result: StructuredProviderResult) -> None:
    if result.provider != "openai" or result.api_style != "openai-responses":
        raise LLMProviderError(
            "Evidence-Gated Build received an unexpected provider runtime result."
        )
    if result.model and not result.model.lower().startswith("gpt-5.6"):
        raise LLMProviderError(
            "Evidence-Gated Build received a response from outside the GPT-5.6 family."
        )


def _proposal_input(package: AlignmentPackage) -> dict[str, Any]:
    return {
        "alignment_package": package.model_dump(mode="json"),
        "allowed_evidence_refs": sorted(ALLOWED_EVIDENCE_REFS),
        "instructions": {
            "claim_count": "Return three to eight candidate capability claims.",
            "evidence": "Use only allowed_evidence_refs; never invent a source.",
            "boundary": "Include at least one plausible overclaim so the gate is demonstrable.",
            "safety": "Safe fallbacks must preserve qualified human decision authority.",
        },
    }


def _mock_proposal(package: AlignmentPackage) -> BuildProposal:
    meaningful_output = (
        package.meaningful_outputs[0]
        if package.meaningful_outputs
        else "a structured review brief"
    )
    human_boundary = (
        package.human_review_required[0]
        if package.human_review_required
        else package.not_allowed_goal
    )
    return BuildProposal(
        problem_summary=package.domain_goal,
        target_user=f"Practitioners working on {package.project_name}",
        workflow_goal=package.domain_goal,
        capability_claims=[
            CapabilityClaim(
                claim_id="BC001",
                statement=(
                    "The assistant can transform provided workflow notes into "
                    f"{meaningful_output} for human inspection."
                ),
                evidence_refs=[
                    "problem_card.md#Domain Goal",
                    "workflow_map.md#Current Workflow",
                ],
                risk_level="low",
                rationale="The workflow and desired output are explicit in the alignment package.",
                safe_fallback=(
                    "The assistant may draft a structured review brief from the provided "
                    "workflow notes for human inspection."
                ),
            ),
            CapabilityClaim(
                claim_id="BC002",
                statement=(
                    "The assistant can prioritize uncertain items and attach evidence cues "
                    "for qualified human review."
                ),
                evidence_refs=[
                    "evidence_contract.yaml#claim_rules",
                    "human_in_loop_plan.md#Required Human Review",
                ],
                risk_level="medium",
                rationale="The evidence contract and human-review plan define review routing.",
                safe_fallback=(
                    "The assistant may group uncertain items and show evidence cues; a "
                    "qualified human decides their priority and disposition."
                ),
            ),
            CapabilityClaim(
                claim_id="BC003",
                statement=(
                    "The AI automatically approves the final workflow decision without human review."
                ),
                evidence_refs=[
                    "problem_card.md#Not Allowed Goal",
                    "human_in_loop_plan.md#Required Human Review",
                ],
                risk_level="high",
                rationale="This intentionally tests whether the gate catches an autonomy overclaim.",
                safe_fallback=(
                    "The assistant may flag relevant records and uncertainty; a qualified "
                    f"human retains final authority. Boundary: {human_boundary}"
                ),
            ),
        ],
        human_boundaries=[package.not_allowed_goal, *package.human_review_required],
        evaluation_signals=package.evaluation_protocol or [
            "Trace every retained claim to an approved workflow artifact.",
            "Confirm that no final professional decision is automated.",
        ],
    )


def _runtime_record(
    config: LLMProviderConfig,
    provider_result: StructuredProviderResult | None,
    *,
    input_sha256: str,
    output_sha256: str,
    completed_at: str,
) -> dict[str, Any]:
    actual_model = (
        provider_result.model
        if provider_result is not None and provider_result.model
        else config.model
    )
    gpt_5_6_used = bool(
        provider_result is not None
        and config.provider == "openai"
        and (actual_model or "").lower().startswith("gpt-5.6")
    )
    return {
        "schema_version": "1.0",
        "provider": config.provider,
        "api_style": config.api_style,
        "model": actual_model or "deterministic-mock",
        "endpoint_origin": (
            "https://api.openai.com" if config.provider == "openai" else None
        ),
        "gpt_5_6_used": gpt_5_6_used,
        "purpose": "Structured workflow interpretation and candidate capability claims",
        "response_id": provider_result.response_id if provider_result is not None else None,
        "input_sha256": input_sha256,
        "output_sha256": output_sha256,
        "completed_at": completed_at,
        "contains_api_key": False,
    }


def _contract_payload(
    package: AlignmentPackage,
    proposal: BuildProposal,
    decisions: list[CapabilityDecision],
    project_id: str,
) -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "project_id": project_id,
        "project_name": package.project_name,
        "problem_summary": proposal.problem_summary,
        "target_user": proposal.target_user,
        "workflow_goal": proposal.workflow_goal,
        "final_capability_claims": [
            {
                "claim_id": decision.claim_id,
                "statement": decision.final_statement,
                "status": decision.status,
                "action": decision.action,
                "evidence_refs": decision.accepted_evidence_refs,
                "human_review_required": decision.human_review_required,
            }
            for decision in decisions
            if decision.final_statement
        ],
        "abstained_or_removed_claim_ids": [
            decision.claim_id for decision in decisions if not decision.final_statement
        ],
        "human_boundaries": list(
            dict.fromkeys([package.not_allowed_goal, *proposal.human_boundaries])
        ),
        "evaluation_signals": proposal.evaluation_signals,
    }


def _build_contract_markdown(
    package: AlignmentPackage,
    proposal: BuildProposal,
    decisions: list[CapabilityDecision],
    runtime_record: dict[str, Any],
) -> str:
    status_counts = Counter(decision.status for decision in decisions)
    claim_sections = []
    for decision in decisions:
        final = decision.final_statement or "ABSTAIN — no deployable claim."
        refs = ", ".join(decision.accepted_evidence_refs) or "None"
        claim_sections.append(
            "\n".join(
                [
                    f"### {decision.claim_id} — {decision.status} / {decision.action}",
                    "",
                    f"- Proposed: {decision.original_statement}",
                    f"- Final: {final}",
                    f"- Evidence: {refs}",
                    f"- Reason: {decision.reason}",
                ]
            )
        )
    return (
        "# Evidence-Gated AI Build Contract\n\n"
        f"**Project:** {package.project_name}\n\n"
        f"**Target user:** {proposal.target_user}\n\n"
        f"**Workflow goal:** {proposal.workflow_goal}\n\n"
        "This contract distinguishes workflow-supported design claims from empirical "
        "performance claims. A `supported` result does not prove real-world accuracy.\n\n"
        "## Gate summary\n\n"
        + "\n".join(
            f"- {status}: {count}" for status, count in sorted(status_counts.items())
        )
        + "\n\n"
        f"- Runtime provider: `{runtime_record['provider']}`\n"
        f"- Runtime model: `{runtime_record['model']}`\n"
        f"- GPT-5.6 runtime verified: `{str(runtime_record['gpt_5_6_used']).lower()}`\n\n"
        "## Claim decisions\n\n"
        + "\n\n".join(claim_sections)
        + "\n\n## Human boundary\n\n"
        + "\n".join(f"- {item}" for item in proposal.human_boundaries)
        + "\n"
    )


def _write_decisions_csv(path: Path, decisions: list[CapabilityDecision]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "claim_id",
                "status",
                "action",
                "original_statement",
                "final_statement",
                "human_review_required",
                "accepted_evidence_refs",
                "rejected_evidence_refs",
                "reason",
            ],
        )
        writer.writeheader()
        for decision in decisions:
            row = decision.model_dump(mode="json")
            row["accepted_evidence_refs"] = " | ".join(decision.accepted_evidence_refs)
            row["rejected_evidence_refs"] = " | ".join(decision.rejected_evidence_refs)
            writer.writerow(row)


def _write_handoff_pack(
    out: Path,
    package: AlignmentPackage,
    proposal: BuildProposal,
    decisions: list[CapabilityDecision],
    project_id: str,
) -> dict[str, str]:
    handoff = out / "codex_handoff"
    handoff.mkdir(parents=True, exist_ok=True)
    retained = [decision for decision in decisions if decision.final_statement]
    boundaries = list(dict.fromkeys([package.not_allowed_goal, *proposal.human_boundaries]))

    (handoff / "AGENTS.md").write_text(
        "# Codex implementation contract\n\n"
        "Implement only the bounded capabilities in SPEC.md. Treat the evidence "
        "contract and risk register as hard constraints. Keep a deterministic mock "
        "path, never store API keys, use synthetic data, add tests for every task, "
        "and preserve qualified human authority for final decisions.\n",
        encoding="utf-8",
    )
    (handoff / "SPEC.md").write_text(
        "# Specification\n\n"
        f"- Project ID: `{project_id}`\n"
        f"- User: {proposal.target_user}\n"
        f"- Goal: {proposal.workflow_goal}\n\n"
        "## Approved capability claims\n\n"
        + "\n".join(
            f"- `{item.claim_id}` [{item.status}]: {item.final_statement}"
            for item in retained
        )
        + "\n\n## Human boundaries\n\n"
        + "\n".join(f"- {item}" for item in boundaries)
        + "\n",
        encoding="utf-8",
    )
    (handoff / "TASKS.md").write_text(
        "# Implementation Tasks\n\n"
        + "\n".join(
            f"- [ ] Implement `{item.claim_id}` as stated in SPEC.md and preserve its evidence links."
            for item in retained
        )
        + "\n- [ ] Add deterministic mock fixtures and failure-path tests.\n"
        "- [ ] Record provider, model, input hash, output hash, and claim decisions without secrets.\n"
        "- [ ] Verify that prohibited autonomous decisions fail closed.\n",
        encoding="utf-8",
    )
    acceptance_payload = {
        "schema_version": "1.0",
        "tests": [
            {
                "id": f"accept-{item.claim_id.lower()}",
                "claim_id": item.claim_id,
                "assert": item.final_statement,
                "evidence_refs": item.accepted_evidence_refs,
            }
            for item in retained
        ]
        + [
            {
                "id": "reject-autonomous-authority",
                "assert": "Autonomous approval, diagnosis, grading, or final decision claims are rejected or downgraded.",
                "evidence_refs": ["human_in_loop_plan.md#Required Human Review"],
            }
        ],
    }
    _write_json(handoff / "acceptance_tests.yaml", acceptance_payload)
    source_contract = out / "evidence_contract.yaml"
    if not source_contract.is_file():
        raise FileNotFoundError(
            "evidence_contract.yaml must be written before the Codex Handoff Pack."
        )
    (handoff / "evidence_contract.yaml").write_text(
        source_contract.read_text(encoding="utf-8"), encoding="utf-8"
    )
    (handoff / "risk_register.md").write_text(
        "# Risk Register\n\n"
        + "\n".join(
            f"- **{item.claim_id} / {item.status}:** {item.reason}"
            for item in decisions
            if item.status != "supported"
        )
        + "\n\n- Remote model output is advisory and must pass deterministic validation.\n"
        "- Workflow evidence supports design intent, not real-world performance.\n"
        "- Never use real patient data, confidential manuscripts, or unpublished private material.\n",
        encoding="utf-8",
    )
    (handoff / "demo_scenario.md").write_text(
        "# Judge Demo Scenario\n\n"
        "1. Start from the bundled synthetic quality-inspection workflow.\n"
        "2. Generate candidate capability claims with mock mode or GPT-5.6.\n"
        "3. Show the claim decision table and open the deliberate autonomy overclaim.\n"
        "4. Show how ClaimHarness downgrades it to human-reviewed decision support.\n"
        "5. Open this Codex Handoff Pack and the replayable build record.\n",
        encoding="utf-8",
    )
    return {
        name: _sha256_file(handoff / name)
        for name in HANDOFF_FILES
    }


def _write_build_record(
    path: Path,
    proposal: BuildProposal,
    decisions: list[CapabilityDecision],
    runtime_record: dict[str, Any],
    handoff_hashes: dict[str, str],
    *,
    timestamp: str,
) -> None:
    counts = Counter(decision.status for decision in decisions)
    events = [
        {
            "event_id": "BR001",
            "timestamp": timestamp,
            "stage": "proposal_generated",
            "details": {
                "provider": runtime_record["provider"],
                "model": runtime_record["model"],
                "gpt_5_6_used": runtime_record["gpt_5_6_used"],
                "response_id": runtime_record["response_id"],
                "claim_ids": [item.claim_id for item in proposal.capability_claims],
            },
        },
        {
            "event_id": "BR002",
            "timestamp": timestamp,
            "stage": "claims_evidence_gated",
            "details": {
                "status_counts": dict(sorted(counts.items())),
                "decisions": [
                    {
                        "claim_id": item.claim_id,
                        "status": item.status,
                        "action": item.action,
                    }
                    for item in decisions
                ],
            },
        },
        {
            "event_id": "BR003",
            "timestamp": timestamp,
            "stage": "codex_handoff_written",
            "details": {"artifact_sha256": handoff_hashes},
        },
    ]
    path.write_text(
        "".join(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n" for event in events),
        encoding="utf-8",
    )


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _sha256_json(payload: Any) -> str:
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
