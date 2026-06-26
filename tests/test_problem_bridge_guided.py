from pathlib import Path

from problem_bridge.guided import (
    FRIENDLY_FILE_LABELS,
    build_ai_practitioner_problem,
    build_domain_practitioner_problem,
    build_workflow_first_problem,
    discover_alignment_outputs,
    friendly_summary,
)


def test_domain_practitioner_answers_build_plain_language_problem_markdown():
    markdown = build_domain_practitioner_problem(
        {
            "field": "embryology lab",
            "workflow": "review microscope notes and prepare injection guidance",
            "repetitive_step": "checking image regions repeatedly",
            "expert_step": "deciding whether the evidence is reliable enough",
            "materials": "images, CSV notes, short reports",
            "not_automatic": "final clinical or operational decision",
            "useful_output": "a short evidence summary and review flag",
        }
    )

    assert "# Domain Practitioner Problem Brief" in markdown
    assert "embryology lab" in markdown
    assert "final clinical or operational decision" in markdown
    assert "AI task spec" not in markdown
    assert "evidence contract" not in markdown


def test_ai_practitioner_answers_build_problem_markdown_with_alignment_checks():
    markdown = build_ai_practitioner_problem(
        {
            "domain_problem": "help art historians evaluate Chinese painting commentary",
            "candidate_task": "image captioning",
            "inputs": "painting images and commentary",
            "outputs": "caption and cultural explanation",
            "metric": "caption similarity",
            "user": "art historian",
            "high_risk_mistakes": "treating object recognition as cultural understanding",
        }
    )

    assert "# AI Practitioner Problem Brief" in markdown
    assert "image captioning" in markdown
    assert "caption similarity" in markdown
    assert "treating object recognition as cultural understanding" in markdown


def test_workflow_first_answers_build_problem_markdown_with_required_sections():
    markdown = build_workflow_first_problem(
        {
            "domain": "embryology lab",
            "repeated_work": "review microscope notes before injection planning",
            "current_owner": "senior embryologist",
            "result": "review note and escalation decision",
            "step_1": "collect image notes",
            "step_2": "compare against prior records",
            "step_3": "flag uncertain regions",
            "step_4": "write a short review note",
            "additional_notes": "workflow varies by case urgency",
            "time_consuming_step": "checking repeated image regions",
            "annoying_step": "copying notes between sheets",
            "error_prone_step": "missing unclear evidence",
            "expert_judgement_step": "deciding whether evidence is reliable enough",
            "materials": ["tables", "images", "reports", "expert judgement"],
            "critical_materials": "microscope notes and prior records",
            "missing_materials": "inconsistent evidence labels",
            "never_automated": "final clinical or operational decision",
            "human_confirmed": "any high-risk judgement",
            "serious_mistakes": "overstating evidence quality",
            "useful_support": ["evidence summaries", "risk flags", "questions for human review"],
        }
    )

    required_sections = [
        "## domain",
        "## repeated_work",
        "## workflow_steps",
        "## pain_points",
        "## judgement_materials",
        "## non_automatable_decisions",
        "## useful_assistant_outputs",
    ]
    for section in required_sections:
        assert section in markdown

    assert "review microscope notes before injection planning" in markdown
    assert "senior embryologist" in markdown
    assert "1. collect image notes" in markdown
    assert "- tables" in markdown
    assert "- evidence summaries" in markdown
    assert "final clinical or operational decision" in markdown
    assert "AI task spec" not in markdown


def test_friendly_labels_hide_default_technical_file_names():
    assert FRIENDLY_FILE_LABELS["problem_card.md"] == "这个项目到底想解决什么"
    assert FRIENDLY_FILE_LABELS["workflow_map.md"] == "Your current workflow"
    assert FRIENDLY_FILE_LABELS["painpoint_opportunity_matrix.csv"] == "Where AI may help"
    assert FRIENDLY_FILE_LABELS["concept_alignment_table.csv"] == "Concepts AI may misunderstand"
    assert FRIENDLY_FILE_LABELS["human_in_loop_plan.md"] == "Boundaries and human review"
    assert FRIENDLY_FILE_LABELS["ai_task_spec.yaml"] == "For AI engineers: task specification"
    assert FRIENDLY_FILE_LABELS["evidence_contract.yaml"] == "For AI engineers: evidence contract"


def test_discover_alignment_outputs_returns_existing_expected_files(tmp_path):
    (tmp_path / "problem_card.md").write_text("summary", encoding="utf-8")
    (tmp_path / "ai_task_spec.yaml").write_text("task", encoding="utf-8")
    (tmp_path / "alignment_trace.jsonl").write_text("{}", encoding="utf-8")

    discovered = discover_alignment_outputs(tmp_path)

    assert [item.filename for item in discovered] == [
        "problem_card.md",
        "ai_task_spec.yaml",
        "alignment_trace.jsonl",
    ]
    assert discovered[0].friendly_label == "这个项目到底想解决什么"


def test_friendly_summary_extracts_cards_from_hsg_package(tmp_path):
    out = tmp_path / "hsg_alignment"
    out.mkdir()
    (out / "problem_card.md").write_text(
        "# Problem Card\n\n## Domain Goal\n\nSupport reviewable HSG interpretation.\n",
        encoding="utf-8",
    )
    (out / "workflow_map.md").write_text(
        "# Domain Workflow Map\n\n1. Image acquisition\n2. Clinician interpretation\n",
        encoding="utf-8",
    )
    (out / "painpoint_opportunity_matrix.csv").write_text(
        "workflow_step,pain_point,ai_opportunity,risk,human_role\n"
        "report drafting,wording overstates evidence,conservative draft,high,approve wording\n",
        encoding="utf-8",
    )
    (out / "misalignment_risk_report.md").write_text(
        "# Misalignment Risk Report\n\n- Do not automate diagnosis.\n",
        encoding="utf-8",
    )
    (out / "implementation_routes.md").write_text(
        "# Implementation Routes\n\n- Start with evidence sidecar prototype.\n",
        encoding="utf-8",
    )

    summary = friendly_summary(out)

    assert summary.one_sentence == "Support reviewable HSG interpretation."
    assert summary.workflow_steps == ["Image acquisition", "Clinician interpretation"]
    assert summary.opportunities[0] == "conservative draft"
    assert summary.must_review[0] == "Do not automate diagnosis."
    assert summary.next_steps[0] == "Start with evidence sidecar prototype."
