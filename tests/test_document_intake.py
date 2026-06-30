import csv
import json
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

from problem_bridge.document_intake import (
    build_problem_seed_from_intake,
    extract_document,
    write_intake_package,
)


def test_extracts_docx_paragraphs_and_tables(tmp_path: Path):
    docx_path = tmp_path / "workflow.docx"
    _write_minimal_docx(
        docx_path,
        paragraphs=["Review image notes", "Confirm risk boundaries"],
        table_rows=[["step", "owner"], ["review", "clinician"]],
    )

    result = extract_document(docx_path)

    assert result.source_name == "workflow.docx"
    assert result.file_type == "docx"
    assert "Review image notes" in result.text
    assert "Confirm risk boundaries" in result.text
    assert result.tables[0].name == "workflow_table_1"
    assert result.tables[0].rows == [["step", "owner"], ["review", "clinician"]]
    assert result.warnings == []


def test_extracts_text_markdown_and_csv(tmp_path: Path):
    txt_path = tmp_path / "notes.txt"
    txt_path.write_text("Repeated work\nSlow review", encoding="utf-8")
    md_path = tmp_path / "brief.md"
    md_path.write_text("# Brief\nAI must not decide final approval.", encoding="utf-8")
    csv_path = tmp_path / "materials.csv"
    csv_path.write_text("item,risk\nimage,needs review\n", encoding="utf-8")

    txt_result = extract_document(txt_path)
    md_result = extract_document(md_path)
    csv_result = extract_document(csv_path)

    assert "Repeated work" in txt_result.text
    assert "# Brief" in md_result.text
    assert csv_result.tables[0].rows == [["item", "risk"], ["image", "needs review"]]
    assert "CSV table extracted" in csv_result.text


def test_unsupported_file_records_warning(tmp_path: Path):
    image_path = tmp_path / "diagram.png"
    image_path.write_bytes(b"not really an image")

    result = extract_document(image_path)

    assert result.text == ""
    assert result.tables == []
    assert result.warnings == ["Unsupported file type '.png'. No text was extracted."]


def test_write_intake_package_creates_auditable_outputs(tmp_path: Path):
    docx_path = tmp_path / "workflow.docx"
    _write_minimal_docx(docx_path, paragraphs=["A domain workflow"], table_rows=[["a", "b"]])
    result = extract_document(docx_path)

    out = tmp_path / "out"
    write_intake_package([result], out)

    assert (out / "extracted_text.md").is_file()
    assert (out / "extracted_tables" / "workflow_table_1.csv").is_file()
    assert (out / "source_manifest.json").is_file()
    assert (out / "extraction_warnings.md").is_file()

    manifest = json.loads((out / "source_manifest.json").read_text(encoding="utf-8"))
    assert manifest["sources"][0]["source_name"] == "workflow.docx"
    assert manifest["sources"][0]["file_type"] == "docx"
    assert manifest["sources"][0]["table_count"] == 1

    extracted_text = (out / "extracted_text.md").read_text(encoding="utf-8")
    assert "A domain workflow" in extracted_text


def test_build_problem_seed_from_intake_keeps_extraction_boundary(tmp_path: Path):
    txt_path = tmp_path / "notes.txt"
    txt_path.write_text("The team needs to understand a slow review workflow.", encoding="utf-8")
    result = extract_document(txt_path)

    seed = build_problem_seed_from_intake([result])

    assert "# Document Intake Problem Seed" in seed
    assert "The team needs to understand a slow review workflow." in seed
    assert "Document intake only extracts text and tables; it does not validate professional claims." in seed


def _write_minimal_docx(path: Path, paragraphs: list[str], table_rows: list[list[str]]) -> None:
    paragraph_xml = "".join(
        f"<w:p><w:r><w:t>{escape(paragraph)}</w:t></w:r></w:p>"
        for paragraph in paragraphs
    )
    table_xml = ""
    if table_rows:
        rows = []
        for row in table_rows:
            cells = "".join(
                f"<w:tc><w:p><w:r><w:t>{escape(cell)}</w:t></w:r></w:p></w:tc>"
                for cell in row
            )
            rows.append(f"<w:tr>{cells}</w:tr>")
        table_xml = f"<w:tbl>{''.join(rows)}</w:tbl>"

    document_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f"<w:body>{paragraph_xml}{table_xml}</w:body>"
        "</w:document>"
    )
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(
            "[Content_Types].xml",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="xml" ContentType="application/xml"/>'
            "</Types>",
        )
        archive.writestr("word/document.xml", document_xml)
