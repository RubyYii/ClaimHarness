import csv
import json
import socket
import sys
import time
import types
import urllib.error
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

import pytest

import problem_bridge.document_intake as intake_module
from problem_bridge.document_intake import (
    MAX_URL_REDIRECTS,
    MAX_URL_RESPONSE_BYTES,
    OCR_PROVENANCE,
    OcrLimits,
    _connect_to_approved_ip,
    _fetch_url,
    _read_url_response,
    build_problem_seed_from_intake,
    extract_document,
    extract_url,
    write_intake_package,
)


def _assert_hashed_url_source_name(source_name: str, origin_name: str) -> None:
    prefix, discriminator = source_name.rsplit("_", 1)
    assert prefix == origin_name
    assert len(discriminator) == 12
    assert set(discriminator) <= set("0123456789abcdef")


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


def test_intake_csv_exports_neutralize_formula_like_uploaded_content(tmp_path: Path):
    csv_path = tmp_path / "untrusted.csv"
    csv_path.write_text(
        "item,risk\n=HYPERLINK(\"https://example.test\"), +cmd\n"
        "metric,-1e-3\n",
        encoding="utf-8",
    )
    extracted = extract_document(csv_path)
    annotated = intake_module.DocumentExtraction(
        source_name="@source.docx",
        file_type="docx",
        text="review",
        tables=[],
        warnings=[],
        annotations=[
            intake_module.AnnotationMark(
                source_name="@source.docx",
                kind="highlight",
                text="-2+3",
                color="yellow",
                context="  =HYPERLINK(\"https://example.test\")",
            )
        ],
    )
    out = tmp_path / "out"

    write_intake_package([extracted, annotated], out)

    with (out / "extracted_tables" / "untrusted.csv").open(
        newline="", encoding="utf-8"
    ) as handle:
        table_rows = list(csv.reader(handle))
    with (out / "highlighted_spans.csv").open(newline="", encoding="utf-8") as handle:
        annotation_rows = list(csv.DictReader(handle))
    annotation_json = json.loads((out / "annotation_map.json").read_text(encoding="utf-8"))

    assert table_rows[1] == ["'=HYPERLINK(\"https://example.test\")", "' +cmd"]
    assert table_rows[2] == ["metric", "-1e-3"]
    assert annotation_rows[0]["source_name"] == "'@source.docx"
    assert annotation_rows[0]["text"] == "'-2+3"
    assert annotation_rows[0]["context"] == "'  =HYPERLINK(\"https://example.test\")"
    # Machine-readable JSON retains the original evidence text; only CSV is neutralized.
    assert annotation_json["annotations"][0]["text"] == "-2+3"


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

    result = extract_url(
        "https://example.org/workflow",
        fetcher=fetcher,
        resolver=lambda host, port: ["8.8.8.8"],
    )

    _assert_hashed_url_source_name(result.source_name, "example.org")
    assert result.file_type == "url"
    assert result.source_url == "https://example.org"
    assert "Title: Remote Guide" in result.text
    assert "Remote workflow" in result.text
    assert result.warnings == []


def test_extract_url_rejects_non_http_urls():
    result = extract_url("file:///private/report.html")

    assert result.file_type == "url"
    assert result.text == ""
    assert result.warnings == ["URL intake only supports public http(s) URLs."]


@pytest.mark.parametrize(
    "url",
    [
        "http://localhost/workflow",
        "http://127.0.0.1/workflow",
        "http://[::1]/workflow",
        "http://10.1.2.3/workflow",
        "http://169.254.169.254/latest/meta-data",
    ],
)
def test_extract_url_rejects_non_public_literal_destinations(url):
    result = extract_url(url, fetcher=lambda value: b"<p>should not fetch</p>")

    assert result.text == ""
    assert "not a public destination" in result.warnings[0]


def test_extract_url_rejects_hostname_if_any_resolved_address_is_private():
    result = extract_url(
        "https://mixed.example.test/workflow",
        fetcher=lambda value: b"<p>should not fetch</p>",
        resolver=lambda host, port: ["8.8.8.8", "192.168.1.10"],
    )

    assert result.text == ""
    assert "non-public address" in result.warnings[0]


