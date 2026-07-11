from problem_bridge.generator import build_alignment_package


def test_guided_answers_override_matching_mock_profile_fields():
    brief = """# Workflow-First Problem Brief

## repeated_work
review microscopy reports

## workflow_steps
1. collect reports
2. compare measurements
3. draft reviewer notes

## judgement_materials
- measurement tables
- reviewer annotations

## non_automatable_decisions
Final clinical interpretation
Human confirmation of ambiguous findings

## useful_assistant_outputs
- evidence checklist
- conservative draft notes
"""

    package = build_alignment_package(brief)

    assert package.workflow_steps == [
        "collect reports",
        "compare measurements",
        "draft reviewer notes",
    ]
    assert package.inputs[:2] == ["measurement tables", "reviewer annotations"]
    assert package.meaningful_outputs == ["evidence checklist", "conservative draft notes"]
    assert package.not_allowed_goal == "Final clinical interpretation"
    assert package.human_review_required[:2] == [
        "Final clinical interpretation",
        "Human confirmation of ambiguous findings",
    ]
    assert "review microscopy reports" in package.domain_goal


def test_unstructured_brief_keeps_conservative_profile_defaults():
    package = build_alignment_package("A team needs quality inspection support for visible defects.")

    assert package.profile == "quality_inspection"
    assert package.not_allowed_goal == "autonomous pass/fail decision"
    assert "Item intake" in package.workflow_steps
