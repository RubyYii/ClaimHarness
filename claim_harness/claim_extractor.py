import re

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


def extract_claims(sections: list[ManuscriptSection]) -> list[Claim]:
    claims: list[Claim] = []
    for section in sections:
        for sentence in _sentences(section.text):
            lowered = sentence.lower()
            if not any(keyword in lowered for keyword in CLAIM_KEYWORDS):
                continue
            claim_id = f"C{len(claims) + 1:03d}"
            claim_type = _claim_type(lowered)
            claims.append(
                Claim(
                    claim_id=claim_id,
                    text=sentence,
                    source_section=section.name,
                    claim_type=claim_type,
                    strength=_claim_strength(claim_type, lowered),
                    requires_evidence=_required_evidence(claim_type),
                )
            )
    return claims


def _sentences(text: str) -> list[str]:
    normalized = " ".join(text.split())
    return [sentence.strip() for sentence in re.split(r"(?<=[.!?])\s+", normalized) if sentence.strip()]


def _claim_type(text: str) -> str:
    if any(term in text for term in ("clinically", "clinical", "diagnosis", "deployment")):
        return "clinical_claim"
    if any(term in text for term in ("outperforms", "improves", "increases", "dice", "iou", "precision", "recall")):
        return "performance_claim"
    if any(term in text for term in ("novel", "first")):
        return "novelty_claim"
    if any(term in text for term in ("robust", "reliable")):
        return "robustness_claim"
    if any(term in text for term in ("workflow", "trace", "review", "auditable", "explainable", "enables", "supports")):
        return "workflow_claim"
    return "general_claim"


def _claim_strength(claim_type: str, text: str) -> str:
    if claim_type == "clinical_claim":
        return "high"
    if any(term in text for term in ("outperforms", "improves", "increases")):
        return "strong"
    if any(term in text for term in ("supports", "enables", "robust", "reliable")):
        return "moderate"
    return "weak"


def _required_evidence(claim_type: str) -> list[str]:
    if claim_type == "performance_claim":
        return ["table", "result_text"]
    if claim_type == "clinical_claim":
        return ["external_validation", "human_review"]
    if claim_type == "workflow_claim":
        return ["ablation", "trace"]
    return ["manuscript_context"]