def test_extract_url_rejects_embedded_credentials():
    result = extract_url(
        "https://user:secret@example.test/workflow",
        fetcher=lambda value: b"<p>should not fetch</p>",
        resolver=lambda host, port: ["8.8.8.8"],
    )

    assert result.text == ""
    assert "credentials" in result.warnings[0]
    assert "secret" not in result.source_name
    assert "secret" not in result.source_url


def test_extract_url_rejects_oversized_injected_response():
    result = extract_url(
        "https://example.test/workflow",
        fetcher=lambda value: b"x" * (MAX_URL_RESPONSE_BYTES + 1),
        resolver=lambda host, port: ["8.8.8.8"],
    )

    assert result.text == ""
    assert "exceeds" in result.warnings[0]


class _FakeURLResponse:
    def __init__(
        self,
        body: bytes,
        headers: dict[str, str] | None = None,
        *,
        status: int = 200,
        location: str | None = None,
    ):
        self.body = body
        self.headers = headers or {}
        self.status = status
        self.location = location
        self.closed = False

    def read(self, size: int = -1) -> bytes:
        return self.body if size < 0 else self.body[:size]

    def getheader(self, name: str) -> str | None:
        return self.location if name.lower() == "location" else self.headers.get(name)

    def close(self) -> None:
        self.closed = True


class _FakeURLConnection:
    def __init__(self):
        self.closed = False

    def close(self) -> None:
        self.closed = True


def test_url_response_content_length_over_limit_is_rejected():
    response = _FakeURLResponse(
        b"small body",
        {"Content-Length": str(MAX_URL_RESPONSE_BYTES + 1)},
    )

    with pytest.raises(ValueError, match="exceeds"):
        _read_url_response(response)


@pytest.mark.parametrize(
    "content_type",
    [
        "text/html",
        "Text/HTML; Charset=UTF-8",
        "application/xhtml+xml; charset=utf-8",
        "text/plain; charset=gb18030",
    ],
)
def test_pinned_fetch_accepts_supported_final_content_types(monkeypatch, content_type):
    response = _FakeURLResponse(
        b"<p>public workflow</p>",
        {"Content-Type": content_type},
    )
    monkeypatch.setattr(
        intake_module,
        "_request_pinned",
        lambda *args: (_FakeURLConnection(), response),
    )

    assert _fetch_url(
        "https://example.test/workflow",
        resolver=lambda host, port: ["8.8.8.8"],
    ) == b"<p>public workflow</p>"


def test_pinned_fetch_rejects_unsupported_final_content_type(monkeypatch):
    response = _FakeURLResponse(
        b"binary payload",
        {"Content-Type": "application/octet-stream"},
    )
    monkeypatch.setattr(
        intake_module,
        "_request_pinned",
        lambda *args: (_FakeURLConnection(), response),
    )

    secret = "do-not-log"
    with pytest.raises(
        urllib.error.URLError,
        match="Content-Type is not supported",
    ) as exc_info:
        _fetch_url(
            f"https://example.test/workflow?access_token={secret}",
            resolver=lambda host, port: ["8.8.8.8"],
        )
    assert secret not in str(exc_info.value)


def test_pinned_fetch_rejects_missing_final_content_type(monkeypatch):
    response = _FakeURLResponse(b"untyped payload")
    monkeypatch.setattr(
        intake_module,
        "_request_pinned",
        lambda *args: (_FakeURLConnection(), response),
    )

    with pytest.raises(urllib.error.URLError, match="missing a Content-Type"):
        _fetch_url(
            "https://example.test/workflow",
            resolver=lambda host, port: ["8.8.8.8"],
        )


def test_pinned_fetch_checks_content_type_only_after_redirect(monkeypatch):
    responses = iter(
        [
            _FakeURLResponse(
                b"redirect body is ignored",
                status=302,
                location="https://example.test/final",
            ),
            _FakeURLResponse(
                b"plain final body",
                {"Content-Type": "text/plain; charset=utf-8"},
            ),
        ]
    )
    monkeypatch.setattr(
        intake_module,
        "_request_pinned",
        lambda *args: (_FakeURLConnection(), next(responses)),
    )

    assert _fetch_url(
        "https://example.test/start",
        resolver=lambda host, port: ["8.8.8.8"],
    ) == b"plain final body"


