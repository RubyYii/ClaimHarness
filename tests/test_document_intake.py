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


def test_legacy_doc_upload_records_conversion_guidance(tmp_path: Path):
    doc_path = tmp_path / "meeting-notes.doc"
    doc_path.write_bytes(b"legacy binary word content")

    result = extract_document(doc_path)

    assert result.source_name == "meeting-notes.doc"
    assert result.file_type == "doc"
    assert result.text == ""
    assert result.tables == []
    assert result.warnings == [
        "Legacy .doc files cannot be parsed locally. Save or export the file as .docx, .txt, or PDF, then upload it again."
    ]


def test_pdf_text_fallback_extracts_simple_text_without_pypdf(tmp_path: Path):
    pdf_path = tmp_path / "brief.pdf"
    _write_simple_text_pdf(pdf_path, "Workflow review needs evidence boundaries.")

    result = extract_document(pdf_path)

    assert result.source_name == "brief.pdf"
    assert result.file_type == "pdf"
    assert "Workflow review needs evidence boundaries." in result.text
    assert result.warnings == []


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


def _write_simple_text_pdf(path: Path, text: str) -> None:
    stream = f"BT\n/F1 12 Tf\n72 720 Td\n({text}) Tj\nET".encode("ascii")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" + stream + b"\nendstream",
    ]
    pdf = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, body in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf.extend(f"{index} 0 obj\n".encode("ascii"))
        pdf.extend(body)
        pdf.extend(b"\nendobj\n")
    xref_start = len(pdf)
    pdf.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    pdf.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        pdf.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    pdf.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_start}\n%%EOF\n".encode("ascii")
    )
    path.write_bytes(bytes(pdf))
