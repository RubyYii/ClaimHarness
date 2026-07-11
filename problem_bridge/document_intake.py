from __future__ import annotations

import csv
import hashlib
import html
import http.client
import ipaddress
import io
import json
import queue
import re
import socket
import ssl
import threading
import urllib.error
import urllib.parse
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
AddressResolver = Callable[[str, int], Iterable[str]]
MAX_URL_RESPONSE_BYTES = 2_000_000
MAX_URL_REDIRECTS = 3
OCR_REPORT_SCHEMA_VERSION = "1.0"
OCR_PROVENANCE = "derived_text/ocr"


@dataclass(frozen=True)
class OcrLimits:
    """Resource limits for optional local OCR.

    The defaults are deliberately conservative for a local-first desktop tool.
    Callers may pass a smaller limit for untrusted files or a larger one after
    an explicit local review.
    """

    max_bytes: int = 25_000_000
    max_pages: int = 50
    max_characters: int = 1_000_000
    timeout_seconds: float = 30.0
    pdf_dpi: int = 150
    max_pixels_per_page: int = 20_000_000

    def __post_init__(self) -> None:
        if (
            self.max_bytes <= 0
            or self.max_pages <= 0
            or self.max_characters <= 0
            or self.timeout_seconds <= 0
            or self.pdf_dpi <= 0
            or self.max_pixels_per_page <= 0
        ):
            raise ValueError("OCR resource limits must all be positive integers.")


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
    text_origin: str = "source_text/direct"
    ocr_quality_report: dict[str, object] | None = None


def extract_document(
    path: str | Path,
    *,
    enable_ocr: bool = False,
    ocr_engine: OcrEngine | None = None,
    ocr_language: str | None = None,
    ocr_limits: OcrLimits | None = None,
) -> DocumentExtraction:
    source = Path(path)
    suffix = source.suffix.lower()
    if suffix == ".doc":
        return _extract_legacy_doc(source)
    if suffix == ".docx":
        return _extract_docx(source)
    if suffix == ".pdf":
        return _extract_pdf(
            source,
            enable_ocr=enable_ocr,
            ocr_engine=ocr_engine,
            ocr_language=ocr_language,
            ocr_limits=ocr_limits,
        )
    if suffix in {".html", ".htm"}:
        return _extract_html(source)
    if suffix in IMAGE_EXTENSIONS:
        return _extract_image(
            source,
            enable_ocr=enable_ocr,
            ocr_engine=ocr_engine,
            ocr_language=ocr_language,
            ocr_limits=ocr_limits,
        )
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