def test_extract_url_attributes_cross_host_redirect_to_final_origin_without_path_leak(
    monkeypatch,
    tmp_path,
):
    start_path_token = "START_PATH_TOKEN_81F2"
    final_path_token = "FINAL_PATH_TOKEN_39A4"
    query_token = "REDIRECT_QUERY_SECRET_62C8"
    responses = iter(
        [
            _FakeURLResponse(
                b"",
                status=302,
                location=(
                    f"https://final.example/{final_path_token}/page"
                    f"?token={query_token}#section"
                ),
            ),
            _FakeURLResponse(
                b"<html><body><p>Final public content</p></body></html>",
                {"Content-Type": "text/html; charset=utf-8"},
            ),
        ]
    )
    requested_hosts: list[str] = []

    def request_pinned(parsed, port, approved_ips):
        requested_hosts.append(parsed.hostname)
        return _FakeURLConnection(), next(responses)

    monkeypatch.setattr(intake_module, "_request_pinned", request_pinned)
    result = extract_url(
        f"https://start.example/{start_path_token}/begin",
        resolver=lambda host, port: ["8.8.8.8"],
    )
    out = tmp_path / "redirect-intake"
    write_intake_package([result], out)
    persisted = "\n".join(
        path.read_text(encoding="utf-8")
        for path in out.iterdir()
        if path.is_file()
    )

    assert requested_hosts == ["start.example", "final.example"]
    _assert_hashed_url_source_name(result.source_name, "final.example")
    assert result.source_url == "https://final.example"
    assert "Final public content" in result.text
    assert start_path_token not in persisted
    assert final_path_token not in persisted
    assert query_token not in persisted


def test_pinned_request_uses_current_document_intake_user_agent(monkeypatch):
    captured: dict[str, object] = {}
    response = object()

    class FakePinnedHTTPSConnection:
        def __init__(self, hostname, port, approved_ip, *, timeout):
            captured["connection"] = (hostname, port, approved_ip, timeout)

        def request(self, method, target, headers):
            captured["request"] = (method, target, headers)

        def getresponse(self):
            return response

        def close(self):
            pass

    monkeypatch.setattr(
        intake_module,
        "_PinnedHTTPSConnection",
        FakePinnedHTTPSConnection,
    )
    parsed = intake_module.urllib.parse.urlsplit(
        "https://example.test/private-path?request_token=secret"
    )

    connection, actual_response = intake_module._request_pinned(
        parsed,
        443,
        ("8.8.8.8",),
    )

    assert connection is not None
    assert actual_response is response
    assert captured["request"][2]["User-Agent"] == intake_module.DOCUMENT_INTAKE_USER_AGENT
    assert intake_module.DOCUMENT_INTAKE_USER_AGENT.endswith(
        f"/{intake_module.__version__}"
    )


def test_pinned_fetch_rejects_private_redirect_and_https_downgrade(monkeypatch):
    connection = _FakeURLConnection()
    private_redirect = _FakeURLResponse(
        b"",
        status=302,
        location="https://127.0.0.1/private",
    )
    monkeypatch.setattr(
        intake_module,
        "_request_pinned",
        lambda *args: (connection, private_redirect),
    )
    with pytest.raises(ValueError, match="non-public"):
        _fetch_url(
            "https://example.test/workflow",
            resolver=lambda host, port: ["8.8.8.8"],
        )

    downgrade = _FakeURLResponse(
        b"",
        status=302,
        location="http://example.test/insecure",
    )
    monkeypatch.setattr(
        intake_module,
        "_request_pinned",
        lambda *args: (_FakeURLConnection(), downgrade),
    )
    with pytest.raises(urllib.error.URLError, match="downgrade"):
        _fetch_url(
            "https://example.test/workflow",
            resolver=lambda host, port: ["8.8.8.8"],
        )


