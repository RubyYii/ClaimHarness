"""A synthetic, deterministic end-to-end example; no model calls or real users."""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

from .clarification import (Interpretation, OpenIssue, Preview, answer_question, choose_question,
    commit_clarification, correct_answer, start_clarification)
from .handoff import ConceptNote, NeedBrief
from .project_lifecycle import is_link_or_reparse, snapshot_completed_run
from .workbench import FRAME_FIELDS, confirm_problem, load_problem

REQUEST = (
    "I monitor several stations. Summarize the daily average level for each site so I can compare daily conditions. "
    "Sensors have different numbers of observations. Keep every listed site on every requested date, including sites "
    "with no observations. Missing readings are not zero; exclude them from averages and use null when no valid "
    "reading exists. Return exactly site, date, mean, sorted by site then date. Round only the final mean to two "
    "decimal places. Dates are already local calendar dates; do not convert time zones."
)
ANSWERS = {
    "observations": "Give every valid observation equal weight, so sensors with more observations contribute more.",
    "sensors": "First calculate each sensor's daily mean from valid observations, then give each sensor with a valid mean equal weight.",
}


def public_data():
    return {"sites": ["North", "South", "West"], "dates": ["2026-06-01", "2026-06-02"], "observations": [
        {"site": "North", "date": "2026-06-01", "sensor": "N1", "value": 10},
        {"site": "North", "date": "2026-06-01", "sensor": "N1", "value": 14},
        {"site": "North", "date": "2026-06-01", "sensor": "N1", "value": 18},
        {"site": "North", "date": "2026-06-01", "sensor": "N2", "value": 30},
        {"site": "North", "date": "2026-06-02", "sensor": "N1", "value": None},
        {"site": "North", "date": "2026-06-02", "sensor": "N2", "value": 20},
        {"site": "South", "date": "2026-06-01", "sensor": "S1", "value": 4},
        {"site": "South", "date": "2026-06-01", "sensor": "S2", "value": 16},
        {"site": "South", "date": "2026-06-01", "sensor": "S2", "value": 20},
        {"site": "South", "date": "2026-06-02", "sensor": "S1", "value": None},
    ]}


def summarize(data, policy):
    """A bounded example adapter, not a general professional-task interpreter."""
    if policy not in ANSWERS:
        raise ValueError("Unknown averaging policy.")
    result = []
    for site in sorted(data["sites"]):
        for date in sorted(data["dates"]):
            selected = [r for r in data["observations"] if r["site"] == site and r["date"] == date and r["value"] is not None]
            if policy == "observations":
                values = [r["value"] for r in selected]
            else:
                groups = {}
                for row in selected:
                    groups.setdefault(row["sensor"], []).append(row["value"])
                values = [sum(v) / len(v) for v in groups.values()]
            result.append({"site": site, "date": date, "mean": round(sum(values) / len(values), 2) if values else None})
    return result


def check_known_requirements(data, result):
    """Checks encoded invariants only; it does not decide the missing policy."""
    if not isinstance(result, list):
        return False
    expected = [(s, d) for s in sorted(data["sites"]) for d in sorted(data["dates"])]
    if len(result) != len(expected):
        return False
    for row, pair in zip(result, expected):
        if not isinstance(row, dict) or set(row) != {"site", "date", "mean"} or (row["site"], row["date"]) != pair:
            return False
        values = [r["value"] for r in data["observations"] if (r["site"], r["date"]) == pair and r["value"] is not None]
        value = row["mean"]
        if not values:
            if value is not None:
                return False
        elif isinstance(value, bool) or not isinstance(value, (int, float)) or not min(values) - 0.005 <= value <= max(values) + 0.005 or abs(value - round(value, 2)) > 1e-9:
            return False
    return True


def make_record(root: Path, project_id: str):
    return confirm_problem(root, project_id, {"question": REQUEST,
        "observation": "Different sensors sample at unequal rates; I need a daily table for comparison.",
        "observation_source": "Synthetic demonstration; no real participant or environmental observations.",
        "desired_change": "A reproducible CSV and a record of how the averaging meaning was agreed.",
        "human_boundary": "The requester chooses what the average should represent."},
        brief=NeedBrief(background="Synthetic monitoring analyst", materials="Synthetic site/date/sensor/value table.",
            success_check="Preserve every requested site-date, missingness rules, column contract and ordering.",
            concepts=[ConceptNote(term="station", meaning="One site in the sites list; not one sensor.",
                example="North is a station with sensors N1 and N2.", non_example="N1 alone is not a station.")]))


def scripted_issue():
    return OpenIssue(issue_id="averaging_unit", description="What contributes equal weight to the daily level?",
        question="Should each valid observation count equally, or should each sensor's daily mean count equally?",
        alternatives=tuple(Interpretation(interpretation_id=k, instruction=v) for k, v in ANSWERS.items()), origin="author_proposal")


