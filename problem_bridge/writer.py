import csv
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from claim_harness.evidence_contract import (
    ClaimEvidenceRule,
    EvidenceContract,
    default_evidence_contract,
    evidence_contract_id,
)

from .revision_governance import initialize_project_record
from .schemas import AlignmentPackage


TRACE_STEPS = [
    "load_problem_brief",
    "detect_alignment_profile",
    "build_alignment_package",
    "write_outputs",
]

ALIGNMENT_RUN_ARTIFACTS = [
    "problem_card.md",
    "workflow_map.md",
    "painpoint_opportunity_matrix.csv",
    "concept_alignment_table.csv",
    "ai_task_spec.yaml",
    "evidence_contract.yaml",
    "evaluation_protocol.md",
    "misalignment_risk_report.md",
    "human_in_loop_plan.md",
    "implementation_routes.md",
    "alignment_trace.jsonl",
]

# These files are a mutable project ledger. They are intentionally excluded
# from an individual run's immutable completion snapshot because recording a
# later revision updates them without changing the completed alignment run.
ALIGNMENT_GOVERNANCE_ARTIFACTS = [
    "project_record.json",
    "project_summary_log.md",
]
ALIGNMENT_ARTIFACTS = [*ALIGNMENT_RUN_ARTIFACTS, *ALIGNMENT_GOVERNANCE_ARTIFACTS]


def write_alignment_package(
    package: AlignmentPackage,
    out: Path,
    *,
    project_id: str | None = None,
) -> None:
    resolved_project_id = project_id or (
        "project-"
        + hashlib.sha256(package.source_problem.encode("utf-8")).hexdigest()[:16]
    )
    out.mkdir(parents=True, exist_ok=True)
    _write_text(out / "problem_card.md", _problem_card(package))
    _write_text(out / "workflow_map.md", _workflow_map(package))
    _write_painpoint_matrix(out / "painpoint_opportunity_matrix.csv", package)
    _write_concept_table(out / "concept_alignment_table.csv", package)
    _write_text(out / "ai_task_spec.yaml", _task_spec_yaml(package))
    _write_text(
        out / "evidence_contract.yaml",
        _evidence_contract_yaml(package, project_id=resolved_project_id),
    )
    _write_text(out / "evaluation_protocol.md", _evaluation_protocol(package))
    _write_text(out / "misalignment_risk_report.md", _misalignment_risk_report(package))
    _write_text(out / "human_in_loop_plan.md", _human_in_loop_plan(package))
    _write_text(out / "implementation_routes.md", _implementation_routes(package))
    _write_trace(out / "alignment_trace.jsonl", package)
    initialize_project_record(
        out,
        project_name=package.project_name,
        project_goal=package.domain_goal,
        project_id=resolved_project_id,
        boundaries=[package.not_allowed_goal, *package.human_review_required],
        artifacts=ALIGNMENT_ARTIFACTS,
    )


def _write_text(path: Path, text: str) -> None:
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def _problem_card(package: AlignmentPackage) -> str:
    return f"""# Problem Card

## Project

{package.title}

## Alignment Profile

`{package.profile}`

## Source Problem

{package.source_problem.strip()}

## Domain Goal

{package.domain_goal}

## Not Allowed Goal

{package.not_allowed_goal}

## Meaningful Outputs

{_bullets(package.meaningful_outputs)}

## Non-Meaningful Outputs

{_bullets(package.non_meaningful_outputs)}
"""


def _workflow_map(package: AlignmentPackage) -> str:
    lines = ["# Domain Workflow Map", ""]
    lines.extend(f"{index}. {step}" for index, step in enumerate(package.workflow_steps, start=1))
    return "\n".join(lines)


def _write_painpoint_matrix(path: Path, package: AlignmentPackage) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["workflow_step", "pain_point", "ai_opportunity", "risk", "human_role"],
        )
        writer.writeheader()
        for row in package.painpoints:
            writer.writerow({key: _spreadsheet_safe(value) for key, value in row.model_dump().items()})


def _write_concept_table(path: Path, package: AlignmentPackage) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "domain_concept",
                "ai_representation",
                "alignment_status",
                "misalignment_risk",
            ],
        )
        writer.writeheader()
        for row in package.concepts:
            writer.writerow({key: _spreadsheet_safe(value) for key, value in row.model_dump().items()})


