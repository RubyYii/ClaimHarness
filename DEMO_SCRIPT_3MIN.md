# 3-Minute Demo Script

## 0:00-0:30 Problem

Interdisciplinary AI projects often fail because the original domain problem is compressed into the wrong AI task. A medical workflow becomes a segmentation task, a cultural interpretation problem becomes captioning, or an educational risk problem becomes factual QA.

## 0:30-1:20 ProblemBridge

Run:

```powershell
.venv\Scripts\python.exe -m problem_bridge demo
```

Show:

- `problem_card.md`
- `workflow_map.md`
- `concept_alignment_table.csv`
- `ai_task_spec.yaml`
- `evidence_contract.yaml`
- `evaluation_protocol.md`

Explain:

ProblemBridge turns a domain problem into an aligned AI task package. It reconstructs workflow, identifies pain points, maps domain concepts to AI representations, defines evidence expectations, and flags misalignment risks.

## 1:20-2:10 ClaimHarness

Run:

```powershell
.venv\Scripts\python.exe -m claim_harness demo
```

Show:

- `claim_table.csv`
- `audit_report.md`
- `revision_suggestions.md`
- `index.html`
- `agent_trace.jsonl`

Explain:

ClaimHarness checks whether generated or written claims are supported by available evidence. It flags weak support, overclaiming, and human-review needs.

## 2:10-3:00 Why It Matters

Together, the two modules support:

- domain workflow discovery
- AI task formulation
- evidence standard alignment
- evaluation alignment
- overclaim detection
- human review routing

The short version:

```text
ProblemBridge keeps the problem from drifting before AI work begins.
ClaimHarness keeps claims from overreaching after outputs exist.
```
