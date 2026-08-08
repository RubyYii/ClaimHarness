import re

from .evidence_contract import EvidenceContract
from .schemas import Claim, ManuscriptSection


CLAIM_KEYWORDS = {
    "improves",
    "outperforms",
    "robust",
    "reliable",
    "clinically",
    "ready",
    "novel",
    "first",
    "supports",
    "enables",
    "reduces",
    "increases",
    "auditable",
    "explainable",
}

META_STATEMENT_PATTERNS = (
    r"\b(?:manuscript|draft|sentence|text|example)\s+"
    r"(?:explicitly\s+|intentionally\s+)?(?:overclaims?|claims?|says|states|warns?)\b",
    r"\bsentence\s+(?:says|states|claims)\b",
    r"\b(?:warns?|warning|cautions?)\s+(?:against|about)\s+"
    r"(?:claiming|saying|calling)\b",
    r"\b(?:claim|statement|sentence)\s+(?:would|should|could|can|is)\s+be\s+"
    r"(?:an?\s+)?overclaim\b",
    r"\bintentionally\s+(?:include|includes|included)\s+claims?\b",
)


def extract_claims(
    sections: list[ManuscriptSection],
    evidence_contract: EvidenceContract | None = None,
) -> list[Claim]:
    claims: list[Claim] = []
    for section in sections:
        for sentence, source_line in sentences_with_lines(section):
            lowered = sentence.lower()
            matched_terms = [term for term in CLAIM_KEYWORDS if contains_term(lowered, term)]
            if not matched_terms or is_meta_statement(lowered):
                continue

            claim_id = f"C{len(claims) + 1:03d}"
            claim_type = _claim_type(lowered)
            claims.append(
                Claim(
                    claim_id=claim_id,
                    text=sentence,
                    source_section=section.name,
                    source_line=source_line,
                    claim_type=claim_type,
                    strength=_claim_strength(claim_type, lowered),
                    polarity=statement_polarity(lowered, matched_terms),
                    requires_evidence=(
                        list(evidence_contract.claim_rules[claim_type].required_evidence)
                        if evidence_contract is not None
                        else _required_evidence(claim_type)
                    ),
                    source_kind=section.source_kind,
                )
            )
    return claims


def sentences_with_lines(section: ManuscriptSection) -> list[tuple[str, int | None]]:
    sentences: list[tuple[str, int | None]] = []
    buffer: list[str] = []
    buffer_line: int | None = None
    content_start = section.content_start_line
    if content_start is None and section.start_line is not None:
        content_start = section.start_line + 1

    for offset, line in enumerate(section.text.splitlines()):
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("<!--") and "provenance:" in stripped.lower():
            # Provenance markers affect source classification but are not
            # manuscript content and must never be merged into a claim.
            continue
        line_number = content_start + offset if content_start is not None else None
        parts = [part.strip() for part in re.split(r"(?<=[.!?])\s+", stripped) if part.strip()]
        for part in parts:
            if not buffer:
                buffer_line = line_number
            buffer.append(part)
            if part.endswith((".", "!", "?")):
                sentences.append((" ".join(buffer).strip(), buffer_line))
                buffer = []
                buffer_line = None

    if buffer:
        sentences.append((" ".join(buffer).strip(), buffer_line))
    return sentences


def contains_term(text: str, term: str) -> bool:
    return bool(re.search(rf"(?<!\w){re.escape(term)}(?!\w)", text, flags=re.IGNORECASE))


def term_is_negated(text: str, term: str) -> bool:
    term_pattern = re.compile(rf"(?<!\w){re.escape(term)}(?!\w)", flags=re.IGNORECASE)
    matches = list(term_pattern.finditer(text))
    if not matches:
        return False

    negation_pattern = re.compile(
        r"(?:\b(?:not|never|cannot|can't|isn't|aren't|wasn't|weren't|doesn't|don't|"
        r"didn't|shouldn't|wouldn't|couldn't|mustn't)\b|\bno\b)"
        r"(?:\W+\w+){0,4}\W*$",
        flags=re.IGNORECASE,
    )
    return all(
        bool(negation_pattern.search(text[max(0, match.start() - 80) : match.start()]))
        for match in matches
    )


def statement_polarity(text: str, terms: list[str] | None = None) -> str:
    if terms:
        matched_terms = [term for term in terms if contains_term(text, term)]
        if matched_terms and all(term_is_negated(text, term) for term in matched_terms):
            return "negative"
        return "positive"

    if re.search(
        r"\b(?:not|never|cannot|can't|isn't|aren't|wasn't|weren't|doesn't|don't|"
        r"didn't|shouldn't|wouldn't|couldn't|mustn't)\b",
        text,
        flags=re.IGNORECASE,
    ):
        return "negative"
    if re.search(
        r"\bno\s+(?:evidence|validation|support|improvement|benefit|difference|effect)\b",
        text,
        flags=re.IGNORECASE,
    ):
        return "negative"
    return "positive"


def is_meta_statement(text: str) -> bool:
    return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in META_STATEMENT_PATTERNS)


def _claim_type(text: str) -> str:
    if any(contains_term(text, term) for term in ("clinically", "clinical", "diagnosis")):
        return "clinical_claim"
    if any(
        contains_term(text, term)
        for term in ("deployment", "operational", "ready", "readiness")
    ):
        return "deployment_claim"
    if any(
        contains_term(text, term)
        for term in ("outperforms", "improves", "increases", "dice", "iou", "precision", "recall")
    ):
        return "performance_claim"
    if any(contains_term(text, term) for term in ("novel", "first")):
        return "novelty_claim"
    if any(contains_term(text, term) for term in ("robust", "reliable")):
        return "robustness_claim"
    if any(
        contains_term(text, term)
        for term in ("workflow", "trace", "review", "auditable", "explainable", "enables", "supports")
    ):
        return "workflow_claim"
    return "general_claim"


def _claim_strength(claim_type: str, text: str) -> str:
    if claim_type in {"clinical_claim", "deployment_claim"}:
        return "high"
    if any(contains_term(text, term) for term in ("outperforms", "improves", "increases")):
        return "strong"
    if any(
        contains_term(text, term) for term in ("supports", "enables", "robust", "reliable")
    ):
        return "moderate"
    return "weak"


def _required_evidence(claim_type: str) -> list[str]:
    if claim_type == "performance_claim":
        return ["table"]
    if claim_type in {"clinical_claim", "deployment_claim"}:
        return ["external_validation", "human_review"]
    if claim_type == "workflow_claim":
        return ["trace"]
    if claim_type == "robustness_claim":
        return ["robustness_test"]
    if claim_type == "novelty_claim":
        return ["citation"]
    return ["manuscript_context"]
