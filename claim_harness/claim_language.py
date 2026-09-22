"""Small shared lexical rules; these do not establish semantic completeness."""
import re


CLINICAL_TERMS = (
    "clinical", "clinically", "diagnosis", "biomedical",
    "oncology", "patient", "patients", "clinician", "clinicians",
)
DEPLOYMENT_TERMS = (
    "deployment", "deploy", "deployed", "operational readiness",
    "operational deployment", "safety-critical",
)
METRIC_PATTERN = re.compile(
    r"(?<!\w)(?:macro[ _-]?f1|micro[ _-]?f1|f1|precision|recall|accuracy|"
    r"dice|iou|auc|auroc|score|latency|runtime|mae|rmse|mse|error[ _-]?rate)(?!\w)",
    re.IGNORECASE,
)


def contains_term(text: str, term: str) -> bool:
    return bool(re.search(rf"(?<!\w){re.escape(term)}(?!\w)", text, re.IGNORECASE))


def high_risk_claim_type(text: str) -> str | None:
    if any(contains_term(text, term) for term in CLINICAL_TERMS):
        return "clinical_claim"
    if any(contains_term(text, term) for term in DEPLOYMENT_TERMS):
        return "deployment_claim"
    return None


def has_risk_assertion(text: str) -> bool:
    if high_risk_claim_type(text) is None:
        return False
    return bool(
        re.search(r"\b(?:is|are|was|were|can|cannot|could|will|may|must|supports?)\b", text, re.I)
        and re.search(r"\b(?:safe|safely|unsafe|suitable|effective|replace|ready|deployed|support|supports)\b", text, re.I)
    )


def has_quantitative_assertion(text: str) -> bool:
    return bool(
        METRIC_PATTERN.search(text)
        and re.search(r"(?<![\w.])(?:\d+(?:\.\d+)?|\.\d+)(?:\s*%)?", text)
        and re.search(r"\b(?:is|are|was|were|achieve[ds]?|recorde?d|reached|yielded|attained|obtained)\b", text, re.I)
    )


def is_nonassertive(text: str) -> bool:
    stripped = text.strip()
    if stripped.endswith("?"):
        return True
    if len(stripped) > 1 and stripped[0] in {'"', '\u201c'} and stripped.rstrip('.').endswith(('"', '\u201d')):
        return True
    return bool(re.search(
        r"\b(?:aim|aims|aimed|plan|plans|planned|intend|intends)\s+to\b|"
        r"\b(?:our|the|a)\s+(?:target|goal|objective|hypothesis)\b|"
        r"\b(?:test|investigate|evaluate|determine|ask|asked)\s+(?:whether|if)\b|"
        r"\b(?:reviewer|draft|manuscript|example|sentence)\s+(?:wrote|states|says|quotes)\b",
        text, re.I,
    ))
