# Guided Interview Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local, rule-based guided interview layer that actively asks follow-up questions, tracks what it understands about a domain workflow, and turns the resulting understanding into a ProblemBridge alignment brief.

**Architecture:** Add a small `problem_bridge.interview` module that owns interview questions, answer state, completeness scoring, missing-information routing, and final markdown generation. Update the Streamlit wizard to offer a step-by-step guided interview path next to the existing full-form path. Keep all behavior deterministic and API-free.

**Tech Stack:** Python dataclasses, existing ProblemBridge guided helpers, Streamlit session state, pytest.

---

### Task 1: Add Interview State Engine

**Files:**
- Create: `problem_bridge/interview.py`
- Test: `tests/test_problem_bridge_interview.py`

- [ ] Write failing tests for question order, state summary, missing information, completeness, and markdown generation.
- [ ] Implement `InterviewQuestion`, `InterviewState`, `UnderstandingSummary`, `start_interview`, `answer_question`, `next_question`, `summarize_understanding`, `is_ready_for_alignment`, and `build_problem_from_interview`.
- [ ] Verify tests pass.

### Task 2: Wire Interview Mode Into Streamlit

**Files:**
- Modify: `apps/problem_bridge_wizard.py`
- Test: `tests/test_release_readiness.py`

- [ ] Add release-readiness assertions for `Guided interview`, `Understanding so far`, `Next question`, and `Generate alignment package from interview`.
- [ ] Add a guided interview UI section using `st.session_state` to store answers.
- [ ] Keep the existing full form available as an advanced/manual option.
- [ ] Verify tests pass.

### Task 3: Document The Differentiator

**Files:**
- Modify: `README.md`
- Modify: `README.zh-CN.md`
- Modify: `docs/static_showcase/en.html`
- Modify: `docs/static_showcase/zh-CN.html`

- [ ] Explain that the differentiator is guided question routing, not just chatting.
- [ ] Explain that no API is required because the initial interview engine is local rule-based slot filling and confirmation.
- [ ] Verify docs tests pass.

### Task 4: Final Verification

**Commands:**
- `.venv\Scripts\python.exe -m pytest --basetemp=.pytest_tmp_run_codex`
- `.venv\Scripts\python.exe -m problem_bridge demo`
- `.venv\Scripts\python.exe -m claim_harness demo`
- `powershell -ExecutionPolicy Bypass -File scripts\build_release_zip_powershell.ps1`
- `powershell -ExecutionPolicy Bypass -File scripts\test_release_zip_powershell.ps1`

---

Self-review:
- Scope is one feature: a deterministic guided interview layer.
- No external API, database, login, deployment, or PDF/image work.
- The existing deterministic output pipeline remains the authority for package generation.