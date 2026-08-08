import re
from numbers import Real

import pandas as pd

from .claim_extractor import sentences_with_lines, statement_polarity
from .schemas import Claim, EvidenceCell, EvidenceItem, EvidenceLocator, ManuscriptSection


STOPWORDS = {
    "about",
    "after",
    "also",
    "and",
    "available",
    "because",
    "before",
    "being",
    "benchmark",
    "claim",
    "claims",
    "could",
    "each",
    "evidence",
    "from",
    "human",
    "into",
    "method",
    "model",
    "more",
    "note",
    "notes",
    "only",
    "report",
    "reports",
    "result",
    "results",
    "review",
    "reviewer",
    "synthetic",
    "system",
    "table",
    "than",
    "that",
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
    *,
    references_file: str | None = None,
) -> list[EvidenceItem]:
    evidence: list[EvidenceItem] = []
    evidence.extend(_table_evidence(tables))
    evidence.extend(_section_evidence(sections))
    evidence.extend(_reference_evidence(references, references_file))

    for item in evidence:
        for claim in claims:
            match = _match_evidence(claim, item)
            if match is None:
                continue
            reason, relation, locator = match
            item.linked_claim_ids.append(claim.claim_id)
            item.claim_link_reasons[claim.claim_id] = reason
            item.claim_link_relations[claim.claim_id] = relation
            item.claim_link_locators[claim.claim_id] = locator

    return evidence


def _table_evidence(tables: dict[str, pd.DataFrame]) -> list[EvidenceItem]:
    items: list[EvidenceItem] = []
    for table_name, frame in sorted(tables.items()):
        evidence_type = (
            "ablation_result" if "ablation" in table_name.lower() else "quantitative_result"
        )
        for row_number, (_, row) in enumerate(frame.iterrows(), start=1):
            row_text = "; ".join(f"{column}={row[column]}" for column in frame.columns)
            numeric_values: dict[str, float] = {}
            categorical_values: list[str] = []
            cells: list[EvidenceCell] = []
            for column_index, column in enumerate(frame.columns, start=1):
                value = row[column]
                if not pd.isna(value):
                    cells.append(
                        EvidenceCell(
                            column=str(column),
                            value=str(value),
                            cell=_cell_reference(column_index, row_number + 1),
                        )
                    )
                numeric_value = _coerce_number(value)
                if numeric_value is None:
                    if not pd.isna(value):
                        categorical_values.append(str(value))
                else:
                    numeric_values[str(column)] = numeric_value

            items.append(
                EvidenceItem(
                    evidence_id=f"E{len(items) + 1:03d}",
                    source=table_name,
                    locator=EvidenceLocator(
                        source_kind="table",
                        source_name=table_name,
                        source_file=_safe_source_file(frame.attrs.get("source_file")),
                        row=row_number,
                        cells=cells,
                    ),
                    evidence_type=evidence_type,
                    text=row_text,
                    polarity="neutral",
                    numeric_values=numeric_values,
                    table_columns=[str(column) for column in frame.columns],
                    categorical_values=categorical_values,
                )
            )
    return items


def _section_evidence(sections: list[ManuscriptSection]) -> list[EvidenceItem]:
    items: list[EvidenceItem] = []
    for section in sections:
        section_role = _section_role(section.name)
        if section_role is None:
            continue
        for sentence, source_line in sentences_with_lines(section):
            lowered = sentence.lower()
            if section_role == "results":
                evidence_type = "result_text"
            elif any(
                phrase in lowered
                for phrase in ("limitation", "not ", "no external", "should not", "cannot")
            ):
                evidence_type = "limitation_statement"
            elif section_role == "discussion":
                evidence_type = "narrative_assertion"
            else:
                evidence_type = "workflow_trace"

            if source_line is None:
                continue
            items.append(
                EvidenceItem(
                    evidence_id=f"S{len(items) + 1:03d}",
                    source=section.name,
                    locator=EvidenceLocator(
                        source_kind=section.source_kind,
                        source_name=section.name,
                        source_file=_safe_source_file(section.source_file),
                        line=source_line,
                    ),
                    evidence_type=evidence_type,
                    text=sentence,
                    polarity=statement_polarity(sentence),
                )
            )
    return items


