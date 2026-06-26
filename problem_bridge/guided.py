import csv
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


FRIENDLY_FILE_LABELS = {
    "problem_card.md": "这个项目到底想解决什么",
    "workflow_map.md": "Your current workflow",
    "painpoint_opportunity_matrix.csv": "Where AI may help",
    "concept_alignment_table.csv": "Concepts AI may misunderstand",
    "ai_task_spec.yaml": "For AI engineers: task specification",
    "evidence_contract.yaml": "For AI engineers: evidence contract",
    "evaluation_protocol.md": "怎么判断这个 AI 真的有用",
    "misalignment_risk_report.md": "哪些地方可能做偏",
    "human_in_loop_plan.md": "Boundaries and human review",
    "implementation_routes.md": "下一步可以怎么做",
    "alignment_trace.jsonl": "生成过程记录",
}

TECHNICAL_FILE_ORDER = [
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


@dataclass(frozen=True)
class OutputFile:
    filename: str
    path: Path
    friendly_label: str


@dataclass(frozen=True)
class FriendlySummary:
    one_sentence: str
    workflow_steps: list[str]
    opportunities: list[str]
    must_review: list[str]
    next_steps: list[str]


def build_domain_practitioner_problem(answers: Mapping[str, str]) -> str:
    return _clean_markdown(
        f"""
        # Domain Practitioner Problem Brief

        I work in {answers.get("field", "an interdisciplinary domain")}.

        The work process I want to improve is:
        {answers.get("workflow", "")}

        The repetitive step is:
        {answers.get("repetitive_step", "")}

        The difficult or expert-dependent step is:
        {answers.get("expert_step", "")}

        The materials I already have are:
        {answers.get("materials", "")}

        The things that should not be decided automatically are:
        {answers.get("not_automatic", "")}

        A useful assistant would produce:
        {answers.get("useful_output", "")}
        """
    )


def build_workflow_first_problem(answers: Mapping[str, object]) -> str:
    materials = _list_block(answers.get("materials"))
    useful_support = _list_block(answers.get("useful_support"))
    return _clean_markdown(
        f"""
        # Workflow-First Problem Brief

        ## domain
        {answers.get("domain", "")}

        ## repeated_work
        {answers.get("repeated_work", "")}

        Current decision maker:
        {answers.get("current_owner", "")}

        Result produced:
        {answers.get("result", "")}

        ## workflow_steps
        1. {answers.get("step_1", "")}
        2. {answers.get("step_2", "")}
        3. {answers.get("step_3", "")}
        4. {answers.get("step_4", "")}

        Additional notes:
        {answers.get("additional_notes", "")}

        ## pain_points
        Most time-consuming step:
        {answers.get("time_consuming_step", "")}

        Most annoying step:
        {answers.get("annoying_step", "")}

        Most error-prone step:
        {answers.get("error_prone_step", "")}

        Most expert-dependent step:
        {answers.get("expert_judgement_step", "")}

        ## judgement_materials
        Materials used:
        {materials}

        Most critical materials:
        {answers.get("critical_materials", "")}

        Materials that are missing, unclear, or hard to organize:
        {answers.get("missing_materials", "")}

        ## non_automatable_decisions
        What should never be automated:
        {answers.get("never_automated", "")}

        What must be confirmed by a human:
        {answers.get("human_confirmed", "")}

        Serious mistakes:
        {answers.get("serious_mistakes", "")}

        ## useful_assistant_outputs
        {useful_support}
        """
    )


def build_ai_practitioner_problem(answers: Mapping[str, str]) -> str:
    return _clean_markdown(
        f"""
        # AI Practitioner Problem Brief

        The domain problem I am trying to solve is:
        {answers.get("domain_problem", "")}

        The AI task I am considering is:
        {answers.get("candidate_task", "")}

        The inputs I have are:
        {answers.get("inputs", "")}

        The outputs I expect are:
        {answers.get("outputs", "")}

        The metric I would use is:
        {answers.get("metric", "")}

        The person or group who will use the result is:
        {answers.get("user", "")}

        The mistakes that would be high-risk are:
        {answers.get("high_risk_mistakes", "")}
        """
    )


def discover_alignment_outputs(output_dir: Path) -> list[OutputFile]:
    files = []
    for filename in TECHNICAL_FILE_ORDER:
        path = output_dir / filename
        if path.is_file():
            files.append(
                OutputFile(
                    filename=filename,
                    path=path,
                    friendly_label=FRIENDLY_FILE_LABELS.get(filename, filename),
                )
            )
    return files


def friendly_summary(output_dir: Path) -> FriendlySummary:
    return FriendlySummary(
        one_sentence=_extract_domain_goal(output_dir / "problem_card.md"),
        workflow_steps=_extract_numbered_steps(output_dir / "workflow_map.md"),
        opportunities=_extract_csv_column(output_dir / "painpoint_opportunity_matrix.csv", "ai_opportunity"),
        must_review=_extract_bullets(output_dir / "misalignment_risk_report.md"),
        next_steps=_extract_bullets(output_dir / "implementation_routes.md"),
    )


def _clean_markdown(text: str) -> str:
    lines = [line.strip() for line in text.strip().splitlines()]
    return "\n".join(lines).strip() + "\n"


def _list_block(value: object) -> str:
    if isinstance(value, str):
        items = [value] if value else []
    else:
        try:
            items = [str(item) for item in value if str(item)]
        except TypeError:
            items = []
    return "\n".join(f"- {item}" for item in items)


def _extract_domain_goal(path: Path) -> str:
    if not path.is_file():
        return "这个项目适合先做工作流梳理和高风险提示，而不是直接自动决策。"
    text = path.read_text(encoding="utf-8")
    marker = "## Domain Goal"
    if marker not in text:
        return _first_nonempty_line(text)
    remainder = text.split(marker, 1)[1]
    return _first_nonempty_line(remainder)


def _first_nonempty_line(text: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            return stripped
    return "这个项目适合先做工作流梳理和高风险提示，而不是直接自动决策。"


def _extract_numbered_steps(path: Path) -> list[str]:
    if not path.is_file():
        return []
    steps = []
    for line in path.read_text(encoding="utf-8").splitlines():
        match = re.match(r"\s*\d+\.\s+(.+?)\s*$", line)
        if match:
            steps.append(match.group(1))
    return steps


def _extract_csv_column(path: Path, column: str) -> list[str]:
    if not path.is_file():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        rows = csv.DictReader(handle)
        return [row[column] for row in rows if row.get(column)]


def _extract_bullets(path: Path) -> list[str]:
    if not path.is_file():
        return []
    bullets = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("- "):
            bullets.append(stripped[2:].strip())
    return bullets
