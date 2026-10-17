# Local research handoffs / 本地研究交接

ProblemBridge keeps the user's confirmed question and conditions. ClaimHarness checks statements against supplied results. Either can now export one selected saved version for a researcher, collaborator or AWT. These commands run locally, use no model API and do not send files to another application. AWT installation is not required.

这边提供可追溯的讨论材料：ProblemBridge 带走问题和条件，ClaimHarness 带走已有结果的核查依据。创新性、研究意义、相关工作检索和投稿差距仍由接收方的研究评估流程处理；导出成功不表示这些评估已经完成。

## Export a confirmed problem / 导出已确认的问题

From this repository's root, save an `export.json` request:

```json
{"out": "handoffs/problem-v1", "language": "zh"}
```

Then use the `run_name`, workspace and project ID returned by your previous ProblemBridge task:

```text
python -m problem_bridge task export --workspace .problembridge --project-id demo --run <run_name> --request export.json
```

`out` is relative to the JSON request's directory, not the saved run. Language is `zh` (default) or `en`; supplied wording is retained in its original language. No `--confirmed` flag is needed or accepted for export. The selected record has already been saved; unconfirmed changes must go through the existing confirmation workflow first.

The output contains:

| File | Contents |
|---|---|
| `problem_context.md` | Confirmed question, observation and origin, intended change, unverified hypothesis, human decisions, background, collaborator role, materials/access, success criteria, definitions and examples, recorded interview/follow-up answers and unknowns |
| `problem_context.json` | Exact saved record as a JSON object, including version history references and all saved continuation data; source identity and SHA-256 fingerprints |
| `run_identity.json`, `run_complete.json` | Identity and integrity records for this new export |

The JSON record retains all saved continuation history; the readable brief highlights the current conditions and latest confirmed continuation. Referenced earlier runs and described materials are not copied into the export. Current wording is labelled as the selected version, not assumed to be the first-ever question. Unsaved drafts and unconfirmed feedback are not adopted. Hypotheses, answers and plans remain user statements, not verified research evidence.

Historical versions remain exportable: `is_current_at_export` is false and the Markdown carries a historical-version warning if a newer confirmed version exists. This is a point-in-time check, not a lock against future versions. The source includes SHA-256 of the original record bytes and completion record. The source run and discussion journal are not modified.

## Export one audit / 导出一次核查

```text
python -m claim_harness handoff --run audits/v1 --out handoffs/evidence-v1
```

To include annotations and handling records from a specific workspace:

```text
python -m claim_harness handoff --run audits/v1 --out handoffs/evidence-v1-with-notes --workspace .claimharness
```

This works for a standalone ClaimHarness audit or an audit saved by ProblemBridge. A second audit is not required. For two-run changes, continue to use `compare --research-questions`.

| File | Contents |
|---|---|
| `evidence_brief.md` | Exact extracted claims, source locations, program statuses and reasons, evidence links/locations, missing evidence, suggested revisions and pending questions |
| `evidence_brief.json` | All claim/evidence records, source identity and canonical manifest digest, input hashes, available rule fingerprints, limitations and unresolved finding IDs |
| `run_identity.json`, `run_complete.json` | Identity and integrity records for this new export |

When a workspace is selected, both files also include its journal revision and user records, labelled separately. Manual annotations remain `not_evaluated`; actions marked `done` and attributed human opinions do not clear program findings. Actor identity is not authenticated. Omitting `--workspace` means records were not included, not that none exist. No journal is created by reading an empty workspace. Described evidence and locations are exported; this does not copy every input file or supply new evidence.

Coverage remains unknown, including when no claims are extracted or all extracted claims are supported. Current screening mainly recognizes English numerical patterns against supplied CSV results. A legacy audit without verifiable lifecycle records, an incomplete run or a tampered package is rejected; rerun it into a fresh directory first. A verified older run that lacks the source/rule snapshot retains that explicit limitation without inventing the missing data.

## Destinations and errors / 保存位置与错误

Use a fresh output directory outside saved runs. Existing nonempty directories, saved-run descendants, symlinks and Windows junctions are rejected. A failed write has no completion record and must not be treated as a finished export. The same source can be exported again to a different fresh directory. Success prints JSON with `source`, `export_path` and `files`; errors exit nonzero. This is additive and does not migrate or edit previous runs.

## Use through a Skill / 在助手里使用

Update the backend and reinstall the copied Skill instructions with `--upgrade` using the same interpreter, client and scope as before; see [installation and update commands](agent_skills.md). The installed ProblemBridge runner exposes `export`, and the ClaimHarness runner exposes `handoff`. Request-file paths still resolve relative to the request file; ordinary CLI path flags resolve from the caller's project.

Example requests to your assistant:

> 把这版已确认的问题、条件和还不知道的事项导出给后续研究讨论，保留用户表述和版本来源。

> 把这次核查的论断、证据位置和待确认问题导出，同时附上我指定工作区里的补标和处理记录。不要把“我说已处理”当作程序已经验证。

The synthetic [Skill demo](../scripts/run_agent_skills_demo.py) exercises both exports from a separate project with installed runners. A receiving AWT workflow can read the Markdown and JSON when the user supplies them; no automatic AWT integration or assessment is claimed here.
