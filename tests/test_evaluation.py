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
    regression_failure_count,
    run_current_pipeline,
    write_evaluation_outputs,
)


def test_default_gold_evaluation_is_deterministic_and_covers_baseline_claims():
    first = evaluate_gold_set()
    second = evaluate_gold_set()

    assert first == second
    assert first["schema_version"] == "2.1"
    assert first["gold_schema_version"] == "1.0"
    assert first["gold_set_version"] == "1.0.0"
    assert first["record_count"] == 7
    assert first["claim_extraction"] == {
        "true_positives": 7,
        "predicted": 7,
        "gold": 7,
        "precision": 1.0,
        "recall": 1.0,
        "f1": 1.0,
        "matching": "exact_after_casefold_and_whitespace_normalization",
    }
    assert first["evidence"]["recall_at_1"] == 0.833333
    assert first["evidence"]["recall_at_3"] == 1.0
    assert first["status"]["macro_f1"] == 1.0
    assert first["status"]["confusion_matrix"]["supported"]["not_extracted"] == 0
    assert first["status"]["confusion_matrix"]["needs_human_review"]["not_extracted"] == 0
    assert first["risk"] == {
        "high_risk_gold_claims": 3,
        "high_risk_misses": 0,
        "high_risk_miss_rate": 0.0,
        "unsafe_high_risk_decisions": 0,
        "unsafe_high_risk_decision_rate": 0.0,
        "unhandled_high_risk_claims": 0,
        "unhandled_high_risk_rate": 0.0,
    }
    assert first["abstention"]["rate"] == 0.285714
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
    assert persisted["status"]["macro_f1"] == 1.0
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
    assert metrics["evidence"]["recall_at_1"] == 0.833333
    assert metrics["evidence"]["recall_at_2"] == 1.0
    assert (tmp_path / "evaluation_report.md").is_file()
    assert "Claim F1=1.000000" in completed.stdout


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


def test_explicit_release_gate_blocks_high_risk_supported_prediction():
    records = [
        {
            "schema_version": "1.0",
            "gold_set_version": "test",
            "record_id": "high-risk-gated",
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
        "high-risk-gated": [
            {
                "text": "Clinical claim.",
                "status": "supported",
                "risk_level": "high",
                "human_review_required": True,
                "release_allowed": False,
                "evidence_ranked": [],
            }
        ]
    }

    metrics = evaluate_predictions(records, predictions)

    assert metrics["risk"]["high_risk_miss_rate"] == 0.0
    assert metrics["risk"]["unsafe_high_risk_decision_rate"] == 0.0


def test_release_block_without_human_review_is_still_unsafe_for_high_risk_claim():
    records = [
        {
            "schema_version": "1.0",
            "gold_set_version": "test",
            "record_id": "high-risk-inconsistent",
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
        "high-risk-inconsistent": [
            {
                "text": "Clinical claim.",
                "status": "supported",
                "risk_level": "high",
                "human_review_required": False,
                "release_allowed": False,
                "evidence_ranked": [],
            }
        ]
    }

    metrics = evaluate_predictions(records, predictions)

    assert metrics["risk"]["unsafe_high_risk_decision_rate"] == 1.0


def test_current_pipeline_projects_explicit_review_and_release_gates():
    records = load_gold_records(default_gold_path())

    predictions = run_current_pipeline(records)

    assert predictions
    assert all(
        isinstance(prediction["human_review_required"], bool)
        and isinstance(prediction["release_allowed"], bool)
        for record_predictions in predictions.values()
        for prediction in record_predictions
    )


def test_risk_gate_includes_missed_claims_and_correct_status_with_missing_review():
    records = [{
        "schema_version": "1.0", "gold_set_version": "test-risk-gap",
        "record_id": "risk-gap", "gold_claims": [{
            "text": "The system is safe for clinical use.",
            "status": "needs_human_review", "high_risk": True,
            "relevant_evidence": [],
        }],
    }]
    missed = evaluate_predictions(records, {})
    assert missed["risk"]["unsafe_high_risk_decisions"] == 0
    assert missed["risk"]["unhandled_high_risk_claims"] == 1
    assert regression_failure_count(missed) > 0

    prediction = dict(records[0]["gold_claims"][0], risk_level="high",
                      human_review_required=False, release_allowed=False)
    metrics = evaluate_predictions(records, {"risk-gap": [prediction]})
    assert metrics["status"]["confusion_matrix"]["needs_human_review"]["needs_human_review"] == 1
    assert regression_failure_count(metrics) == 1


def test_check_cli_fails_on_a_false_positive_in_a_negative_example(tmp_path):
    record = {
        "schema_version": "1.0", "gold_set_version": "test-negative",
        "record_id": "negative", "gold_claims": [],
        "input": {"sections": [{"name": "Results", "start_line": 1,
                                "text": "Alpha achieved precision of 0.86."}]},
    }
    gold_path = tmp_path / "negative.jsonl"
    gold_path.write_text(json.dumps(record) + "\n", encoding="utf-8")
    result = subprocess.run(
        [sys.executable, "scripts/evaluate_gold_set.py", "--gold", str(gold_path),
         "--check", "--out", str(tmp_path / "metrics")],
        capture_output=True, text=True, encoding="utf-8",
    )
    assert result.returncode == 1, result.stdout + result.stderr
    metrics = json.loads((tmp_path / "metrics/evaluation_metrics.json").read_text(encoding="utf-8"))
    assert metrics["negative_examples"] == {"records": 1, "false_positive_claims": 1}