def _task_spec_yaml(package: AlignmentPackage) -> str:
    data = {
        "project_name": package.project_name,
        "domain_goal": package.domain_goal,
        "not_allowed_goal": package.not_allowed_goal,
        "ai_task_type": package.ai_task_type,
        "inputs": package.inputs,
        "outputs": package.outputs,
        "evaluation": package.evaluation_protocol,
        "human_review_required": package.human_review_required,
    }
    return _to_yaml(data)


def _evidence_contract_yaml(package: AlignmentPackage, *, project_id: str) -> str:
    boundary_notes = [*package.human_review_required]
    boundary_notes.extend(
        f"{claim_type} requires: {', '.join(requirements)}"
        for claim_type, requirements in package.required_evidence.items()
    )
    boundary_notes.extend(
        f"{claim_type} is forbidden without: {', '.join(requirements)}"
        for claim_type, requirements in package.forbidden_without.items()
    )
    roles = (
        {"domain_reviewer": "Review the ProblemBridge boundaries: " + "; ".join(boundary_notes)}
        if boundary_notes
        else {}
    )
    contract = default_evidence_contract(
        project_id=project_id,
        human_review_roles=roles,
        role_claim_types={"clinical_claim", "deployment_claim", "general_claim"},
    )

    rules = dict(contract.claim_rules)
    domain_claim_types = set(package.required_evidence) | set(package.forbidden_without)
    for domain_claim_type in sorted(domain_claim_types):
        claim_type = _contract_claim_type(domain_claim_type)
        current = rules[claim_type]
        raw_required = package.required_evidence.get(domain_claim_type, [])
        raw_forbidden = package.forbidden_without.get(domain_claim_type, [])
        required = _stable_unique(
            [*current.required_evidence, *[_contract_requirement(item) for item in raw_required]]
        )
        forbidden = _stable_unique(
            [*current.forbidden_without, *[_contract_requirement(item) for item in raw_forbidden]]
        )
        review_roles = list(current.human_review_roles)
        if roles and (raw_forbidden or claim_type != "performance_claim"):
            review_roles = _stable_unique([*review_roles, "domain_reviewer"])
        rules[claim_type] = ClaimEvidenceRule(
            minimum_evidence_count=max(
                current.minimum_evidence_count,
                len(raw_required),
                len(required),
            ),
            required_evidence=required,
            forbidden_without=forbidden,
            human_review_roles=review_roles,
        )

    payload = contract.model_dump(mode="json")
    payload["claim_rules"] = {
        claim_type: rule.model_dump(mode="json")
        for claim_type, rule in rules.items()
    }
    payload["contract_id"] = evidence_contract_id(payload)
    contract = EvidenceContract.model_validate(payload)
    # JSON is valid YAML 1.2 and lets the core package load contracts without
    # adding a YAML parser dependency to the local-first installation.
    return json.dumps(contract.model_dump(mode="json"), indent=2, ensure_ascii=False)


