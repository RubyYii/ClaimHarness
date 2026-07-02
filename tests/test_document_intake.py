import csv
import json
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

from problem_bridge.document_intake import (
    build_problem_seed_from_intake,
    extract_document,
    extract_url,
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


def test_extracts_docx_comments_highlights_and_font_colors(tmp_path: Path):
    docx_path = tmp_path / "annotated.docx"
    _write_annotated_docx(docx_path)

    result = extract_document(docx_path)

    assert result.source_name == "annotated.docx"
    assert "uncertain boundary" in result.text
    assert [
        (annotation.kind, annotation.text, annotation.color, annotation.comment_text)
        for annotation in result.annotations
    ] == [
        ("comment", "uncertain boundary", "", "Ask domain expert whether this is a risk."),
        ("highlight", "high priority", "yellow", ""),
        ("font_color", "risk wording", "FF0000", ""),
    ]


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


def test_extracts_gb18030_chinese_text_and_csv(tmp_path: Path):
    txt_path = tmp_path / "中文记录.txt"
    txt_path.write_bytes("重复工作\n人工复核边界".encode("gb18030"))
    csv_path = tmp_path / "材料表.csv"
    csv_path.write_bytes("项目,风险\n报告,需要复核\n".encode("gb18030"))

    txt_result = extract_document(txt_path)
    csv_result = extract_document(csv_path)

    assert "重复工作" in txt_result.text
    assert "人工复核边界" in txt_result.text
    assert csv_result.tables[0].rows == [["项目", "风险"], ["报告", "需要复核"]]


def test_unsupported_non_image_file_records_warning(tmp_path: Path):
    image_path = tmp_path / "diagram.xyz"
    image_path.write_bytes(b"not really a supported file")

    result = extract_document(image_path)

    assert result.text == ""
    assert result.tables == []
    assert result.warnings == ["Unsupported file type '.xyz'. No text was extracted."]


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


def test_extracts_pdf_highlight_annotations(tmp_path: Path):
    pdf_path = tmp_path / "annotated.pdf"
    _write_simple_annotated_pdf(pdf_path, "Workflow review needs evidence boundaries.", "Ask expert about this boundary.")

    result = extract_document(pdf_path)

    assert result.source_name == "annotated.pdf"
    assert "Workflow review needs evidence boundaries." in result.text
    assert len(result.annotations) == 1
    assert result.annotations[0].kind == "highlight"
    assert result.annotations[0].comment_text == "Ask expert about this boundary."
    assert result.annotations[0].color == "1 1 0"
    assert "page 1" in result.annotations[0].context


def test_extracts_html_title_text_links_and_tables(tmp_path: Path):
    html_path = tmp_path / "workflow.html"
    html_path.write_text(
        """
        <!doctype html>
        <html>
          <head><title>Workflow Guide</title><style>.hidden{display:none}</style></head>
          <body>
            <nav>Menu text should not dominate extraction</nav>
            <h1>Review workflow</h1>
            <p>Teams inspect repeated work before deciding what to ask.</p>
            <ul><li>Find the expert reviewer</li></ul>
            <a href="/guide">Expert guide</a>
            <table>
              <tr><th>step</th><th>owner</th></tr>
              <tr><td>review</td><td>domain expert</td></tr>
            </table>
            <script>window.secret = "skip me";</script>
          </body>
        </html>
        """,
        encoding="utf-8",
    )

    result = extract_document(html_path)

    assert result.file_type == "html"
    assert "Title: Workflow Guide" in result.text
    assert "Review workflow" in result.text
    assert "Teams inspect repeated work" in result.text
    assert "Find the expert reviewer" in result.text
    assert "skip me" not in result.text
    assert result.tables[0].name == "workflow_links"
    assert result.tables[0].rows == [["text", "url"], ["Expert guide", "/guide"]]
    assert result.tables[1].name == "workflow_table_1"
    assert result.tables[1].rows == [["step", "owner"], ["review", "domain expert"]]


def test_extract_url_parses_static_html_with_injected_fetcher():
    def fetcher(url: str) -> bytes:
        assert url == "https://example.org/workflow"
        return b"<html><head><title>Remote Guide</title></head><body><h1>Remote workflow</h1><p>Ask who owns the judgement.</p></body></html>"

    result = extract_url("https://example.org/workflow", fetcher=fetcher)

    assert result.source_name == "example.org_workflow"
    assert result.file_type == "url"
    assert result.source_url == "https://example.org/workflow"
    assert "Title: Remote Guide" in result.text
    assert "Remote workflow" in result.text
    assert result.warnings == []


def test_extract_url_rejects_non_http_urls():
    result = extract_url("file:///private/report.html")

    assert result.file_type == "url"
    assert result.text == ""
    assert result.warnings == ["URL intake only supports public http(s) URLs."]


def test_optional_ocr_engine_extracts_image_text(tmp_path: Path):
    image_path = tmp_path / "scan.png"
    image_path.write_bytes(b"not a real image; fake OCR engine handles it")

    result = extract_document(image_path, enable_ocr=True, ocr_engine=lambda path: "OCR workflow text")

    assert result.source_name == "scan.png"
    assert result.file_type == "png"
    assert result.text == "OCR workflow text"
    assert result.warnings == []


def test_image_without_ocr_records_guidance(tmp_path: Path):
    image_path = tmp_path / "scan.jpg"
    image_path.write_bytes(b"not a real image")

    result = extract_document(image_path)

    assert result.text == ""
    assert result.tables == []
    assert result.warnings == [
        "Image files require optional OCR. Enable OCR and install local OCR dependencies to extract text."
    ]


def test_optional_ocr_engine_extracts_image_only_pdf_text(tmp_path: Path):
    pdf_path = tmp_path / "scan.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n%%EOF\n")

    result = extract_document(pdf_path, enable_ocr=True, ocr_engine=lambda path: "OCR PDF workflow text")

    assert result.source_name == "scan.pdf"
    assert result.file_type == "pdf"
    assert result.text == "OCR PDF workflow text"
    assert result.warnings == ["PDF text extraction returned no text; optional OCR was used."]


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
    assert (out / "annotation_map.json").is_file()
    assert (out / "highlighted_spans.csv").is_file()
    assert (out / "comment_threads.md").is_file()
    assert (out / "priority_marks.md").is_file()

    manifest = json.loads((out / "source_manifest.json").read_text(encoding="utf-8"))
    assert manifest["sources"][0]["source_name"] == "workflow.docx"
    assert manifest["sources"][0]["file_type"] == "docx"
    assert manifest["sources"][0]["table_count"] == 1
    assert manifest["sources"][0]["annotation_count"] == 0

    extracted_text = (out / "extracted_text.md").read_text(encoding="utf-8")
    assert "A domain workflow" in extracted_text


