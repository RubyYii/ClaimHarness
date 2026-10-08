"""User actions and attributed opinions never overwrite deterministic verdicts."""
from __future__ import annotations

from pathlib import Path

from .comparison import AuditRun, compare_runs, load_audit_run
from .continuity_store import Journal


def audit_journal(workspace: Path, run: AuditRun) -> Journal:
    if run.integrity != "verified":
        raise ValueError("A verified complete run is required for version-bound annotations.")
    return Journal(workspace, {"kind": "audit_handling", "run": run.ref})


def annotate(workspace: Path, run_path: Path, *, start: int, end: int, question: str,
             candidate_evidence: list[str] | None = None, expected_revision: int = 0) -> dict:
    run = load_audit_run(run_path)
    if run.text is None:
        raise ValueError("This run has no original source snapshot; annotate a new run instead.")
    if not 0 <= start < end <= len(run.text) or not run.text[start:end].strip() or not question.strip():
        raise ValueError("Select a non-empty exact source span and write a human-check question.")
    candidates = candidate_evidence or []
    if not set(candidates) <= run.evidence.keys():
        raise ValueError("Candidate evidence must belong to this run.")
    journal = audit_journal(workspace, run)
    return journal.append("manual_claim", {
        "manual_id": f"M{expected_revision + 1:03d}", "text": run.text[start:end],
        "source": {"name": run.snapshot["manuscript"]["name"], "sha256": run.snapshot["manuscript"]["sha256"],
                   "start": start, "end": end, "line": run.text[:start].count("\n") + 1},
        "question": question.strip(), "candidate_evidence_ids": candidates,
        "evaluation": "not_evaluated", "status": "needs_human_review", "origin": "user_annotation",
    }, expected_revision=expected_revision)


def record_handling(workspace: Path, run_path: Path, *, claim_id: str, layer: str, action: str,
                    note: str, actor: str = "", source: str = "", expected_revision: int = 0,
                    rerun: Path | None = None, same_task: bool = False) -> dict:
    run = load_audit_run(run_path)
    journal = audit_journal(workspace, run)
    saved = journal.read()
    manual_ids = {e["payload"]["manual_id"] for e in saved["events"] if e["kind"] == "manual_claim"}
    if claim_id not in {c["claim_id"] for c in run.claims} | manual_ids:
        raise ValueError("Unknown finding in this run.")
    if layer not in {"user_action", "human_review"} or action not in {"planned", "done", "retain_with_explanation", "request_review"}:
        raise ValueError("Unknown handling layer or action.")
    if not note.strip() or (layer == "human_review" and (not actor.strip() or not source.strip())):
        raise ValueError("Write the note; human opinions also need an attributed person and source.")
    comparison = None
    if rerun is not None:
        newer = load_audit_run(rerun)
        if newer.integrity != "verified" or newer.ref["run_id"] == run.ref["run_id"] or not same_task:
            raise ValueError("Link a different complete rerun and confirm it is the same task.")
        value = compare_runs(run, newer, same_task=True)
        matched = [item for item in value["changes"] if any(c["claim_id"] == claim_id for c in item["previous"])]
        comparison = {"run": newer.ref, "changes": matched,
                      "boundary": "Compare the recorded action with these program results; no manual closure is inferred."}
    return journal.append(layer, {"claim_id": claim_id, "action": action, "note": note.strip(),
                          "actor": actor.strip(), "source": source.strip(), "actor_verified": False,
                          "rerun": comparison}, expected_revision=expected_revision)
