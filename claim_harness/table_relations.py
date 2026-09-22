"""Shared deterministic numeric relations for retrieval and verification."""
import re
from collections import defaultdict
from dataclasses import dataclass, field
from .claim_language import contains_term
from .schemas import Claim, EvidenceItem

COMPARISON_TERMS = ("outperforms", "improves", "increases", "reduces", "higher", "lower")
LOWER_IS_BETTER_METRIC_TOKENS = {
    "cer",
    "cost",
    "duration",
    "error",
    "errors",
    "latency",
    "loss",
    "mae",
    "mse",
    "perplexity",
    "rmse",
    "runtime",
    "time",
    "wer",
}
NUMBER_FRAGMENT = r"([-+]?(?:\d+(?:\.\d+)?|\.\d+))(?:\s*(%|percent\b|per\s+cent\b))?"


@dataclass
class TableAssessment:
    supported: bool = False
    support_ids: set[str] = field(default_factory=set)
    contradictions: dict[str, str] = field(default_factory=dict)
    review_reason: str | None = None


def has_verifiable_table_relation(claim: Claim, items: list[EvidenceItem]) -> bool:
    return assess_table_relation(claim, items).supported


def assess_table_relation(claim: Claim, items: list[EvidenceItem]) -> TableAssessment:
    """Bind context before comparing. Unresolved bindings are never contradictions."""
    groups: dict[str, list[EvidenceItem]] = defaultdict(list)
    for item in items:
        if item.locator.source_kind == 'table' and item.numeric_values:
            groups[item.locator.source_name].append(item)
    if groups and claim.claim_type != 'performance_claim' and not _number_mentions(claim.text) and not any(contains_term(claim.text, term) for term in COMPARISON_TERMS):
        # A contract may ask for the presence of an ablation artifact for a
        # non-quantitative workflow claim. This is not a numerical assertion.
        return TableAssessment(supported=True)
    groups = {name: rows for name, rows in groups.items() if _explicit_metrics(claim, rows)}
    if not groups:
        return TableAssessment()
    named_sources = [name for name in groups if _phrase_present(_normalized_phrase(claim.text), _normalized_phrase(name))]
    if len(named_sources) == 1:
        groups = {named_sources[0]: groups[named_sources[0]]}
    if len(groups) != 1:
        return TableAssessment(review_reason='More than one table supplies the named metric; identify the intended table and experiment.')
    rows, problem = _scope_context(claim.text, next(iter(groups.values())))
    if problem:
        return TableAssessment(review_reason=problem)
    if claim.polarity == 'negative':
        return TableAssessment(review_reason='A negated numerical or comparison statement requires human interpretation; matching a value does not support its negation.')
    # Bound support is intentionally limited to affirmative measurements and
    # comparisons, not inequalities, uncertainty ranges, or unparsed qualifiers.
    if re.search(r'\b(?:at least|at most|less than|more than|no less|no more|approximately|about|between)\b|[<>±]', claim.text, re.I):
        return TableAssessment(review_reason='The numerical qualifier or range is outside the supported exact-comparison grammar.')
    metrics = _explicit_metrics(claim, rows)
    is_comparison = any(contains_term(claim.text, term) for term in COMPARISON_TERMS)
    targets = _target_items(claim, rows) if is_comparison else _measurement_targets(claim, rows)
    if len(targets) != 1:
        return TableAssessment(review_reason='The model or measurement row is missing or ambiguous; identify the model and experiment before comparison.')
    target = targets[0]
    if any(metric not in target.numeric_values for metric in metrics):
        return TableAssessment(review_reason='The selected model row does not contain every named metric.')
    if not is_comparison:
        numbers = _number_mentions(claim.text)
        if len(metrics) != len(numbers):
            return TableAssessment(review_reason='Each stated number must bind to one named metric; this statement cannot be fully matched.')
        differences = []
        for metric, number in zip(metrics, numbers):
            if not _numeric_matches(target.numeric_values[metric], number):
                differences.append(_value_difference(metric, number, target))
        if differences:
            return TableAssessment(contradictions={target.evidence_id: '; '.join(differences)})
        return TableAssessment(supported=True, support_ids={target.evidence_id})

    non_targets = [row for row in rows if row.evidence_id != target.evidence_id]
    pairs = _from_to_pairs(claim.text) or _versus_pairs(claim.text)
    from_to = bool(_from_to_pairs(claim.text))
    if _from_to_pairs(claim.text) and _versus_pairs(claim.text):
        return TableAssessment(review_reason='Mixed from/to and versus clauses need separate claim statements.')
    deltas = _delta_values(claim.text)
    if (pairs and len(pairs) != len(metrics)) or (deltas and len(deltas) != len(metrics)):
        return TableAssessment(review_reason='The number of comparison constraints does not match the named metrics.')
    baselines = _explicit_baseline_items(claim, non_targets)
    if not baselines and pairs:
        baselines = [row for row in non_targets if all(
            metric in row.numeric_values and _numeric_matches(row.numeric_values[metric], pair[0 if from_to else 1])
            for metric, pair in zip(metrics, pairs)
        )]
        if len(baselines) != 1:
            return TableAssessment(review_reason='The starting value does not identify one baseline row; provide the comparator and experiment.')
    elif not baselines and deltas and len(non_targets) == 1:
        baselines = non_targets
    if not baselines:
        return TableAssessment(review_reason='The comparator is not identified by the provided statement and table.')
    if _has_duplicate_identity(baselines):
        return TableAssessment(review_reason='The comparator has multiple measurement rows; identify the experiment or split.')
    if any(metric not in row.numeric_values for row in baselines for metric in metrics):
        return TableAssessment(review_reason='The comparator rows do not contain every named metric.')

    differences: dict[str, list[str]] = defaultdict(list)
    if pairs:
        for metric, pair in zip(metrics, pairs):
            expected_target = pair[1 if from_to else 0]
            expected_baseline = pair[0 if from_to else 1]
            if not _numeric_matches(target.numeric_values[metric], expected_target):
                differences[target.evidence_id].append(_value_difference(metric, expected_target, target))
            for row in baselines:
                if not _numeric_matches(row.numeric_values[metric], expected_baseline):
                    differences[row.evidence_id].append(_value_difference(metric, expected_baseline, row))
    for row in baselines:
        for metric in metrics:
            direction = _expected_direction(claim, metric)
            actual, baseline = target.numeric_values[metric], row.numeric_values[metric]
            if not _direction_holds(actual, baseline, direction):
                message = f'{metric}: claimed target {"higher" if direction > 0 else "lower"} than comparator; observed target {actual:g}, comparator {baseline:g}'
                differences[target.evidence_id].append(message)
                differences[row.evidence_id].append(message)
        for metric, delta in zip(metrics, deltas):
            actual, baseline = target.numeric_values[metric], row.numeric_values[metric]
            if not _delta_matches(actual, baseline, delta):
                number, points = delta
                observed = abs(actual - baseline)
                label = 'percentage points' if points else ('relative change' if number[1] else 'absolute change')
                if number[1] and not points:
                    if baseline == 0:
                        return TableAssessment(review_reason='Relative percentage change from a zero baseline is undefined.')
                    observed /= abs(baseline)
                message = f'{metric}: claimed {label} {_format_number(number)}, observed change {observed:g} (target {actual:g}, comparator {baseline:g})'
                differences[target.evidence_id].append(message)
                differences[row.evidence_id].append(message)
    if differences:
        return TableAssessment(contradictions={key: '; '.join(values) for key, values in differences.items()})
    if not _all_numbers_accounted_for(claim.text, target, baselines, metrics, deltas):
        return TableAssessment(review_reason='Some numerical constraints were not bound; split the statement or clarify its context.')
    return TableAssessment(supported=True, support_ids={target.evidence_id, *(row.evidence_id for row in baselines)})