def _contract_claim_type(domain_claim_type: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", domain_claim_type.strip().lower()).strip("_")
    if "performance" in normalized or "metric" in normalized:
        return "performance_claim"
    if "robust" in normalized:
        return "robustness_claim"
    if "novel" in normalized or "first" in normalized:
        return "novelty_claim"
    if "workflow" in normalized or "trace" in normalized:
        return "workflow_claim"
    if "clinical" in normalized:
        return "clinical_claim"
    if "deploy" in normalized or "operational" in normalized:
        return "deployment_claim"
    return "general_claim"


def _contract_requirement(requirement: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", requirement.strip().lower()).strip("_")
    explicit_domain_mappings = {
        "visible_image_detail": "source_inspection",
        "catalog_or_context_note": "citation",
        "alternative_interpretation_check": "human_review",
        "expert_review": "human_review",
        "catalog_or_context_support": "citation",
        "source_region_or_record": "source_inspection",
        "uncertainty_statement": "manuscript_context",
        "human_review_flag": "human_review",
        "quantitative_table": "table",
        "baseline_comparison": "table",
        "error_analysis": "robustness_test",
        "reviewer_confirmation": "human_review",
        "input_quality_assessment": "source_inspection",
        "training_objective": "manuscript_context",
        "policy_source_fragment": "citation",
        "uncertainty_or_scope_statement": "manuscript_context",
        "reviewer_approval": "human_review",
        "source_grounding": "citation",
        "domain_note": "manuscript_context",
        "workflow_step": "trace",
        "human_review_boundary": "human_review",
        "domain_practitioner_review": "human_review",
    }
    if normalized in explicit_domain_mappings:
        return explicit_domain_mappings[normalized]
    known = {
        "table",
        "ablation",
        "trace",
        "result_text",
        "external_validation",
        "human_review",
        "robustness_test",
        "citation",
        "manuscript_context",
        "source_inspection",
    }
    if normalized in known:
        return normalized
    if any(token in normalized for token in ("review", "approval", "confirmation", "practitioner")):
        return "human_review"
    if any(token in normalized for token in ("external", "validation")):
        return "external_validation"
    if any(token in normalized for token in ("quantitative", "metric", "table", "baseline")):
        return "table"
    if any(token in normalized for token in ("ablation",)):
        return "ablation"
    if any(token in normalized for token in ("robust", "error", "quality", "uncertainty")):
        return "robustness_test"
    if any(token in normalized for token in ("workflow", "trace", "record")):
        return "trace"
    if any(token in normalized for token in ("citation", "catalog", "policy", "reference", "source")):
        return "citation"
    raise ValueError(
        "Cannot map domain evidence requirement to the executable evidence contract: "
        f"{requirement!r}. Use an explicit supported requirement instead of silently "
        "downgrading it to manuscript context."
    )


def _stable_unique(items: list[str]) -> list[str]:
    return list(dict.fromkeys(items))


def _evaluation_protocol(package: AlignmentPackage) -> str:
    return f"""# Evaluation Protocol

## What To Evaluate

{_bullets(package.evaluation_protocol)}

## Insufficient Metrics

{_bullets(package.insufficient_metrics)}
"""


def _misalignment_risk_report(package: AlignmentPackage) -> str:
    return f"""# Misalignment Risk Report

These are formulation risks where an AI task could drift away from the source-domain problem.

{_bullets(package.misalignment_risks)}
"""


def _human_in_loop_plan(package: AlignmentPackage) -> str:
    return f"""# Human-In-The-Loop Plan

Human review is required for:

{_bullets(package.human_review_required)}
"""


def _implementation_routes(package: AlignmentPackage) -> str:
    return f"""# Implementation Routes

{_bullets(package.implementation_routes)}
"""


def _write_trace(path: Path, package: AlignmentPackage) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for step in TRACE_STEPS:
            event = {
                "step": step,
                "profile": package.profile,
                "project_name": package.project_name,
            }
            handle.write(json.dumps(event, ensure_ascii=False) + "\n")


def _bullets(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items)


def _to_yaml(value: Any, indent: int = 0) -> str:
    spaces = " " * indent
    if isinstance(value, dict):
        lines = []
        for key, item in value.items():
            if isinstance(item, (dict, list)):
                lines.append(f"{spaces}{key}:")
                lines.append(_to_yaml(item, indent + 2))
            else:
                lines.append(f"{spaces}{key}: {_scalar(item)}")
        return "\n".join(lines)
    if isinstance(value, list):
        if not value:
            return f"{spaces}[]"
        lines = []
        for item in value:
            if isinstance(item, (dict, list)):
                lines.append(f"{spaces}-")
                lines.append(_to_yaml(item, indent + 2))
            else:
                lines.append(f"{spaces}- {_scalar(item)}")
        return "\n".join(lines)
    return f"{spaces}{_scalar(value)}"


def _scalar(value: Any) -> str:
    text = str(value)
    if any(char in text for char in (":", "#", "\n")):
        return json.dumps(text, ensure_ascii=False)
    return text


def _spreadsheet_safe(value: object) -> object:
    if isinstance(value, str):
        candidate = value.lstrip()
        if candidate.startswith(("+", "-")) and re.fullmatch(
            r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?",
            candidate.strip(),
        ):
            return value
        if candidate.startswith(("=", "+", "-", "@")):
            return "'" + value
    return value
