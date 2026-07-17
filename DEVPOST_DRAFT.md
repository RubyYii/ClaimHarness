# Devpost Draft

## Project name

ProblemBridge: From Fuzzy Workflows to Evidence-Gated AI Build Contracts

## Tagline

Turn an expert's informal workflow into a testable Codex build contract without
letting unsupported AI capability claims enter implementation.

## Inspiration

Interdisciplinary AI projects often fail before modelling begins. A domain
expert describes a real workflow, that description is compressed into an AI
task, and plausible-sounding capability promises enter the plan without a clear
evidence standard or human-review boundary.

## What it does

ProblemBridge guides a user from documents and vague concerns to a workflow map,
AI task specification, evidence contract, evaluation protocol, and explicit
human boundaries. The Build Week extension then asks GPT-5.6 for a strict
structured build proposal. ClaimHarness audits every candidate capability
claim, assigning an evidence status and one of four actions: retain, downgrade,
remove, or abstain. The accepted result becomes a Codex Handoff Pack with a
specification, tasks, acceptance tests, evidence contract, risk register, and
replayable provenance record.

## How we built it

The project uses Python 3.10+, Pydantic, Typer, Streamlit, and inspectable
Markdown/CSV/JSON/YAML/JSONL artifacts. GPT-5.6 is called through the OpenAI
Responses API with strict Structured Outputs. A deterministic ClaimHarness gate
validates evidence references and rejects autonomous authority, guarantees, and
unsupported claims. The default mock path requires no API key so judges can run
the complete workflow locally.

Codex was used in the primary Build Week task to audit the pre-existing
repository, establish the baseline, design the new cross-module contract,
implement the Responses API and UI paths, add tests and documentation, run the
judge commands, and review the final diff. Key product and safety decisions
remain documented in the repository and task history.

## Challenges

The main challenge was preserving a truthful evidence boundary. Workflow
artifacts can support a bounded design requirement, but they cannot prove
real-world model accuracy. The implementation therefore keeps GPT-5.6 advisory,
separates mock runs from verified GPT-5.6 runs, and records every downgrade.

## Accomplishments

- One continuous workflow from problem discovery to a Codex-ready build pack.
- Explicit evidence decisions for every model-proposed capability claim.
- A strict GPT-5.6 Responses API path plus a no-key deterministic judge path.
- Replayable, hash-linked runtime and handoff records without stored secrets.
- Synthetic examples, bilingual UI, Windows launcher, CLI, and automated tests.

## What we learned

The useful unit of governance is not the whole model response; it is each
individual capability claim and the evidence required to keep it. Linking
problem alignment to claim gating also gives Codex a much safer implementation
contract than a free-form product brief.

## What's next

Next steps are external usability testing with domain practitioners, stronger
evaluation datasets for capability-gate rules, and reviewed integrations for
additional evidence sources. The project will remain local-first and will not
expand into automated professional decision-making.

## Built with

Python, Pydantic, Typer, Streamlit, OpenAI GPT-5.6 Responses API, Codex, JSON
Schema, Markdown, CSV, JSON, YAML, and JSONL.
