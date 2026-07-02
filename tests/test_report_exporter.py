from pathlib import Path
from zipfile import ZipFile

from claim_harness.report_exporter import export_output_report


def test_export_output_report_writes_docx_and_pdf(tmp_path):
    out_dir = tmp_path / "alignment_run"
    out_dir.mkdir()
    (out_dir / "problem_card.md").write_text(
        "# Problem Card\n\n## Project\n\nHSG alignment demo\n", encoding="utf-8"
    )
    (out_dir / "workflow_map.md").write_text(
        "# Domain Workflow Map\n\n1. Review image quality\n2. Confirm uncertainty\n", encoding="utf-8"
    )
    (out_dir / "ai_task_spec.yaml").write_text(
        "project_name: HSG alignment demo\noutputs:\n- review checklist\n", encoding="utf-8"
    )
    (out_dir / "concept_alignment_table.csv").write_text(
        "domain_concept,ai_representation\nclinical readiness,deployment status\n", encoding="utf-8"
    )

    package = export_output_report(out_dir)

    assert package.docx_path == out_dir / "export_report.docx"
    assert package.pdf_path == out_dir / "export_report.pdf"
    assert package.docx_path.is_file()
    assert package.pdf_path.is_file()

    with ZipFile(package.docx_path) as docx:
        document_xml = docx.read("word/document.xml").decode("utf-8")

    assert "ProblemBridge / ClaimHarness Export Report" in document_xml
    assert "HSG alignment demo" in document_xml
    assert "clinical readiness" in document_xml

    pdf_bytes = package.pdf_path.read_bytes()
    assert pdf_bytes.startswith(b"%PDF-1.4")
    assert b"<feff" in pdf_bytes
    assert b"ProblemBridge / ClaimHarness Export Report" in pdf_bytes
    assert b"HSG alignment demo" in pdf_bytes
