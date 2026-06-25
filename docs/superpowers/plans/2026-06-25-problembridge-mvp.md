# ProblemBridge MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a deterministic ProblemBridge MVP that generates workflow discovery and problem-alignment packages for interdisciplinary AI projects.

**Architecture:** Add a sister Python package named `problem_bridge` without changing the existing ClaimHarness pipeline. The package exposes a Typer CLI, loads a Markdown problem brief, selects a deterministic mock profile, builds structured alignment artifacts, writes Markdown/CSV/YAML/JSONL files, and documents how ProblemBridge relates to ClaimHarness.

**Tech Stack:** Python 3.10+, Typer, Pydantic, standard-library CSV/JSON/pathlib, pytest.

---

## File Structure

- Create `problem_bridge/__init__.py`: package version.
- Create `problem_bridge/__main__.py`: `python -m problem_bridge` entrypoint.
- Create `problem_bridge/cli.py`: Typer app with `demo` and `align`.
- Create `problem_bridge/schemas.py`: Pydantic models for profile content and rows.
- Create `problem_bridge/mock_profiles.py`: deterministic HSG, Chinese painting, political education, and generic profiles.
- Create `problem_bridge/generator.py`: profile detection and package construction.
- Create `problem_bridge/writer.py`: output file writers and JSONL trace helper.
- Create examples under `examples/problem_bridge/*/problem.md`.
- Modify `pyproject.toml`: include `problem_bridge*` packages and `problem-bridge` console script.
- Modify `README.md`: explain ProblemBridge usage and relation to ClaimHarness.
- Add tests in `tests/test_problem_bridge_cli.py` and `tests/test_problem_bridge_outputs.py`.

## Tasks

### Task 1: Failing CLI and Output Tests

- [ ] Add tests for package import, CLI help, unsupported provider error, demo output file creation, deterministic HSG align output, CSV headers, trace steps, and all bundled examples.
- [ ] Run `pytest tests/test_problem_bridge_cli.py tests/test_problem_bridge_outputs.py -v` and confirm failures are due to missing `problem_bridge`.

### Task 2: Package Skeleton and CLI

- [ ] Create `problem_bridge/__init__.py`, `__main__.py`, and `cli.py`.
- [ ] Implement `demo` and `align` command signatures with `--llm mock` validation.
- [ ] Run targeted CLI tests and confirm they now reach missing generator/output behavior.

### Task 3: Schemas and Mock Profiles

- [ ] Create `schemas.py` with row/profile/package models.
- [ ] Create `mock_profiles.py` with deterministic content for HSG, Chinese painting, political education, and generic fallback.
- [ ] Run profile-related targeted tests.

### Task 4: Generator and Writer

- [ ] Implement profile detection from problem brief text.
- [ ] Build package content and write all expected artifacts.
- [ ] Write ordered `alignment_trace.jsonl` steps.
- [ ] Run targeted ProblemBridge tests.

### Task 5: Examples and Docs

- [ ] Add three synthetic example briefs.
- [ ] Update README with ProblemBridge quickstart and relation to STORM/RAG/ClaimHarness.
- [ ] Update release-readiness tests if needed.

### Task 6: Verification and Publish

- [ ] Run `python -m problem_bridge demo`.
- [ ] Run `python -m problem_bridge align --brief examples/problem_bridge/hsg/problem.md --out outputs/hsg_alignment --llm mock`.
- [ ] Run full `pytest`.
- [ ] Check `git diff --check`.
- [ ] Commit and push.

## Self-Review

- The plan keeps ProblemBridge independent from ClaimHarness while documenting their relationship.
- MVP is deterministic and local; optional provider work is explicitly out of scope.
- No private data or deployment-validity claims are introduced.
- Each artifact in the design spec has an implementation task and test coverage.
