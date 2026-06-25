# ProblemBridge MVP Design

## Product Positioning

ProblemBridge is a workflow discovery and problem alignment harness for interdisciplinary AI projects. It helps domain practitioners turn implicit workflows, pain points, evidence standards, and human decision boundaries into structured AI-ready specifications. It helps AI practitioners check whether a proposed AI task remains faithful to the original domain problem.

ProblemBridge is not STORM, RAG, a writing assistant, an automatic reviewer, or a clinical/educational/cultural authority. It is a deterministic first-pass alignment package generator. ClaimHarness remains the downstream claim-evidence audit module; ProblemBridge is the upstream problem-alignment layer.

## Users

Domain practitioners use ProblemBridge when they know a workflow is painful but do not know how to make it AI-ready. The MVP should expose workflow steps, pain points, AI opportunities, risk, evidence expectations, and human review boundaries.

AI practitioners use ProblemBridge when they have an AI idea but need to avoid distorting the domain problem. The MVP should produce task specs, concept alignment tables, evaluation protocols, misalignment risks, and implementation routes.

## CLI Surface

The MVP adds a sister package named `problem_bridge` inside the current repository.

```powershell
.venv\Scripts\python.exe -m problem_bridge demo
```

```powershell
.venv\Scripts\python.exe -m problem_bridge align `
  --brief examples/problem_bridge/hsg/problem.md `
  --out outputs/hsg_alignment `
  --llm mock
```

The only supported provider in MVP is `mock`. The mock mode is deterministic and local-first.

## Inputs

The MVP reads one Markdown problem brief. Examples live under:

```text
examples/problem_bridge/
  hsg/problem.md
  chinese_painting/problem.md
  political_education/problem.md
```

The examples are synthetic and must not contain private medical data, patient records, confidential manuscripts, or real sensitive educational records.

## Outputs

Each run writes a Problem Alignment Package:

```text
problem_card.md
workflow_map.md
painpoint_opportunity_matrix.csv
concept_alignment_table.csv
ai_task_spec.yaml
evidence_contract.yaml
evaluation_protocol.md
misalignment_risk_report.md
human_in_loop_plan.md
implementation_routes.md
alignment_trace.jsonl
```

The trace records loading, classification, package construction, and file-writing steps.

## Mock Alignment Behavior

The mock pipeline detects one of four profiles from the problem brief:

- `hsg`: HSG evidence-ready second-reader support.
- `chinese_painting`: VLM understanding of Chinese painting commentary.
- `political_education`: LLM risk evaluation in value-sensitive political theory education.
- `generic`: a conservative fallback for unknown interdisciplinary problems.

Each profile returns deterministic content for:

- domain workflow map
- pain point to opportunity mapping
- concept alignment table
- AI task specification
- evidence contract
- evaluation protocol
- misalignment risks
- human-in-the-loop plan
- implementation routes

## Boundaries

ProblemBridge must not claim that any output is clinically valid, educationally approved, culturally authoritative, deployment-ready, or a substitute for domain experts. For high-risk domains, the output should explicitly prefer support, review, evidence sidecars, and human approval over autonomous decisions.

## Tests

Tests should cover:

- package import and CLI help
- `demo` creates all expected files
- `align --brief ... --llm mock` creates deterministic HSG outputs
- unsupported LLM provider fails clearly
- concept alignment CSV headers include alignment status and misalignment risk
- trace contains ordered pipeline steps
- all bundled examples can generate packages

## Documentation

README should explain:

- ClaimHarness audits claim-evidence alignment.
- ProblemBridge aligns domain workflow, AI task specification, evidence contract, and evaluation protocol.
- ProblemBridge differs from STORM/RAG because it does not generate generic topic reports; it prevents problem-formulation drift before model building.