def _cell_value(row: EvidenceItem, column: str) -> str | None:
    for cell in row.locator.cells:
        if cell.column.casefold() == column:
            return cell.value.casefold().strip()
    return None


def _scope_context(text: str, rows: list[EvidenceItem]) -> tuple[list[EvidenceItem], str | None]:
    normalized = _normalized_phrase(text)
    scoped = rows
    for column in ('dataset', 'split', 'cohort', 'condition', 'experiment'):
        values = {_cell_value(row, column) for row in scoped} - {None}
        if not values:
            continue
        selected = {value for value in values if _phrase_present(normalized, _normalized_phrase(value))}
        if len(selected) > 1 or (not selected and len(values) > 1):
            return [], f'Table {column} is ambiguous; name one experiment context.'
        if selected:
            scoped = [row for row in scoped if _cell_value(row, column) in selected]
        elif column == 'split':
            requested = set(re.findall(r'\b(?:train|training|test|testing|validation)\b', text, re.I))
            if requested:
                return [], 'The requested split is not present in this table; values from another split are not contradictory evidence.'
    unit_values = {_cell_value(row, 'unit') or _cell_value(row, 'units') for row in scoped} - {None}
    units = {_canonical_unit(value) for value in unit_values}
    requested_units = {_canonical_unit(value) for value in re.findall(r'\d\s*(milliseconds?|ms|seconds?|s|minutes?|min)\b', text, re.I)}
    if units and (len(units) != 1 or requested_units != units):
        return [], 'Measurement units are missing, mixed, or different; confirm units before comparing values. Automatic unit conversion is not performed.'
    if requested_units and not units:
        headers = {column.lower() for row in scoped for column in row.numeric_values}
        header_units = {_canonical_unit(column.rsplit('_', 1)[-1]) for column in headers if column.endswith(('_ms', '_s', '_min'))}
        if header_units != requested_units:
            return [], 'The table does not specify the measurement unit requested by the claim.'
    return scoped, None


