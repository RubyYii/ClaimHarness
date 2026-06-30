# Document Intake Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a local document intake layer that converts `.docx`, text-based `.pdf`, `.txt`, `.md`, and `.csv` files into auditable Markdown/CSV extraction outputs before Question Discovery, ProblemBridge, or ClaimHarness.

**Architecture:** Create a focused `problem_bridge.document_intake` module with dataclasses, extension dispatch, docx XML extraction, optional pypdf PDF extraction, and writers for `extracted_text.md`, `extracted_tables/`, `source_manifest.json`, and `extraction_warnings.md`. Expose the intake workflow in the Streamlit wizard and document its safety boundary.

**Tech Stack:** Python standard library (`zipfile`, `xml.etree.ElementTree`, `csv`, `json`), optional `pypdf` dependency for text-based PDFs, Streamlit upload UI, pytest.

---

### Task 1: Core Intake Tests And Module

**Files:**
- Create: `tests/test_document_intake.py`
- Create: `problem_bridge/document_intake.py`
- Modify: `pyproject.toml`

- [ ] Write tests for `.docx`, `.txt`, `.md`, `.csv`, unsupported extension warnings, and package output file names.
- [ ] Run tests and confirm they fail because the module does not exist.
- [ ] Implement `extract_document`, `write_intake_package`, and `build_problem_seed_from_intake`.
- [ ] Add `pypdf>=4.0` as the PDF parser dependency while keeping a warning fallback if unavailable.
- [ ] Run targeted tests and confirm they pass.

### Task 2: UI Integration

**Files:**
- Modify: `apps/problem_bridge_wizard.py`
- Modify: `tests/test_release_readiness.py`

- [ ] Add release-readiness assertions for `Document intake`, `extracted_text.md`, `source_manifest.json`, and `text-based PDF`.
- [ ] Run the new assertion and confirm it fails.
- [ ] Add a `Document intake` page with file uploader, extraction output viewer, and zip download.
- [ ] Run targeted release-readiness tests and Python compile.

### Task 3: Documentation And Release Verification

**Files:**
- Modify: `README.md`
- Modify: `README.zh-CN.md`
- Modify: `NON_AI_USER_GUIDE.md`
- Modify: `docs/static_showcase/en.html`
- Modify: `docs/static_showcase/zh-CN.html`

- [ ] Document supported file types and limitations: text-based PDFs only, no OCR, no image understanding, no professional judgement.
- [ ] Run full pytest, ProblemBridge demo, ClaimHarness demo, build release zip, and test release zip.
- [ ] Commit and push to `main`.
