import csv
import json
from pathlib import Path
from typing import Any

from .schemas import AlignmentPackage


TRACE_STEPS = [
    "load_problem_brief",
    "detect_alignment_profile",
    "build_alignment_package",
    "write_outputs",
]


def write_alignment_package(package: AlignmentPackage, out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    _write_text(out / "problem_card.md", _problem_card(package))
    _write_text(out / "workflow_map.md", _workflow_map(package))
    _write_painpoint_matrix(out / "painpoint_opportunity_matrix.csv", package)
    _write_concept_table(out / "concept_alignment_table.csv", package)
    _write_text(out / "ai_task_spec.yaml", _task_spec_yaml(package))
    _write_text(out / "evidence_contract.yaml", _evidence_contract_yaml(package))
    _write_text(out / "evaluation_protocol.md", _evaluation_protocol(package))
    _write_text(out / "misalignment_risk_report.md", _misalignment_risk_report(package))
    _write_text(out / "human_in_loop_plan.md", _human_in_loop_plan(package))
    _write_text(out / "implementation_routes.md", _implementation_routes(package))
    _write_trace(out / "alignment_trace.jsonl", package)


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
            writer.writerow(row.model_dump())


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
            writer.writerow(row.model_dump())


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


def _evidence_contract_yaml(package: AlignmentPackage) -> str:
    data = {
        "claim_type": {
            claim_type: {
                "required_evidence": required,
                "forbidden_without": package.forbidden_without.get(claim_type, []),
            }
            for claim_type, required in package.required_evidence.items()
        }
    }
    return _to_yaml(data)


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
