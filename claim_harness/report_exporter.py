import csv
import html
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


REPORT_TITLE = "ProblemBridge / ClaimHarness Export Report"
DEFAULT_DOCX_NAME = "export_report.docx"
DEFAULT_PDF_NAME = "export_report.pdf"
MAX_FILE_CHARS = 18000

SUPPORTED_REPORT_FILES = [
    "problem_card.md",
    "question_brief.md",
    "extracted_text.md",
    "workflow_map.md",
    "painpoint_opportunity_matrix.csv",
    "concept_alignment_table.csv",
    "ai_task_spec.yaml",
    "evidence_contract.yaml",
    "evaluation_protocol.md",
    "misalignment_risk_report.md",
    "human_in_loop_plan.md",
    "implementation_routes.md",
    "audit_report.md",
    "revision_suggestions.md",
    "claim_table.csv",
    "project_record.json",
    "run_manifest.json",
    "source_manifest.json",
    "evidence_map.json",
    "project_summary_log.md",
    "revision_history.jsonl",
    "alignment_trace.jsonl",
    "agent_trace.jsonl",
    "extraction_warnings.md",
    "problem_seed.md",
    "problem.md",
]


@dataclass(frozen=True)
class ExportPackage:
    docx_path: Path
    pdf_path: Path


@dataclass(frozen=True)
class ReportSection:
    title: str
    source_file: str
    body: str


def export_output_report(output_dir: Path | str) -> ExportPackage:
    """Export a local output directory to lightweight DOCX and PDF reports."""
    run_dir = Path(output_dir)
    if not run_dir.is_dir():
        raise FileNotFoundError(f"Output directory does not exist: {run_dir}")

    sections = collect_report_sections(run_dir)
    if not sections:
        sections = [
            ReportSection(
                title="No supported report files found",
                source_file=str(run_dir),
                body="The selected folder did not contain recognized Markdown, CSV, YAML, JSON, or trace output files.",
            )
        ]

    docx_path = run_dir / DEFAULT_DOCX_NAME
    pdf_path = run_dir / DEFAULT_PDF_NAME
    write_docx_report(docx_path, run_dir, sections)
    write_pdf_report(pdf_path, run_dir, sections)
    return ExportPackage(docx_path=docx_path, pdf_path=pdf_path)


def collect_report_sections(run_dir: Path) -> list[ReportSection]:
    sections = []
    for filename in SUPPORTED_REPORT_FILES:
        path = run_dir / filename
        if path.is_file():
            sections.append(ReportSection(title=_title_for(filename), source_file=filename, body=_read_report_file(path)))

    extracted_tables = run_dir / "extracted_tables"
    if extracted_tables.is_dir():
        for table_path in sorted(extracted_tables.glob("*.csv")):
            sections.append(
                ReportSection(
                    title=f"Extracted Table: {table_path.name}",
                    source_file=str(table_path.relative_to(run_dir)),
                    body=_read_csv(table_path),
                )
            )
    return sections


def write_docx_report(path: Path, run_dir: Path, sections: list[ReportSection]) -> None:
    document_xml = _docx_document(run_dir, sections)
    styles_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:style w:type="paragraph" w:default="1" w:styleId="Normal">
    <w:name w:val="Normal"/>
    <w:rPr><w:sz w:val="22"/></w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Title">
    <w:name w:val="Title"/>
    <w:rPr><w:b/><w:sz w:val="34"/></w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Heading1">
    <w:name w:val="heading 1"/>
    <w:rPr><w:b/><w:sz w:val="28"/></w:rPr>
  </w:style>
</w:styles>
"""
    content_types = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
  <Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
</Types>
"""
    package_rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>
"""
    document_rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"/>
"""

    with ZipFile(path, "w", compression=ZIP_DEFLATED) as docx:
        docx.writestr("[Content_Types].xml", content_types)
        docx.writestr("_rels/.rels", package_rels)
        docx.writestr("word/document.xml", document_xml)
        docx.writestr("word/styles.xml", styles_xml)
        docx.writestr("word/_rels/document.xml.rels", document_rels)