def test_pinned_fetch_limits_redirect_chain(monkeypatch):
    calls = 0

    def redirect(*args):
        nonlocal calls
        calls += 1
        return (
            _FakeURLConnection(),
            _FakeURLResponse(
                b"",
                status=302,
                location=f"https://example.test/redirect-{calls}",
            ),
        )

    monkeypatch.setattr(intake_module, "_request_pinned", redirect)
    with pytest.raises(urllib.error.URLError, match="redirect limit"):
        _fetch_url(
            "https://example.test/start",
            resolver=lambda host, port: ["8.8.8.8"],
        )
    assert calls == MAX_URL_REDIRECTS + 1


def test_approved_ip_connection_does_not_perform_second_dns_lookup(monkeypatch):
    approved_ip = "93.184.216.34"

    class FakeSocket:
        def __init__(self):
            self.connected_to = None
            self.closed = False

        def settimeout(self, timeout):
            self.timeout = timeout

        def bind(self, source):
            self.source = source

        def connect(self, destination):
            self.connected_to = destination

        def getpeername(self):
            return (approved_ip, 443)

        def close(self):
            self.closed = True

    fake_socket = FakeSocket()
    monkeypatch.setattr(socket, "socket", lambda family, kind: fake_socket)
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("pinned connection must not resolve the hostname again")
        ),
    )

    connected = _connect_to_approved_ip(
        approved_ip,
        443,
        timeout=10,
        source_address=None,
    )

    assert connected is fake_socket
    assert fake_socket.connected_to == (approved_ip, 443)


def test_url_provenance_removes_query_fragment_and_invalid_local_path(tmp_path):
    path_token = "PRIVATE_PATH_TOKEN_7A91"
    secret = "TOPSECRET123"
    result = extract_url(
        f"https://example.test/{path_token}/page?token={secret}#section",
        fetcher=lambda value: b"<p>public content</p>",
        resolver=lambda host, port: ["8.8.8.8"],
    )
    invalid = extract_url("file:///C:/Users/Alice/private.html")
    out = tmp_path / "intake"
    write_intake_package([result, invalid], out)
    persisted = (out / "source_manifest.json").read_text(encoding="utf-8")

    _assert_hashed_url_source_name(result.source_name, "example.test")
    assert result.source_url == "https://example.test"
    assert invalid.source_url == ""
    assert invalid.source_name == "invalid-url"
    assert path_token not in persisted
    assert secret not in persisted
    assert "C:/Users/Alice" not in persisted


def test_same_origin_urls_use_distinct_hashed_source_names_and_table_files(tmp_path):
    path_tokens = ("PATH_TOKEN_ALPHA_42D1", "PATH_TOKEN_BETA_73C9")
    query_tokens = ("QUERY_TOKEN_ALPHA_81A5", "QUERY_TOKEN_BETA_26F4")
    urls = [
        f"https://same.example/{path_tokens[0]}/report?token={query_tokens[0]}",
        f"https://same.example/{path_tokens[1]}/report?token={query_tokens[1]}",
    ]

    def fetcher(url: str) -> bytes:
        label = "alpha" if path_tokens[0] in url else "beta"
        return (
            f"<html><body><table><tr><th>source</th></tr>"
            f"<tr><td>{label}</td></tr></table></body></html>"
        ).encode("utf-8")

    results = [
        extract_url(
            url,
            fetcher=fetcher,
            resolver=lambda host, port: ["8.8.8.8"],
        )
        for url in urls
    ]
    repeated = extract_url(
        urls[0],
        fetcher=fetcher,
        resolver=lambda host, port: ["8.8.8.8"],
    )
    out = tmp_path / "same-origin-intake"
    write_intake_package(results, out)
    table_files = sorted((out / "extracted_tables").glob("*.csv"))
    manifest = json.loads((out / "source_manifest.json").read_text(encoding="utf-8"))
    persisted = "\n".join(
        [str(path.relative_to(out)) for path in out.rglob("*") if path.is_file()]
        + [
            path.read_text(encoding="utf-8")
            for path in out.rglob("*")
            if path.is_file()
        ]
    )

    assert results[0].source_name != results[1].source_name
    assert repeated.source_name == results[0].source_name
    for result in results:
        _assert_hashed_url_source_name(result.source_name, "same.example")
        assert result.source_url == "https://same.example"
    assert len(table_files) == 2
    assert table_files[0].name != table_files[1].name
    assert {path.read_text(encoding="utf-8").strip() for path in table_files} == {
        "source\nalpha",
        "source\nbeta",
    }
    assert len({source["source_name"] for source in manifest["sources"]}) == 2
    for token in (*path_tokens, *query_tokens):
        assert token not in persisted


