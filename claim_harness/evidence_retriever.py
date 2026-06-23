import re
from collections.abc import Iterable

import pandas as pd

from .schemas import Claim, EvidenceItem, ManuscriptSection


STOPWORDS = {
    "about",
    "after",
    "also",
    "and",
    "because",
    "before",
    "being",
    "claim",
    "claims",
    "could",
    "from",
    "into",
    "more",
    "that",
    "than",
    "the",
    "this",
    "under",
    "when",
    "with",
    "without",
    "workflow",
}


def retrieve_evidence(
    claims: list[Claim],
    sections: list[ManuscriptSection],
    tables: dict[str, pd.DataFrame],
    references: str,
) -> list[EvidenceItem]:
    evidence: list[EvidenceItem] = []
    evidence.extend(_table_evidence(tables))
    evidence.extend(_section_evidence(sections))
    evidence.extend(_reference_evidence(references))

    for item in evidence:
        item.linked_claim_ids = [
            claim.claim_id
            for claim in claims
            if _has_overlap(claim.text, item.text) or _source_mentions_claim(item.source, claim.text)
        ]

    return evidence


def _table_evidence(tables: dict[str, pd.DataFrame]) -> list[EvidenceItem]:
    items: list[EvidenceItem] = []
    for table_name, frame in sorted(tables.items()):
        evidence_type = "ablation_result" if "ablation" in table_name else "quantitative_result"
        for row_index, row in frame.iterrows():
            row_text = "; ".join(f"{column}={row[column]}" for column in frame.columns)
            items.append(
                EvidenceItem(
                    evidence_id=f"E{len(items) + 1:03d}",
                    source=table_name,
                    evidence_type=evidence_type,
                    text=row_text,
                )
            )
    return items


def _section_evidence(sections: list[ManuscriptSection]) -> list[EvidenceItem]:
    items: list[EvidenceItem] = []
    for section in sections:
        if section.name.lower() not in {"results", "discussion", "methods"}:
            continue
        for sentence in _sentences(section.text):
            lowered = sentence.lower()
            if section.name.lower() == "results":
                evidence_type = "quantitative_result"
            elif any(term in lowered for term in ("limitation", "not ", "no external", "should not")):
                evidence_type = "limitation_statement"
            else:
                evidence_type = "workflow_trace"
            items.append(
                EvidenceItem(
                    evidence_id=f"S{len(items) + 1:03d}",
                    source=section.name,
                    evidence_type=evidence_type,
                    text=sentence,
                )
            )
    return items


def _reference_evidence(references: str) -> list[EvidenceItem]:
    items: list[EvidenceItem] = []
    for line in references.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        items.append(
            EvidenceItem(
                evidence_id=f"R{len(items) + 1:03d}",
                source="references",
                evidence_type="citation",
                text=stripped,
            )
        )
    return items


def _sentences(text: str) -> list[str]:
    normalized = " ".join(text.split())
    return [sentence.strip() for sentence in re.split(r"(?<=[.!?])\s+", normalized) if sentence.strip()]


def _tokens(text: str) -> set[str]:
    tokens = {token for token in re.findall(r"[a-zA-Z0-9_]+", text.lower()) if len(token) > 3}
    return tokens - STOPWORDS


def _has_overlap(claim_text: str, evidence_text: str) -> bool:
    claim_tokens = _tokens(claim_text)
    evidence_tokens = _tokens(evidence_text)
    return len(claim_tokens & evidence_tokens) >= 2


def _source_mentions_claim(source: str, claim_text: str) -> bool:
    source_tokens = _tokens(source)
    claim_tokens = _tokens(claim_text)
    return bool(source_tokens & claim_tokens)