def _canonical_unit(value: str) -> str:
    lowered = value.casefold()
    return {'milliseconds':'ms','millisecond':'ms','seconds':'s','second':'s','minutes':'min','minute':'min'}.get(lowered, lowered)


def _measurement_targets(claim: Claim, rows: list[EvidenceItem]) -> list[EvidenceItem]:
    named = _maximally_mentioned_items(claim.text, rows)
    if named:
        return named
    # An implicit metric statement can refer to the sole measurement row, but
    # never choose a row merely because its value happens to match.
    metrics = _explicit_metrics(claim, rows)
    if len(rows) == 1 and metrics:
        normalized = _normalized_phrase(claim.text)
        starts_with_metric = any(normalized.startswith(prefix + _normalized_phrase(metric)) for metric in metrics for prefix in ('', 'the '))
        if starts_with_metric and not re.search(r'\bof\s+[A-Za-z]', claim.text, re.I):
            return rows
    return []


def _has_duplicate_identity(rows: list[EvidenceItem]) -> bool:
    identities = [tuple(_row_phrases(row)) for row in rows]
    return len(identities) != len(set(identities))


def _format_number(number: 'NumberSpec') -> str:
    return f'{number[0] * 100:g}%' if number[1] else f'{number[0]:g}'


def _value_difference(metric: str, expected: 'NumberSpec', row: EvidenceItem) -> str:
    return f'{metric}: claimed {_format_number(expected)}, observed {row.numeric_values[metric]:g} in data row {row.locator.row or "unknown"}'






def _target_items(claim: Claim, items: list[EvidenceItem]) -> list[EvidenceItem]:
    match = re.search(
        r"(?<!\w)(?:outperforms|improves|increases|reduces|higher|lower)(?!\w)",
        claim.text,
        flags=re.IGNORECASE,
    )
    if match is None:
        return []
    subject = claim.text[: match.start()]
    normalized_subject = _normalized_phrase(subject)

    exact_scores: dict[str, int] = {}
    for item in items:
        lengths = [
            len(phrase.split())
            for phrase in _row_phrases(item)
            if _phrase_present(normalized_subject, phrase)
        ]
        if lengths:
            exact_scores[item.evidence_id] = max(lengths)
    if exact_scores:
        best = max(exact_scores.values())
        return [item for item in items if exact_scores.get(item.evidence_id) == best]

    subject_tokens = _entity_tokens(subject)
    if len(subject_tokens) < 2:
        return []
    fallback_scores: dict[str, int] = {}
    for item in items:
        for value in item.categorical_values:
            value_tokens = _entity_tokens(value)
            if len(value_tokens) < 2:
                continue
            if subject_tokens <= value_tokens or value_tokens <= subject_tokens:
                fallback_scores[item.evidence_id] = max(
                    fallback_scores.get(item.evidence_id, 0),
                    len(subject_tokens & value_tokens),
                )
    if not fallback_scores:
        return []
    best = max(fallback_scores.values())
    return [item for item in items if fallback_scores.get(item.evidence_id) == best]