def test_write_intake_package_exports_annotation_files(tmp_path: Path):
    docx_path = tmp_path / "annotated.docx"
    _write_annotated_docx(docx_path)
    result = extract_document(docx_path)

    out = tmp_path / "out"
    write_intake_package([result], out)

    annotation_map = json.loads((out / "annotation_map.json").read_text(encoding="utf-8"))
    assert annotation_map["annotations"][0]["kind"] == "comment"
    assert annotation_map["annotations"][0]["comment_text"] == "Ask domain expert whether this is a risk."

    with (out / "highlighted_spans.csv").open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert rows[0]["kind"] == "highlight"
    assert rows[0]["text"] == "high priority"
    assert rows[1]["kind"] == "font_color"
    assert rows[1]["color"] == "FF0000"

    comments = (out / "comment_threads.md").read_text(encoding="utf-8")
    assert "Ask domain expert whether this is a risk." in comments

    priority = (out / "priority_marks.md").read_text(encoding="utf-8")
    assert "high priority" in priority
    assert "risk wording" in priority


def test_build_problem_seed_from_intake_keeps_extraction_boundary(tmp_path: Path):
    txt_path = tmp_path / "notes.txt"
    txt_path.write_text("The team needs to understand a slow review workflow.", encoding="utf-8")
    result = extract_document(txt_path)

    seed = build_problem_seed_from_intake([result])

    assert "# Document Intake Problem Seed" in seed
    assert "The team needs to understand a slow review workflow." in seed
    assert "Document intake only extracts text and tables; it does not validate professional claims." in seed


def test_build_problem_seed_from_intake_includes_annotation_signals(tmp_path: Path):
    docx_path = tmp_path / "annotated.docx"
    _write_annotated_docx(docx_path)
    result = extract_document(docx_path)

    seed = build_problem_seed_from_intake([result])

    assert "## Extracted annotation signals" in seed
    assert "comment: uncertain boundary" in seed
    assert "Ask domain expert whether this is a risk." in seed
    assert "highlight:yellow" in seed
    assert "font_color:FF0000" in seed


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


def _write_annotated_docx(path: Path) -> None:
    document_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        "<w:body><w:p>"
        "<w:r><w:t>Review </w:t></w:r>"
        '<w:commentRangeStart w:id="0"/>'
        "<w:r><w:t>uncertain boundary</w:t></w:r>"
        '<w:commentRangeEnd w:id="0"/>'
        '<w:r><w:commentReference w:id="0"/></w:r>'
        '<w:r><w:rPr><w:highlight w:val="yellow"/></w:rPr><w:t>high priority</w:t></w:r>'
        '<w:r><w:rPr><w:color w:val="FF0000"/></w:rPr><w:t>risk wording</w:t></w:r>'
        "</w:p></w:body></w:document>"
    )
    comments_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:comments xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        '<w:comment w:id="0" w:author="Reviewer">'
        "<w:p><w:r><w:t>Ask domain expert whether this is a risk.</w:t></w:r></w:p>"
        "</w:comment>"
        "</w:comments>"
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
        archive.writestr("word/comments.xml", comments_xml)


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


def _write_simple_annotated_pdf(path: Path, text: str, annotation: str) -> None:
    _write_simple_text_pdf(path, text)
    path.write_bytes(
        path.read_bytes()
        + f"\n6 0 obj\n<< /Subtype /Highlight /Contents ({annotation}) /C [1 1 0] >>\nendobj\n".encode("ascii")
    )
