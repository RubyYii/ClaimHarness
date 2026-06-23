import csv
import json
from collections import Counter
from pathlib import Path

from .schemas import Claim, EvidenceItem, VerificationResult


def write_outputs(
    out_dir: str | Path,
    claims: list[Claim],
    evidence: list[EvidenceItem],
    results: list[VerificationResult],
) -> None:
    output_path = Path(out_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    _write_claim_table(output_path / "claim_table.csv", claims, results)
    _write_evidence_map(output_path / "evidence_map.json", claims, evidence)
    _write_audit_report(output_path / "audit_report.md", claims, evidence, results)
    _write_revision_suggestions(output_path / "revision_suggestions.md", claims, results)


def _write_claim_table(path: Path, claims: list[Claim], results: list[VerificationResult]) -> None:
    result_by_claim = {result.claim_id: result for result in results}
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "claim_id",
                "text",
                "source_section",
                "claim_type",
                "strength",
                "status",
                "risk_level",
                "reason",
                "suggested_revision",
            ],
        )
        writer.writeheader()
        for claim in claims:
            result = result_by_claim[claim.claim_id]
            writer.writerow(
                {
                    "claim_id": claim.claim_id,
                    "text": claim.text,
                    "source_section": claim.source_section,
                    "claim_type": claim.claim_type,
                    "strength": claim.strength,
                    "status": result.status,
                    "risk_level": result.risk_level,
                    "reason": result.reason,
                    "suggested_revision": result.suggested_revision,
                }
            )


def _write_evidence_map(path: Path, claims: list[Claim], evidence: list[EvidenceItem]) -> None:
    payload = {
        "claims": [
            {
                "claim_id": claim.claim_id,
                "text": claim.text,
                "evidence_ids": [
                    item.evidence_id for item in evidence if claim.claim_id in item.linked_claim_ids
                ],
            }
            for claim in claims
        ],
        "evidence": [item.model_dump() for item in evidence],
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _write_audit_report(
    path: Path,
    claims: list[Claim],
    evidence: list[EvidenceItem],
    results: list[VerificationResult],
) -> None:
    counts = Counter(result.status for result in results)
    lines = [
        "# ClaimHarness Audit Report",
        "",
        "## Summary",
        "",
        f"- Claims audited: {len(claims)}",
        f"- Evidence items collected: {len(evidence)}",
    ]
    for status, count in sorted(counts.items()):
        lines.append(f"- {status}: {count}")
    lines.extend(["", "## Claim Results", ""])
    result_by_claim = {result.claim_id: result for result in results}
    for claim in claims:
        result = result_by_claim[claim.claim_id]
        lines.extend(
            [
                f"### {claim.claim_id}: {result.status}",
                "",
                claim.text,
                "",
                f"- Source section: {claim.source_section}",
                f"- Risk level: {result.risk_level}",
                f"- Reason: {result.reason}",
                "",
            ]
        )
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_revision_suggestions(
    path: Path,
    claims: list[Claim],
    results: list[VerificationResult],
) -> None:
    claim_by_id = {claim.claim_id: claim for claim in claims}
    lines = ["# Revision Suggestions", ""]
    for result in results:
        if result.status == "supported":
            continue
        claim = claim_by_id[result.claim_id]
        lines.extend(
            [
                f"## {claim.claim_id}: {result.status}",
                "",
                f"Original: {claim.text}",
                "",
                f"Suggestion: {result.suggested_revision}",
                "",
            ]
        )
    if len(lines) == 2:
        lines.append("No revisions suggested.")
    path.write_text("\n".join(lines), encoding="utf-8")
