# Clarification and task alignment mechanism

The mechanism connects one confirmed ProblemBridge need to explicit open issues, public execution previews, one-question updates, and a versioned model handoff. It is exposed through a Python API, a synthetic CLI example and the [feedback/discussion interface](continuous_review.md).

## Run the complete example

From the repository root:

```bash
python -m problem_bridge clarify-demo --out outputs/clarification_demo --answer sensors
```

To include a subsequent explicit correction:

```bash
python -m problem_bridge clarify-demo --out outputs/clarification_correction --answer sensors --correct-to observations
```

Use a fresh output folder for each run. This default demonstration uses no API key, model calls, or real participants. The candidate interpretations and replies are scripted and labeled as such. It demonstrates software behavior, not scientific superiority.

The synthetic requester wants daily site averages while retaining sites without data, excluding missing readings, preserving output columns/order, and rounding only the final result. `station` is explicitly defined as a site rather than a sensor. Unequal sampling makes observation-weighted and sensor-weighted averages differ: for North on the first day the actual results are 18.0 and 22.0. A reply selects the intended meaning; an explicit correction can change it later without overwriting the original records.

## Outputs

- `DEMO.md`: a readable walkthrough with the synthetic-data boundary.
- `initial_state.json`, `decision.json`, `answered_state.json`, `final_state.json`: the task state and selection/update decisions.
- `public_previews.json`: actual example outputs under each candidate interpretation.
- `clarification_trace.jsonl`: answers and explicit corrections with prior-answer links.
- `model_task.md`: the versioned task handoff generated through the existing workbench.
- `result_before_correction.csv`, `result.csv`: executable results before and after any correction. Null is serialized as an empty CSV cell.
- `workbench_runs/`: normal immutable ProblemBridge snapshots, records and bilingual handoffs.
- `verification.json`, `demo_manifest.json`: checks, model/human counts, provenance and artifact hashes.

## Python API

`problem_bridge.clarification` makes no model or execution calls. A caller supplies `OpenIssue` candidates and `Preview` records from a trusted execution adapter. An issue has an open question with no alternatives, or a question with two to six distinct interpretations. A preview binds one issue/interpretation to one public input case and records a task-relevant structured outcome plus the result of checking known requirements. `Preview.kind` separates actual execution, explanatory examples and untested inferences; only execution records enter actual outcome comparisons. Do not use hidden evaluation targets to construct preview evidence. Do not use incidental file names, logging text, or presentation differences as outcome signatures unless the actual acceptance contract makes them relevant.

```python
state = start_clarification(problem_record, issues, budget=1)
decision = choose_question(state, public_previews)
updated = answer_question(
    state, decision, user_reply, expected_revision=state.revision
)
new_problem_run = commit_clarification(root, original_problem_run, updated)
```

The generic-selection ablation uses the same state and issues:

```python
decision = choose_question(
    state, [], policy="generic", generic_issue_id=chosen_issue_id
)
```

An independent caller chooses that ID; the core does not disguise a fixed ordering as an ordinary conversational model.

For a user correction, call `correct_answer` with the issue ID, replacement answer, nonempty reason and expected revision. To export after a previous export, also pass the original snapshot and the previously exported state to `commit_clarification`. It verifies the prior history and unchanged original fields, and replaces the earlier clarification appendix rather than accumulating contradictory current answers. Each export is an immutable branch/version. Callers manage their own current-state pointer; no global mutable session or concurrent last-writer-wins store is introduced.

## Selection behavior

For each unresolved issue, compare its successfully executed alternatives on matching public case IDs, after checks of known requirements. Prefer an issue with observed outcome differences, then unknown effects, then observed agreement. Within a category, the fraction of comparable alternative pairs with different outputs breaks ties; input order breaks exact ties.

This fraction is a descriptive witness score, not expected information gain or an estimate of a real user's preference distribution. Partial previews, failed programs and alternatives that violate known requirements remain distinguishable from valid executions. Missing cases can bias this simple ranking; no claim of optimal question selection is made.

Public equality never resolves an issue automatically. With remaining issues and no budget, the state is `budget_exhausted` and the handoff retains them as unresolved. No issues proposed is only completion relative to the candidate set; it does not establish complete task understanding. Generic selection and full selection use exactly the same answer/update machinery.

## Protected updates and limits

Replies add one issue resolution. They cannot replace the original frame fields through this API. Expected revisions and state fingerprints reject stale or cross-task questions. Explicit corrections preserve the earlier event and replace only the named answer. Exports preserve the original question, observation, hypothesis, desired outcome, human boundary, materials and concept notes, and supplement the existing acceptance description.

This structural preservation is not a complete natural-language contradiction detector. A free-text reply can still contain conflicting or additional requirements; those need caller/user interpretation and semantic checks. Preview trust also depends on the execution adapter. The demo adapter only implements its stated averaging task; the module does not autonomously translate arbitrary professional requests or execute arbitrary code.

## Mechanism demonstration versus research evidence

The local CLI is a deterministic working example. The separately archived `research/publication_2026-09-21/mechanism_2026-09-24/` comparison adds model-generated candidates, restricted execution of their programs, ordinary dialogue, and a generic-selection ablation. The comparison uses one synthetic case, two target interpretations and a one-question budget. It records extra model/execution costs and never treats private fixtures as independent research tasks. None of these artifacts establish cross-disciplinary user benefit, scientific novelty, or broad method superiority.
