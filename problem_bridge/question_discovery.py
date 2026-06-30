from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class DiscoveryQuestion:
    category: str
    question: str
    why_it_matters: str
    ask_who: str


@dataclass(frozen=True)
class StakeholderTarget:
    role: str
    why: str
    first_questions: list[str]


@dataclass(frozen=True)
class QuestionDiscoveryPackage:
    source_context: str
    uncertainty: str
    desired_change: str
    focus: str
    questions: list[DiscoveryQuestion]
    stakeholders: list[StakeholderTarget]
    unknowns_to_validate: list[str]
    discussion_plan: list[str]


def discover_questions(
    seed_text: str,
    uncertainty: str = "",
    desired_change: str = "",
) -> QuestionDiscoveryPackage:
    """Build a local question-first handoff before AI task design."""

    source_context = _clean(seed_text) or "A domain user has a vague workflow problem."
    clean_uncertainty = _clean(uncertainty) or "The user does not yet know what to ask or who to ask."
    clean_desired_change = _clean(desired_change) or "Prepare a better first expert conversation."
    focus = _focus_from(source_context, clean_desired_change)

    questions = [
        DiscoveryQuestion(
            category="workflow",
            question=f"What repeated work or decision is actually happening in: {focus}?",
            why_it_matters="A useful AI task cannot be defined until the real workflow is visible.",
            ask_who="frontline practitioner",
        ),
        DiscoveryQuestion(
            category="evidence",
            question="What materials do people inspect when making this judgement?",
            why_it_matters="Inputs, missing context, and evidence standards determine what support is possible.",
            ask_who="data or materials owner",
        ),
        DiscoveryQuestion(
            category="expertise",
            question="Which parts depend on trained judgement, tacit rules, or local context?",
            why_it_matters="These parts should shape human-review boundaries and expert validation.",
            ask_who="domain expert",
        ),
        DiscoveryQuestion(
            category="failure_modes",
            question="What would count as a misleading, harmful, or unacceptable answer?",
            why_it_matters="Failure modes reveal where automation would be risky or inappropriate.",
            ask_who="risk or governance reviewer",
        ),
        DiscoveryQuestion(
            category="stakeholders",
            question="Who owns the decision, who is affected by it, and who can verify the problem framing?",
            why_it_matters="The first conversation can fail if it asks only the easiest person, not the right mix of people.",
            ask_who="project lead",
        ),
        DiscoveryQuestion(
            category="evaluation",
            question="What would convince practitioners that support is useful without replacing their decision?",
            why_it_matters="Evaluation should measure workflow value and safety boundaries, not just model fluency.",
            ask_who="frontline practitioner and AI practitioner",
        ),
        DiscoveryQuestion(
            category="data_readiness",
            question="What examples, labels, records, guidelines, or edge cases are needed before design begins?",
            why_it_matters="Data readiness shapes whether the next step is research, annotation, workflow redesign, or model work.",
            ask_who="data or system owner",
        ),
    ]

    stakeholders = _stakeholders_for(source_context)
    unknowns = [
        "Which workflow step is repeated often enough to justify support?",
        "Which judgement materials are reliable, available, and allowed to be used?",
        "Which decisions must stay with a human reviewer?",
        "Which mistake would be serious enough to stop or redesign the project?",
        "Which expert can say whether the question is framed correctly?",
    ]
    discussion_plan = [
        "Do not propose a solution yet; first validate the questions and stakeholders.",
        "Start with the frontline workflow, then ask what evidence is inspected.",
        "Ask domain experts where judgement becomes ambiguous or high-risk.",
        "Ask data or system owners what materials are available and what cannot be shared.",
        "After these unknowns are validated, move into ProblemBridge guided interview or alignment generation.",
    ]

    return QuestionDiscoveryPackage(
        source_context=source_context,
        uncertainty=clean_uncertainty,
        desired_change=clean_desired_change,
        focus=focus,
        questions=questions,
        stakeholders=stakeholders,
        unknowns_to_validate=unknowns,
        discussion_plan=discussion_plan,
    )


