from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Mapping


@dataclass(frozen=True)
class InterviewQuestion:
    key: str
    prompt: str
    helper: str
    reframe: str = ""


@dataclass(frozen=True)
class InterviewState:
    answers: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class UnderstandingSummary:
    known_items: list[str]
    missing_items: list[str]
    completeness: float
    next_question: InterviewQuestion


QUESTION_FLOW: tuple[InterviewQuestion, ...] = (
    InterviewQuestion(
        key="repeated_work",
        prompt="What repeated work do you want to understand better?",
        helper="Describe a real task you do again and again.",
        reframe="Do not start with an AI task. Start with the work people already do.",
    ),
    InterviewQuestion(
        key="materials",
        prompt="What materials do you inspect when doing this work?",
        helper="Examples: images, notes, tables, reports, cases, rubrics, guidelines.",
    ),
    InterviewQuestion(
        key="pain_points",
        prompt="Where does this work become slow, ambiguous, annoying, or error-prone?",
        helper="Name the steps where human judgement becomes difficult.",
    ),
    InterviewQuestion(
        key="human_boundaries",
        prompt="Which decisions must remain under human review?",
        helper="List conclusions, approvals, or high-risk decisions that should not be automated.",
    ),
    InterviewQuestion(
        key="useful_support",
        prompt="If an assistant only supported the work, what would be useful?",
        helper="Examples: summaries, risk flags, evidence lists, draft notes, review questions.",
    ),
)

OPTIONAL_QUESTION = InterviewQuestion(
    key="domain",
    prompt="What domain or setting is this work in?",
    helper="A short label is enough, such as clinical imaging, education, cultural heritage, or lab work.",
)

CONFIRMATION_QUESTION = InterviewQuestion(
    key="confirmation",
    prompt="Does this understanding look right enough to generate an alignment package?",
    helper="Review the summary, edit any answer if needed, then generate the package.",
)

REQUIRED_KEYS = tuple(question.key for question in QUESTION_FLOW)
MISSING_LABELS: Mapping[str, str] = {
    "repeated_work": "repeated work",
    "materials": "materials",
    "pain_points": "pain points",
    "human_boundaries": "human review boundaries",
    "useful_support": "useful support outputs",
}


def start_interview() -> InterviewState:
    return InterviewState()


def answer_question(state: InterviewState, key: str, answer: str) -> InterviewState:
    next_answers = dict(state.answers)
    cleaned = answer.strip()
    if cleaned:
        next_answers[key] = cleaned
    else:
        next_answers.pop(key, None)
    return replace(state, answers=next_answers)


def next_question(state: InterviewState) -> InterviewQuestion:
    for question in QUESTION_FLOW:
        if not _has_answer(state, question.key):
            return question
    return CONFIRMATION_QUESTION


def summarize_understanding(state: InterviewState) -> UnderstandingSummary:
    known_items = []
    for key in ("domain", *REQUIRED_KEYS):
        if _has_answer(state, key):
            known_items.append(f"{MISSING_LABELS.get(key, key.replace('_', ' '))}: {state.answers[key]}")

    missing_items = [
        label for key, label in MISSING_LABELS.items() if not _has_answer(state, key)
    ]
    completeness = round((len(REQUIRED_KEYS) - len(missing_items)) / len(REQUIRED_KEYS), 2)
    return UnderstandingSummary(
        known_items=known_items,
        missing_items=missing_items,
        completeness=completeness,
        next_question=next_question(state),
    )


def is_ready_for_alignment(state: InterviewState) -> bool:
    return all(_has_answer(state, key) for key in REQUIRED_KEYS)


def build_problem_from_interview(state: InterviewState) -> str:
    answers = state.answers
    return _clean_markdown(
        f"""
        # Guided Interview Problem Brief

        ## domain
        {answers.get("domain", "unspecified domain")}

        ## repeated_work
        {answers.get("repeated_work", "")}

        ## workflow_steps
        1. Start from the repeated work described by the domain user.
        2. Inspect the judgement materials.
        3. Identify pain points and ambiguity.
        4. Route high-risk decisions to human review.

        ## pain_points
        {answers.get("pain_points", "")}

        ## judgement_materials
        {answers.get("materials", "")}

        ## non_automatable_decisions
        {answers.get("human_boundaries", "")}

        ## useful_assistant_outputs
        {answers.get("useful_support", "")}
        """
    )


def _has_answer(state: InterviewState, key: str) -> bool:
    return bool(state.answers.get(key, "").strip())


def _clean_markdown(text: str) -> str:
    lines = [line.strip() for line in text.strip().splitlines()]
    return "\n".join(lines).strip() + "\n"
