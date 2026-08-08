import re

from .mock_profiles import (
    cultural_archive_profile,
    generic_profile,
    quality_inspection_profile,
    training_policy_profile,
)
from .schemas import AlignmentPackage


def detect_profile(problem_text: str) -> str:
    text = problem_text.casefold()
    if any(
        token in text
        for token in (
            "quality inspection",
            "inspection workflow",
            "defect",
            "pass/fail",
            "visual review",
            "reviewable inspection",
        )
    ):
        return "quality_inspection"
    if any(
        token in text
        for token in (
            "cultural archive",
            "archive interpretation",
            "catalog note",
            "metadata",
            "provenance",
            "expert interpretation",
        )
    ):
        return "cultural_archive"
    if any(
        token in text
        for token in (
            "training policy",
            "policy support",
            "policy source",
            "training content",
            "compliance guidance",
        )
    ):
        return "training_policy"
    return "generic"


def build_alignment_package(problem_text: str) -> AlignmentPackage:
    profile = detect_profile(problem_text)
    if profile == "quality_inspection":
        package = quality_inspection_profile(problem_text)
    elif profile == "cultural_archive":
        package = cultural_archive_profile(problem_text)
    elif profile == "training_policy":
        package = training_policy_profile(problem_text)
    else:
        package = generic_profile(problem_text)
    return _apply_guided_context(package, problem_text)


def _apply_guided_context(package: AlignmentPackage, problem_text: str) -> AlignmentPackage:
    """Apply explicit guided-form answers without claiming free-form semantic understanding."""

    sections = _markdown_sections(problem_text)
    updates: dict[str, object] = {}

    workflow_steps = _numbered_items(sections.get("workflow_steps", []))
    if len(workflow_steps) >= 2:
        updates["workflow_steps"] = workflow_steps

    materials = _section_values(sections.get("judgement_materials", []))
    if materials:
        updates["inputs"] = _stable_unique([*materials, *package.inputs])

    useful_outputs = _section_values(sections.get("useful_assistant_outputs", []))
    if useful_outputs:
        updates["meaningful_outputs"] = useful_outputs
        updates["outputs"] = _stable_unique([*useful_outputs, *package.outputs])

    human_boundaries = _section_values(sections.get("non_automatable_decisions", []))
    if human_boundaries:
        updates["not_allowed_goal"] = human_boundaries[0]
        updates["human_review_required"] = _stable_unique(
            [*human_boundaries, *package.human_review_required]
        )

    repeated_work = _first_value(sections.get("repeated_work", []))
    if repeated_work:
        updates["domain_goal"] = (
            f"Support the documented workflow for {repeated_work.rstrip('.')} while preserving "
            "the recorded evidence and human-review boundaries."
        )

    return package.model_copy(update=updates) if updates else package


def _markdown_sections(text: str) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {}
    current: str | None = None
    for raw_line in text.splitlines():
        heading = re.match(r"^\s*##\s+(.+?)\s*$", raw_line)
        if heading:
            current = re.sub(r"[^a-z0-9]+", "_", heading.group(1).casefold()).strip("_")
            sections.setdefault(current, [])
            continue
        if current is not None:
            sections[current].append(raw_line.strip())
    return sections


def _numbered_items(lines: list[str]) -> list[str]:
    items = []
    for line in lines:
        match = re.match(r"^\d+[.)]\s+(.+)$", line)
        if match and match.group(1).strip():
            items.append(match.group(1).strip())
    return items


def _section_values(lines: list[str]) -> list[str]:
    values = []
    for line in lines:
        cleaned = re.sub(r"^[-*]\s+", "", line).strip()
        if not cleaned or cleaned.endswith(":") or cleaned.lower() in {"none", "n/a"}:
            continue
        values.append(cleaned)
    return _stable_unique(values)


def _first_value(lines: list[str]) -> str:
    values = _section_values(lines)
    return values[0] if values else ""


def _stable_unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    output = []
    for value in values:
        key = value.casefold()
        if key not in seen:
            seen.add(key)
            output.append(value)
    return output