def write_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def write_csv(path, rows):
    with Path(path).open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["site", "date", "mean"])
        writer.writeheader()
        writer.writerows(rows)


def run_demo(out: Path, *, answer: str = "sensors", correct_to: str | None = None):
    if answer not in ANSWERS or correct_to is not None and correct_to not in ANSWERS:
        raise ValueError("Unknown averaging answer.")
    out = out.absolute()
    if any(is_link_or_reparse(p) for p in (out, *out.parents) if p.exists() or p.is_symlink()):
        raise ValueError("Use an unlinked output directory.")
    out.mkdir(parents=True, exist_ok=False)
    runs = out / "workbench_runs"
    original = make_record(runs, "clarification-synthetic-demo")
    record = load_problem(runs, original, "clarification-synthetic-demo")
    state = start_clarification(record, [scripted_issue()], budget=1)
    data = public_data()
    previews = [Preview(issue_id="averaging_unit", interpretation_id=policy, case_id="public-monitoring-table",
        status="executed", outcome=summarize(data, policy), known_requirements_passed=check_known_requirements(data, summarize(data, policy))) for policy in ANSWERS]
    decision = choose_question(state, previews)
    answered = answer_question(state, decision, ANSWERS[answer], expected_revision=0, interpretation_id=answer, actor="simulated_user")
    answered_run = commit_clarification(runs, original, answered)
    final, final_run, final_policy = answered, answered_run, answer
    if correct_to is not None:
        final = correct_answer(answered, "averaging_unit", ANSWERS[correct_to], reason="Scripted requester changes the intended weighting.",
            expected_revision=answered.revision, interpretation_id=correct_to, actor="simulated_user")
        final_run = commit_clarification(runs, answered_run, final, original=original, previous_state=answered)
        final_policy = correct_to
    final_record = load_problem(runs, final_run, state.project_id)
    assert all(getattr(record, key) == getattr(final_record, key) for key in FRAME_FIELDS)
    assert record.brief.concepts == final_record.brief.concepts
    result = summarize(data, final_policy)
    assert check_known_requirements(data, result)
    write_json(out / "public_data.json", data)
    for name, value in [("initial_state", state), ("decision", decision), ("answered_state", answered), ("final_state", final)]:
        write_json(out / (name + ".json"), value.model_dump(mode="json"))
    write_json(out / "public_previews.json", [p.model_dump(mode="json") for p in previews])
    write_csv(out / "result_before_correction.csv", summarize(data, answer))
    write_csv(out / "result.csv", result)
    (out / "clarification_trace.jsonl").write_text("".join(json.dumps(e.model_dump(mode="json"), ensure_ascii=False) + "\n" for e in final.events), encoding="utf-8")
    (out / "model_task.md").write_bytes(snapshot_completed_run(final_run)["model_task_en.md"])
    verification = {"synthetic_demo": True, "model_calls": 0, "human_participants": 0,
        "proposal_source": "scripted_author_example", "execution_adapter": "fixed_daily_averaging_demo",
        "questions_used": final.turns_used, "state_revisions": final.revision,
        "problem_revisions": final_record.revision, "original_fields_preserved": True,
        "known_requirements_passed": True, "final_policy": final_policy,
        "original_problem": original.name, "answered_problem": answered_run.name, "final_problem": final_run.name}
    write_json(out / "verification.json", verification)
    (out / "DEMO.md").write_text(
        "# 需求澄清与任务对齐：完整可执行示例\n\n"
        "这是合成数据和脚本答复演示，没有真人参与或模型调用，也不构成方法优越性证据。\n\n"
        "1. 原始需求要求按站点逐日汇总，同时保护缺测、覆盖、列名和排序要求。station 的含义已明确为 site，无需重复询问。\n"
        "2. ‘日平均水平’存在两种可执行含义：每条观测等权，或先在传感器内平均再让传感器等权。\n"
        "3. 实际预览中，North 第一天两种结果分别为18.0和22.0，South分别为13.33和11.0。机制记录结果差异后选择这一问题。\n"
        "4. 一次脚本答复只补充这项要求；其他原始字段逐字保留，并通过原有工作台生成新版本和交接说明。\n"
        "5. 最终CSV由所选规则实际计算；如指定 --correct-to，另记录显式需求修正，并重新生成结果，旧版本保留。\n\n"
        f"最终政策：{final_policy}。提问数：{final.turns_used}。任务版本：{final_record.revision}。\n\n"
        "核心文件：decision.json、clarification_trace.jsonl、model_task.md、result.csv、verification.json。\n"
        "这里的候选由作者预设，执行器只覆盖本例。模型候选生成与普通对话比较须由另行记录的实验完成。\n",
        encoding="utf-8")
    files = {p.relative_to(out).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(out.rglob("*")) if p.is_file() and not p.name.endswith(".lock")}
    write_json(out / "demo_manifest.json", {"algorithm": "sha256", "files": files})
    return verification
