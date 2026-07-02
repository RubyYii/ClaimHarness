from __future__ import annotations

import csv
import html
import io
import json
import re
import urllib.parse
import urllib.request
import zlib
import zipfile
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from typing import Callable, Iterable
from xml.etree import ElementTree


WORD_NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp"}
SUPPORTED_EXTENSIONS = {".doc", ".docx", ".pdf", ".txt", ".md", ".csv", ".html", ".htm"} | IMAGE_EXTENSIONS
TEXT_ENCODINGS = ("utf-8-sig", "utf-8", "gb18030", "gbk", "big5")
OcrEngine = Callable[[Path], str]


@dataclass(frozen=True)
class ExtractedTable:
    name: str
    rows: list[list[str]]


@dataclass(frozen=True)
class AnnotationMark:
    source_name: str
    kind: str
    text: str
    color: str = ""
    comment_text: str = ""
    author: str = ""
    context: str = ""
    page_number: int | None = None


@dataclass(frozen=True)
class DocumentExtraction:
    source_name: str
    file_type: str
    text: str
    tables: list[ExtractedTable]
    warnings: list[str]
    annotations: list[AnnotationMark] = field(default_factory=list)
    source_url: str = ""


def extract_document(path: str | Path, *, enable_ocr: bool = False, ocr_engine: OcrEngine | None = None) -> DocumentExtraction:
    source = Path(path)
    suffix = source.suffix.lower()
    if suffix == ".doc":
        return _extract_legacy_doc(source)
    if suffix == ".docx":
        return _extract_docx(source)
    if suffix == ".pdf":
        return _extract_pdf(source, enable_ocr=enable_ocr, ocr_engine=ocr_engine)
    if suffix in {".html", ".htm"}:
        return _extract_html(source)
    if suffix in IMAGE_EXTENSIONS:
        return _extract_image(source, enable_ocr=enable_ocr, ocr_engine=ocr_engine)
    if suffix in {".txt", ".md"}:
        return DocumentExtraction(
            source_name=source.name,
            file_type=suffix.lstrip("."),
            text=_read_text_with_fallback(source),
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


def extract_url(url: str, *, fetcher: Callable[[str], bytes] | None = None) -> DocumentExtraction:
    normalized_url = url.strip()
    parsed = urllib.parse.urlparse(normalized_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return DocumentExtraction(
            source_name=normalized_url or "invalid-url",
            file_type="url",
            text="",
            tables=[],
            warnings=["URL intake only supports public http(s) URLs."],
            source_url=normalized_url,
        )

    try:
        raw = fetcher(normalized_url) if fetcher is not None else _fetch_url(normalized_url)
    except Exception as exc:
        return DocumentExtraction(
            source_name=_url_source_name(normalized_url),
            file_type="url",
            text="",
            tables=[],
            warnings=[f"URL could not be fetched: {exc}"],
            source_url=normalized_url,
        )

    if isinstance(raw, str):
        raw = raw.encode("utf-8")
    return _extract_html_bytes(
        source_name=_url_source_name(normalized_url),
        file_type="url",
        stem=_url_source_name(normalized_url),
        raw=raw,
        source_url=normalized_url,
    )


def write_intake_package(results: Iterable[DocumentExtraction], out: str | Path) -> None:
    output_dir = Path(out)
    output_dir.mkdir(parents=True, exist_ok=True)
    table_dir = output_dir / "extracted_tables"
    table_dir.mkdir(parents=True, exist_ok=True)

    result_list = list(results)
    (output_dir / "extracted_text.md").write_text(_combined_text(result_list), encoding="utf-8")
    _write_tables(result_list, table_dir)
    _write_annotations(result_list, output_dir)
    (output_dir / "source_manifest.json").write_text(
        json.dumps(_manifest(result_list), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (output_dir / "extraction_warnings.md").write_text(_warnings_markdown(result_list), encoding="utf-8")


def build_problem_seed_from_intake(results: Iterable[DocumentExtraction]) -> str:
    result_list = list(results)
    combined = _combined_text(result_list).strip()
    annotations = _combined_annotations(result_list).strip()
    return _clean_markdown(
        f"""
        # Document Intake Problem Seed

        ## Extracted context
        {combined}

        ## Extracted annotation signals
        {annotations}

        ## Boundary
        Document intake only extracts text and tables; it does not validate professional claims.
        Word comments, highlights, and font colors are preserved as user attention signals, not interpreted as final risk labels.
        Use Question Discovery or ProblemBridge after a human checks whether the extracted context is complete.
        """
    )


def _extract_legacy_doc(path: Path) -> DocumentExtraction:
    return DocumentExtraction(
        source_name=path.name,
        file_type="doc",
        text="",
        tables=[],
        warnings=[
            "Legacy .doc files cannot be parsed locally. Save or export the file as .docx, .txt, or PDF, then upload it again."
        ],
    )


def _fetch_url(url: str) -> bytes:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "ProblemBridge-DocumentIntake/0.3"},
    )
    with urllib.request.urlopen(request, timeout=10) as response:  # nosec B310 - public user-provided HTTP(S) intake.
        return response.read(2_000_000)


def _url_source_name(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    path = parsed.path.strip("/").replace("/", "_") or "index"
    raw_name = f"{parsed.netloc}_{path}"
    return re.sub(r"[^A-Za-z0-9._-]+", "_", raw_name).strip("_") or "webpage"


def _extract_html(path: Path) -> DocumentExtraction:
    return _extract_html_bytes(
        source_name=path.name,
        file_type="html",
        stem=path.stem,
        raw=path.read_bytes(),
    )


def _extract_html_bytes(source_name: str, file_type: str, stem: str, raw: bytes, source_url: str = "") -> DocumentExtraction:
    parser = _HTMLIntakeParser()
    text = _decode_text_with_fallback(raw)
    try:
        parser.feed(text)
        parser.close()
    except Exception as exc:
        return DocumentExtraction(
            source_name=source_name,
            file_type=file_type,
            text=_normalize_space(_strip_html_tags(text)),
            tables=[],
            warnings=[f"HTML was malformed; fallback text extraction was used: {exc}"],
            source_url=source_url,
        )

    tables: list[ExtractedTable] = []
    if parser.links:
        tables.append(ExtractedTable(name=f"{stem}_links", rows=[["text", "url"], *parser.links]))
    for index, rows in enumerate(parser.tables, start=1):
        if rows:
            tables.append(ExtractedTable(name=f"{stem}_table_{index}", rows=rows))

    return DocumentExtraction(
        source_name=source_name,
        file_type=file_type,
        text=parser.to_text(),
        tables=tables,
        warnings=[],
        source_url=source_url,
    )


class _HTMLIntakeParser(HTMLParser):
    SKIP_TAGS = {"script", "style", "noscript", "svg", "nav", "footer", "header"}
    BLOCK_TAGS = {"h1", "h2", "h3", "h4", "h5", "h6", "p", "li"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title = ""
        self.blocks: list[str] = []
        self.links: list[list[str]] = []
        self.tables: list[list[list[str]]] = []
        self._skip_depth = 0
        self._capture_tag = ""
        self._capture_parts: list[str] = []
        self._link_href = ""
        self._table_rows: list[list[str]] | None = None
        self._current_row: list[str] | None = None
        self._cell_parts: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag in self.SKIP_TAGS:
            self._skip_depth += 1
            return
        if self._skip_depth:
            return
        attrs_dict = {name.lower(): value or "" for name, value in attrs}
        if tag == "title":
            self._start_capture(tag)
        elif tag in self.BLOCK_TAGS:
            self._start_capture(tag)
        elif tag == "a":
            self._link_href = attrs_dict.get("href", "")
            self._start_capture(tag)
        elif tag == "table":
            self._table_rows = []
        elif tag == "tr" and self._table_rows is not None:
            self._current_row = []
        elif tag in {"td", "th"} and self._current_row is not None:
            self._cell_parts = []

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in self.SKIP_TAGS and self._skip_depth:
            self._skip_depth -= 1
            return
        if self._skip_depth:
            return
        if tag in {"td", "th"} and self._cell_parts is not None and self._current_row is not None:
            self._current_row.append(_normalize_space(" ".join(self._cell_parts)))
            self._cell_parts = None
            return
        if tag == "tr" and self._current_row is not None and self._table_rows is not None:
            if any(cell for cell in self._current_row):
                self._table_rows.append(self._current_row)
            self._current_row = None
            return
        if tag == "table" and self._table_rows is not None:
            if self._table_rows:
                self.tables.append(self._table_rows)
            self._table_rows = None
            return
        if tag == self._capture_tag:
            text = _normalize_space(" ".join(self._capture_parts))
            if tag == "title":
                self.title = text
            elif tag == "a":
                if text or self._link_href:
                    self.links.append([text, self._link_href])
                self._link_href = ""
            elif text:
                self.blocks.append(text)
            self._capture_tag = ""
            self._capture_parts = []

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        if self._cell_parts is not None:
            self._cell_parts.append(data)
            return
        if self._capture_tag:
            self._capture_parts.append(data)

    def _start_capture(self, tag: str) -> None:
        self._capture_tag = tag
        self._capture_parts = []

    def to_text(self) -> str:
        lines: list[str] = []
        if self.title:
            lines.append(f"Title: {self.title}")
        lines.extend(block for block in self.blocks if block)
        if self.links:
            lines.append("Links:")
            lines.extend(f"- {text}: {url}" for text, url in self.links)
        return "\n".join(lines).strip()


def _strip_html_tags(text: str) -> str:
    return re.sub(r"<[^>]+>", " ", text)


def _extract_image(path: Path, *, enable_ocr: bool, ocr_engine: OcrEngine | None) -> DocumentExtraction:
    if not enable_ocr:
        return DocumentExtraction(
            source_name=path.name,
            file_type=path.suffix.lower().lstrip("."),
            text="",
            tables=[],
            warnings=["Image files require optional OCR. Enable OCR and install local OCR dependencies to extract text."],
        )
    text, warnings = _ocr_file(path, ocr_engine=ocr_engine)
    return DocumentExtraction(
        source_name=path.name,
        file_type=path.suffix.lower().lstrip("."),
        text=text,
        tables=[],
        warnings=warnings,
    )


def _extract_docx(path: Path) -> DocumentExtraction:
    warnings: list[str] = []
    try:
        with zipfile.ZipFile(path) as archive:
            xml_bytes = archive.read("word/document.xml")
            comments = _docx_comments(archive)
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
    annotations = _docx_annotations(path.name, root, comments)
    return DocumentExtraction(
        source_name=path.name,
        file_type="docx",
        text=text,
        tables=tables,
        warnings=warnings,
        annotations=annotations,
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


def _docx_comments(archive: zipfile.ZipFile) -> dict[str, dict[str, str]]:
    try:
        comments_xml = archive.read("word/comments.xml")
    except KeyError:
        return {}
    root = ElementTree.fromstring(comments_xml)
    comments: dict[str, dict[str, str]] = {}
    for comment in root.findall(".//w:comment", WORD_NS):
        comment_id = comment.attrib.get(f"{{{WORD_NS['w']}}}id", "")
        if not comment_id:
            continue
        comments[comment_id] = {
            "author": comment.attrib.get(f"{{{WORD_NS['w']}}}author", ""),
            "text": _paragraph_text(comment),
        }
    return comments


def _docx_annotations(source_name: str, root: ElementTree.Element, comments: dict[str, dict[str, str]]) -> list[AnnotationMark]:
    annotations: list[AnnotationMark] = []
    for paragraph in root.findall(".//w:p", WORD_NS):
        context = _paragraph_text(paragraph)
        comment_ranges: dict[str, list[str]] = {}
        active_comment_ids: list[str] = []

        for child in list(paragraph):
            local_name = _local_name(child.tag)
            if local_name == "commentRangeStart":
                comment_id = child.attrib.get(f"{{{WORD_NS['w']}}}id", "")
                if comment_id:
                    active_comment_ids.append(comment_id)
                    comment_ranges.setdefault(comment_id, [])
                continue
            if local_name == "commentRangeEnd":
                comment_id = child.attrib.get(f"{{{WORD_NS['w']}}}id", "")
                if comment_id in active_comment_ids:
                    active_comment_ids.remove(comment_id)
                continue
            if local_name != "r":
                continue

            run_text = _paragraph_text(child)
            if not run_text:
                continue
            for comment_id in active_comment_ids:
                comment_ranges.setdefault(comment_id, []).append(run_text)

            highlight = child.find("./w:rPr/w:highlight", WORD_NS)
            if highlight is not None:
                color = highlight.attrib.get(f"{{{WORD_NS['w']}}}val", "")
                if color and color != "none":
                    annotations.append(
                        AnnotationMark(
                            source_name=source_name,
                            kind="highlight",
                            text=run_text,
                            color=color,
                            context=context,
                        )
                    )

            font_color = child.find("./w:rPr/w:color", WORD_NS)
            if font_color is not None:
                color = font_color.attrib.get(f"{{{WORD_NS['w']}}}val", "")
                if color and color.lower() != "auto":
                    annotations.append(
                        AnnotationMark(
                            source_name=source_name,
                            kind="font_color",
                            text=run_text,
                            color=color,
                            context=context,
                        )
                    )

        for comment_id, text_parts in comment_ranges.items():
            comment = comments.get(comment_id, {})
            annotations.insert(
                0,
                AnnotationMark(
                    source_name=source_name,
                    kind="comment",
                    text="".join(text_parts).strip(),
                    comment_text=comment.get("text", ""),
                    author=comment.get("author", ""),
                    context=context,
                ),
            )
    return annotations


def _local_name(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[1]
    return tag


def _extract_pdf(path: Path, *, enable_ocr: bool, ocr_engine: OcrEngine | None) -> DocumentExtraction:
    try:
        from pypdf import PdfReader  # type: ignore[import-not-found]
    except ImportError:
        return _extract_pdf_fallback(path, pypdf_missing=True, enable_ocr=enable_ocr, ocr_engine=ocr_engine)

    try:
        reader = PdfReader(str(path))
        pages = [page.extract_text() or "" for page in reader.pages]
    except Exception as exc:  # pragma: no cover - parser-specific failures vary
        fallback = _extract_pdf_fallback(path, pypdf_missing=False, enable_ocr=enable_ocr, ocr_engine=ocr_engine)
        if fallback.text.strip():
            return fallback
        return DocumentExtraction(
            source_name=path.name,
            file_type="pdf",
            text="",
            tables=[],
            warnings=[f"PDF text could not be extracted: {exc}"],
        )

    text = "\n\n".join(page.strip() for page in pages if page.strip())
    annotations = _pdf_annotations_from_reader(path.name, reader)
    try:
        raw = path.read_bytes()
        annotations.extend(_pdf_annotations_from_raw(path.name, raw, existing_count=len(annotations)))
    except OSError:
        pass
    warnings = []
    if not text:
        if enable_ocr:
            ocr_text, ocr_warnings = _ocr_file(path, ocr_engine=ocr_engine)
            if ocr_text:
                text = ocr_text
                warnings.append("PDF text extraction returned no text; optional OCR was used.")
            warnings.extend(ocr_warnings)
        if not text:
            warnings.append("No text was extracted. Scanned PDFs and image-only PDFs require optional OCR.")
    return DocumentExtraction(
        source_name=path.name,
        file_type="pdf",
        text=text,
        tables=[],
        warnings=warnings,
        annotations=annotations,
    )


def _extract_pdf_fallback(
    path: Path,
    *,
    pypdf_missing: bool,
    enable_ocr: bool = False,
    ocr_engine: OcrEngine | None = None,
) -> DocumentExtraction:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        return DocumentExtraction(
            source_name=path.name,
            file_type="pdf",
            text="",
            tables=[],
            warnings=[f"PDF file could not be read: {exc}"],
        )

    text_fragments: list[str] = []
    for stream in _pdf_streams(raw):
        text_fragments.extend(_pdf_text_fragments(stream))

    text = "\n".join(fragment for fragment in text_fragments if fragment.strip()).strip()
    annotations = _pdf_annotations_from_raw(path.name, raw)
    warnings = []
    if not text:
        if enable_ocr:
            ocr_text, ocr_warnings = _ocr_file(path, ocr_engine=ocr_engine)
            if ocr_text:
                text = ocr_text
                warnings.append("PDF text extraction returned no text; optional OCR was used.")
            warnings.extend(ocr_warnings)
        if not text:
            if pypdf_missing:
                warnings.append(
                    "No PDF text was extracted. Install pypdf for broader text-based PDF support; scanned PDFs require optional OCR."
                )
            else:
                warnings.append("No text was extracted. Scanned PDFs and image-only PDFs require optional OCR.")
    return DocumentExtraction(
        source_name=path.name,
        file_type="pdf",
        text=text,
        tables=[],
        warnings=warnings,
        annotations=annotations,
    )


def _pdf_streams(raw: bytes) -> list[bytes]:
    streams: list[bytes] = []
    for match in re.finditer(rb"stream\r?\n(.*?)\r?\nendstream", raw, flags=re.DOTALL):
        stream = match.group(1)
        header = raw[max(0, match.start() - 300) : match.start()]
        if b"/FlateDecode" in header:
            try:
                stream = zlib.decompress(stream)
            except zlib.error:
                continue
        streams.append(stream)
    return streams


def _pdf_text_fragments(stream: bytes) -> list[str]:
    fragments: list[str] = []
    for literal in re.findall(rb"\((?:\\.|[^\\()])*\)", stream):
        text = _decode_pdf_literal(literal[1:-1])
        if text:
            fragments.append(text)
    for hex_string in re.findall(rb"<([0-9A-Fa-f\s]+)>", stream):
        text = _decode_pdf_hex(hex_string)
        if text:
            fragments.append(text)
    return fragments


def _pdf_annotations_from_reader(source_name: str, reader: object) -> list[AnnotationMark]:
    annotations: list[AnnotationMark] = []
    pages = getattr(reader, "pages", [])
    for page_number, page in enumerate(pages, start=1):
        try:
            page_text = (page.extract_text() or "").strip()
            raw_annots = page.get("/Annots", []) or []
        except Exception:
            continue
        for raw_annot in raw_annots:
            try:
                annot = raw_annot.get_object() if hasattr(raw_annot, "get_object") else raw_annot
                subtype = str(annot.get("/Subtype", "")).lstrip("/")
                kind = _pdf_annotation_kind(subtype)
                if not kind:
                    continue
                contents = _pdf_object_text(annot.get("/Contents", ""))
                color = _pdf_color_text(annot.get("/C", ""))
                annotations.append(
                    AnnotationMark(
                        source_name=source_name,
                        kind=kind,
                        text=contents if kind == "comment" else f"PDF {kind} annotation",
                        color=color,
                        comment_text=contents if kind != "comment" else "",
                        context=f"page {page_number}: {page_text[:240]}".strip(),
                        page_number=page_number,
                    )
                )
            except Exception:
                continue
    return annotations


def _pdf_annotations_from_raw(source_name: str, raw: bytes, *, existing_count: int = 0) -> list[AnnotationMark]:
    if existing_count:
        return []
    annotations: list[AnnotationMark] = []
    pattern = re.compile(
        rb"<<(?P<body>(?:(?!>>).)*?/Subtype\s*/(?P<subtype>Highlight|Text|FreeText)(?:(?!>>).)*?)>>",
        flags=re.DOTALL,
    )
    for match in pattern.finditer(raw):
        body = match.group("body")
        subtype = _decode_text_with_fallback(match.group("subtype")).strip()
        kind = _pdf_annotation_kind(subtype)
        if not kind:
            continue
        contents = _pdf_raw_annotation_contents(body)
        color = _pdf_raw_annotation_color(body)
        annotations.append(
            AnnotationMark(
                source_name=source_name,
                kind=kind,
                text=contents if kind == "comment" else f"PDF {kind} annotation",
                color=color,
                comment_text=contents if kind != "comment" else "",
                context="page 1 PDF annotation",
                page_number=1,
            )
        )
    return annotations


def _pdf_annotation_kind(subtype: str) -> str:
    normalized = subtype.strip().lstrip("/")
    if normalized == "Highlight":
        return "highlight"
    if normalized in {"Text", "FreeText"}:
        return "comment"
    return ""


def _pdf_raw_annotation_contents(body: bytes) -> str:
    match = re.search(rb"/Contents\s*(?P<value>\((?:\\.|[^\\()])*\)|<[^>]*>)", body, flags=re.DOTALL)
    if not match:
        return ""
    value = match.group("value")
    if value.startswith(b"("):
        return _decode_pdf_literal(value[1:-1])
    if value.startswith(b"<"):
        return _decode_pdf_hex(value[1:-1])
    return ""


def _pdf_raw_annotation_color(body: bytes) -> str:
    match = re.search(rb"/C\s*\[(?P<value>[^\]]+)\]", body, flags=re.DOTALL)
    if not match:
        return ""
    return _normalize_space(_decode_text_with_fallback(match.group("value")))


def _pdf_object_text(value: object) -> str:
    if value is None:
        return ""
    try:
        if hasattr(value, "get_object"):
            value = value.get_object()
    except Exception:
        return ""
    return str(value).strip()


def _pdf_color_text(value: object) -> str:
    if not value:
        return ""
    try:
        if hasattr(value, "get_object"):
            value = value.get_object()
        if isinstance(value, (list, tuple)):
            return " ".join(str(item) for item in value)
        return str(value).strip("[]")
    except Exception:
        return ""


def _ocr_file(path: Path, *, ocr_engine: OcrEngine | None) -> tuple[str, list[str]]:
    if ocr_engine is not None:
        try:
            return str(ocr_engine(path)).strip(), []
        except Exception as exc:
            return "", [f"Optional OCR failed: {exc}"]

    suffix = path.suffix.lower()
    try:
        import pytesseract  # type: ignore[import-not-found]
        if suffix == ".pdf":
            from pdf2image import convert_from_path  # type: ignore[import-not-found]

            pages = convert_from_path(str(path))
            text = "\n\n".join(pytesseract.image_to_string(page).strip() for page in pages).strip()
        else:
            from PIL import Image  # type: ignore[import-not-found]

            with Image.open(path) as image:
                text = pytesseract.image_to_string(image).strip()
    except ImportError:
        return "", [
            "Optional OCR is not available locally. Install the OCR extra and required system OCR tools: Tesseract for images, plus Poppler for PDF OCR."
        ]
    except Exception as exc:
        return "", [f"Optional OCR failed: {exc}"]

    if not text:
        return "", ["Optional OCR ran but no text was extracted."]
    return text, []


def _decode_pdf_literal(raw: bytes) -> str:
    output = bytearray()
    index = 0
    escapes = {
        ord("n"): b"\n",
        ord("r"): b"\r",
        ord("t"): b"\t",
        ord("b"): b"\b",
        ord("f"): b"\f",
        ord("("): b"(",
        ord(")"): b")",
        ord("\\"): b"\\",
    }
    while index < len(raw):
        byte = raw[index]
        if byte != ord("\\"):
            output.append(byte)
            index += 1
            continue
        index += 1
        if index >= len(raw):
            break
        escaped = raw[index]
        if escaped in escapes:
            output.extend(escapes[escaped])
            index += 1
            continue
        if ord("0") <= escaped <= ord("7"):
            digits = bytes([escaped])
            index += 1
            while index < len(raw) and len(digits) < 3 and ord("0") <= raw[index] <= ord("7"):
                digits += bytes([raw[index]])
                index += 1
            output.append(int(digits, 8))
            continue
        output.append(escaped)
        index += 1
    return _decode_text_with_fallback(bytes(output)).strip()


def _decode_pdf_hex(raw: bytes) -> str:
    cleaned = re.sub(rb"\s+", b"", raw)
    if len(cleaned) % 2:
        cleaned += b"0"
    try:
        data = bytes.fromhex(cleaned.decode("ascii"))
    except ValueError:
        return ""
    if data.startswith(b"\xfe\xff"):
        return data[2:].decode("utf-16-be", errors="replace").strip()
    return _decode_text_with_fallback(data).strip()


def _extract_csv(path: Path) -> DocumentExtraction:
    rows = [row for row in csv.reader(io.StringIO(_read_text_with_fallback(path)))]
    table = ExtractedTable(name=path.stem, rows=rows)
    return DocumentExtraction(
        source_name=path.name,
        file_type="csv",
        text=f"CSV table extracted from {path.name}.",
        tables=[table],
        warnings=[],
    )


def _read_text_with_fallback(path: Path) -> str:
    return _decode_text_with_fallback(path.read_bytes())


def _decode_text_with_fallback(raw: bytes) -> str:
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        try:
            return raw.decode("utf-16")
        except UnicodeDecodeError:
            pass
    for encoding in TEXT_ENCODINGS:
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def _normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


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


def _combined_annotations(results: list[DocumentExtraction]) -> str:
    lines: list[str] = []
    for result in results:
        for annotation in result.annotations:
            if annotation.kind == "comment":
                label = f"comment: {annotation.text or 'unmarked text'}"
                line = f"- {result.source_name} [{label}]"
            else:
                label = annotation.kind
                if annotation.color:
                    label = f"{label}:{annotation.color}"
                line = f"- {result.source_name} [{label}] {annotation.text}"
            if annotation.comment_text:
                line += f" | comment: {annotation.comment_text}"
            lines.append(line)
    if not lines:
        return "_No annotation signals extracted._\n"
    return "\n".join(lines).rstrip() + "\n"


def _write_tables(results: list[DocumentExtraction], table_dir: Path) -> None:
    for result in results:
        for table in result.tables:
            with (table_dir / f"{table.name}.csv").open("w", newline="", encoding="utf-8") as handle:
                writer = csv.writer(handle)
                writer.writerows(table.rows)


def _write_annotations(results: list[DocumentExtraction], output_dir: Path) -> None:
    annotations = [annotation for result in results for annotation in result.annotations]
    (output_dir / "annotation_map.json").write_text(
        json.dumps({"annotations": [_annotation_dict(annotation) for annotation in annotations]}, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    with (output_dir / "highlighted_spans.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["source_name", "kind", "color", "text", "context"])
        writer.writeheader()
        for annotation in annotations:
            if annotation.kind in {"highlight", "font_color"}:
                writer.writerow(
                    {
                        "source_name": annotation.source_name,
                        "kind": annotation.kind,
                        "color": annotation.color,
                        "text": annotation.text,
                        "context": annotation.context,
                    }
                )

    (output_dir / "comment_threads.md").write_text(_comments_markdown(annotations), encoding="utf-8")
    (output_dir / "priority_marks.md").write_text(_priority_marks_markdown(annotations), encoding="utf-8")


def _annotation_dict(annotation: AnnotationMark) -> dict[str, str]:
    return {
        "source_name": annotation.source_name,
        "kind": annotation.kind,
        "text": annotation.text,
        "color": annotation.color,
        "comment_text": annotation.comment_text,
        "author": annotation.author,
        "context": annotation.context,
        "page_number": "" if annotation.page_number is None else str(annotation.page_number),
    }


def _comments_markdown(annotations: list[AnnotationMark]) -> str:
    lines = ["# Comment Threads", ""]
    comments = [annotation for annotation in annotations if annotation.kind == "comment"]
    if not comments:
        lines.append("- No Word comment threads extracted.")
        return "\n".join(lines).rstrip() + "\n"
    for annotation in comments:
        author = f" ({annotation.author})" if annotation.author else ""
        lines.extend(
            [
                f"## {annotation.source_name}{author}",
                "",
                f"- Marked text: {annotation.text or '_No marked text captured._'}",
                f"- Comment: {annotation.comment_text or '_No comment text captured._'}",
                f"- Context: {annotation.context or '_No paragraph context captured._'}",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def _priority_marks_markdown(annotations: list[AnnotationMark]) -> str:
    lines = ["# Priority Marks", ""]
    marks = [annotation for annotation in annotations if annotation.kind in {"highlight", "font_color"}]
    if not marks:
        lines.append("- No highlighted spans or font-color marks extracted.")
        return "\n".join(lines).rstrip() + "\n"
    for annotation in marks:
        lines.append(f"- {annotation.source_name} [{annotation.kind}:{annotation.color}] {annotation.text}")
    return "\n".join(lines).rstrip() + "\n"


def _manifest(results: list[DocumentExtraction]) -> dict[str, object]:
    return {
        "sources": [
            {
                "source_name": result.source_name,
                "file_type": result.file_type,
                "text_length": len(result.text),
                "table_count": len(result.tables),
                "annotation_count": len(result.annotations),
                "source_url": result.source_url,
                "warnings": result.warnings,
            }
            for result in results
        ],
        "supported_extensions": sorted(SUPPORTED_EXTENSIONS),
        "boundaries": [
            "Text-based PDFs are supported directly; scanned PDFs and images require optional local OCR.",
            "URL intake supports public static http(s) pages only; it does not log in, execute JavaScript, or crawl sites.",
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
            "- Text-based PDFs are supported directly; scanned PDFs and image files require optional local OCR.",
            "- URL intake supports public static http(s) pages only; it does not log in, execute JavaScript, or crawl sites.",
            "- No image understanding, figure interpretation, clinical judgement, or education-policy authority is performed.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def _clean_markdown(text: str) -> str:
    lines = [line.strip() for line in text.strip().splitlines()]
    return "\n".join(lines).strip() + "\n"