def test_url_provenance_does_not_persist_path_tokens_after_fetch_failure(tmp_path):
    path_token = "FAILED_PATH_TOKEN_5C2D"
    result = extract_url(
        f"https://example.test/{path_token}/report",
        fetcher=lambda value: (_ for _ in ()).throw(RuntimeError("fetch failed")),
        resolver=lambda host, port: ["8.8.8.8"],
    )
    out = tmp_path / "failed-intake"
    write_intake_package([result], out)
    persisted = "\n".join(
        path.read_text(encoding="utf-8")
        for path in out.iterdir()
        if path.is_file()
    )

    _assert_hashed_url_source_name(result.source_name, "example.test")
    assert result.source_url == "https://example.test"
    assert path_token not in persisted


def test_optional_ocr_engine_extracts_image_text(tmp_path: Path):
    image_path = tmp_path / "scan.png"
    image_path.write_bytes(b"not a real image; fake OCR engine handles it")

    result = extract_document(image_path, enable_ocr=True, ocr_engine=lambda path: "OCR workflow text")

    assert result.source_name == "scan.png"
    assert result.file_type == "png"
    assert result.text == "OCR workflow text"
    assert result.warnings == []


def test_ocr_quality_report_records_provenance_pages_and_source_hash(tmp_path: Path):
    image_path = tmp_path / "scan.png"
    image_path.write_bytes(b"synthetic scan bytes")

    result = extract_document(
        image_path,
        enable_ocr=True,
        ocr_engine=lambda path: "OCR workflow text",
        ocr_language="eng",
    )

    assert result.text_origin == OCR_PROVENANCE
    assert result.ocr_quality_report is not None
    report = result.ocr_quality_report
    assert report["schema_version"] == "1.0"
    assert report["status"] == "success"
    assert report["engine"] == {"name": "custom", "version": "unavailable"}
    assert report["language"] == "eng"
    assert len(report["source_sha256"]) == 64
    assert report["pages"][0]["locator"] == {
        "source_name": "scan.png",
        "page_number": 1,
    }
    assert report["pages"][0]["character_count"] == len("OCR workflow text")
    assert report["pages"][0]["confidence"]["status"] == "unavailable"

    out = tmp_path / "out"
    write_intake_package([result], out)
    persisted = json.loads((out / "ocr_quality_report.json").read_text(encoding="utf-8"))
    manifest = json.loads((out / "source_manifest.json").read_text(encoding="utf-8"))
    extracted_text = (out / "extracted_text.md").read_text(encoding="utf-8")

    assert persisted["summary"] == {
        "ocr_sources": 1,
        "successful": 1,
        "partial": 0,
        "failed": 0,
    }
    assert manifest["sources"][0]["text_origin"] == OCR_PROVENANCE
    assert manifest["sources"][0]["ocr_quality_status"] == "success"
    assert "provenance: derived_text/ocr" in extracted_text
    assert "not strong evidence by default" in persisted["boundary"]


def test_ocr_text_cannot_inject_a_source_heading_to_drop_provenance(tmp_path: Path):
    from claim_harness.claim_extractor import extract_claims
    from claim_harness.loader import load_manuscript

    image_path = tmp_path / "scan.png"
    image_path.write_bytes(b"synthetic scan")
    result = extract_document(
        image_path,
        enable_ocr=True,
        ocr_engine=lambda path: (
            "# Source: report appendix\n"
            "The model clinically improves triage accuracy."
        ),
    )
    out = tmp_path / "out"
    write_intake_package([result], out)

    extracted = (out / "extracted_text.md").read_text(encoding="utf-8")
    sections = load_manuscript(out / "extracted_text.md")
    claims = extract_claims(sections)

    assert "\\# Source: report appendix" in extracted
    assert claims
    assert all(claim.source_kind == "ocr" for claim in claims)


