from pathlib import Path

import pandas as pd

from claim_harness.loader import load_manuscript, load_references, load_tables


def test_load_manuscript_parses_markdown_headings(tmp_path):
    manuscript = tmp_path / "manuscript.md"
    manuscript.write_text(
        "# Title\n\n"
        "Opening context.\n\n"
        "## Methods\n\n"
        "Method text.\n\n"
        "## Results\n\n"
        "Result text.\n",
        encoding="utf-8",
    )

    sections = load_manuscript(manuscript)

    assert [section.name for section in sections] == ["Title", "Methods", "Results"]
    assert sections[0].text == "Opening context."
    assert sections[0].start_line == 1
    assert sections[1].text == "Method text."
    assert sections[1].start_line == 5
    assert sections[2].text == "Result text."


def test_load_tables_reads_all_csv_files_by_stem(tmp_path):
    tables_dir = tmp_path / "tables"
    tables_dir.mkdir()
    (tables_dir / "metrics.csv").write_text("model,dice\nbaseline,0.81\n", encoding="utf-8")
    (tables_dir / "ablation.csv").write_text("setting,success_rate\nfull,0.86\n", encoding="utf-8")
    (tables_dir / "notes.txt").write_text("ignore me\n", encoding="utf-8")

    tables = load_tables(tables_dir)

    assert sorted(tables) == ["ablation", "metrics"]
    assert isinstance(tables["metrics"], pd.DataFrame)
    assert tables["metrics"].iloc[0]["model"] == "baseline"
    assert tables["ablation"].iloc[0]["success_rate"] == 0.86


def test_load_references_reads_text(tmp_path):
    references = tmp_path / "references.md"
    references.write_text("# References\n\n1. Synthetic reference.\n", encoding="utf-8")

    text = load_references(references)

    assert "Synthetic reference" in text
