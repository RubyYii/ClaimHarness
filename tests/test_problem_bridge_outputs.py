import csv
import json
from pathlib import Path

from problem_bridge.generator import build_alignment_package
from problem_bridge.writer import write_alignment_package


def test_concept_alignment_table_has_alignment_columns(tmp_path):
    package = build_alignment_package(
        "I want to evaluate whether VLMs understand Chinese painting commentary."
    )
    write_alignment_package(package, tmp_path)

    with (tmp_path / "concept_alignment_table.csv").open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    assert rows
    assert set(rows[0]) == {
        "domain_concept",
        "ai_representation",
        "alignment_status",
        "misalignment_risk",
    }
    assert any(row["alignment_status"] == "misaligned" for row in rows)


def test_alignment_trace_records_ordered_steps(tmp_path):
    package = build_alignment_package(
        "I want to evaluate LLM hallucination and value risk in political theory education."
    )
    write_alignment_package(package, tmp_path)

    trace_lines = (tmp_path / "alignment_trace.jsonl").read_text(encoding="utf-8").splitlines()
    steps = [json.loads(line)["step"] for line in trace_lines]

    assert steps == [
        "load_problem_brief",
        "detect_alignment_profile",
        "build_alignment_package",
        "write_outputs",
    ]


def test_all_bundled_examples_generate_named_profiles(tmp_path):
    examples = {
        "hsg": "hsg",
        "chinese_painting": "chinese_painting",
        "political_education": "political_education",
    }

    for folder, expected_profile in examples.items():
        text = Path(f"examples/problem_bridge/{folder}/problem.md").read_text(encoding="utf-8")
        package = build_alignment_package(text)
        out = tmp_path / folder
        write_alignment_package(package, out)

        assert package.profile == expected_profile
        assert (out / "problem_card.md").is_file()
        assert (out / "implementation_routes.md").is_file()