def write_question_discovery_package(package: QuestionDiscoveryPackage, out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    _write_text(out / "question_brief.md", _question_brief(package))
    _write_text(out / "stakeholder_map.md", _stakeholder_map(package))
    _write_text(out / "expert_interview_guide.md", _expert_interview_guide(package))
    _write_text(out / "unknowns_to_validate.md", _unknowns_to_validate(package))
    _write_text(out / "discussion_plan.md", _discussion_plan(package))


def build_problem_from_discovery(package: QuestionDiscoveryPackage) -> str:
    return _clean_markdown(
        f"""
        # Question Discovery Problem Seed

        ## Source context
        {package.source_context}

        ## Current uncertainty
        {package.uncertainty}

        ## Desired change
        {package.desired_change}

        ## Questions to validate before solution design
        {_numbered_questions(package.questions)}

        ## Stakeholders to interview
        {_stakeholder_bullets(package.stakeholders)}

        ## Boundary
        Do not turn this into an AI task until these questions are discussed.
        """
    )


def _stakeholders_for(source_context: str) -> list[StakeholderTarget]:
    roles = [
        StakeholderTarget(
            role="frontline practitioner",
            why="They know the repeated work, real constraints, and informal judgement steps.",
            first_questions=[
                "What do you do repeatedly?",
                "Which step is slow, ambiguous, or easy to get wrong?",
            ],
        ),
        StakeholderTarget(
            role="domain expert",
            why="They can identify tacit rules, high-risk conclusions, and professional boundaries.",
            first_questions=[
                "Which judgement requires expertise?",
                "What should not be automated?",
            ],
        ),
        StakeholderTarget(
            role="data or materials owner",
            why="They know which materials exist, which are reliable, and which cannot be shared.",
            first_questions=[
                "What records, examples, or guidelines exist?",
                "Which materials are missing, noisy, or sensitive?",
            ],
        ),
        StakeholderTarget(
            role="affected user or reviewer",
            why="They can explain what useful support looks like from the receiving side.",
            first_questions=[
                "What output would help you review faster or more safely?",
                "What output would be confusing or unacceptable?",
            ],
        ),
        StakeholderTarget(
            role="risk or governance reviewer",
            why="They can define privacy, policy, safety, and accountability boundaries.",
            first_questions=[
                "What information cannot be entered into a tool?",
                "Which mistakes would require escalation?",
            ],
        ),
        StakeholderTarget(
            role="AI practitioner",
            why="They can translate validated questions into candidate task types and evaluation designs.",
            first_questions=[
                "What support task is feasible after expert validation?",
                "What evidence contract and evaluation protocol would be needed?",
            ],
        ),
    ]
    if _contains_any(source_context, ("clinical", "patient", "medical", "diagnosis", "hsg")):
        roles.insert(
            2,
            StakeholderTarget(
                role="clinical safety reviewer",
                why="They can prevent visual support from being mistaken for a clinical conclusion.",
                first_questions=[
                    "Which output would require clinician confirmation?",
                    "What claim would be unsafe without validation?",
                ],
            ),
        )
    if _contains_any(source_context, ("school", "student", "education", "lesson", "teacher")):
        roles.insert(
            2,
            StakeholderTarget(
                role="teacher or curriculum reviewer",
                why="They can define educational goals, value-sensitive boundaries, and acceptable feedback.",
                first_questions=[
                    "What educational judgement is being made?",
                    "Which feedback could mislead students or teachers?",
                ],
            ),
        )
    if _contains_any(source_context, ("painting", "heritage", "museum", "culture", "cultural")):
        roles.insert(
            2,
            StakeholderTarget(
                role="cultural interpretation expert",
                why="They can prevent object recognition from being mistaken for cultural interpretation.",
                first_questions=[
                    "Which interpretation requires cultural context?",
                    "What evidence supports a symbolic or historical reading?",
                ],
            ),
        )
    return roles


def _question_brief(package: QuestionDiscoveryPackage) -> str:
    return f"""# Question Brief

## Starting context

{package.source_context}

## Current uncertainty

{package.uncertainty}

## Desired change

{package.desired_change}

## Questions to validate

{_numbered_questions(package.questions)}
"""


def _stakeholder_map(package: QuestionDiscoveryPackage) -> str:
    blocks = ["# Stakeholder Map", "", "## Who to ask", ""]
    for stakeholder in package.stakeholders:
        blocks.extend(
            [
                f"### {stakeholder.role}",
                "",
                f"Why this person matters: {stakeholder.why}",
                "",
                "First questions:",
                _bullets(stakeholder.first_questions),
                "",
            ]
        )
    return "\n".join(blocks)


def _expert_interview_guide(package: QuestionDiscoveryPackage) -> str:
    lines = [
        "# Question discovery interview guide",
        "",
        "Use this guide before discussing AI methods or solution design.",
        "",
    ]
    for question in package.questions:
        lines.extend(
            [
                f"## {question.category.replace('_', ' ').title()}",
                "",
                f"Question: {question.question}",
                "",
                f"Ask who: {question.ask_who}",
                "",
                f"Why it matters: {question.why_it_matters}",
                "",
            ]
        )
    return "\n".join(lines)


def _unknowns_to_validate(package: QuestionDiscoveryPackage) -> str:
    return f"""# Unknowns To Validate

{_bullets(package.unknowns_to_validate)}
"""


def _discussion_plan(package: QuestionDiscoveryPackage) -> str:
    return f"""# Discussion Plan

{_numbered(package.discussion_plan)}
"""


def _focus_from(source_context: str, desired_change: str) -> str:
    first_sentence = source_context.split(".", 1)[0].strip()
    if first_sentence:
        return first_sentence[:160]
    return desired_change[:160]


def _numbered_questions(questions: list[DiscoveryQuestion]) -> str:
    lines = []
    for index, question in enumerate(questions, start=1):
        lines.append(f"{index}. [{question.category}] {question.question} Ask: {question.ask_who}.")
    return "\n".join(lines)


def _stakeholder_bullets(stakeholders: list[StakeholderTarget]) -> str:
    return "\n".join(f"- {stakeholder.role}: {stakeholder.why}" for stakeholder in stakeholders)


def _numbered(items: list[str]) -> str:
    return "\n".join(f"{index}. {item}" for index, item in enumerate(items, start=1))


def _bullets(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items)


def _write_text(path: Path, text: str) -> None:
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def _clean(value: str) -> str:
    return " ".join(value.strip().split())


def _clean_markdown(text: str) -> str:
    lines = [line.strip() for line in text.strip().splitlines()]
    return "\n".join(lines).strip() + "\n"


def _contains_any(value: str, needles: tuple[str, ...]) -> bool:
    haystack = value.lower()
    return any(needle in haystack for needle in needles)
