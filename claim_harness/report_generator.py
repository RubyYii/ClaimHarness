import csv
import json
import re
from collections import Counter
from pathlib import Path

from .diagnostics import write_audit_diagnostics
from .review_queue import write_human_review_queue
from .schemas import Claim, EvidenceItem, EvidenceLocator, VerificationResult


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
    write_audit_diagnostics(
        output_path / "audit_diagnostics.json", claims, evidence, results
    )
    write_human_review_queue(
        output_path / "human_review_queue.json", claims, results
    )


def _write_claim_table(path: Path, claims: list[Claim], results: list[VerificationResult]) -> None:
    result_by_claim = {result.claim_id: result for result in results}
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "claim_id",
                "text",
                "source_section",
                "source_line",
                "source_kind",
                "claim_type",
                "strength",
                "polarity",
                "requires_evidence",
                "status",
                "risk_level",
                "reason",
                "missing_evidence",
                "supporting_evidence_ids",
                "contradicting_evidence_ids",
                "suggested_revision",
            ],
        )
        writer.writeheader()
        for claim in claims:
            result = result_by_claim[claim.claim_id]
            writer.writerow(
                {
                    "claim_id": claim.claim_id,
                    "text": _spreadsheet_safe(claim.text),
                    "source_section": _spreadsheet_safe(claim.source_section),
                    "source_line": claim.source_line,
                    "source_kind": claim.source_kind,
                    "claim_type": claim.claim_type,
                    "strength": claim.strength,
                    "polarity": claim.polarity,
                    "requires_evidence": ";".join(claim.requires_evidence),
                    "status": result.status,
                    "risk_level": result.risk_level,
                    "reason": _spreadsheet_safe(result.reason),
                    "missing_evidence": ";".join(result.missing_evidence),
                    "supporting_evidence_ids": ";".join(result.supporting_evidence_ids),
                    "contradicting_evidence_ids": ";".join(result.contradicting_evidence_ids),
                    "suggested_revision": _spreadsheet_safe(result.suggested_revision),
                }
            )


def _write_evidence_map(path: Path, claims: list[Claim], evidence: list[EvidenceItem]) -> None:
    payload = {
        "claims": [
            {
                "claim_id": claim.claim_id,
                "text": claim.text,
                "source_section": claim.source_section,
                "source_line": claim.source_line,
                "source_kind": claim.source_kind,
                "claim_type": claim.claim_type,
                "polarity": claim.polarity,
                "requires_evidence": claim.requires_evidence,
                "evidence_ids": [
                    item.evidence_id for item in evidence if claim.claim_id in item.linked_claim_ids
                ],
                "evidence_links": [
                    {
                        "evidence_id": item.evidence_id,
                        "match_reason": item.claim_link_reasons.get(claim.claim_id, "linked by retrieval rule"),
                        "relation": item.claim_link_relations.get(claim.claim_id, "related"),
                        "locator": item.claim_link_locators.get(
                            claim.claim_id, item.locator
                        ).model_dump(),
                    }
                    for item in evidence
                    if claim.claim_id in item.linked_claim_ids
                ],
            }
            for claim in claims
        ],
        "evidence": [
            item.model_dump(exclude={"claim_link_locators"}) for item in evidence
        ],
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
    evidence_by_id = {item.evidence_id: item for item in evidence}
    for claim in claims:
        result = result_by_claim[claim.claim_id]
        supporting_locations = _evidence_locations(
            claim.claim_id, result.supporting_evidence_ids, evidence_by_id
        )
        contradicting_locations = _evidence_locations(
            claim.claim_id, result.contradicting_evidence_ids, evidence_by_id
        )
        lines.extend(
            [
                f"### {claim.claim_id}: {result.status}",
                "",
                claim.text,
                "",
                f"- Source section: {claim.source_section}",
                f"- Source line: {claim.source_line if claim.source_line is not None else 'unknown'}",
                f"- Source kind: {claim.source_kind}",
                f"- Risk level: {result.risk_level}",
                f"- Reason: {result.reason}",
                f"- Required evidence: {', '.join(claim.requires_evidence) or 'none'}",
                f"- Missing evidence: {', '.join(result.missing_evidence) or 'none'}",
                f"- Supporting evidence IDs: {', '.join(result.supporting_evidence_ids) or 'none'}",
                f"- Supporting evidence locations: {'; '.join(supporting_locations) or 'none'}",
                f"- Contradicting evidence IDs: {', '.join(result.contradicting_evidence_ids) or 'none'}",
                f"- Contradicting evidence locations: {'; '.join(contradicting_locations) or 'none'}",
                "",
            ]
        )
    path.write_text("\n".join(lines), encoding="utf-8")


def _evidence_locations(
    claim_id: str,
    evidence_ids: list[str],
    evidence_by_id: dict[str, EvidenceItem],
) -> list[str]:
    locations: list[str] = []
    for evidence_id in evidence_ids:
        item = evidence_by_id.get(evidence_id)
        if item is None:
            locations.append(f"{evidence_id} @ location unavailable")
            continue
        locator = item.claim_link_locators.get(claim_id, item.locator)
        locations.append(f"{evidence_id} @ {_format_locator(locator)}")
    return locations


def _format_locator(locator: EvidenceLocator) -> str:
    parts = [locator.source_file or locator.source_name]
    if locator.page_number is not None:
        parts.append(f"page {locator.page_number}")
    if locator.line is not None:
        parts.append(f"line {locator.line}")
    if locator.row is not None:
        parts.append(f"data row {locator.row}")
    if locator.cells:
        parts.append(
            "cells "
            + ", ".join(
                f"{cell.column}={cell.value}"
                + (f" ({cell.cell})" if cell.cell else "")
                for cell in locator.cells
            )
        )
    return ", ".join(parts)


def _spreadsheet_safe(value: object) -> object:
    """Prevent user-controlled CSV cells from being interpreted as spreadsheet formulas."""

    if isinstance(value, str):
        candidate = value.lstrip()
        if candidate.startswith(("+", "-")) and re.fullmatch(
            r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?",
            candidate.strip(),
        ):
            return value
        if candidate.startswith(("=", "+", "-", "@")):
            return "'" + value
    return value


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
