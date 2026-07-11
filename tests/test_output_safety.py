import csv
from zipfile import ZipFile

from claim_harness.report_exporter import export_output_report
from claim_harness.report_generator import write_outputs
from claim_harness.schemas import Claim, VerificationResult


def test_claim_csv_escapes_formula_cells_but_json_keeps_original(tmp_path):
    claim = Claim(
        claim_id="C001",
        text="=HYPERLINK(\"https://example.test\", \"improves\")",
        source_section="+Results",
        source_line=1,
        claim_type="performance_claim",
        strength="strong",
        requires_evidence=["table"],
    )
    result = VerificationResult(
        claim_id="C001",
        status="unsupported",
        reason="No evidence.",
        risk_level="low",
        suggested_revision="Remove it.",
    )

    write_outputs(tmp_path, [claim], [], [result])

    with (tmp_path / "claim_table.csv").open(newline="", encoding="utf-8") as handle:
        row = next(csv.DictReader(handle))
    assert row["text"].startswith("'=")
    assert row["source_section"].startswith("'+")
    assert '=HYPERLINK' in (tmp_path / "evidence_map.json").read_text(encoding="utf-8")


def test_portable_export_does_not_embed_absolute_source_path(tmp_path):
    run = tmp_path / "private-user-project"
    run.mkdir()
    (run / "problem_card.md").write_text("# Project\n\nSafe summary.\n", encoding="utf-8")

    package = export_output_report(run)

    with ZipFile(package.docx_path) as document:
        document_xml = document.read("word/document.xml").decode("utf-8")
    pdf_text = package.pdf_path.read_bytes().decode("latin-1", errors="ignore")
    assert str(tmp_path) not in document_xml
    assert str(tmp_path) not in pdf_text
    assert "Source folder: private-user-project" in document_xml
