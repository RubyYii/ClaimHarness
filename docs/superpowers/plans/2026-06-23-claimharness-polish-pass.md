# ClaimHarness Polish Pass Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the next polish layer: CI, better packaging, a demo command, viewer filters, source-line and evidence-link explanations, sharper docs, stronger snapshot tests, and safer CLI errors.

**Architecture:** Keep the product CLI-first. Add small, local enhancements around the existing deterministic pipeline: schema fields for source line and evidence-link reasons, richer generated outputs, a static viewer with client-side filters, and a `demo` command that composes `run` plus `view`. Add GitHub Actions and package-data wiring without introducing a web framework or changing mock determinism.

**Tech Stack:** Python 3.10+, Typer, Pytest, Pydantic, pandas, standard-library HTML/JSON/CSV utilities, GitHub Actions.

---

## File Structure

- Create `.github/workflows/ci.yml`: run tests on push and pull request.
- Modify `pyproject.toml`: include package data and prompt package files.
- Create `claim_harness/prompts/audit_summary.md`: packaged prompt copy.
- Modify `claim_harness/llm.py`: load packaged prompts and include evidence context in optional provider payload.
- Modify `claim_harness/schemas.py`: add `source_line` to `Claim` and `claim_link_reasons` to `EvidenceItem`.
- Modify `claim_harness/claim_extractor.py`: preserve source line numbers while extracting sentences.
- Modify `claim_harness/evidence_retriever.py`: record why each evidence item links to each claim.
- Modify `claim_harness/report_generator.py`: write `source_line`, evidence link reasons, and match explanations.
- Modify `claim_harness/report_viewer.py`: add status/risk filters and show evidence match reasons.
- Modify `claim_harness/cli.py`: add `demo` command and clearer input path validation.
- Modify `README.md`, `docs/architecture.md`, `docs/demo_walkthrough.md`, `docs/limitations.md`: document CI, demo, filters, source lines, and link reasons.
- Modify tests and add new tests for all behavior.

## Tasks

### Task 1: Protective Tests

- [ ] Add tests that initially fail for `source_line`, evidence `claim_link_reasons`, `demo` command, viewer filter controls, prompt packaging, and snapshot counts.
- [ ] Run targeted tests to confirm red state.

### Task 2: Traceability Fields

- [ ] Add `source_line` to `Claim`.
- [ ] Update claim extraction to attach approximate manuscript line numbers.
- [ ] Add `claim_link_reasons` to `EvidenceItem`.
- [ ] Update evidence retrieval to explain lexical-overlap and source-match links.
- [ ] Update generated CSV/JSON/Markdown and viewer rendering.

### Task 3: Demo Command and CLI Errors

- [ ] Add `claim_harness demo --out outputs/oocyte_demo_run`.
- [ ] Validate input paths before loading and report missing files or table folders clearly.
- [ ] Ensure `demo` runs deterministic mock audit and generates `index.html`.

### Task 4: Viewer Filters

- [ ] Add native JavaScript filter controls for all, weak-or-worse, high-risk, supported, and overclaimed claims.
- [ ] Use `data-status` and `data-risk` attributes on rows.
- [ ] Keep no-build, static HTML behavior.

### Task 5: CI and Packaging

- [ ] Add GitHub Actions workflow.
- [ ] Package prompt data under `claim_harness/prompts`.
- [ ] Update `load_prompt` to prefer root prompts during development and package prompts after installation.

### Task 6: Docs and Verification

- [ ] Refine README first screen.
- [ ] Update architecture/demo/limitations docs.
- [ ] Run full tests, demo generation, viewer generation, browser smoke check, visual gate fallback, commit, and push.

## Self-Review

- Scope covers the requested optimizations without adding PDF parsing, clinical validation, Streamlit, or a required server.
- No unresolved placeholder language remains.
- Deterministic mock output remains the source of truth; optional LLM output stays advisory.
