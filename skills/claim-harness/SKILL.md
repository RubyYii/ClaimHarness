---
name: claim-harness
description: Run local claim-evidence screening on a manuscript and CSV results, inspect source-bound findings, compare revisions, annotate missed statements, and record follow-up actions separately from program verdicts. Use for 论断证据核查, 版本比较, 漏检标注 or 核查处理记录. Works from Codex or Claude Code with the existing ClaimHarness backend.
---

# ClaimHarness

Help the user inspect what a manuscript says and which supplied results support it. Explain the actual screening scope before interpreting results: the deterministic extractor primarily recognizes supported patterns of English numerical claims. It is not comprehensive fact checking, peer review or clinical validation. Chinese discussion is supported; Chinese claim extraction coverage is not established.

## Runtime

Resolve this skill's `scripts/run.py` and run `python <absolute-runner-path> --check`. Installed `references/runtime.json` binds a local backend checkout and Python environment. Missing dependencies or a moved checkout require repair/reinstallation, not a silent switch to a cloud service. Read [commands.md](references/commands.md) for flags and complete examples.

Path arguments resolve against the caller's project; the runner invokes the existing backend from its repository root. Use the host's normal execution permissions. No API key or additional model call is needed for the default `--llm mock` checker. The host conversation still follows the client's own data/service settings.

## Workflow

1. Identify the intended manuscript, result tables, optional references, project ID and a fresh output directory. Use public/synthetic inputs, not private patient data or confidential manuscripts. Keep draft proposals separate from actual results.
2. Run the existing `run` command with explicit paths and `--llm mock`. Use its default `--mode new`; preserve prior output directories. Check the exit code and required artifacts before saying the audit completed.
3. Use `inspect --run ... --workspace ...` to read verified identity, saved manuscript text, claims, evidence and the actual journal revision. Read report limitations and evidence locators before discussing a finding. A zero-finding result does not prove coverage or correctness.
4. For a missed statement, compute zero-based **Python Unicode code point** offsets in the saved `manuscript.text`, with exclusive end. Verify `text[start:end]` equals the exact selection. Do not guess offsets from display lines or JavaScript UTF-16 indices. Call `annotate` with the observed `--expected-revision`; annotation means unevaluated human-check item, not a new supported claim.
5. For revisions, verify the two saved run identities and that the user intends the same document/task lineage. Reuse existing authorization; otherwise clarify the lineage before `compare --same-task`. IDs such as C001 are local to each run and cannot establish cross-run correspondence. Read pending matches. Removed or unextracted text is not proof that a problem was fixed. Do not manufacture mappings to eliminate uncertainty.
6. Record user handling with `record-action`. Attribute human review only when the user supplies the person and source; never label the host model's opinion as a human review. Keep actions and opinions separate from deterministic verdicts. Re-read `inspect` and use the observed journal revision before writing; stale failures require re-reading and reassessing, not an automatic revision-number retry.
7. Rerun changed materials into a fresh directory and compare. State what the new program result shows and what still needs domain judgement. If findings raise a question about the intended task, bring the exact finding/source back through `problem-bridge` feedback without silently changing its confirmed goal.

## Export a single audit

Use `handoff --run <saved-audit> --out <fresh-export-directory>` to produce `evidence_brief.md` and `evidence_brief.json` without requiring a second run. Include `--workspace` only for the user-selected annotations/actions. Read both the program findings and the separately labelled user records; an action marked done does not clear a finding. Keep source identity, input/rule hashes, evidence locations and coverage limitations with the handoff. This supplies material for AWT or another researcher and does not perform research-value, novelty or submission assessment. Do not send files automatically.

## Deliver

Provide the saved report paths, run identity, material limitations, actionable findings and unresolved questions. Required artifacts are `claim_table.csv`, `evidence_map.json`, `audit_report.md`, `revision_suggestions.md`, `agent_trace.jsonl`; current runs also preserve an input snapshot. Never edit completed audit files or present local technical checks as scientific validity, author approval or submission clearance.