NumberSpec = tuple[float, bool]
NumberPair = tuple[NumberSpec, NumberSpec]
DeltaSpec = tuple[NumberSpec, bool]


def _from_to_pairs(text: str) -> list[NumberPair]:
    pattern = rf"(?<!\w)from\s+{NUMBER_FRAGMENT}\s+to\s+{NUMBER_FRAGMENT}"
    return [
        (_number_spec(match.group(1), match.group(2)), _number_spec(match.group(3), match.group(4)))
        for match in re.finditer(pattern, text, flags=re.IGNORECASE)
    ]


def _versus_pairs(text: str) -> list[NumberPair]:
    pattern = rf"{NUMBER_FRAGMENT}\s+(?:versus|vs\.?)\s+{NUMBER_FRAGMENT}"
    return [
        (_number_spec(match.group(1), match.group(2)), _number_spec(match.group(3), match.group(4)))
        for match in re.finditer(pattern, text, flags=re.IGNORECASE)
    ]


def _delta_values(text: str) -> list[DeltaSpec]:
    pattern = rf"(?<!\w)by\s+{NUMBER_FRAGMENT}(?:\s+(percentage\s+points?|points?))?"
    return [
        (_number_spec(match.group(1), match.group(2)), bool(match.group(3)))
        for match in re.finditer(pattern, text, flags=re.IGNORECASE)
    ]


def _number_mentions(text: str) -> list[NumberSpec]:
    pattern = rf"(?<![\w.]){NUMBER_FRAGMENT}"
    return [
        _number_spec(match.group(1), match.group(2))
        for match in re.finditer(pattern, text, flags=re.IGNORECASE)
    ]


def _number_spec(raw: str, percent: str | None) -> NumberSpec:
    value = float(raw)
    return (value / 100 if percent else value, bool(percent))


def _expected_direction(claim: Claim, metric: str) -> int:
    normalized_claim = _normalized_phrase(claim.text)
    metric_phrase = _normalized_phrase(metric)
    metric_position = normalized_claim.find(metric_phrase)
    direction = None
    if metric_position >= 0:
        prefix_tokens = normalized_claim[:metric_position].split()
        for token in reversed(prefix_tokens):
            if token in {"reduces", "lower"}:
                direction = -1
                break
            if token in {"increases", "higher"}:
                direction = 1
                break
    if direction is None:
        direction = -1 if _entity_tokens(metric) & LOWER_IS_BETTER_METRIC_TOKENS else 1
    return -direction if claim.polarity == "negative" else direction


def _direction_holds(target: float, baseline: float, direction: int) -> bool:
    if direction > 0:
        return target > baseline
    return target < baseline


def _numeric_equal(left: float, right: float) -> bool:
    return abs(left - right) <= 1e-9 * max(1.0, abs(left), abs(right))


def _numeric_matches(value: float, spec: NumberSpec) -> bool:
    expected, is_percent = spec
    candidates = [expected]
    if is_percent:
        candidates.append(expected * 100)
    return any(_numeric_equal(value, candidate) for candidate in candidates)


def _explicit_metrics(claim: Claim, items: list[EvidenceItem]) -> list[str]:
    normalized_claim = _normalized_phrase(claim.text)
    columns = {
        column
        for item in items
        for column in item.numeric_values
    }
    located = []
    for column in columns:
        metric_name = re.sub(r'_(?:ms|s|min)$', '', column, flags=re.I)
        phrase = _normalized_phrase(metric_name)
        if not phrase or not _phrase_present(normalized_claim, phrase):
            continue
        located.append((normalized_claim.find(phrase), -len(phrase.split()), column))
    return [column for _, _, column in sorted(located)]


