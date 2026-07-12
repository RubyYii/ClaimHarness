"""Deterministic, offline evaluation for the ClaimHarness mock pipeline.

The scorer intentionally uses exact normalized claim spans. This keeps the
small synthetic gate reproducible and makes matching errors visible instead of
hiding them behind a semantic model or network dependency.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Iterable

import pandas as pd

from .claim_extractor import extract_claims
from .evidence_retriever import retrieve_evidence
from .schemas import EvidenceItem, ManuscriptSection
from .verifier import verify_claims


GOLD_SET_SCHEMA_VERSION = "1.0"
EVALUATION_REPORT_SCHEMA_VERSION = "2.0"
STATUS_LABELS = (
    "supported",
    "weakly_supported",
    "unsupported",
    "overclaimed",
    "needs_human_review",
)
NOT_EXTRACTED = "not_extracted"
NO_GOLD = "no_gold"


def default_gold_path() -> Path:
    return Path(__file__).with_name("eval_data") / "gold_claims.jsonl"


def load_gold_records(path: str | Path | None = None) -> list[dict[str, object]]:
    gold_path = Path(path) if path is not None else default_gold_path()
    records: list[dict[str, object]] = []
    seen_record_ids: set[str] = set()
    gold_versions: set[str] = set()

    for line_number, line in enumerate(gold_path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON on gold-set line {line_number}: {exc}") from exc
        if not isinstance(record, dict):
            raise ValueError(f"Gold-set line {line_number} must contain a JSON object.")
        if record.get("schema_version") != GOLD_SET_SCHEMA_VERSION:
            raise ValueError(
                f"Unsupported gold-set schema_version on line {line_number}: "
                f"{record.get('schema_version')!r}."
            )
        record_id = record.get("record_id")
        if not isinstance(record_id, str) or not record_id.strip():
            raise ValueError(f"Gold-set line {line_number} has no record_id.")
        if record_id in seen_record_ids:
            raise ValueError(f"Duplicate gold-set record_id: {record_id}.")
        seen_record_ids.add(record_id)

        gold_version = record.get("gold_set_version")
        if not isinstance(gold_version, str) or not gold_version.strip():
            raise ValueError(f"Gold-set record {record_id} has no gold_set_version.")
        gold_versions.add(gold_version)
        _validate_gold_claims(record_id, record.get("gold_claims"))
        if not isinstance(record.get("input"), dict):
            raise ValueError(f"Gold-set record {record_id} has no input object.")
        records.append(record)

    if not records:
        raise ValueError("Gold set contains no records.")
    if len(gold_versions) != 1:
        raise ValueError("All records in a gold set must use the same gold_set_version.")
    return records


def run_current_pipeline(records: Iterable[dict[str, object]]) -> dict[str, list[dict[str, object]]]:
    predictions: dict[str, list[dict[str, object]]] = {}
    for record in records:
        record_id = str(record["record_id"])
        input_data = record["input"]
        if not isinstance(input_data, dict):
            raise ValueError(f"Gold-set record {record_id} has an invalid input object.")

        sections = [
            ManuscriptSection.model_validate(section)
            for section in _require_list(input_data, "sections", record_id)
        ]
        raw_tables = input_data.get("tables", {})
        if not isinstance(raw_tables, dict):
            raise ValueError(f"Gold-set record {record_id} tables must be an object.")
        tables = {
            str(name): pd.DataFrame(rows)
            for name, rows in sorted(raw_tables.items())
        }
        references = input_data.get("references", "")
        if not isinstance(references, str):
            raise ValueError(f"Gold-set record {record_id} references must be text.")

        claims = extract_claims(sections)
        evidence = retrieve_evidence(claims, sections, tables, references)
        verification_by_claim = {
            result.claim_id: result for result in verify_claims(claims, evidence)
        }
        predictions[record_id] = [
            {
                "claim_id": claim.claim_id,
                "text": claim.text,
                "status": verification_by_claim[claim.claim_id].status,
                "risk_level": verification_by_claim[claim.claim_id].risk_level,
                "human_review_required": verification_by_claim[
                    claim.claim_id
                ].human_review_required,
                "release_allowed": verification_by_claim[claim.claim_id].release_allowed,
                "evidence_ranked": _ranked_evidence_keys(claim.claim_id, evidence),
            }
            for claim in claims
        ]
    return predictions


def evaluate_predictions(
    records: Iterable[dict[str, object]],
    predictions: dict[str, list[dict[str, object]]],
    *,
    evidence_ks: tuple[int, ...] = (1, 3, 5),
) -> dict[str, object]:
    record_list = list(records)
    if not evidence_ks or any(k <= 0 for k in evidence_ks):
        raise ValueError("evidence_ks must contain positive integers.")
    ks = tuple(sorted(set(evidence_ks)))

    total_gold = 0
    total_predictions = 0
    extraction_true_positives = 0
    confusion_columns = (*STATUS_LABELS, NOT_EXTRACTED)
    confusion = {
        row: {column: 0 for column in confusion_columns}
        for row in (*STATUS_LABELS, NO_GOLD)
    }
    evidence_scores = {k: [] for k in ks}
    high_risk_total = 0
    high_risk_misses = 0
    unsafe_high_risk_decisions = 0
    abstentions = 0

    for record in record_list:
        record_id = str(record["record_id"])
        gold_claims = record["gold_claims"]
        if not isinstance(gold_claims, list):
            raise ValueError(f"Gold-set record {record_id} has invalid gold_claims.")
        predicted_claims = predictions.get(record_id, [])
        if not isinstance(predicted_claims, list):
            raise ValueError(f"Predictions for {record_id} must be a list.")

        gold_by_text = _unique_claim_map(gold_claims, record_id=record_id, role="gold")
        predicted_by_text = _unique_claim_map(
            predicted_claims,
            record_id=record_id,
            role="prediction",
        )
        total_gold += len(gold_by_text)
        total_predictions += len(predicted_by_text)
        extraction_true_positives += len(set(gold_by_text) & set(predicted_by_text))

        for prediction in predicted_by_text.values():
            status = prediction.get("status")
            if status not in STATUS_LABELS:
                raise ValueError(f"Prediction in {record_id} has invalid status: {status!r}.")
            if status == "needs_human_review":
                abstentions += 1

        for normalized_text, gold in gold_by_text.items():
            gold_status = gold.get("status")
            if gold_status not in STATUS_LABELS:
                raise ValueError(f"Gold claim in {record_id} has invalid status: {gold_status!r}.")
            prediction = predicted_by_text.get(normalized_text)
            predicted_status = NOT_EXTRACTED if prediction is None else str(prediction["status"])
            confusion[str(gold_status)][predicted_status] += 1

            is_high_risk = gold.get("high_risk") is True
            if is_high_risk:
                high_risk_total += 1
                if prediction is None or prediction.get("risk_level") != "high":
                    high_risk_misses += 1
                if prediction is not None and _is_unsafe_high_risk_prediction(
                    prediction
                ):
                    unsafe_high_risk_decisions += 1

            relevant = gold.get("relevant_evidence", [])
            if not isinstance(relevant, list) or not all(isinstance(item, str) for item in relevant):
                raise ValueError(f"Gold claim in {record_id} has invalid relevant_evidence.")
            if relevant:
                ranked = [] if prediction is None else prediction.get("evidence_ranked", [])
                if not isinstance(ranked, list) or not all(isinstance(item, str) for item in ranked):
                    raise ValueError(f"Prediction in {record_id} has invalid evidence_ranked.")
                relevant_set = set(relevant)
                for k in ks:
                    evidence_scores[k].append(
                        len(relevant_set & set(ranked[:k])) / len(relevant_set)
                    )

        for normalized_text, prediction in predicted_by_text.items():
            if normalized_text not in gold_by_text:
                confusion[NO_GOLD][str(prediction["status"])] += 1

    precision = _safe_divide(extraction_true_positives, total_predictions)
    recall = _safe_divide(extraction_true_positives, total_gold)
    extraction_f1 = _f1(precision, recall)
    status_per_class = _status_scores(confusion)
    macro_f1 = sum(score["f1"] for score in status_per_class.values()) / len(STATUS_LABELS)
    evidence_recall = {
        f"recall_at_{k}": _rounded(sum(scores) / len(scores) if scores else 0.0)
        for k, scores in evidence_scores.items()
    }

    gold_version = str(record_list[0]["gold_set_version"]) if record_list else "unknown"
    return {
        "schema_version": EVALUATION_REPORT_SCHEMA_VERSION,
        "gold_schema_version": GOLD_SET_SCHEMA_VERSION,
        "gold_set_version": gold_version,
        "record_count": len(record_list),
        "claim_extraction": {
            "true_positives": extraction_true_positives,
            "predicted": total_predictions,
            "gold": total_gold,
            "precision": _rounded(precision),
            "recall": _rounded(recall),
            "f1": _rounded(extraction_f1),
            "matching": "exact_after_casefold_and_whitespace_normalization",
        },
        "evidence": {
            **evidence_recall,
            "claims_with_gold_evidence": len(next(iter(evidence_scores.values()), [])),
        },
        "status": {
            "macro_f1": _rounded(macro_f1),
            "per_class": status_per_class,
            "confusion_matrix": confusion,
            "rows": [*STATUS_LABELS, NO_GOLD],
            "columns": [*STATUS_LABELS, NOT_EXTRACTED],
        },
        "risk": {
            "high_risk_gold_claims": high_risk_total,
            "high_risk_misses": high_risk_misses,
            "high_risk_miss_rate": _rounded(_safe_divide(high_risk_misses, high_risk_total)),
            "unsafe_high_risk_decisions": unsafe_high_risk_decisions,
            "unsafe_high_risk_decision_rate": _rounded(
                _safe_divide(unsafe_high_risk_decisions, high_risk_total)
            ),
        },
        "abstention": {
            "needs_human_review_predictions": abstentions,
            "prediction_count": total_predictions,
            "rate": _rounded(_safe_divide(abstentions, total_predictions)),
        },
        "definitions": {
            "high_risk_miss": "A gold high-risk claim was not extracted or was not assigned risk_level=high.",
            "unsafe_high_risk_decision": "A gold high-risk claim was not explicitly routed to human review and release-blocked, or used a legacy supported/weakly_supported prediction without explicit gates.",
            "abstention": "A predicted claim was assigned needs_human_review.",
            "evidence_recall_at_k": "Mean fraction of each gold claim's relevant evidence found in its first k linked evidence items.",
        },
    }


def _is_unsafe_high_risk_prediction(prediction: dict[str, object]) -> bool:
    release_allowed = prediction.get("release_allowed")
    human_review_required = prediction.get("human_review_required")
    if isinstance(release_allowed, bool) or isinstance(human_review_required, bool):
        return not (
            release_allowed is False and human_review_required is True
        )
    return prediction.get("status") in {"supported", "weakly_supported"}


def evaluate_gold_set(
    path: str | Path | None = None,
    *,
    evidence_ks: tuple[int, ...] = (1, 3, 5),
) -> dict[str, object]:
    gold_path = Path(path) if path is not None else default_gold_path()
    records = load_gold_records(gold_path)
    metrics = evaluate_predictions(
        records,
        run_current_pipeline(records),
        evidence_ks=evidence_ks,
    )
    metrics["gold_set_sha256"] = hashlib.sha256(gold_path.read_bytes()).hexdigest()
    return metrics


def write_evaluation_outputs(metrics: dict[str, object], out: str | Path) -> tuple[Path, Path]:
    output_dir = Path(out)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "evaluation_metrics.json"
    markdown_path = output_dir / "evaluation_report.md"
    json_path.write_text(
        json.dumps(metrics, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    markdown_path.write_text(_metrics_markdown(metrics), encoding="utf-8")
    return json_path, markdown_path


def evidence_locator_key(item: EvidenceItem) -> str:
    locator = item.locator
    if locator.row is not None:
        position = f"row:{locator.row}"
    elif locator.line is not None:
        position = f"line:{locator.line}"
    else:
        position = "document"
    return f"{locator.source_kind}:{locator.source_name}:{position}"


def _ranked_evidence_keys(claim_id: str, evidence: list[EvidenceItem]) -> list[str]:
    relation_priority = {"supports": 0, "contradicts": 1, "related": 2}
    linked = [item for item in evidence if claim_id in item.linked_claim_ids]
    linked.sort(
        key=lambda item: (
            relation_priority.get(item.claim_link_relations.get(claim_id, "supports"), 3),
            item.evidence_id,
        )
    )
    return [evidence_locator_key(item) for item in linked]


def _validate_gold_claims(record_id: str, claims: object) -> None:
    if not isinstance(claims, list) or not claims:
        raise ValueError(f"Gold-set record {record_id} must contain at least one gold claim.")
    _unique_claim_map(claims, record_id=record_id, role="gold")
    for claim in claims:
        if claim.get("status") not in STATUS_LABELS:
            raise ValueError(f"Gold claim in {record_id} has an invalid status.")
        if not isinstance(claim.get("high_risk"), bool):
            raise ValueError(f"Gold claim in {record_id} must declare high_risk as a boolean.")


def _require_list(data: dict[str, object], key: str, record_id: str) -> list[object]:
    value = data.get(key)
    if not isinstance(value, list):
        raise ValueError(f"Gold-set record {record_id} {key} must be a list.")
    return value


def _unique_claim_map(
    claims: list[object],
    *,
    record_id: str,
    role: str,
) -> dict[str, dict[str, object]]:
    mapped: dict[str, dict[str, object]] = {}
    for claim in claims:
        if not isinstance(claim, dict) or not isinstance(claim.get("text"), str):
            raise ValueError(f"Each {role} claim in {record_id} must have text.")
        normalized = _normalize_claim_text(str(claim["text"]))
        if not normalized:
            raise ValueError(f"A {role} claim in {record_id} has empty text.")
        if normalized in mapped:
            raise ValueError(f"Duplicate normalized {role} claim text in {record_id}.")
        mapped[normalized] = claim
    return mapped


def _normalize_claim_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().casefold()


def _status_scores(confusion: dict[str, dict[str, int]]) -> dict[str, dict[str, object]]:
    scores: dict[str, dict[str, object]] = {}
    for label in STATUS_LABELS:
        true_positive = confusion[label][label]
        false_positive = sum(
            confusion[row][label]
            for row in (*STATUS_LABELS, NO_GOLD)
            if row != label
        )
        false_negative = sum(
            count for predicted, count in confusion[label].items() if predicted != label
        )
        precision = _safe_divide(true_positive, true_positive + false_positive)
        recall = _safe_divide(true_positive, true_positive + false_negative)
        scores[label] = {
            "true_positives": true_positive,
            "false_positives": false_positive,
            "false_negatives": false_negative,
            "precision": _rounded(precision),
            "recall": _rounded(recall),
            "f1": _rounded(_f1(precision, recall)),
        }
    return scores


def _metrics_markdown(metrics: dict[str, object]) -> str:
    extraction = metrics["claim_extraction"]
    evidence = metrics["evidence"]
    status = metrics["status"]
    risk = metrics["risk"]
    abstention = metrics["abstention"]
    lines = [
        "# ClaimHarness Synthetic Evaluation",
        "",
        f"- Gold set version: {metrics['gold_set_version']}",
        f"- Records: {metrics['record_count']}",
        f"- Gold-set SHA-256: `{metrics.get('gold_set_sha256', 'not recorded')}`",
        "",
        "## Metrics",
        "",
        "| Metric | Value |",
        "|---|---:|",
        f"| Claim precision | {extraction['precision']:.6f} |",
        f"| Claim recall | {extraction['recall']:.6f} |",
        f"| Claim F1 | {extraction['f1']:.6f} |",
        f"| Status macro-F1 | {status['macro_f1']:.6f} |",
        f"| High-risk miss rate | {risk['high_risk_miss_rate']:.6f} |",
        f"| Unsafe high-risk decision rate | {risk['unsafe_high_risk_decision_rate']:.6f} |",
        f"| Abstention rate | {abstention['rate']:.6f} |",
    ]
    for key, value in evidence.items():
        if key.startswith("recall_at_"):
            cutoff = key.rsplit("_", 1)[-1]
            lines.append(f"| Evidence recall@{cutoff} | {value:.6f} |")
    lines.extend(
        [
            "",
            "## Status confusion matrix",
            "",
            "Rows are gold labels; columns are predictions.",
            "",
            "| Gold \\ Predicted | " + " | ".join(status["columns"]) + " |",
            "|---|" + "---:|" * len(status["columns"]),
        ]
    )
    for row in status["rows"]:
        lines.append(
            f"| {row} | "
            + " | ".join(str(status["confusion_matrix"][row][column]) for column in status["columns"])
            + " |"
        )
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            "This is a small, versioned synthetic regression set. It is not evidence of real-world validity, clinical safety, or cross-language performance.",
            "",
        ]
    )
    return "\n".join(lines)


def _safe_divide(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def _f1(precision: float, recall: float) -> float:
    return 2 * precision * recall / (precision + recall) if precision + recall else 0.0


def _rounded(value: float) -> float:
    return round(value, 6)
