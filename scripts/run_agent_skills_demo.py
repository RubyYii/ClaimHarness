"""Exercise installed portable skills from a separate synthetic project."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys


REPOSITORY = Path(__file__).resolve().parents[1]


def run_demo(out: Path) -> dict:
    out = out.absolute()
    out.mkdir(parents=True, exist_ok=False)
    project = out / "client project"
    project.mkdir()
    subprocess.run([sys.executable, "-X", "utf8", str(REPOSITORY / "scripts/install_agent_skills.py"),
                    "--client", "both", "--scope", "project", "--project", str(project)], cwd=REPOSITORY, check=True)

    def invoke(skill, *args, json_result=False, client=".agents"):
        runner = project / client / "skills" / skill / "scripts/run.py"
        result = subprocess.run([sys.executable, "-X", "utf8", str(runner), *args], cwd=project,
                                capture_output=True, text=True, encoding="utf-8")
        if result.returncode:
            raise RuntimeError(result.stderr or result.stdout)
        return json.loads(result.stdout) if json_result else result.stdout

    def task(action, data=None, current=None, confirmed=False):
        args = [action, "--workspace", "runs", "--project-id", "agent-demo"]
        if current:
            args += ["--run", current["run_name"]]
        if data is not None:
            request = project / (action + ".json")
            request.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            args += ["--request", request.name]
        if confirmed:
            args += ["--confirmed"]
        return invoke("problem-bridge", *args, json_result=True)

    for skill in ("problem-bridge", "claim-harness"):
        for client in (".agents", ".claude"):
            invoke(skill, "--check", json_result=True, client=client)
    first = task("create", {"fields": {"question": "Explain the synthetic score difference"}}, confirmed=True)
    feedback = task("feedback", {"expected_revision": first["journal_revision"], "sender": "Synthetic collaborator",
                    "sender_kind": "collaborator", "original": "Clarify the averaging unit.", "selected": "averaging unit",
                    "interpretation": "We need the denominator", "category": "terminology", "question": "Average by what?"}, first)
    answered = task("respond", {"expected_revision": feedback["journal_revision"],
                    "issue_id": feedback["discussion"]["feedback"][0]["feedback_id"],
                    "mode": "answer", "answer": "By device"}, feedback)
    revised = task("confirm", {"expected_revision": answered["journal_revision"], "kind": "supplement",
                   "reason": "Synthetic user clarified the unit", "next_action": "Check the example table"}, answered, True)
    (project / "manuscript.md").write_text("# Results\nThe model achieves precision of 0.95.\n", encoding="utf-8")
    (project / "tables").mkdir()
    (project / "tables/results.csv").write_text("model,precision\nmodel,0.85\n", encoding="utf-8")
    audit_request = {"manuscript": "manuscript.md", "tables": ["tables/results.csv"]}
    audit1 = task("audit", audit_request, revised)
    (project / "manuscript.md").write_text("# Results\nThe model achieves precision of 0.85.\n", encoding="utf-8")
    audit2 = task("audit", audit_request, audit1)
    # Use the Claude-installed launcher as well as the Codex-installed launcher.
    inspected = invoke("claim-harness", "inspect", "--run", "runs/" + audit1["run_name"],
                       "--workspace", "handling", json_result=True, client=".claude")
    text = inspected["manuscript"]["text"]
    start = text.index("The model")
    invoke("claim-harness", "annotate", "--run", "runs/" + audit1["run_name"], "--workspace", "handling",
           "--start", str(start), "--end", str(len(text.rstrip())), "--question", "Confirm the numerical mismatch",
           "--expected-revision", str(inspected["journal_revision"]))
    invoke("claim-harness", "compare", "--previous", "runs/" + audit1["run_name"], "--current", "runs/" + audit2["run_name"],
           "--out", "comparison", "--same-task", "--workspace", "handling")
    invoke("claim-harness", "record-action", "--run", "runs/" + audit1["run_name"], "--workspace", "handling",
           "--claim-id", "M001", "--note", "Synthetic text corrected; compare the new screening separately",
           "--action", "done", "--expected-revision", "1", "--rerun", "runs/" + audit2["run_name"], "--same-task")
    invoke("claim-harness", "run", "--manuscript", "manuscript.md", "--tables", "tables",
           "--out", "standalone", "--project-id", "agent-demo", "--llm", "mock", client=".claude")
    problem_export = task("export", {"out": "problem export", "language": "zh"}, revised)
    audit_export = invoke("claim-harness", "handoff", "--run", "runs/" + audit1["run_name"],
                          "--out", "evidence export", "--workspace", "handling", json_result=True, client=".claude")
    summary = {"synthetic": True, "problem_export": problem_export, "audit_export": audit_export, "project": str(project), "original": first["run_path"],
               "confirmed": revised["run_path"], "previous_audit": audit1["run_path"],
               "current_audit": audit2["run_path"], "comparison": str(project / "comparison"),
               "handoffs": revised["handoffs"], "standalone_audit": str(project / "standalone")}
    (out / "demo_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    print(json.dumps(run_demo(parser.parse_args().out), indent=2, ensure_ascii=False))
