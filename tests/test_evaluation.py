import json
import subprocess
import sys
from pathlib import Path

import pytest

from claim_harness.evaluation import (
    default_gold_path,
    evaluate_gold_set,
    evaluate_predictions,
    load_gold_records,
    write_evaluation_outputs,
)


def test_default_gold_evaluation_is_deterministic_and_exposes_known_gaps():
    first = evaluate_gold_set()
    second = evaluate_gold_set()

    assert first == second
    assert first["schema_version"] == "1.0"
    assert first["gold_set_version"] == "1.0.0"
    assert first["record_count"] == 7
    assert first["claim_extraction"] == {
        "true_positives": 5,
        "predicted": 5,
        "gold": 7,
        "precision": 1.0,
        "recall": 0.714286,
        "f1": 0.833333,
        "matching": "exact_after_casefold_and_whitespace_normalization",
    }
    assert first["evidence"]["recall_at_1"] == 0.5
    assert first["evidence"]["recall_at_3"] == 0.666667
    assert first["status"]["macro_f1"] == 0.866667
    assert first["status"]["confusion_matrix"]["supported"]["not_extracted"] == 1
    assert first["status"]["confusion_matrix"]["needs_human_review"]["not_extracted"] == 1
    assert first["risk"] == {
        "high_risk_gold_claims": 3,
        "high_risk_misses": 1,
        "high_risk_miss_rate": 0.333333,
        "unsafe_high_risk_decisions": 0,
        "unsafe_high_risk_decision_rate": 0.0,
    }
    assert first["abstention"]["rate"] == 0.2
    assert len(first["gold_set_sha256"]) == 64


def test_evaluation_writes_stable_json_and_markdown(tmp_path: Path):
    metrics = evaluate_gold_set()
    json_path, markdown_path = write_evaluation_outputs(metrics, tmp_path)
    first_json = json_path.read_bytes()
    first_markdown = markdown_path.read_bytes()

    write_evaluation_outputs(metrics, tmp_path)

    assert json_path.read_bytes() == first_json
    assert markdown_path.read_bytes() == first_markdown
    persisted = json.loads(json_path.read_text(encoding="utf-8"))
    assert persisted["status"]["macro_f1"] == 0.866667
    report = markdown_path.read_text(encoding="utf-8")
    assert "Evidence recall@1" in report
    assert "Status confusion matrix" in report
    assert "not evidence of real-world validity" in report


def test_evaluation_script_runs_offline_and_writes_both_formats(tmp_path: Path):
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/evaluate_gold_set.py",
            "--gold",
            str(default_gold_path()),
            "--out",
            str(tmp_path),
            "--evidence-k",
            "1",
            "2",
        ],
        cwd=Path(__file__).resolve().parents[1],
        check=True,
        capture_output=True,
        text=True,
    )

    metrics = json.loads((tmp_path / "evaluation_metrics.json").read_text(encoding="utf-8"))
    assert metrics["evidence"]["recall_at_1"] == 0.5
    assert metrics["evidence"]["recall_at_2"] == 0.666667
    assert (tmp_path / "evaluation_report.md").is_file()
    assert "Claim F1=0.833333" in completed.stdout


def test_gold_loader_rejects_unknown_schema_version(tmp_path: Path):
    invalid = tmp_path / "invalid.jsonl"
    invalid.write_text(
        json.dumps(
            {
                "schema_version": "99",
                "gold_set_version": "1.0.0",
                "record_id": "future",
                "input": {},
                "gold_claims": [],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Unsupported gold-set schema_version"):
        load_gold_records(invalid)


def test_gold_loader_rejects_ambiguous_duplicate_claim_spans(tmp_path: Path):
    invalid = tmp_path / "duplicate.jsonl"
    invalid.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "gold_set_version": "1.0.0",
                "record_id": "duplicate",
                "input": {"sections": [], "tables": {}, "references": ""},
                "gold_claims": [
                    {
                        "text": "Same claim.",
                        "status": "supported",
                        "high_risk": False,
                        "relevant_evidence": [],
                    },
                    {
                        "text": "  same   CLAIM. ",
                        "status": "supported",
                        "high_risk": False,
                        "relevant_evidence": [],
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Duplicate normalized gold claim"):
        load_gold_records(invalid)


def test_prediction_scorer_counts_false_positive_status_and_validates_cutoffs():
    records = [
        {
            "schema_version": "1.0",
            "gold_set_version": "test",
            "record_id": "one",
            "input": {},
            "gold_claims": [
                {
                    "text": "Gold claim.",
                    "status": "unsupported",
                    "high_risk": False,
                    "relevant_evidence": [],
                }
            ],
        }
    ]
    predictions = {
        "one": [
            {
                "text": "Extra claim.",
                "status": "supported",
                "risk_level": "low",
                "evidence_ranked": [],
            }
        ]
    }

    metrics = evaluate_predictions(records, predictions)

    assert metrics["claim_extraction"]["precision"] == 0.0
    assert metrics["status"]["confusion_matrix"]["unsupported"]["not_extracted"] == 1
    assert metrics["status"]["confusion_matrix"]["no_gold"]["supported"] == 1
    assert metrics["status"]["per_class"]["supported"]["false_positives"] == 1
    with pytest.raises(ValueError, match="positive integers"):
        evaluate_predictions(records, predictions, evidence_ks=(0,))


def test_high_risk_supported_prediction_counts_as_unsafe_even_when_risk_flag_is_high():
    records = [
        {
            "schema_version": "1.0",
            "gold_set_version": "test",
            "record_id": "high-risk",
            "input": {},
            "gold_claims": [
                {
                    "text": "Clinical claim.",
                    "status": "needs_human_review",
                    "high_risk": True,
                    "relevant_evidence": [],
                }
            ],
        }
    ]
    predictions = {
        "high-risk": [
            {
                "text": "Clinical claim.",
                "status": "supported",
                "risk_level": "high",
                "evidence_ranked": [],
            }
        ]
    }

    metrics = evaluate_predictions(records, predictions)

    assert metrics["risk"]["high_risk_miss_rate"] == 0.0
    assert metrics["risk"]["unsafe_high_risk_decision_rate"] == 1.0