def extract_url(
    url: str,
    *,
    fetcher: Callable[[str], bytes] | None = None,
    resolver: AddressResolver | None = None,
) -> DocumentExtraction:
    normalized_url = url.strip()
    safe_url = _safe_source_url(normalized_url)
    try:
        parsed = urllib.parse.urlparse(normalized_url)
    except ValueError:
        parsed = urllib.parse.urlparse("")
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return DocumentExtraction(
            source_name="invalid-url",
            file_type="url",
            text="",
            tables=[],
            warnings=["URL intake only supports public http(s) URLs."],
            source_url="",
        )

    address_resolver = resolver or _resolve_host_addresses
    try:
        validate_public_url(normalized_url, resolver=address_resolver)
    except (OSError, ValueError) as exc:
        return DocumentExtraction(
            source_name=_url_source_name(normalized_url),
            file_type="url",
            text="",
            tables=[],
            warnings=[f"URL is not a public destination: {exc}"],
            source_url=safe_url,
        )

    try:
        raw = (
            fetcher(normalized_url)
            if fetcher is not None
            else _fetch_url(normalized_url, resolver=address_resolver)
        )
        if isinstance(raw, str):
            raw = raw.encode("utf-8")
        if len(raw) > MAX_URL_RESPONSE_BYTES:
            raise ValueError(
                f"URL response exceeds the {MAX_URL_RESPONSE_BYTES}-byte limit."
            )
    except Exception as exc:
        detail = str(exc)
        warning = (
            f"URL could not be fetched: {detail}"
            if detail.startswith("URL response exceeds the ")
            else "URL could not be fetched safely. Check that it is a reachable public static http(s) page."
        )
        return DocumentExtraction(
            source_name=_url_source_name(normalized_url),
            file_type="url",
            text="",
            tables=[],
            warnings=[warning],
            source_url=safe_url,
        )

    return _extract_html_bytes(
        source_name=_url_source_name(normalized_url),
        file_type="url",
        stem=_url_source_name(normalized_url),
        raw=raw,
        source_url=safe_url,
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
    (output_dir / "ocr_quality_report.json").write_text(
        json.dumps(_ocr_quality_package(result_list), indent=2, ensure_ascii=False) + "\n",
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


def validate_public_url(url: str, *, resolver: AddressResolver | None = None) -> None:
    _validated_public_destination(url, resolver=resolver)


def _validated_public_destination(
    url: str,
    *,
    resolver: AddressResolver | None = None,
) -> tuple[urllib.parse.SplitResult, int, tuple[str, ...]]:
    try:
        parsed = urllib.parse.urlsplit(url)
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
    except ValueError as exc:
        raise ValueError("invalid URL syntax") from exc

    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("only http(s) URLs with a hostname are supported")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("URL credentials are not allowed")

    hostname = parsed.hostname.rstrip(".").lower()
    if hostname == "localhost":
        raise ValueError("localhost is not a public destination")

    try:
        literal_address = ipaddress.ip_address(hostname.split("%", 1)[0])
    except ValueError:
        literal_address = None

    address_resolver = resolver or _resolve_host_addresses
    addresses = [str(literal_address)] if literal_address is not None else list(
        address_resolver(parsed.hostname, port)
    )
    if not addresses:
        raise ValueError("hostname did not resolve to an address")
    approved: list[str] = []
    for address in addresses:
        normalized = address.split("%", 1)[0]
        try:
            parsed_address = ipaddress.ip_address(normalized)
        except ValueError as exc:
            raise ValueError("hostname resolved to an invalid address") from exc
        if not parsed_address.is_global:
            raise ValueError(f"hostname resolves to non-public address {parsed_address}")
        canonical = str(parsed_address)
        if canonical not in approved:
            approved.append(canonical)
    return parsed, port, tuple(approved)


def _resolve_host_addresses(hostname: str, port: int) -> Iterable[str]:
    results = socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
    return sorted({result[4][0] for result in results})


class _PinnedHTTPConnection(http.client.HTTPConnection):
    """Connect to an approved IP while retaining the original HTTP Host."""

    def __init__(self, hostname: str, port: int, approved_ip: str, *, timeout: int):
        super().__init__(hostname, port=port, timeout=timeout)
        self._approved_ip = approved_ip

    def connect(self) -> None:
        self.sock = _connect_to_approved_ip(
            self._approved_ip,
            self.port,
            timeout=self.timeout,
            source_address=self.source_address,
        )


class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    """Pin TCP to an approved IP and keep hostname-based SNI/certificate checks."""

    def __init__(self, hostname: str, port: int, approved_ip: str, *, timeout: int):
        super().__init__(hostname, port=port, timeout=timeout)
        self._approved_ip = approved_ip

    def connect(self) -> None:
        raw_socket = _connect_to_approved_ip(
            self._approved_ip,
            self.port,
            timeout=self.timeout,
            source_address=self.source_address,
        )
        try:
            self.sock = self._context.wrap_socket(raw_socket, server_hostname=self.host)
        except Exception:
            raw_socket.close()
            raise


def _connect_to_approved_ip(
    approved_ip: str,
    port: int,
    *,
    timeout: float | object,
    source_address: tuple[str, int] | None,
) -> socket.socket:
    address = ipaddress.ip_address(approved_ip)
    if not address.is_global:
        raise OSError("approved destination is not a public address")
    family = socket.AF_INET6 if address.version == 6 else socket.AF_INET
    sock = socket.socket(family, socket.SOCK_STREAM)
    try:
        if timeout is not socket._GLOBAL_DEFAULT_TIMEOUT:
            sock.settimeout(timeout)
        if source_address is not None:
            sock.bind(source_address)
        destination = (
            (str(address), port, 0, 0)
            if address.version == 6
            else (str(address), port)
        )
        sock.connect(destination)
        peer = ipaddress.ip_address(str(sock.getpeername()[0]).split("%", 1)[0])
        if peer != address or not peer.is_global:
            raise OSError("connected peer does not match the approved public address")
    except Exception:
        sock.close()
        raise
    return sock


def _fetch_url(url: str, *, resolver: AddressResolver | None = None) -> bytes:
    address_resolver = resolver or _resolve_host_addresses
    current_url = url
    redirect_count = 0

    while True:
        parsed, port, approved_ips = _validated_public_destination(
            current_url,
            resolver=address_resolver,
        )
        connection, response = _request_pinned(parsed, port, approved_ips)
        try:
            if response.status in {301, 302, 303, 307, 308}:
                location = response.getheader("Location")
                if not location:
                    raise urllib.error.URLError("redirect response is missing a Location header")
                if redirect_count >= MAX_URL_REDIRECTS:
                    raise urllib.error.URLError(
                        f"URL exceeded the {MAX_URL_REDIRECTS}-redirect limit"
                    )
                target_url = urllib.parse.urljoin(current_url, location)
                source = urllib.parse.urlsplit(current_url)
                target = urllib.parse.urlsplit(target_url)
                if source.scheme == "https" and target.scheme != "https":
                    raise urllib.error.URLError("HTTPS URL redirect downgrade is not allowed")
                current_url = target_url
                redirect_count += 1
                continue
            if response.status >= 400:
                raise urllib.error.URLError(f"public URL returned HTTP {response.status}")
            return _read_url_response(response)
        finally:
            response.close()
            connection.close()


def _request_pinned(
    parsed: urllib.parse.SplitResult,
    port: int,
    approved_ips: tuple[str, ...],
) -> tuple[http.client.HTTPConnection, http.client.HTTPResponse]:
    hostname = parsed.hostname
    if hostname is None:
        raise ValueError("public URL is missing a hostname")
    request_target = urllib.parse.urlunsplit(("", "", parsed.path or "/", parsed.query, ""))
    last_error: Exception | None = None
    for approved_ip in approved_ips:
        connection: http.client.HTTPConnection
        if parsed.scheme == "https":
            connection = _PinnedHTTPSConnection(hostname, port, approved_ip, timeout=10)
        else:
            connection = _PinnedHTTPConnection(hostname, port, approved_ip, timeout=10)
        try:
            connection.request(
                "GET",
                request_target,
                headers={
                    "User-Agent": "ProblemBridge-DocumentIntake/0.3",
                    "Accept-Encoding": "identity",
                },
            )
            return connection, connection.getresponse()
        except (OSError, ssl.SSLError, http.client.HTTPException) as exc:
            last_error = exc
            connection.close()
    raise urllib.error.URLError("connection to the approved public destination failed") from last_error


def _read_url_response(response: object) -> bytes:
    headers = getattr(response, "headers", None)
    content_length = headers.get("Content-Length") if headers is not None else None
    if content_length:
        try:
            declared_length = int(content_length)
        except ValueError:
            declared_length = None
        if declared_length is not None and declared_length > MAX_URL_RESPONSE_BYTES:
            raise ValueError(
                f"URL response exceeds the {MAX_URL_RESPONSE_BYTES}-byte limit."
            )

    body = response.read(MAX_URL_RESPONSE_BYTES + 1)
    if len(body) > MAX_URL_RESPONSE_BYTES:
        raise ValueError(f"URL response exceeds the {MAX_URL_RESPONSE_BYTES}-byte limit.")
    return body


def _url_source_name(url: str) -> str:
    safe_url = _safe_source_url(url)
    if not safe_url:
        return "invalid-url"
    parsed = urllib.parse.urlparse(safe_url)
    path = parsed.path.strip("/").replace("/", "_") or "index"
    raw_name = f"{parsed.netloc}_{path}"
    return re.sub(r"[^A-Za-z0-9._-]+", "_", raw_name).strip("_") or "webpage"


def _safe_source_url(url: str) -> str:
    """Return a share-safe URL without credentials, query parameters, or fragments."""

    try:
        parsed = urllib.parse.urlsplit(url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            return ""
        hostname = parsed.hostname or ""
        if ":" in hostname:
            hostname = f"[{hostname}]"
        port = f":{parsed.port}" if parsed.port is not None else ""
        return urllib.parse.urlunsplit(
            (parsed.scheme, f"{hostname}{port}", parsed.path, "", "")
        )
    except ValueError:
        return ""


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


def _extract_image(
    path: Path,
    *,
    enable_ocr: bool,
    ocr_engine: OcrEngine | None,
    ocr_language: str | None = None,
    ocr_limits: OcrLimits | None = None,
) -> DocumentExtraction:
    if not enable_ocr:
        return DocumentExtraction(
            source_name=path.name,
            file_type=path.suffix.lower().lstrip("."),
            text="",
            tables=[],
            warnings=["Image files require optional OCR. Enable OCR and install local OCR dependencies to extract text."],
        )
    text, warnings, quality_report = _ocr_file_with_report(
        path,
        ocr_engine=ocr_engine,
        language=ocr_language,
        limits=ocr_limits,
    )
    return DocumentExtraction(
        source_name=path.name,
        file_type=path.suffix.lower().lstrip("."),
        text=text,
        tables=[],
        warnings=warnings,
        text_origin=OCR_PROVENANCE,
        ocr_quality_report=quality_report,
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


def _extract_pdf(
    path: Path,
    *,
    enable_ocr: bool,
    ocr_engine: OcrEngine | None,
    ocr_language: str | None = None,
    ocr_limits: OcrLimits | None = None,
) -> DocumentExtraction:
    try:
        from pypdf import PdfReader  # type: ignore[import-not-found]
    except ImportError:
        return _extract_pdf_fallback(
            path,
            pypdf_missing=True,
            enable_ocr=enable_ocr,
            ocr_engine=ocr_engine,
            ocr_language=ocr_language,
            ocr_limits=ocr_limits,
        )

    try:
        reader = PdfReader(str(path))
        pages = [page.extract_text() or "" for page in reader.pages]
    except Exception as exc:  # pragma: no cover - parser-specific failures vary
        fallback = _extract_pdf_fallback(
            path,
            pypdf_missing=False,
            enable_ocr=enable_ocr,
            ocr_engine=ocr_engine,
            ocr_language=ocr_language,
            ocr_limits=ocr_limits,
        )
        if fallback.text.strip():
            return fallback
        if fallback.ocr_quality_report is not None:
            return DocumentExtraction(
                source_name=path.name,
                file_type="pdf",
                text="",
                tables=[],
                warnings=[f"PDF text could not be extracted: {exc}", *fallback.warnings],
                annotations=fallback.annotations,
                text_origin=fallback.text_origin,
                ocr_quality_report=fallback.ocr_quality_report,
            )
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
    text_origin = "source_text/direct"
    ocr_quality_report: dict[str, object] | None = None
    empty_page_numbers = [
        page_number
        for page_number, page_text in enumerate(pages, start=1)
        if not page_text.strip()
    ]
    if text and empty_page_numbers:
        page_list = ", ".join(str(number) for number in empty_page_numbers)
        warning = (
            "PDF contains page(s) with no extractable text: "
            f"{page_list}. Mixed text/scanned PDFs require page-level source review; "
            "these pages were not silently treated as empty evidence."
        )
        warnings.append(warning)
        if enable_ocr:
            active_limits = ocr_limits or OcrLimits()
            ocr_quality_report = _base_ocr_report(
                path, language=ocr_language, limits=active_limits
            )
            try:
                ocr_quality_report["source_bytes"] = path.stat().st_size
                ocr_quality_report["source_sha256"] = _sha256_file(path)
            except OSError:
                pass
            ocr_quality_report.update(
                status="failed",
                failure="mixed_pdf_requires_page_review",
                engine={"name": "not_run", "version": "not_run"},
                pages_total=len(pages),
                pages_processed=0,
                failed_pages=empty_page_numbers,
                warnings=[warning],
            )
            ocr_quality_report["pages"] = [
                _page_quality(
                    path.name,
                    page_number,
                    "",
                    status=(
                        "requires_page_review"
                        if page_number in empty_page_numbers
                        else "direct_text_present"
                    ),
                )
                for page_number in range(1, len(pages) + 1)
            ]
    if not text:
        if enable_ocr:
            ocr_text, ocr_warnings, ocr_quality_report = _ocr_file_with_report(
                path,
                ocr_engine=ocr_engine,
                language=ocr_language,
                limits=ocr_limits,
            )
            text_origin = OCR_PROVENANCE
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
        text_origin=text_origin,
        ocr_quality_report=ocr_quality_report,
    )


def _extract_pdf_fallback(
    path: Path,
    *,
    pypdf_missing: bool,
    enable_ocr: bool = False,
    ocr_engine: OcrEngine | None = None,
    ocr_language: str | None = None,
    ocr_limits: OcrLimits | None = None,
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
    text_origin = "source_text/direct"
    ocr_quality_report: dict[str, object] | None = None
    if not text:
        if enable_ocr:
            ocr_text, ocr_warnings, ocr_quality_report = _ocr_file_with_report(
                path,
                ocr_engine=ocr_engine,
                language=ocr_language,
                limits=ocr_limits,
            )
            text_origin = OCR_PROVENANCE
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
        text_origin=text_origin,
        ocr_quality_report=ocr_quality_report,
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
    """Backward-compatible text/warnings wrapper around the quality-gated OCR path."""

    text, warnings, _ = _ocr_file_with_report(path, ocr_engine=ocr_engine)
    return text, warnings


def _ocr_file_with_report(
    path: Path,
    *,
    ocr_engine: OcrEngine | None,
    language: str | None = None,
    limits: OcrLimits | None = None,
) -> tuple[str, list[str], dict[str, object]]:
    active_limits = limits or OcrLimits()
    report = _base_ocr_report(path, language=language, limits=active_limits)
    extraction_warnings: list[str] = []

    try:
        source_bytes = path.stat().st_size
    except OSError as exc:
        warning = f"Optional OCR failed before reading the source: {exc}"
        report.update(status="failed", failure="source_unreadable")
        report["warnings"] = [warning]
        return "", [warning], report

    report["source_bytes"] = source_bytes
    try:
        report["source_sha256"] = _sha256_file(path)
    except OSError as exc:
        warning = f"OCR source SHA-256 could not be calculated: {exc}"
        report["warnings"] = [warning]
        extraction_warnings.append(warning)

    if source_bytes > active_limits.max_bytes:
        warning = (
            f"Optional OCR was not run because the source exceeds the "
            f"{active_limits.max_bytes}-byte OCR limit."
        )
        report.update(
            status="failed",
            failure="resource_limit_exceeded",
            limit_exceeded=["max_bytes"],
        )
        report["warnings"] = [*report.get("warnings", []), warning]
        return "", [*extraction_warnings, warning], report

    total_pages = 1 if path.suffix.lower() != ".pdf" else _estimate_pdf_page_count(path)
    report["pages_total"] = total_pages
    if ocr_engine is not None:
        return _run_custom_ocr(
            path,
            ocr_engine=ocr_engine,
            report=report,
            extraction_warnings=extraction_warnings,
            total_pages=total_pages,
            limits=active_limits,
        )
    return _run_tesseract_ocr(
        path,
        report=report,
        extraction_warnings=extraction_warnings,
        total_pages=total_pages,
        language=language,
        limits=active_limits,
    )


def _base_ocr_report(path: Path, *, language: str | None, limits: OcrLimits) -> dict[str, object]:
    return {
        "schema_version": OCR_REPORT_SCHEMA_VERSION,
        "source_name": path.name,
        "source_sha256": "unavailable",
        "source_bytes": None,
        "text_origin": OCR_PROVENANCE,
        "status": "pending",
        "failure": None,
        "engine": {"name": "pending", "version": "unavailable"},
        "language": language or "engine-default",
        "resource_limits": {
            "max_bytes": limits.max_bytes,
            "max_pages": limits.max_pages,
            "max_characters": limits.max_characters,
            "timeout_seconds_per_operation": limits.timeout_seconds,
            "pdf_dpi": limits.pdf_dpi,
            "max_pixels_per_page": limits.max_pixels_per_page,
        },
        "limit_exceeded": [],
        "truncated": False,
        "pages_total": None,
        "pages_processed": 0,
        "pages": [],
        "failed_pages": [],
        "skipped_pages": [],
        "warnings": [],
        "limitations": [
            "OCR confidence is unavailable on this text-only extraction path unless a future engine exposes calibrated page confidence.",
            "OCR output is derived_text/ocr and must not count as strong evidence without source inspection and human review.",
            "OCR extracts text only; it does not interpret figures, charts, diagrams, or their scientific meaning.",
        ],
    }


def _run_custom_ocr(
    path: Path,
    *,
    ocr_engine: OcrEngine,
    report: dict[str, object],
    extraction_warnings: list[str],
    total_pages: int | None,
    limits: OcrLimits,
) -> tuple[str, list[str], dict[str, object]]:
    engine_name = getattr(ocr_engine, "engine_name", None) or getattr(ocr_engine, "__name__", None)
    if not engine_name or str(engine_name).startswith("<"):
        engine_name = "custom"
    report["engine"] = {
        "name": str(engine_name),
        "version": str(getattr(ocr_engine, "version", "unavailable")),
    }

    if total_pages is not None and total_pages > limits.max_pages:
        warning = (
            f"Optional OCR was not run because this custom engine cannot be safely bounded to "
            f"{limits.max_pages} pages (source has {total_pages})."
        )
        report.update(
            status="failed",
            failure="resource_limit_exceeded",
            limit_exceeded=["max_pages"],
        )
        report["warnings"] = [*report.get("warnings", []), warning]
        return "", [*extraction_warnings, warning], report

    try:
        raw_text = str(
            _call_custom_ocr_with_timeout(
                ocr_engine,
                path,
                timeout_seconds=limits.timeout_seconds,
            )
        ).strip()
    except TimeoutError:
        warning = (
            f"Optional OCR exceeded the {limits.timeout_seconds:g}-second execution limit."
        )
        report.update(status="failed", failure="timeout", limit_exceeded=["timeout_seconds"])
        report["warnings"] = [*report.get("warnings", []), warning]
        return "", [*extraction_warnings, warning], report
    except Exception as exc:
        warning = f"Optional OCR failed: {exc}"
        report.update(status="failed", failure="engine_error")
        report["warnings"] = [*report.get("warnings", []), warning]
        return "", [*extraction_warnings, warning], report

    page_texts = raw_text.split("\f") if "\f" in raw_text else [raw_text]
    detected_pages = len(page_texts)
    if total_pages is None or detected_pages > total_pages:
        total_pages = detected_pages
        report["pages_total"] = total_pages
    if detected_pages > limits.max_pages:
        report["skipped_pages"] = list(range(limits.max_pages + 1, detected_pages + 1))
        page_texts = page_texts[: limits.max_pages]
        report["truncated"] = True
        report["limit_exceeded"] = ["max_pages"]
        extraction_warnings.append(
            f"Optional OCR output was truncated at the {limits.max_pages}-page limit."
        )

    text, page_reports, character_truncated = _bounded_page_texts(
        path.name,
        page_texts,
        max_characters=limits.max_characters,
    )
    if character_truncated:
        report["truncated"] = True
        report["limit_exceeded"] = sorted({*report.get("limit_exceeded", []), "max_characters"})
        extraction_warnings.append(
            f"Optional OCR output was truncated at the {limits.max_characters}-character limit."
        )
        if len(page_reports) < len(page_texts):
            report["skipped_pages"] = sorted(
                {
                    *report.get("skipped_pages", []),
                    *range(len(page_reports) + 1, len(page_texts) + 1),
                }
            )

    if total_pages and total_pages > 1 and len(page_texts) == 1:
        page_reports[0]["locator_scope"] = "document_aggregate"
        for page_number in range(2, total_pages + 1):
            page_reports.append(
                _page_quality(
                    path.name,
                    page_number,
                    "",
                    status="not_separable",
                    locator_scope="page_boundary_unavailable",
                )
            )
        report["warnings"] = [
            *report.get("warnings", []),
            "The custom OCR engine returned aggregate text without page separators; page attribution is unavailable.",
        ]

    report["pages"] = page_reports
    report["pages_processed"] = len(page_reports)
    report["warnings"] = [*report.get("warnings", []), *extraction_warnings]
    if not text:
        warning = "Optional OCR ran but no text was extracted."
        report.update(status="failed", failure="no_text")
        report["warnings"] = [*report.get("warnings", []), warning]
        return "", [*extraction_warnings, warning], report

    report["status"] = "partial" if report["truncated"] else "success"
    return text, extraction_warnings, report


def _call_custom_ocr_with_timeout(
    ocr_engine: OcrEngine,
    path: Path,
    *,
    timeout_seconds: float,
) -> object:
    """Bound the caller-facing execution time of a custom local OCR hook.

    A daemon worker is used because arbitrary Python callables cannot be
    reliably killed or pickled into a subprocess on every supported platform.
    The built-in Tesseract path below uses process-level timeouts as well.
    """

    result_queue: queue.Queue[tuple[bool, object]] = queue.Queue(maxsize=1)

    def run_engine() -> None:
        try:
            result_queue.put((True, ocr_engine(path)), block=False)
        except Exception as exc:  # pragma: no cover - exercised via caller
            result_queue.put((False, exc), block=False)

    worker = threading.Thread(target=run_engine, name="problembridge-ocr", daemon=True)
    worker.start()
    try:
        succeeded, value = result_queue.get(timeout=timeout_seconds)
    except queue.Empty as exc:
        raise TimeoutError("custom OCR timed out") from exc
    if not succeeded:
        assert isinstance(value, Exception)
        raise value
    return value


def _run_tesseract_ocr(
    path: Path,
    *,
    report: dict[str, object],
    extraction_warnings: list[str],
    total_pages: int | None,
    language: str | None,
    limits: OcrLimits,
) -> tuple[str, list[str], dict[str, object]]:
    suffix = path.suffix.lower()
    try:
        import pytesseract  # type: ignore[import-not-found]

        try:
            engine_version = str(pytesseract.get_tesseract_version())
        except Exception:
            engine_version = str(getattr(pytesseract, "__version__", "unavailable"))
        report["engine"] = {"name": "tesseract", "version": engine_version}

        if suffix == ".pdf":
            from pdf2image import convert_from_path  # type: ignore[import-not-found]
        else:
            from PIL import Image  # type: ignore[import-not-found]
    except ImportError:
        warning = (
            "Optional OCR is not available locally. Install the OCR extra and required system OCR tools: "
            "Tesseract for images, plus Poppler for PDF OCR."
        )
        report.update(status="failed", failure="dependency_unavailable")
        report["warnings"] = [*report.get("warnings", []), warning]
        return "", [*extraction_warnings, warning], report

    if total_pages is not None and total_pages > limits.max_pages:
        report["truncated"] = True
        report["limit_exceeded"] = ["max_pages"]
        report["skipped_pages"] = list(range(limits.max_pages + 1, total_pages + 1))
        extraction_warnings.append(
            f"Optional OCR was truncated at the {limits.max_pages}-page limit."
        )

    page_texts: list[str] = []
    page_reports: list[dict[str, object]] = []
    failed_pages: list[int] = []
    remaining_characters = limits.max_characters
    timed_out = False
    last_page = min(total_pages, limits.max_pages) if total_pages else limits.max_pages
    page_numbers = range(1, last_page + 1) if suffix == ".pdf" else range(1, 2)

    for page_number in page_numbers:
        if remaining_characters <= 0:
            report["truncated"] = True
            report["limit_exceeded"] = sorted(
                {*report.get("limit_exceeded", []), "max_characters"}
            )
            report["skipped_pages"] = sorted(
                {
                    *report.get("skipped_pages", []),
                    *range(page_number, last_page + 1),
                }
            )
            break

        image = None
        extra_images: list[object] = []
        try:
            if suffix == ".pdf":
                # Convert one bounded page at a time instead of materialising a
                # potentially large PDF into memory before OCR begins.
                converted = convert_from_path(
                    str(path),
                    dpi=limits.pdf_dpi,
                    first_page=page_number,
                    last_page=page_number,
                    thread_count=1,
                    timeout=limits.timeout_seconds,
                )
                if not converted:
                    if total_pages is None:
                        break
                    raise RuntimeError("PDF renderer returned no page image")
                image = converted[0]
                extra_images = list(converted[1:])
            else:
                image = Image.open(path)

            width, height = getattr(image, "size", (0, 0))
            pixel_count = int(width) * int(height)
            if width <= 0 or height <= 0:
                raise RuntimeError("OCR image has invalid dimensions")
            if pixel_count > limits.max_pixels_per_page:
                failed_pages.append(page_number)
                page_reports.append(_page_quality(path.name, page_number, "", status="failed"))
                report["limit_exceeded"] = sorted(
                    {*report.get("limit_exceeded", []), "max_pixels_per_page"}
                )
                extraction_warnings.append(
                    f"Optional OCR skipped page {page_number}: {pixel_count} pixels exceeds "
                    f"the {limits.max_pixels_per_page}-pixel limit."
                )
                continue

            try:
                kwargs = {"lang": language} if language else {}
                page_text = str(
                    pytesseract.image_to_string(
                        image,
                        timeout=limits.timeout_seconds,
                        **kwargs,
                    )
                ).strip()
            except Exception as exc:
                if "timeout" in str(exc).lower():
                    timed_out = True
                    report["limit_exceeded"] = sorted(
                        {*report.get("limit_exceeded", []), "timeout_seconds"}
                    )
                failed_pages.append(page_number)
                page_reports.append(
                    _page_quality(path.name, page_number, "", status="failed")
                )
                extraction_warnings.append(f"Optional OCR failed on page {page_number}: {exc}")
                continue
            separator_characters = 2 if page_text and any(page_texts) else 0
            allowed_characters = max(0, remaining_characters - separator_characters)
            truncated_page = len(page_text) > allowed_characters
            if truncated_page:
                page_text = page_text[:allowed_characters]
                report["truncated"] = True
                report["limit_exceeded"] = sorted({*report.get("limit_exceeded", []), "max_characters"})
            page_texts.append(page_text)
            page_reports.append(
                _page_quality(
                    path.name,
                    page_number,
                    page_text,
                    status="text_present" if page_text else "empty",
                    truncated=truncated_page,
                )
            )
            remaining_characters -= len(page_text) + (separator_characters if page_text else 0)
            if truncated_page and allowed_characters == 0:
                remaining_characters = 0
        except Exception as exc:
            if "timeout" in str(exc).lower():
                timed_out = True
                report["limit_exceeded"] = sorted(
                    {*report.get("limit_exceeded", []), "timeout_seconds"}
                )
            failed_pages.append(page_number)
            page_reports.append(_page_quality(path.name, page_number, "", status="failed"))
            extraction_warnings.append(
                f"Optional OCR could not prepare page {page_number}: {exc}"
            )
            if suffix == ".pdf" and total_pages is None:
                break
        finally:
            close = getattr(image, "close", None)
            if callable(close):
                close()
            for extra_image in extra_images:
                close = getattr(extra_image, "close", None)
                if callable(close):
                    close()

    text = "\n\n".join(page for page in page_texts if page).strip()
    report["pages"] = page_reports
    report["pages_processed"] = len(page_reports)
    report["failed_pages"] = failed_pages
    report["warnings"] = [*report.get("warnings", []), *extraction_warnings]
    if not text:
        warning = "Optional OCR ran but no text was extracted."
        report.update(status="failed", failure="timeout" if timed_out else "no_text")
        report["warnings"] = [*report.get("warnings", []), warning]
        return "", [*extraction_warnings, warning], report

    report["status"] = "partial" if report["truncated"] or failed_pages else "success"
    return text, extraction_warnings, report


def _bounded_page_texts(
    source_name: str,
    page_texts: list[str],
    *,
    max_characters: int,
) -> tuple[str, list[dict[str, object]], bool]:
    bounded: list[str] = []
    page_reports: list[dict[str, object]] = []
    remaining = max_characters
    truncated = False
    for page_number, raw_text in enumerate(page_texts, start=1):
        page_text = raw_text.strip()
        separator_characters = 2 if page_text and any(bounded) else 0
        allowed_characters = max(0, remaining - separator_characters)
        page_truncated = len(page_text) > allowed_characters
        if page_truncated:
            page_text = page_text[:allowed_characters]
            truncated = True
        bounded.append(page_text)
        page_reports.append(
            _page_quality(
                source_name,
                page_number,
                page_text,
                status="text_present" if page_text else "empty",
                truncated=page_truncated,
            )
        )
        remaining -= len(page_text) + (separator_characters if page_text else 0)
        if page_truncated and allowed_characters == 0:
            remaining = 0
        if remaining <= 0 and page_number < len(page_texts):
            truncated = True
            break
    return "\n\n".join(part for part in bounded if part).strip(), page_reports, truncated


def _page_quality(
    source_name: str,
    page_number: int,
    text: str,
    *,
    status: str,
    locator_scope: str = "page",
    truncated: bool = False,
) -> dict[str, object]:
    printable = sum(1 for character in text if character.isprintable())
    return {
        "locator": {"source_name": source_name, "page_number": page_number},
        "locator_scope": locator_scope,
        "status": status,
        "character_count": len(text),
        "non_whitespace_character_count": sum(1 for character in text if not character.isspace()),
        "printable_ratio": round(printable / len(text), 4) if text else None,
        "confidence": {
            "status": "unavailable",
            "value": None,
            "reason": "The text-only OCR API does not expose calibrated page confidence.",
        },
        "truncated": truncated,
    }


def _estimate_pdf_page_count(path: Path) -> int | None:
    try:
        from pypdf import PdfReader  # type: ignore[import-not-found]

        return len(PdfReader(str(path)).pages)
    except Exception:
        try:
            raw = path.read_bytes()
        except OSError:
            return None
        count = len(re.findall(rb"/Type\s*/Page\b", raw))
        return count or None


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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
        if result.text_origin == OCR_PROVENANCE:
            sections.append(
                "<!-- provenance: derived_text/ocr; inspect the source before treating this text as evidence -->"
            )
        if result.text.strip():
            sections.append(_escape_embedded_markdown_headings(result.text.strip()))
        else:
            sections.append("_No text extracted._")
        sections.append("")
    return "\n\n".join(sections).rstrip() + "\n"


def _escape_embedded_markdown_headings(text: str) -> str:
    """Prevent source content from impersonating generated source boundaries."""

    escaped: list[str] = []
    for line in text.splitlines():
        match = re.match(
            r"^(\s*)(#+)(\s*source\s*:.*)$",
            line,
            flags=re.IGNORECASE,
        )
        if match:
            line = f"{match.group(1)}\\{match.group(2)}{match.group(3)}"
        escaped.append(line)
    return "\n".join(escaped)


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
                writer.writerows(
                    [_spreadsheet_safe(value) for value in row] for row in table.rows
                )


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
                        "source_name": _spreadsheet_safe(annotation.source_name),
                        "kind": _spreadsheet_safe(annotation.kind),
                        "color": _spreadsheet_safe(annotation.color),
                        "text": _spreadsheet_safe(annotation.text),
                        "context": _spreadsheet_safe(annotation.context),
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


def _spreadsheet_safe(value: object) -> object:
    """Force formula-like user content to remain literal in exported CSV files."""

    if isinstance(value, str):
        candidate = value.lstrip()
        if candidate.startswith(("+", "-")) and re.fullmatch(
            r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?",
            candidate.strip(),
        ):
            return value
        if candidate.startswith(("=", "+", "-", "@")):
            return "'" + value
    return value


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
                "source_url": _safe_source_url(result.source_url),
                "text_origin": result.text_origin,
                "ocr_quality_status": (
                    result.ocr_quality_report.get("status")
                    if result.ocr_quality_report is not None
                    else "not_run"
                ),
                "warnings": result.warnings,
            }
            for result in results
        ],
        "supported_extensions": sorted(SUPPORTED_EXTENSIONS),
        "boundaries": [
            "Text-based PDFs are supported directly; scanned PDFs and images require optional local OCR.",
            "OCR output is marked derived_text/ocr and is not strong evidence without source inspection and human review.",
            "URL intake supports public static http(s) pages only; it does not log in, execute JavaScript, or crawl sites.",
            "Image, figure, chart, and diagram understanding and professional judgement are not performed by document intake.",
            "Human review is required before using extracted content for problem alignment or evidence audit.",
        ],
    }


def _ocr_quality_package(results: list[DocumentExtraction]) -> dict[str, object]:
    reports = [
        result.ocr_quality_report
        for result in results
        if result.ocr_quality_report is not None
    ]
    return {
        "schema_version": OCR_REPORT_SCHEMA_VERSION,
        "reports": reports,
        "summary": {
            "ocr_sources": len(reports),
            "successful": sum(report.get("status") == "success" for report in reports),
            "partial": sum(report.get("status") == "partial" for report in reports),
            "failed": sum(report.get("status") == "failed" for report in reports),
        },
        "boundary": (
            "OCR is text derivation only. derived_text/ocr is not strong evidence by default, "
            "and no figure, chart, diagram, or scientific-image interpretation is performed."
        ),
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
            "- OCR-derived text is marked derived_text/ocr and requires source inspection before it can support a claim.",
            "- URL intake supports public static http(s) pages only; it does not log in, execute JavaScript, or crawl sites.",
            "- No image understanding, figure/chart/diagram interpretation, clinical judgement, or education-policy authority is performed.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def _clean_markdown(text: str) -> str:
    lines = [line.strip() for line in text.strip().splitlines()]
    return "\n".join(lines).strip() + "\n"
