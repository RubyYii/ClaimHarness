from __future__ import annotations

import csv
import json
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
from xml.etree import ElementTree


WORD_NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
SUPPORTED_EXTENSIONS = {".docx", ".pdf", ".txt", ".md", ".csv"}


@dataclass(frozen=True)
class ExtractedTable:
    name: str
    rows: list[list[str]]


@dataclass(frozen=True)
class DocumentExtraction:
    source_name: str
    file_type: str
    text: str
    tables: list[ExtractedTable]
    warnings: list[str]


def extract_document(path: str | Path) -> DocumentExtraction:
    source = Path(path)
    suffix = source.suffix.lower()
    if suffix == ".docx":
        return _extract_docx(source)
    if suffix == ".pdf":
        return _extract_pdf(source)
    if suffix in {".txt", ".md"}:
        return DocumentExtraction(
            source_name=source.name,
            file_type=suffix.lstrip("."),
            text=source.read_text(encoding="utf-8"),
            tables=[],
            warnings=[],
        )
    if suffix == ".csv":
        return _extract_csv(source)

    return DocumentExtraction(
        source_name=source.name,
        file_type=suffix.lstrip(".") or "unknown",
        text="",
        tables=[],
        warnings=[f"Unsupported file type '{suffix}'. No text was extracted."],
    )


def write_intake_package(results: Iterable[DocumentExtraction], out: str | Path) -> None:
    output_dir = Path(out)
    output_dir.mkdir(parents=True, exist_ok=True)
    table_dir = output_dir / "extracted_tables"
    table_dir.mkdir(parents=True, exist_ok=True)

    result_list = list(results)
    (output_dir / "extracted_text.md").write_text(_combined_text(result_list), encoding="utf-8")
    _write_tables(result_list, table_dir)
    (output_dir / "source_manifest.json").write_text(
        json.dumps(_manifest(result_list), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (output_dir / "extraction_warnings.md").write_text(_warnings_markdown(result_list), encoding="utf-8")


def build_problem_seed_from_intake(results: Iterable[DocumentExtraction]) -> str:
    result_list = list(results)
    combined = _combined_text(result_list).strip()
    return _clean_markdown(
        f"""
        # Document Intake Problem Seed

        ## Extracted context
        {combined}

        ## Boundary
        Document intake only extracts text and tables; it does not validate professional claims.
        Use Question Discovery or ProblemBridge after a human checks whether the extracted context is complete.
        """
    )


def _extract_docx(path: Path) -> DocumentExtraction:
    warnings: list[str] = []
    try:
        with zipfile.ZipFile(path) as archive:
            xml_bytes = archive.read("word/document.xml")
    except (KeyError, zipfile.BadZipFile) as exc:
        return DocumentExtraction(
            source_name=path.name,
            file_type="docx",
            text="",
            tables=[],
            warnings=[f"DOCX text could not be extracted: {exc}"],
        )

    root = ElementTree.fromstring(xml_bytes)
    paragraphs = [_paragraph_text(paragraph) for paragraph in root.findall(".//w:p", WORD_NS)]
    text = "\n".join(paragraph for paragraph in paragraphs if paragraph)
    tables = _docx_tables(path.stem, root)
    return DocumentExtraction(
        source_name=path.name,
        file_type="docx",
        text=text,
        tables=tables,
        warnings=warnings,
    )


def _docx_tables(stem: str, root: ElementTree.Element) -> list[ExtractedTable]:
    tables: list[ExtractedTable] = []
    for table_index, table in enumerate(root.findall(".//w:tbl", WORD_NS), start=1):
        rows: list[list[str]] = []
        for row in table.findall(".//w:tr", WORD_NS):
            cells = [_paragraph_text(cell) for cell in row.findall("./w:tc", WORD_NS)]
            rows.append(cells)
        if rows:
            tables.append(ExtractedTable(name=f"{stem}_table_{table_index}", rows=rows))
    return tables


def _paragraph_text(element: ElementTree.Element) -> str:
    texts = [node.text or "" for node in element.findall(".//w:t", WORD_NS)]
    return "".join(texts).strip()


def _extract_pdf(path: Path) -> DocumentExtraction:
    try:
        from pypdf import PdfReader  # type: ignore[import-not-found]
    except ImportError:
        return DocumentExtraction(
            source_name=path.name,
            file_type="pdf",
            text="",
            tables=[],
            warnings=[
                "PDF text extraction requires pypdf. Text-based PDF support is available after installing project dependencies."
            ],
        )

    try:
        reader = PdfReader(str(path))
        pages = [page.extract_text() or "" for page in reader.pages]
    except Exception as exc:  # pragma: no cover - parser-specific failures vary
        return DocumentExtraction(
            source_name=path.name,
            file_type="pdf",
            text="",
            tables=[],
            warnings=[f"PDF text could not be extracted: {exc}"],
        )

    text = "\n\n".join(page.strip() for page in pages if page.strip())
    warnings = []
    if not text:
        warnings.append("No text was extracted. Scanned PDFs and image-only PDFs require OCR, which is not supported.")
    return DocumentExtraction(
        source_name=path.name,
        file_type="pdf",
        text=text,
        tables=[],
        warnings=warnings,
    )


def _extract_csv(path: Path) -> DocumentExtraction:
    with path.open(newline="", encoding="utf-8") as handle:
        rows = [row for row in csv.reader(handle)]
    table = ExtractedTable(name=path.stem, rows=rows)
    return DocumentExtraction(
        source_name=path.name,
        file_type="csv",
        text=f"CSV table extracted from {path.name}.",
        tables=[table],
        warnings=[],
    )


def _combined_text(results: list[DocumentExtraction]) -> str:
    sections = []
    for result in results:
        sections.append(f"# Source: {result.source_name}")
        if result.text.strip():
            sections.append(result.text.strip())
        else:
            sections.append("_No text extracted._")
        sections.append("")
    return "\n\n".join(sections).rstrip() + "\n"


def _write_tables(results: list[DocumentExtraction], table_dir: Path) -> None:
    for result in results:
        for table in result.tables:
            with (table_dir / f"{table.name}.csv").open("w", newline="", encoding="utf-8") as handle:
                writer = csv.writer(handle)
                writer.writerows(table.rows)


def _manifest(results: list[DocumentExtraction]) -> dict[str, object]:
    return {
        "sources": [
            {
                "source_name": result.source_name,
                "file_type": result.file_type,
                "text_length": len(result.text),
                "table_count": len(result.tables),
                "warnings": result.warnings,
            }
            for result in results
        ],
        "supported_extensions": sorted(SUPPORTED_EXTENSIONS),
        "boundaries": [
            "Text-based PDFs only; scanned PDFs and image-only PDFs require OCR and are not supported.",
            "Image understanding and professional judgement are not performed by document intake.",
            "Human review is required before using extracted content for problem alignment or evidence audit.",
        ],
    }


def _warnings_markdown(results: list[DocumentExtraction]) -> str:
    lines = ["# Extraction Warnings", ""]
    warnings_found = False
    for result in results:
        for warning in result.warnings:
            warnings_found = True
            lines.append(f"- {result.source_name}: {warning}")
    if not warnings_found:
        lines.append("- No extraction warnings.")
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            "- Text-based PDFs only; scanned PDFs and image-only PDFs require OCR and are not supported.",
            "- No image understanding, figure interpretation, clinical judgement, or education-policy authority is performed.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def _clean_markdown(text: str) -> str:
    lines = [line.strip() for line in text.strip().splitlines()]
    return "\n".join(lines).strip() + "\n"
