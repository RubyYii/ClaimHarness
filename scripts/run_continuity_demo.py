"""Run the complete synthetic PB feedback and CH comparison flow from repo root."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from claim_harness.comparison import compare_runs, export_comparison
from claim_harness.handling import annotate, record_handling
from problem_bridge.feedback import add_feedback, confirm_discussion, respond
from problem_bridge.handoff import NeedBrief, build_research_input
from problem_bridge.workbench import audit_problem, confirm_problem, load_problem


def run_demo(out: Path):
    out.mkdir(parents=True, exist_ok=False)
    sources = Path(__file__).resolve().parents[1] / "examples/continuity_demo"
    root, project = out / "runs", "synthetic-continuity-demo"
    first = confirm_problem(root, project, {"question": "解释设备记录差异，先明确平均口径。", "desired_change": "可核对的合成样例"},
                            brief=NeedBrief(materials="合成观测记录；由接收方另行取得文件"))
    history = add_feedback(root, project, first, target=first, sender="Synthetic collaborator", sender_kind="collaborator",
        original="平均值是按观测次数，还是先按设备平均？也许可以改做预测。", selected="平均值是按观测次数，还是先按设备平均？",
        interpretation="先讨论平均口径，不自动接受预测建议", category="terminology", question="这次平均值采用哪个口径？",
        alternatives=["每次观测等权", "每个设备等权"], consequence="设备记录次数不同可能改变汇总值；还未在用户材料上运行。")
    issue_id = history["events"][-1]["payload"]["feedback"][0]["feedback_id"]
    respond(root, project, first, issue_id=issue_id, mode="answer", answer="先按设备平均，再汇总。", interpretation_id="option-2", expected_revision=1)
    need = confirm_discussion(root, project, first, kind="supplement", reason="确认合成样例的平均口径", next_action="请合作者按设备等权提供样例，并注明缺失数据处理。", expected_revision=2)
    before = audit_problem(root, project, need, manuscript=(sources / "before.md").read_text(encoding="utf-8"), tables={"results.csv": (sources / "tables_before/results.csv").read_bytes()})
    after_text = (sources / "after.md").read_text(encoding="utf-8")
    after = audit_problem(root, project, before, manuscript=after_text, tables={"results.csv": (sources / "tables_after/results.csv").read_bytes()})
    start = after_text.index("不同设备")
    annotate(root, after, start=start, end=start + len("不同设备的观测次数可能不同，需要确认平均值的计算口径。"), question="是否按设备等权，缺失值如何处理？")
    record_handling(root, after, claim_id="C002", layer="user_action", action="done", note="已更正数值并更新表格；请对照新程序结果。", expected_revision=1)
    mapping = json.loads((sources / "mappings.json").read_text(encoding="utf-8"))
    value = compare_runs(before, after, same_task=True, mappings=mapping, workspace=root)
    export_comparison(value, out / "comparison", research=True)
    record = load_problem(root, need, project)
    (out / "research_discussion_zh.md").write_text(build_research_input(record), encoding="utf-8")
    manifest = {"synthetic_only": True, "external_calls": 0, "initial_need": first.name, "confirmed_need": need.name,
                "previous_audit": before.name, "current_audit": after.name, "comparability": value["comparability"],
                "change_kinds": [c["kind"] for c in value["changes"]]}
    (out / "demo_result.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=Path("outputs/continuity_demo"))
    run_demo(parser.parse_args().out)
