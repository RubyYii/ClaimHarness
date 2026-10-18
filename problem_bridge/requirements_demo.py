"""Synthetic illustration of requirement checks; no user-benefit evaluation."""
import json
from pathlib import Path

from .clarification_demo import public_data, summarize, write_csv
from .handoff import NeedBrief
from .project_lifecycle import is_link_or_reparse
from .requirements import confirm_requirements, export_trace, record_check
from .workbench import confirm_problem, load_problem


def run_demo(out: Path) -> dict:
    if any(is_link_or_reparse(p) for p in (out, *out.parents) if p.exists() or p.is_symlink()):
        raise ValueError("Use an unlinked output directory.")
    out.mkdir(parents=True, exist_ok=False)
    root, project = out / "workspace", "synthetic-requirements-demo"
    clauses = ["Give each sensor equal weight.", "Keep sites with no observations.", "Missing readings are not zero."]
    initial = confirm_problem(root, project, {"question": "Summarize daily site conditions.",
        "desired_change": " ".join(clauses)}, brief=NeedBrief(materials="Public synthetic sensor observations."))
    need = confirm_requirements(root, project, initial, {"select": [
        {"source_key": "desired_change", "quote": clauses[0], "acceptance": "North on 2026-06-01 must be (14 + 30) / 2 = 22, not the observation-weighted 18."},
        {"source_key": "desired_change", "quote": clauses[1], "acceptance": "West must have a row for each requested date."},
        {"source_key": "desired_change", "quote": clauses[2], "acceptance": "No valid reading means a blank mean, not zero."},
    ]}, confirmed=True, expected_revision=1)
    record = load_problem(root, need, project)
    data = public_data()
    write_csv(root / "observations_weighted.csv", summarize(data, "observations"))
    write_csv(root / "sensors_weighted.csv", summarize(data, "sensors"))
    rid = record.requirements[0].requirement_id
    for revision, (file, result, note) in enumerate([
        ("observations_weighted.csv", "not_met", "Scripted fixture: North mean is 18; the stated sensor-weighting requirement expects 22."),
        ("sensors_weighted.csv", "met", "Scripted fixture: North mean is 22. This illustrates an attributed record, not general automatic acceptance."),
    ]):
        record_check(root, project, need, requirement_id=rid, result=result,
            actor="synthetic fixture; no human participant", method="Compare the North row with the explicitly stated arithmetic.",
            note=note, artifact=file, location="site=North,date=2026-06-01,mean",
            expected_revision=revision)
    export_trace(root, project, need, root / "review")
    manifest = {"synthetic_only": True, "external_calls": 0, "project_id": project,
        "confirmed_run": f"workspace/{need.name}", "selected_requirements": 3,
        "review": "workspace/review/requirement_trace.md", "check_authority": "user_reported_not_verified",
        "remaining_unchecked": 2, "real_user_benefit": "not_evaluated"}
    (out / "demo_result.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest
