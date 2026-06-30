# Question Discovery Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a local Question Discovery Layer that helps non-AI users produce useful questions, stakeholder targets, and validation unknowns before they discuss AI task design.

**Architecture:** Add a deterministic `problem_bridge.question_discovery` module with small dataclasses, a package builder, and a writer for Markdown handoff files. Integrate it into the Streamlit wizard as the first page before guided interview and alignment generation.

**Tech Stack:** Python dataclasses, pathlib Markdown writers, existing Streamlit wizard, pytest release-readiness checks.

---

### Task 1: Core Discovery Model

**Files:**
- Create: `problem_bridge/question_discovery.py`
- Test: `tests/test_problem_bridge_question_discovery.py`

- [ ] Write failing tests for categorized discovery questions, stakeholder map contents, and package file output.
- [ ] Run targeted tests and confirm they fail because the module does not exist.
- [ ] Implement the minimal dataclasses and deterministic builder.
- [ ] Implement package writer for `question_brief.md`, `stakeholder_map.md`, `expert_interview_guide.md`, `unknowns_to_validate.md`, and `discussion_plan.md`.
- [ ] Run targeted tests and confirm they pass.

### Task 2: Guided UI Entry

**Files:**
- Modify: `apps/problem_bridge_wizard.py`
- Test: `tests/test_release_readiness.py`

- [ ] Add release-readiness assertions for `Question discovery`, `Who to ask`, `Questions to validate`, and `Do not propose a solution yet`.
- [ ] Run release-readiness tests and confirm the new assertions fail.
- [ ] Add a `Question discovery` sidebar page before the domain practitioner wizard.
- [ ] Render generated discovery package files and offer zip download.
- [ ] Run release-readiness tests and confirm they pass.

### Task 3: Documentation And Showcase

**Files:**
- Modify: `README.md`
- Modify: `README.zh-CN.md`
- Modify: `NON_AI_USER_GUIDE.md`
- Modify: `docs/static_showcase/en.html`
- Modify: `docs/static_showcase/zh-CN.html`

- [ ] Document the new layer as the first step before ProblemBridge alignment.
- [ ] Explain that local mode does not need an API because it uses deterministic rule-based question routing.
- [ ] Keep safety language: no private data, no clinical or education-policy authority claims.
- [ ] Run full verification, build release zip, test release zip, then commit and push.
