from problem_bridge.interview import (
    answer_question,
    build_problem_from_interview,
    is_ready_for_alignment,
    next_question,
    start_interview,
    summarize_understanding,
)


def test_interview_starts_from_repeated_work_not_ai_task():
    state = start_interview()

    question = next_question(state)

    assert question.key == "repeated_work"
    assert "repeated work" in question.prompt
    assert "AI task" in question.reframe
    assert state.answers == {}


def test_interview_routes_questions_based_on_missing_understanding():
    state = start_interview()
    state = answer_question(state, "repeated_work", "I repeatedly review microscope notes before injection guidance.")

    question = next_question(state)
    assert question.key == "materials"

    state = answer_question(state, "materials", "microscope images, notes, prior case records")
    question = next_question(state)
    assert question.key == "pain_points"


def test_understanding_summary_tracks_known_and_missing_slots():
    state = start_interview()
    state = answer_question(state, "repeated_work", "I review student answers for political education risks.")
    state = answer_question(state, "materials", "student answers, rubric, teacher notes")

    summary = summarize_understanding(state)

    assert "repeated work" in summary.known_items[0].lower()
    assert "materials" in " ".join(summary.known_items).lower()
    assert "pain points" in summary.missing_items
    assert "human review boundaries" in summary.missing_items
    assert 0 < summary.completeness < 1


def test_interview_ready_after_core_slots_are_answered():
    state = start_interview()
    for key, value in {
        "repeated_work": "I compare painting commentary with image details.",
        "materials": "painting images, commentary, catalog metadata",
        "pain_points": "commentary concepts are hard to align with image regions",
        "human_boundaries": "humans must confirm cultural interpretations",
        "useful_support": "evidence summaries and questions for human review",
    }.items():
        state = answer_question(state, key, value)

    summary = summarize_understanding(state)

    assert is_ready_for_alignment(state)
    assert summary.completeness == 1
    assert next_question(state).key == "confirmation"


def test_interview_builds_problembridge_brief():
    state = start_interview()
    for key, value in {
        "domain": "cultural heritage",
        "repeated_work": "I compare painting commentary with image details.",
        "materials": "painting images, commentary, catalog metadata",
        "pain_points": "object descriptions can be mistaken for interpretation",
        "human_boundaries": "humans must confirm cultural meaning and attribution",
        "useful_support": "evidence summaries, risk flags, and review questions",
    }.items():
        state = answer_question(state, key, value)

    brief = build_problem_from_interview(state)

    assert "# Guided Interview Problem Brief" in brief
    assert "## repeated_work" in brief
    assert "painting commentary" in brief
    assert "## judgement_materials" in brief
    assert "catalog metadata" in brief
    assert "## non_automatable_decisions" in brief
    assert "humans must confirm cultural meaning" in brief
