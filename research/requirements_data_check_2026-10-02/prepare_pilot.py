"""Prepare a fixed-dialogue development pilot, with references kept separate."""
from __future__ import annotations

import collections
import hashlib
import json
from pathlib import Path

from inspect_sources import ROOT, verify

SEED = "requirements-data-check-2026-10-02:"
N_PER_SOURCE = 12


def jl(path: Path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def sort_key(identity: str):
    return hashlib.sha256((SEED + identity).encode("utf-8")).hexdigest()


def save_jsonl(path: Path, rows):
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8", newline="\n")


def main():
    verify()
    raw = ROOT / "raw"
    tasks = jl(raw / "in3/test.jsonl")
    records = jl(raw / "in3/user_records_gpt4.jsonl")
    task_by_text = {row["task"]: row for row in tasks}
    record_by_text = {row["actions"][0]["content"]: row for row in records}
    if len(task_by_text) != len(tasks) or len(record_by_text) != len(records):
        raise ValueError("Repeated task text requires an explicit join policy.")
    if set(task_by_text) != set(record_by_text):
        raise ValueError("IN3 task and recorded-dialogue identities do not match.")

    inputs, references = [], []
    for task_text in sorted(task_by_text, key=sort_key)[:N_PER_SOURCE]:
        task, record = task_by_text[task_text], record_by_text[task_text]
        episode_id = "in3-" + sort_key(task_text)[:12]
        summaries = [a["content"] for a in record["actions"] if a["type"] == "summary"]
        messages = [{"turn_id": i, "role": a["role"].lower(), "content": a["content"]}
                    for i, a in enumerate(record["actions"]) if a["type"] == "response"]
        inputs.append({
            "episode_id": episode_id, "dataset": "in3", "source_identity": task_text,
            "source": "raw/in3/user_records_gpt4.jsonl",
            "origin": "recorded_human_participant_and_gpt4_assigned_task",
            "messages": messages,
        })
        references.append({
            "episode_id": episode_id, "category": task["category"],
            "source_vagueness_label": task["vague"],
            "source_missing_detail_labels": task["missing_details"],
            "recorded_assistant_summaries_NOT_GOLD": summaries,
            "source_participant_counts_NOT_INDEPENDENT_AUDIT": record["user_record"],
            "user_approved_final_brief": None,
        })

    ccpe = json.loads((raw / "ccpe/data.json").read_text(encoding="utf-8"))
    ids = [row["conversationId"] for row in ccpe]
    if len(set(ids)) != len(ids):
        raise ValueError("Repeated CCPE conversation identity.")
    for row in sorted(ccpe, key=lambda x: sort_key(x["conversationId"]))[:N_PER_SOURCE]:
        episode_id = row["conversationId"]
        inputs.append({
            "episode_id": episode_id, "dataset": "ccpe", "source_identity": episode_id,
            "source": "raw/ccpe/data.json", "origin": "human_human_wizard_of_oz_movie_preferences",
            "messages": [{"turn_id": u["index"], "role": u["speaker"].lower(), "content": u["text"]}
                         for u in row["utterances"]],
        })
        references.append({
            "episode_id": episode_id,
            "source_user_span_annotations": [{"turn_id": u["index"], "segments": u.get("segments"),
                                               "source_annotation_field_present": "segments" in u}
                                             for u in row["utterances"] if u["speaker"] == "USER"],
            "recorded_assistant_summaries_NOT_GOLD": [], "user_approved_final_brief": None,
        })

    req = json.loads((raw / "reqelicitgym/test.json").read_text(encoding="utf-8"))
    result = {
        "purpose": "data_suitability_and_fixed_dialogue_pilot_preparation",
        "new_model_inference_calls": 0, "new_human_participants": 0,
        "selection": {"seed_prefix": SEED, "sort": "ascending_sha256", "per_source": N_PER_SOURCE,
                      "heldout_claim": False, "all_selected_cases_retained": True},
        "in3": {
            "tasks": len(tasks), "gpt4_recorded_dialogues": len(records), "exact_task_joins": len(task_by_text),
            "vague_tasks": sum(x["vague"] for x in tasks),
            "not_vague_tasks": sum(not x["vague"] for x in tasks),
            "recorded_assistant_summaries": sum(a["type"] == "summary" for x in records for a in x["actions"]),
        },
        "ccpe": {"dialogues": len(ccpe), "utterances": sum(len(x["utterances"]) for x in ccpe),
                 "speaker_counts": dict(collections.Counter(u["speaker"] for x in ccpe for u in x["utterances"])),
                 "utterances_without_segments_field": sum("segments" not in u for x in ccpe for u in x["utterances"])},
        "reqelicitgym": {"scenarios": len(req), "application_types": len({x["application_type"] for x in req}),
                         "implicit_requirements": sum(len(x["Implicit Requirements"]) for x in req),
                         "final_user_stories_in_URL_field": sum(len(x["URL"]) for x in req),
                         "used_in_pilot": False, "reuse_license": "not_specified_in_source_readme"},
        "pilot": {"episodes": len(inputs), "input_messages": sum(len(x["messages"]) for x in inputs),
                  "reference_rows": len(references), "inference_status": "not_run", "semantic_review_status": "six_cases_reviewed_exploratorily"},
        "checks": {"unique_episode_ids": len({x["episode_id"] for x in inputs}) == len(inputs),
                   "paired_reference_ids": [x["episode_id"] for x in inputs] == [x["episode_id"] for x in references],
                   "sources_separate_from_model_predictions": True},
    }
    if not all(result["checks"].values()):
        raise ValueError("Pilot identity check failed.")
    save_jsonl(ROOT / "pilot_inputs.jsonl", inputs)
    save_jsonl(ROOT / "review_only.jsonl", references)
    (ROOT / "data_check.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
