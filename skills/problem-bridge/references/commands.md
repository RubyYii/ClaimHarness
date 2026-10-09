# ProblemBridge commands

Replace `<runner>` with this skill's absolute `scripts/run.py` path. Run from the user's project:

```text
python <runner> --check
python <runner> create --workspace .problembridge --project-id demo --request create.json --confirmed
python <runner> show --workspace .problembridge --project-id demo --run <run_name>
python <runner> feedback --workspace .problembridge --project-id demo --run <run_name> --request feedback.json
python <runner> respond --workspace .problembridge --project-id demo --run <run_name> --request response.json
python <runner> confirm --workspace .problembridge --project-id demo --run <run_name> --request confirm.json --confirmed
python <runner> next-round --workspace .problembridge --project-id demo --run <new_run_name> --request round.json
python <runner> audit --workspace .problembridge --project-id demo --run <new_run_name> --request audit.json
```

Equivalent backend command: `python -m problem_bridge task <action> ...` from the backend repository. Success prints JSON with `run_name`, `run_path`, `record`, `is_current`, `journal_revision`, `discussion`, `history`, `handoffs` and `follow_up`. Failure prints JSON to stderr and exits 1 (argument parser errors exit 2). Save returned identities; inspect the relevant paths, not another run with a similar name. `show` may inspect history, but mutations require the current version. A workspace stores immutable run subdirectories and a separate `.continuity` journal.

Requests are UTF-8 JSON objects. Unknown or duplicate fields and wrong types fail. Each file is at most 2 MiB. All journal writes require an explicit integer `expected_revision` observed in `show`; examples below assume a fresh journal and must not be blindly reused.

`create.json`:

```json
{
  "fields": {
    "question": "Why do these synthetic measurements differ?",
    "observation": "Two synthetic devices report different means.",
    "observation_source": "Public example CSV, not a patient dataset",
    "desired_change": "Agree on the averaging definition",
    "hypothesis": "Sampling frequency may differ; unverified",
    "human_boundary": "The domain owner decides the intended comparison"
  },
  "brief": {
    "background": "A synthetic teaching example",
    "collaborator": "Data analyst",
    "materials": "Example measurements.csv",
    "success_check": "The analyst restates the intended averaging unit",
    "concepts": [{"term": "mean", "meaning": "Not yet agreed", "example": "", "non_example": ""}]
  }
}
```

Only `fields.question` is required; other fields and `brief` are optional. `create` always starts a new problem, not a revision of another problem.

`feedback.json` (optional `target` is a saved run name within this workspace, default current; optional `alternatives` is a list of possible interpretations, not automatically adopted):

```json
{
  "expected_revision": 0,
  "sender": "AI assistant",
  "sender_kind": "ai",
  "original": "Consider a predictor. Also clarify the averaging unit.",
  "selected": "clarify the averaging unit",
  "interpretation": "Discuss the mean without changing the goal",
  "category": "terminology",
  "question": "Average by observation or device?",
  "budget": 5
}
```

`sender_kind`: `collaborator`, `ai`, `user`. `category`: `goal_meaning`, `terminology`, `missing_condition`, `method_proposal`, `new_goal`. Optional `consequence` records why this matters. Budget is 1–20. Exact `selected` must occur within `original`.

`response.json`: use the returned `discussion.feedback[].feedback_id` as `issue_id`.

```json
{"expected_revision": 1, "issue_id": "<returned feedback_id>", "mode": "answer", "answer": "Average by device"}
```

Modes: `answer`, `unknown`, `defer`, `none_accurate`, `correct`. Optional `interpretation_id` selects a returned alternative. A correction requires `reason` and corrected `answer`; use `none_accurate` for a user-written interpretation outside the alternatives.

`confirm.json`:

```json
{"expected_revision": 2, "kind": "supplement", "reason": "The user clarified the unit", "next_action": "Ask the analyst to restate it"}
```

`kind`: `supplement`, `correction`, `goal_change`. Only `goal_change` accepts `fields` (same fields as create; requires the explicit new `question`). Other kinds preserve framing. A correction first needs a recorded corrected answer. Confirmation uses two journal events; always take the returned revision instead of adding one yourself.

`round.json`: `{"expected_revision": 4, "budget": 3}`. Confirm recorded answers before starting another round.

`audit.json`:

```json
{"manuscript": "manuscript.md", "tables": ["tables/results.csv"], "references": "references.md"}
```

Paths **inside this JSON** are relative to the request file's directory; absolute paths are also accepted. Manuscript/references are UTF-8 text, tables are 1–20 UTF-8 CSV files with distinct basenames. References are optional. Inputs are limited to 2 MiB per file and 10 MiB combined. For PDF/DOCX loaders use the standalone ClaimHarness skill instead. The original ProblemBridge run remains unchanged. The returned run contains audit files and `follow_up.json` for questions to discuss.

## Export confirmed context

```text
python <runner> export --workspace .problembridge --project-id demo --run <run_name> --request export.json
```

`export.json`: `{"out":"handoffs/problem-v1","language":"zh"}`. Language is `zh` (default) or `en`. The output path is relative to the request file's directory. The destination must be fresh and outside saved runs. This writes `problem_context.md` and `problem_context.json` plus lifecycle identity/completion records. It returns JSON with `source`, `export_path` and `files`; unlike mutations it does not return a new problem version. Export does not accept `--confirmed`, adopt unsaved/unconfirmed discussion or change the journal. Historical versions remain exportable with an explicit `is_current_at_export: false` and warning. The JSON preserves the exact selected saved record, including previous-version references; the Markdown carries its conditions, unknowns and confirmed answers. Files are not sent to AWT automatically.