def _explicit_baseline_items(
    claim: Claim,
    items: list[EvidenceItem],
) -> list[EvidenceItem]:
    match = re.search(
        r"(?<!\w)(?:outperforms|improves|increases|reduces|higher|lower)(?!\w)",
        claim.text,
        flags=re.IGNORECASE,
    )
    if match is None:
        return []
    return _maximally_mentioned_items(claim.text[match.end() :], items)


def _maximally_mentioned_items(
    text: str,
    items: list[EvidenceItem],
) -> list[EvidenceItem]:
    normalized_text = _normalized_phrase(text)
    present: list[tuple[EvidenceItem, str]] = []
    for item in items:
        for phrase in _row_phrases(item):
            if _phrase_present(normalized_text, phrase):
                present.append((item, phrase))

    maximal = [
        (item, phrase)
        for item, phrase in present
        if not any(
            other_phrase != phrase and _phrase_present(other_phrase, phrase)
            for _, other_phrase in present
        )
    ]
    ids = {item.evidence_id for item, _ in maximal}
    return [item for item in items if item.evidence_id in ids]








def _delta_matches(target: float, baseline: float, delta: DeltaSpec) -> bool:
    spec, percentage_points = delta
    difference = abs(target - baseline)
    expected, is_percent = spec
    if percentage_points:
        candidates = [expected, expected * 100] if is_percent else [expected, expected / 100]
        return any(_numeric_equal(difference, candidate) for candidate in candidates)
    if is_percent:
        if _numeric_equal(baseline, 0.0):
            return False
        return _numeric_equal(difference / abs(baseline), expected)
    return _numeric_matches(difference, spec)


def _all_numbers_accounted_for(
    text: str,
    target: EvidenceItem,
    baselines: list[EvidenceItem],
    metrics: list[str],
    deltas: list[DeltaSpec],
) -> bool:
    mentions = _number_mentions(text)
    if not mentions:
        return True
    row_values = [target.numeric_values[metric] for metric in metrics]
    row_values.extend(
        baseline.numeric_values[metric]
        for baseline in baselines
        for metric in metrics
        if metric in baseline.numeric_values
    )
    differences = [
        abs(target.numeric_values[metric] - baseline.numeric_values[metric])
        for baseline in baselines
        for metric in metrics
        if metric in baseline.numeric_values
    ]
    delta_numbers = {spec for spec, _ in deltas}
    return all(
        mention in delta_numbers
        or any(_numeric_matches(value, mention) for value in [*row_values, *differences])
        for mention in mentions
    )


def _row_phrases(item: EvidenceItem) -> list[str]:
    noise = {"disabled", "enabled", "false", "n", "a", "na", "no", "none", "true", "yes"}
    phrases = []
    identity_values = [cell.value for cell in item.locator.cells if cell.column.lower() in {'model', 'method', 'system', 'algorithm', 'setting', 'name'}]
    for value in identity_values or item.categorical_values:
        phrase = _normalized_phrase(value)
        tokens = set(phrase.split())
        if phrase and not tokens <= noise:
            phrases.append(phrase)
    return phrases


def _normalized_phrase(text: str) -> str:
    return " ".join(re.findall(r"[a-zA-Z0-9]+", text.lower()))


def _phrase_present(text: str, phrase: str) -> bool:
    return f" {phrase} " in f" {text} "


def _entity_tokens(text: str) -> set[str]:
    ignored = {
        "a",
        "an",
        "and",
        "adding",
        "adds",
        "at",
        "by",
        "claim",
        "evidence",
        "for",
        "from",
        "in",
        "method",
        "model",
        "of",
        "on",
        "over",
        "proposed",
        "result",
        "results",
        "setting",
        "system",
        "table",
        "the",
        "to",
        "with",
    }
    return {
        token
        for token in re.findall(r"[a-zA-Z0-9]+", text.lower())
        if token not in ignored and not token.isdigit() and len(token) > 1
    }
