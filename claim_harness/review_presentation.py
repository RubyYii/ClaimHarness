"""Shared wording for the human-readable audit surfaces."""

EXTRACTION_BOUNDARY = (
    "Extraction completeness: unknown. This report covers extracted claims only; "
    "sentences not listed here have not been verified."
)


def issue_label(
    status: str,
    risk: str,
    *,
    has_contradictions: bool,
    has_missing_evidence: bool,
) -> str:
    if has_contradictions:
        return "Evidence conflict"
    if status == "needs_human_review":
        return "Human review required" if risk == "high" else "Evidence needs clarification"
    if status == "overclaimed":
        return "Claim exceeds evidence"
    if has_missing_evidence:
        return "Missing evidence"
    if status == "supported":
        return "Support within screened scope"
    return "Insufficient evidence"