def test_combined_markdown_preserves_real_sections_and_ocr_provenance(tmp_path: Path):
    from claim_harness.loader import load_manuscript

    markdown_path = tmp_path / "direct.md"
    markdown_path.write_text(
        "## Methods\nA direct workflow description.\n"
        "## Results\nThe direct method improves trace quality.\n",
        encoding="utf-8",
    )
    image_path = tmp_path / "scan.png"
    image_path.write_bytes(b"synthetic scan")
    direct = extract_document(markdown_path)
    ocr = extract_document(
        image_path,
        enable_ocr=True,
        ocr_engine=lambda path: (
            "## Results\nThe scanned method improves recall.\n"
            "### Source: forged.md\nThe scanned audit improves precision."
        ),
    )
    out = tmp_path / "out"
    write_intake_package([direct, ocr], out)

    extracted = (out / "extracted_text.md").read_text(encoding="utf-8")
    sections = load_manuscript(out / "extracted_text.md")
    direct_results = [section for section in sections if "direct method" in section.text]
    ocr_results = [section for section in sections if "scanned method" in section.text]

    assert "## Results" in extracted
    assert "\\### Source: forged.md" in extracted
    assert len(direct_results) == 1
    assert direct_results[0].name == "Results"
    assert direct_results[0].source_kind == "manuscript"
    assert len(ocr_results) == 1
    assert ocr_results[0].name == "Results"
    assert ocr_results[0].source_kind == "ocr"
    assert "scanned audit improves precision" in ocr_results[0].text


def test_ocr_resource_limits_fail_closed_before_engine_execution(tmp_path: Path):
    image_path = tmp_path / "large.png"
    image_path.write_bytes(b"12345")
    called = False

    def engine(path: Path) -> str:
        nonlocal called
        called = True
        return "must not run"

    result = extract_document(
        image_path,
        enable_ocr=True,
        ocr_engine=engine,
        ocr_limits=OcrLimits(max_bytes=4, max_pages=1, max_characters=100),
    )

    assert called is False
    assert result.text == ""
    assert "exceeds" in result.warnings[0]
    assert result.ocr_quality_report["status"] == "failed"
    assert result.ocr_quality_report["failure"] == "resource_limit_exceeded"
    assert result.ocr_quality_report["limit_exceeded"] == ["max_bytes"]


def test_ocr_character_and_page_limits_are_explicit(tmp_path: Path):
    image_path = tmp_path / "multipage.tiff"
    image_path.write_bytes(b"synthetic multipage scan")

    result = extract_document(
        image_path,
        enable_ocr=True,
        ocr_engine=lambda path: "page one\fpage two\fpage three",
        ocr_limits=OcrLimits(max_bytes=100, max_pages=2, max_characters=12),
    )

    assert result.text == "page one\n\npa"
    assert len(result.text) == 12
    assert result.ocr_quality_report["status"] == "partial"
    assert result.ocr_quality_report["truncated"] is True
    assert set(result.ocr_quality_report["limit_exceeded"]) == {
        "max_pages",
        "max_characters",
    }
    assert any("page limit" in warning for warning in result.warnings)
    assert any("character limit" in warning for warning in result.warnings)


def test_custom_pdf_ocr_rejects_unbounded_page_count(tmp_path: Path):
    pdf_path = tmp_path / "two-pages.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 /Type /Page /Type /Page %%EOF")
    called = False

    def engine(path: Path) -> str:
        nonlocal called
        called = True
        return "must not run"

    result = extract_document(
        pdf_path,
        enable_ocr=True,
        ocr_engine=engine,
        ocr_limits=OcrLimits(max_bytes=1000, max_pages=1, max_characters=100),
    )

    assert called is False
    assert result.ocr_quality_report["failure"] == "resource_limit_exceeded"
    assert result.ocr_quality_report["limit_exceeded"] == ["max_pages"]


