import csv
from pathlib import Path


DEMO_ROOT = Path("examples/lab_report_audit_demo")


def test_lab_report_audit_demo_files_exist():
    expected_paths = [
        DEMO_ROOT / "manuscript.md",
        DEMO_ROOT / "references.md",
        DEMO_ROOT / "tables" / "table1_metrics.csv",
        DEMO_ROOT / "tables" / "table2_ablation.csv",
    ]

    for path in expected_paths:
        assert path.exists(), f"Missing demo input: {path}"
        assert path.read_text(encoding="utf-8").strip()


def test_lab_report_audit_manuscript_has_required_sections_and_claims():
    text = (DEMO_ROOT / "manuscript.md").read_text(encoding="utf-8")
    required_headings = [
        "# Human-in-the-loop Evidence Review for Synthetic Lab Reports",
        "## Abstract",
        "## Introduction",
        "## Methods",
        "## Results",
        "## Discussion",
        "## Conclusion",
    ]
    claim_keywords = [
        "improves",
        "outperforms",
        "robust",
        "reliable",
        "deployment",
        "ready",
        "novel",
        "first",
        "supports",
        "enables",
        "reduces",
        "increases",
        "auditable",
        "explainable",
    ]

    for heading in required_headings:
        assert heading in text

    claim_like_sentences = [
        sentence
        for sentence in text.replace("\n", " ").split(".")
        if any(keyword in sentence.lower() for keyword in claim_keywords)
    ]
    assert 12 <= len(claim_like_sentences) <= 18
    assert "synthetic" in text.lower()
    assert "patient" not in text.lower()


def test_lab_report_audit_demo_metric_table_columns():
    path = DEMO_ROOT / "tables" / "table1_metrics.csv"
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        assert reader.fieldnames == ["model", "macro_f1", "precision", "recall", "notes"]
        rows = list(reader)

    assert len(rows) >= 3
    assert any(row["model"] == "evidence_guided_reviewer_v1" for row in rows)


def test_lab_report_audit_demo_ablation_table_columns():
    path = DEMO_ROOT / "tables" / "table2_ablation.csv"
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        assert reader.fieldnames == [
            "setting",
            "evidence_logging",
            "human_review_gate",
            "trace_replay",
            "success_rate",
            "notes",
        ]
        rows = list(reader)

    assert len(rows) >= 4
    assert any(row["human_review_gate"] == "enabled" for row in rows)
