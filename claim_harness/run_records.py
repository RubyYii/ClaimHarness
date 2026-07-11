from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from .evidence_contract import LoadedEvidenceContract
from .schemas import Claim, VerificationResult


MANIFEST_NAME = "run_manifest.json"
SUMMARY_LOG_NAME = "project_summary_log.md"
MANIFEST_SCHEMA_VERSION = 2
MAX_REVISION_ROUNDS = 3


def capture_input_records(
    manuscript: Path,
    tables: Path,
    references: Path | None,
    evidence_contract: LoadedEvidenceContract | None = None,
) -> dict[str, object]:
    """Capture one immutable, share-safe input fingerprint set before a run."""

    return {
        "manuscript": _file_record(manuscript),
        "tables": [_file_record(path) for path in sorted(tables.glob("*.csv"))],
        "references": _file_record(references) if references is not None else None,
        "evidence_contract": (
            {
                "path": evidence_contract.safe_path,
                "size_bytes": evidence_contract.size_bytes,
                "sha256": evidence_contract.sha256,
                "schema_version": evidence_contract.contract.schema_version,
                "project_id": evidence_contract.contract.project_id,
                "contract_id": evidence_contract.contract.contract_id,
            }
            if evidence_contract is not None
            else None
        ),
    }


def write_run_records(
    out_dir: str | Path,
    *,
    run_id: str,
    started_at: str,
    tool_version: str,
    provider: str,
    provider_status: str,
    manuscript: Path,
    tables: Path,
    references: Path | None,
    claims: list[Claim],
    results: list[VerificationResult],
    artifact_names: Iterable[str],
    evidence_contract: LoadedEvidenceContract | None = None,
    project_id: str | None = None,
    input_records: dict[str, object] | None = None,
    provider_details: dict[str, object] | None = None,
    run_spec_sha256: str | None = None,
) -> tuple[Path, Path]:
    """Write machine-readable provenance and a concise human project log.

    Paths in these records are reduced to filenames so a shared audit package
    does not disclose the user's absolute local filesystem layout.
    """

    root = Path(out_dir)
    artifacts = [name for name in artifact_names if (root / name).is_file()]
    counts = Counter(result.status for result in results)
    inputs = input_records or capture_input_records(
        manuscript, tables, references, evidence_contract
    )
    outputs = [_file_record(root / name) for name in artifacts]
    completed_at = _utc_now()
    manifest = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "project_id": project_id,
        "run_id": run_id,
        "tool": {"name": "claim-harness", "version": tool_version},
        "started_at": started_at,
        "completed_at": completed_at,
        "provider": {
            "name": provider,
            "status": provider_status,
            **(provider_details or {}),
        },
        "run_spec_sha256": run_spec_sha256,
        "inputs": inputs,
        "summary": {
            "claims": len(claims),
            "status_counts": dict(sorted(counts.items())),
            "high_risk_claim_ids": [
                result.claim_id for result in results if result.risk_level == "high"
            ],
        },
        "outputs": outputs,
    }
    manifest_path = root / MANIFEST_NAME
    _atomic_write(
        manifest_path,
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
    )

    result_by_id = {result.claim_id: result for result in results}
    unresolved = [
        claim
        for claim in claims
        if result_by_id[claim.claim_id].status != "supported"
    ]
    lines = [
        "# Project Summary Log",
        "",
        "## Run",
        "",
        f"- Project ID: `{project_id or 'not assigned'}`",
        f"- Run ID: `{run_id}`",
        f"- Started: {started_at}",
        f"- Completed: {completed_at}",
        f"- ClaimHarness version: {tool_version}",
        f"- Provider: {provider} ({provider_status})",
        f"- Manuscript: {manuscript.name}",
        f"- References: {references.name if references is not None else 'not supplied'}",
        (
            f"- Evidence contract: {evidence_contract.safe_path} "
            f"(schema {evidence_contract.contract.schema_version}; sha256 {evidence_contract.sha256})"
            if evidence_contract is not None
            else "- Evidence contract: not supplied (built-in legacy verification rules used)"
        ),
        f"- Tables: {', '.join(path.name for path in sorted(tables.glob('*.csv')))}",
        "",
        "## Audit Snapshot",
        "",
        f"- Claims audited: {len(claims)}",
    ]
    for status in (
        "supported",
        "weakly_supported",
        "unsupported",
        "overclaimed",
        "needs_human_review",
    ):
        lines.append(f"- {status}: {counts.get(status, 0)}")
    lines.extend(["", "## Claims Requiring Follow-up", ""])
    if unresolved:
        for claim in unresolved:
            result = result_by_id[claim.claim_id]
            location = (
                f"{claim.source_section}, line {claim.source_line}"
                if claim.source_line is not None
                else claim.source_section
            )
            lines.append(
                f"- {claim.claim_id} [{result.status}; {result.risk_level} risk] "
                f"{location}: {claim.text}"
            )
    else:
        lines.append("- No follow-up claims in this run.")
    lines.extend(
        [
            "",
            "## Artifact Index",
            "",
            *[f"- `{name}`" for name in [*artifacts, MANIFEST_NAME, SUMMARY_LOG_NAME]],
            "",
            "## Revision Guardrail",
            "",
            f"- Use at most {MAX_REVISION_ROUNDS} revision rounds for one stable target.",
            "- After round 3, accept the result or escalate the specification, evidence, or structure; do not apply a fourth patch to the same target.",
            "- Record what changed and how it was verified before starting the next round.",
            "",
            "## Interpretation Boundary",
            "",
            "This log is a navigation and provenance aid. It is not scientific evidence, a peer review, or a clinical decision.",
        ]
    )
    summary_path = root / SUMMARY_LOG_NAME
    _atomic_write(summary_path, "\n".join(lines).rstrip() + "\n")
    return manifest_path, summary_path


def _file_record(path: Path) -> dict[str, object]:
    return {
        "name": path.name,
        "size_bytes": path.stat().st_size,
        "sha256": _sha256(path),
    }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _atomic_write(path: Path, text: str) -> None:
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(text, encoding="utf-8")
    temporary.replace(path)


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
