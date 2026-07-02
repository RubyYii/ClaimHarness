# PDF, Web, and Optional OCR Intake Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add lightweight HTML/URL intake, best-effort PDF annotations, and optional local OCR to the Document Intake Layer.

**Architecture:** Keep the existing `problem_bridge.document_intake` entry point and extend it with small helper functions. OCR is an optional adapter: deterministic tests can inject a fake OCR engine, while real runtime attempts local optional packages only when enabled.

**Tech Stack:** Python standard library for HTML parsing and URL fetching, existing CSV/JSON/Markdown outputs, optional `pytesseract`, `pdf2image`, and `Pillow` extras for OCR.

---

### Task 1: Document the Updated Scope

**Files:**
- Modify: `docs/superpowers/specs/2026-07-02-pdf-web-intake-design.md`
- Create: `docs/superpowers/plans/2026-07-02-pdf-web-ocr-intake.md`

- [ ] Update the design spec so OCR is optional, local, disabled by default, and warning-based when missing.
- [ ] Keep OCR out of default dependencies.
- [ ] Run `git diff --check`.

### Task 2: Add Failing Document Intake Tests

**Files:**
- Modify: `tests/test_document_intake.py`

- [ ] Add a test for `.html` extraction of title, headings, paragraph/list text, links, and table rows.
- [ ] Add a test for URL intake using a fake fetcher, with no external network.
- [ ] Add a test rejecting non-HTTP(S) URLs.
- [ ] Add a test for PDF annotation extraction from a simple synthetic PDF.
- [ ] Add a test for optional OCR on an image file using an injected fake OCR engine.
- [ ] Add a test for optional OCR on an image-only PDF using an injected fake OCR engine.
- [ ] Add a test that image upload without OCR records a clear warning.
- [ ] Run the new tests and verify they fail for missing behavior.

### Task 3: Implement Core Intake Helpers

**Files:**
- Modify: `problem_bridge/document_intake.py`

- [ ] Add `.html`, `.htm`, and common image suffixes to `SUPPORTED_EXTENSIONS`.
- [ ] Extend `extract_document(path, enable_ocr=False, ocr_engine=None)`.
- [ ] Implement HTML extraction with a small `HTMLParser` subclass.
- [ ] Implement `extract_url(url, fetcher=None)` using HTTP(S)-only validation.
- [ ] Implement best-effort raw PDF annotation extraction and attach records to existing annotation outputs.
- [ ] Implement optional OCR helpers with injected engine support and local dependency fallback.
- [ ] Keep old call sites working without new arguments.

### Task 4: Update UI and Docs

**Files:**
- Modify: `apps/problem_bridge_wizard.py`
- Modify: `README.md`
- Modify: `README.zh-CN.md`
- Modify: `tests/test_release_readiness.py`
- Modify: `pyproject.toml`

- [ ] Add `.html`, `.htm`, and image types to the uploader.
- [ ] Add a URL input area for public static webpages.
- [ ] Add an "Enable optional OCR" checkbox.
- [ ] Pass `enable_ocr` into document extraction.
- [ ] Add optional `ocr` extra dependencies without making OCR part of the default install.
- [ ] Update English and Chinese README boundaries.
- [ ] Update release-readiness assertions.

### Task 5: Verify and Publish

**Files:**
- All modified files.

- [ ] Run `tests/test_document_intake.py`.
- [ ] Run the targeted release-readiness test.
- [ ] Run full `.venv\Scripts\python.exe -m pytest`.
- [ ] Run `git diff --check`.
- [ ] Commit the implementation.
- [ ] Push `main` to GitHub.