def _reference_evidence(
    references: str,
    references_file: str | None = None,
) -> list[EvidenceItem]:
    items: list[EvidenceItem] = []
    for line_number, line in enumerate(references.splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        items.append(
            EvidenceItem(
                evidence_id=f"R{len(items) + 1:03d}",
                source="references",
                locator=EvidenceLocator(
                    source_kind="references",
                    source_name="references",
                    source_file=_safe_source_file(references_file),
                    line=line_number,
                ),
                evidence_type="citation",
                text=stripped,
                polarity="neutral",
            )
        )
    return items


def _section_role(name: str) -> str | None:
    lowered = name.lower()
    if re.search(r"(?<!\w)results?(?!\w)", lowered):
        return "results"
    if re.search(r"(?<!\w)discussion(?!\w)", lowered):
        return "discussion"
    if re.search(r"(?<!\w)methods?(?!\w)", lowered):
        return "methods"
    return None


def _coerce_number(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, Real):
        if pd.isna(value):
            return None
        return float(value)
    if isinstance(value, str) and re.fullmatch(r"[-+]?\d+(?:\.\d+)?", value.strip()):
        return float(value)
    return None


def _cell_reference(column_number: int, row_number: int) -> str:
    """Return an A1-style coordinate for a one-based column and file row."""

    label = ""
    remaining = column_number
    while remaining:
        remaining, remainder = divmod(remaining - 1, 26)
        label = chr(ord("A") + remainder) + label
    return f"{label}{row_number}"


def _safe_source_file(value: object) -> str | None:
    """Reduce a provenance filename to a share-safe basename."""

    if value is None:
        return None
    normalized = str(value).replace("\\", "/")
    basename = normalized.rsplit("/", 1)[-1].strip()
    return basename or None


def _tokens(text: str) -> set[str]:
    tokens: set[str] = set()
    for token in re.findall(r"[a-zA-Z0-9]+", text.lower()):
        if token.isdigit() or token in STOPWORDS:
            continue
        if len(token) > 2 or (any(char.isalpha() for char in token) and any(char.isdigit() for char in token)):
            tokens.add(token)
    return tokens


def _numbers(text: str) -> set[float]:
    numbers: set[float] = set()
    for match in re.finditer(r"(?<![\w.])[-+]?\d+(?:\.\d+)?\s*%?", text):
        raw = match.group(0).strip()
        is_percent = raw.endswith("%")
        value = float(raw.rstrip("%").strip())
        numbers.add(value / 100 if is_percent else value)
        if is_percent:
            # Tables commonly encode percentages either as 0.90 or 90. Keep
            # both representations available for candidate-row retrieval; the
            # verifier performs the stricter value binding later.
            numbers.add(value)
    return numbers


def _numeric_equal(left: float, right: float) -> bool:
    return abs(left - right) <= 1e-9 * max(1.0, abs(left), abs(right))


def is_claim_self_evidence(claim: Claim, item: EvidenceItem) -> bool:
    """Identify the claim's own source span without discarding distinct same-line text."""

    if item.locator.source_kind not in {"manuscript", "ocr", "derived_text"}:
        return False
    claim_text = " ".join(claim.text.split()).casefold()
    evidence_text = " ".join(item.text.split()).casefold()
    if evidence_text == claim_text:
        return True
    same_location = (
        item.locator.source_kind == claim.source_kind
        and item.locator.source_name == claim.source_section
        and claim.source_line is not None
        and item.locator.line == claim.source_line
    )
    if not same_location:
        return False
    if claim_text in evidence_text or evidence_text in claim_text:
        return True
    claim_tokens = _tokens(claim.text)
    evidence_tokens = _tokens(item.text)
    union = claim_tokens | evidence_tokens
    similarity = len(claim_tokens & evidence_tokens) / len(union) if union else 0.0
    return similarity >= 0.8


def _match_evidence(
    claim: Claim,
    item: EvidenceItem,
) -> tuple[str, str, EvidenceLocator] | None:
    if is_claim_self_evidence(claim, item):
        return None
    if item.locator.source_kind == "table":
        return _match_table_evidence(claim, item)

    overlap = sorted(_tokens(claim.text) & _tokens(item.text))
    if len(overlap) < 2:
        return None
    shown = ", ".join(overlap[:5])
    reason = f"distinctive lexical overlap with claim tokens: {shown}"

    if item.evidence_type == "citation":
        return reason, "related", item.locator.model_copy(deep=True)
    if item.polarity != "neutral" and item.polarity != claim.polarity:
        return (
            f"potential contradiction; {reason}",
            "contradicts",
            item.locator.model_copy(deep=True),
        )
    return reason, "supports", item.locator.model_copy(deep=True)


def _match_table_evidence(
    claim: Claim,
    item: EvidenceItem,
) -> tuple[str, str, EvidenceLocator] | None:
    claim_tokens = _tokens(claim.text)
    row_tokens = _tokens(" ".join(item.categorical_values))
    metric_tokens = _tokens(" ".join(item.numeric_values))
    entity_overlap = sorted(claim_tokens & row_tokens)
    metric_overlap = sorted(claim_tokens & metric_tokens)

    claim_numbers = _numbers(claim.text)
    matched_numbers = sorted(
        claim_number
        for claim_number in claim_numbers
        if any(_numeric_equal(claim_number, value) for value in item.numeric_values.values())
    )

    if metric_overlap and (entity_overlap or matched_numbers):
        details = []
        if metric_overlap:
            details.append(f"metric(s): {', '.join(metric_overlap[:4])}")
        if entity_overlap:
            details.append(f"row entity token(s): {', '.join(entity_overlap[:4])}")
        if matched_numbers:
            details.append(f"matching value(s): {', '.join(str(value) for value in matched_numbers[:4])}")
        return (
            "verifiable table-row relation; " + "; ".join(details),
            "supports",
            _claim_specific_table_locator(claim, item),
        )

    overlap = sorted(claim_tokens & _tokens(item.text))
    if len(overlap) >= 2:
        return (
            f"table row is topically related but lacks a verifiable metric/value relation: {', '.join(overlap[:5])}",
            "related",
            _claim_specific_table_locator(claim, item),
        )
    return None


def _claim_specific_table_locator(claim: Claim, item: EvidenceItem) -> EvidenceLocator:
    """Narrow a row locator to cells actually matched for one claim.

    The base evidence item remains the complete row. This claim-specific copy
    avoids implying that unrelated cells in that row support every linked claim.
    """

    claim_tokens = _tokens(claim.text)
    claim_numbers = _numbers(claim.text)
    matched_cells: list[EvidenceCell] = []
    for cell in item.locator.cells:
        column_tokens = _tokens(cell.column)
        value_tokens = _tokens(cell.value)
        numeric_value = item.numeric_values.get(cell.column)
        numeric_match = (
            numeric_value is not None
            and any(_numeric_equal(number, numeric_value) for number in claim_numbers)
        )
        if claim_tokens & column_tokens or claim_tokens & value_tokens or numeric_match:
            matched_cells.append(cell.model_copy())

    return item.locator.model_copy(update={"cells": matched_cells}, deep=True)
