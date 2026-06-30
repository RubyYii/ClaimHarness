from pathlib import Path

from problem_bridge.question_discovery import (
    build_problem_from_discovery,
    discover_questions,
    write_question_discovery_package,
)


def test_discovers_questions_and_stakeholders_before_solution_design():
    package = discover_questions(
        seed_text=(
            "I feel our lab review process is slow and hard to explain, "
            "but I do not know whether this is an AI problem yet."
        ),
        uncertainty="I do not know who to ask first.",
        desired_change="Find the right questions before discussing a system design.",
    )

    categories = {question.category for question in package.questions}
    assert {
        "workflow",
        "evidence",
        "expertise",
        "failure_modes",
        "stakeholders",
        "evaluation",
    }.issubset(categories)

    assert all(question.ask_who for question in package.questions)
    assert all(question.why_it_matters for question in package.questions)
    assert any(stakeholder.role == "frontline practitioner" for stakeholder in package.stakeholders)
    assert any(stakeholder.role == "AI practitioner" for stakeholder in package.stakeholders)
    assert "Do not propose a solution yet" in package.discussion_plan[0]


def test_question_discovery_writer_creates_handoff_files(tmp_path: Path):
    package = discover_questions(
        seed_text="We want to understand why image review takes so long.",
        uncertainty="We are not sure whether to ask the operator, supervisor, or data team.",
        desired_change="Prepare a useful first expert conversation.",
    )

    write_question_discovery_package(package, tmp_path)

    expected_files = [
        "question_brief.md",
        "stakeholder_map.md",
        "expert_interview_guide.md",
        "unknowns_to_validate.md",
        "discussion_plan.md",
    ]
    for filename in expected_files:
        assert (tmp_path / filename).is_file(), filename

    question_brief = (tmp_path / "question_brief.md").read_text(encoding="utf-8")
    stakeholder_map = (tmp_path / "stakeholder_map.md").read_text(encoding="utf-8")
    interview_guide = (tmp_path / "expert_interview_guide.md").read_text(encoding="utf-8")
    discussion_plan = (tmp_path / "discussion_plan.md").read_text(encoding="utf-8")

    assert "Questions to validate" in question_brief
    assert "Who to ask" in stakeholder_map
    assert "Why this person matters" in stakeholder_map
    assert "Question discovery interview guide" in interview_guide
    assert "Do not propose a solution yet" in discussion_plan


def test_discovery_package_can_become_problembridge_seed_brief():
    package = discover_questions(
        seed_text="A school team wants to know what to ask before using AI in lesson review.",
        uncertainty="They do not know which expert can define the real risk.",
        desired_change="Prepare questions for the first discussion.",
    )

    brief = build_problem_from_discovery(package)

    assert "# Question Discovery Problem Seed" in brief
    assert "Questions to validate before solution design" in brief
    assert "Stakeholders to interview" in brief
    assert "Do not turn this into an AI task until these questions are discussed." in brief