def write_pdf_report(path: Path, run_dir: Path, sections: list[ReportSection]) -> None:
    lines = _report_lines(run_dir, sections)
    pages = _paginate(lines, lines_per_page=48)
    objects: list[bytes] = []

    objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    page_refs = " ".join(f"{3 + index * 2} 0 R" for index in range(len(pages)))
    objects.append(f"<< /Type /Pages /Kids [{page_refs}] /Count {len(pages)} >>".encode("ascii"))

    content_object_numbers = []
    for index, page_lines in enumerate(pages):
        page_object_number = 3 + index * 2
        content_object_number = page_object_number + 1
        content_object_numbers.append(content_object_number)
        objects.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 5 0 R >> >> /Contents {content_object_number} 0 R >>".encode(
                "ascii"
            )
        )
        stream = _pdf_text_stream(page_lines)
        objects.append(b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" + stream + b"\nendstream")

    font_object_number = 5
    if content_object_numbers:
        font_object_number = max(content_object_numbers) + 1
    objects.append(
        b"<< /Type /Font /Subtype /Type0 /BaseFont /STSong-Light /Encoding /UniGB-UCS2-H "
        b"/DescendantFonts [<< /Type /Font /Subtype /CIDFontType0 /BaseFont /STSong-Light "
        b"/CIDSystemInfo << /Registry (Adobe) /Ordering (GB1) /Supplement 2 >> "
        b"/FontDescriptor << /Type /FontDescriptor /FontName /STSong-Light /Flags 6 "
        b"/FontBBox [0 -200 1000 900] /ItalicAngle 0 /Ascent 880 /Descent -120 /CapHeight 700 /StemV 80 >> >>] >>"
    )

    # Rebuild page resources if the font object was not object 5.
    if font_object_number != 5:
        for index in range(len(pages)):
            page_index = 2 + index * 2
            content_object_number = 4 + index * 2
            objects[page_index] = (
                f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 {font_object_number} 0 R >> >> "
                f"/Contents {content_object_number} 0 R >>"
            ).encode("ascii")

    comments = "\n".join(f"% {_ascii_comment(line)}" for line in lines[:80])
    pdf = bytearray(b"%PDF-1.4\n")
    if comments:
        pdf.extend(comments.encode("ascii", errors="ignore") + b"\n")

    offsets = [0]
    for object_number, body in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf.extend(f"{object_number} 0 obj\n".encode("ascii"))
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


def _docx_document(run_dir: Path, sections: list[ReportSection]) -> str:
    paragraphs = [
        _docx_paragraph(REPORT_TITLE, "Title"),
        _docx_paragraph(f"Source folder: {run_dir.name}"),
        _docx_paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"),
        _docx_paragraph("Review before sharing. This export may contain user-provided sensitive material."),
    ]
    for section in sections:
        paragraphs.append(_docx_paragraph(section.title, "Heading1"))
        paragraphs.append(_docx_paragraph(f"Source file: {section.source_file}"))
        for line in section.body.splitlines() or [""]:
            paragraphs.append(_docx_paragraph(line))

    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    {''.join(paragraphs)}
    <w:sectPr><w:pgSz w:w="12240" w:h="15840"/><w:pgMar w:top="1080" w:right="1080" w:bottom="1080" w:left="1080"/></w:sectPr>
  </w:body>
</w:document>
"""


def _docx_paragraph(text: str, style: str | None = None) -> str:
    style_xml = f'<w:pPr><w:pStyle w:val="{style}"/></w:pPr>' if style else ""
    escaped = html.escape(text, quote=False)
    preserve = ' xml:space="preserve"' if text.startswith(" ") or text.endswith(" ") else ""
    return f"<w:p>{style_xml}<w:r><w:t{preserve}>{escaped}</w:t></w:r></w:p>"


def _report_lines(run_dir: Path, sections: list[ReportSection]) -> list[str]:
    lines = [
        REPORT_TITLE,
        f"Source folder: {run_dir.name}",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "Review before sharing. This export may contain user-provided sensitive material.",
        "",
    ]
    for section in sections:
        lines.extend([section.title, f"Source file: {section.source_file}"])
        lines.extend(section.body.splitlines())
        lines.append("")
    return lines


def _read_report_file(path: Path) -> str:
    if path.suffix == ".csv":
        return _read_csv(path)
    if path.suffix == ".json":
        return _read_json(path)
    text = path.read_text(encoding="utf-8", errors="replace")
    return _truncate(text)


def _read_csv(path: Path) -> str:
    with path.open(newline="", encoding="utf-8", errors="replace") as handle:
        rows = list(csv.reader(handle))
    lines = [" | ".join(cell.strip() for cell in row) for row in rows[:60]]
    if len(rows) > 60:
        lines.append(f"... truncated after 60 rows from {len(rows)} total rows")
    return _truncate("\n".join(lines))


def _read_json(path: Path) -> str:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return _truncate(path.read_text(encoding="utf-8", errors="replace"))
    return _truncate(json.dumps(data, ensure_ascii=False, indent=2))


def _truncate(text: str) -> str:
    if len(text) <= MAX_FILE_CHARS:
        return text
    return text[:MAX_FILE_CHARS].rstrip() + "\n... truncated for export"


def _title_for(filename: str) -> str:
    return filename.replace("_", " ").replace(".md", "").replace(".yaml", "").replace(".csv", "").replace(".jsonl", "").replace(".json", "").title()


def _paginate(lines: list[str], lines_per_page: int) -> list[list[str]]:
    wrapped = []
    for line in lines:
        wrapped.extend(_wrap_line(line, 88) or [""])
    pages = [wrapped[index : index + lines_per_page] for index in range(0, len(wrapped), lines_per_page)]
    return pages or [[""]]


def _wrap_line(line: str, width: int) -> list[str]:
    if len(line) <= width:
        return [line]
    pieces = []
    current = line
    while len(current) > width:
        split_at = current.rfind(" ", 0, width)
        if split_at < width // 2:
            split_at = width
        pieces.append(current[:split_at].rstrip())
        current = current[split_at:].lstrip()
    if current:
        pieces.append(current)
    return pieces


def _pdf_text_stream(lines: list[str]) -> bytes:
    commands = ["BT", "/F1 10 Tf", "14 TL", "50 790 Td"]
    for index, line in enumerate(lines):
        if index:
            commands.append("T*")
        commands.append(f"<{_utf16_hex(line)}> Tj")
    commands.append("ET")
    return "\n".join(commands).encode("ascii")


def _utf16_hex(text: str) -> str:
    return (b"\xfe\xff" + text.encode("utf-16-be")).hex()


def _ascii_comment(text: str) -> str:
    return "".join(char if 32 <= ord(char) < 127 else " " for char in text).strip()