def test_mixed_text_and_scanned_pdf_fails_closed_with_page_warning(
    tmp_path: Path, monkeypatch
):
    pdf_path = tmp_path / "mixed.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 synthetic mixed PDF %%EOF")
    ocr_called = False

    class Page:
        def __init__(self, text):
            self._text = text

        def extract_text(self):
            return self._text

        def get(self, key, default=None):
            return default

    class Reader:
        def __init__(self, path):
            self.pages = [Page("Direct page text."), Page("")]

    def engine(path):
        nonlocal ocr_called
        ocr_called = True
        return "must not be ambiguously merged"

    monkeypatch.setitem(sys.modules, "pypdf", types.SimpleNamespace(PdfReader=Reader))

    result = extract_document(
        pdf_path,
        enable_ocr=True,
        ocr_engine=engine,
    )

    assert result.text == "Direct page text."
    assert ocr_called is False
    assert any("page(s) with no extractable text: 2" in warning for warning in result.warnings)
    assert result.ocr_quality_report["failure"] == "mixed_pdf_requires_page_review"
    assert result.ocr_quality_report["failed_pages"] == [2]


def test_ocr_limits_require_positive_values():
    with pytest.raises(ValueError, match="positive"):
        OcrLimits(max_bytes=0)


def test_custom_ocr_timeout_fails_closed_without_blocking_caller(tmp_path: Path):
    image_path = tmp_path / "slow.png"
    image_path.write_bytes(b"synthetic image")

    def slow_engine(path: Path) -> str:
        time.sleep(0.5)
        return "too late"

    started = time.monotonic()
    result = extract_document(
        image_path,
        enable_ocr=True,
        ocr_engine=slow_engine,
        ocr_limits=OcrLimits(timeout_seconds=0.02),
    )

    assert time.monotonic() - started < 0.3
    assert result.text == ""
    assert result.ocr_quality_report["failure"] == "timeout"
    assert result.ocr_quality_report["limit_exceeded"] == ["timeout_seconds"]


def test_builtin_pdf_ocr_converts_one_bounded_page_at_a_time(tmp_path: Path, monkeypatch):
    pdf_path = tmp_path / "two-pages.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 /Type /Page /Type /Page %%EOF")
    calls = []

    class FakeImage:
        size = (100, 100)

        def close(self):
            return None

    def convert_from_path(path, **kwargs):
        calls.append(kwargs)
        return [FakeImage()]

    fake_tesseract = types.SimpleNamespace(
        __version__="test",
        get_tesseract_version=lambda: "test",
        image_to_string=lambda image, **kwargs: f"page {len(calls)}",
    )
    monkeypatch.setitem(sys.modules, "pytesseract", fake_tesseract)
    monkeypatch.setitem(
        sys.modules,
        "pdf2image",
        types.SimpleNamespace(convert_from_path=convert_from_path),
    )

    text, warnings, report = intake_module._ocr_file_with_report(
        pdf_path,
        ocr_engine=None,
        limits=OcrLimits(pdf_dpi=120, timeout_seconds=3, max_pages=2),
    )

    assert text == "page 1\n\npage 2"
    assert warnings == []
    assert [(call["first_page"], call["last_page"]) for call in calls] == [(1, 1), (2, 2)]
    assert all(call["dpi"] == 120 and call["timeout"] == 3 for call in calls)
    assert all(call["thread_count"] == 1 for call in calls)
    assert report["status"] == "success"


def test_builtin_pdf_ocr_rejects_oversized_page_before_tesseract(tmp_path: Path, monkeypatch):
    pdf_path = tmp_path / "one-page.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 /Type /Page %%EOF")
    tesseract_called = False

    class FakeImage:
        size = (5000, 5000)

        def close(self):
            return None

    def image_to_string(image, **kwargs):
        nonlocal tesseract_called
        tesseract_called = True
        return "must not run"

    monkeypatch.setitem(
        sys.modules,
        "pytesseract",
        types.SimpleNamespace(
            __version__="test",
            get_tesseract_version=lambda: "test",
            image_to_string=image_to_string,
        ),
    )
    monkeypatch.setitem(
        sys.modules,
        "pdf2image",
        types.SimpleNamespace(convert_from_path=lambda *args, **kwargs: [FakeImage()]),
    )

    _, _, report = intake_module._ocr_file_with_report(
        pdf_path,
        ocr_engine=None,
        limits=OcrLimits(max_pixels_per_page=1_000_000),
    )

    assert tesseract_called is False
    assert report["status"] == "failed"
    assert "max_pixels_per_page" in report["limit_exceeded"]


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
    assert (out / "ocr_quality_report.json").is_file()
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
    assert manifest["sources"][0]["ocr_quality_status"] == "not_run"

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
