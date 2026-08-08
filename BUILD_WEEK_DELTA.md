# OpenAI Build Week 2026: Pre-existing Baseline and New Work

This file distinguishes the repository that existed before the submission
period from work added during OpenAI Build Week. It is intended to be read
alongside the dated Git history and the primary Codex task `/feedback` Session
ID supplied in the Devpost submission.

## Pre-existing project

Baseline tag: `pre-build-week-2026`

Baseline commit: `b5e9960` (`2026-07-12 02:43:27 +0100`)

The baseline already included:

- the local-first ProblemBridge question-discovery and workflow-alignment flow;
- the bilingual Streamlit workbench;
- deterministic ClaimHarness manuscript claim extraction, evidence retrieval,
  verification, reports, and trace artifacts;
- optional advisory remote-provider summaries in the ClaimHarness CLI;
- evidence contracts, evaluation protocols, project lifecycle records, static
  report viewing, synthetic examples, tests, and Windows release tooling.

These capabilities are not presented as Build Week work.

## Build Week additions

Work implemented after the submission period opened on 13 July 2026:

- an Evidence-Gated Build Mode connecting ProblemBridge proposals to a
  ClaimHarness capability-claim gate;
- an explicit GPT-5.6 Responses API runtime path for structured workflow
  interpretation and candidate capability claims;
- auditable retain, downgrade, remove, and abstain decisions for every proposed
  capability claim;
- a Codex Handoff Pack containing `AGENTS.md`, `SPEC.md`, `TASKS.md`,
  `acceptance_tests.yaml`, `evidence_contract.yaml`, `risk_register.md`, and
  `demo_scenario.md`;
- a replayable build record with input/output hashes and non-secret model
  metadata;
- a judge-ready UI and CLI path, synthetic demo, automated tests, and submission
  documentation.

## Evidence boundary

The deterministic `mock` path remains the default so judges can run the full
workflow without an API key. It demonstrates the product flow but does not
claim that GPT-5.6 was called. A completed `--llm openai` run records the
GPT-5.6 model and response identifier in `gpt_5_6_runtime.json`; this is the
runtime evidence used for the competition demonstration.
