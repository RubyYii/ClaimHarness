import re
from collections import defaultdict

from .claim_extractor import contains_term, term_is_negated
from .evidence_contract import DERIVED_SOURCE_KINDS, EvidenceContract
from .evidence_retriever import is_claim_self_evidence
from .schemas import Claim, EvidenceItem, VerificationResult


STRONG_EVIDENCE_TYPES = {
    "quantitative_result",
    "ablation_result",
    "external_validation",
    "robustness_test",
}
HIGH_RISK_TERMS = {
    "clinical",
    "clinically",
    "deployment",
    "diagnosis",
    "biomedical",
    "operational readiness",
    "operational deployment",
    "safety-critical",
}
OVERCLAIM_TERMS = {
    "clinically ready",
    "clinical deployment",
    "diagnosis",
    "real-world clinical deployment",
    "ready for real-world deployment",
    "ready for real-world operational deployment",
    "real-world operational deployment",
    "deployment-ready",
    "operationally ready",
}
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
NUMBER_FRAGMENT = r"([-+]?(?:\d+(?:\.\d+)?|\.\d+))(?:\s*(%))?"


def verify_claims(
    claims: list[Claim],
    evidence: list[EvidenceItem],
    evidence_contract: EvidenceContract | None = None,
) -> list[VerificationResult]:
    evidence_by_claim: dict[str, list[EvidenceItem]] = defaultdict(list)
    for item in evidence:
        for claim_id in item.linked_claim_ids:
            evidence_by_claim[claim_id].append(item)

    results: list[VerificationResult] = []
    for claim in claims:
        result = _verify_claim(
            claim,
            evidence_by_claim.get(claim.claim_id, []),
            evidence_contract,
        )
        human_review_required = result.human_review_required
        release_allowed = (
            result.risk_level == "low"
            and result.status == "supported"
            and not human_review_required
        )
        results.append(
            result.model_copy(
                update={
                    "human_review_required": human_review_required,
                    "release_allowed": release_allowed,
                }
            )
        )
    return results


def _verify_claim(
    claim: Claim,
    evidence_items: list[EvidenceItem],
    evidence_contract: EvidenceContract | None = None,
) -> VerificationResult:
    allowed_source_kinds = (
        set(evidence_contract.source_kinds) if evidence_contract is not None else None
    )
    evidence_items = [
        item for item in evidence_items if not is_claim_self_evidence(claim, item)
    ]
    supporting = [
        item
        for item in evidence_items
        if item.claim_link_relations.get(claim.claim_id, "supports") == "supports"
        and (
            allowed_source_kinds is None
            or item.locator.source_kind in allowed_source_kinds
        )
    ]
    contradicting = [
        item
        for item in evidence_items
        if item.claim_link_relations.get(claim.claim_id) == "contradicts"
    ]
    related = [
        item
        for item in evidence_items
        if item.claim_link_relations.get(claim.claim_id) == "related"
        and (
            allowed_source_kinds is None
            or item.locator.source_kind in allowed_source_kinds
        )
    ]

    table_support = [item for item in supporting if item.locator.source_kind == "table"]
    valid_table_relation = _has_verifiable_table_relation(claim, table_support)
    strong_evidence_types = (
        set(evidence_contract.strong_evidence_types)
        if evidence_contract is not None
        else STRONG_EVIDENCE_TYPES
    )
    strong = [
        item
        for item in supporting
        if item.evidence_type in strong_evidence_types
        and item.locator.source_kind not in DERIVED_SOURCE_KINDS
        and (item.locator.source_kind != "table" or valid_table_relation)
    ]
    rule = evidence_contract.claim_rules[claim.claim_type] if evidence_contract is not None else None
    requirements = list(rule.required_evidence) if rule is not None else claim.requires_evidence
    missing = _missing_requirements(
        claim,
        supporting,
        related,
        strong,
        requirements=requirements,
    )
    forbidden_missing: list[str] = []
    missing_review_roles: list[str] = []
    if rule is not None:
        supporting_count = len(
            {
                item.evidence_id
                for item in supporting
                if item.locator.source_kind not in DERIVED_SOURCE_KINDS
            }
        )
        if supporting_count < rule.minimum_evidence_count:
            missing.append(f"minimum_evidence_count={rule.minimum_evidence_count}")
        forbidden_missing = _missing_requirements(
            claim,
            supporting,
            related,
            strong,
            requirements=list(rule.forbidden_without),
        )
        completed_review_roles = {
            role_id
            for item in supporting
            if item.evidence_type == "human_review"
            and item.locator.source_kind not in DERIVED_SOURCE_KINDS
            for role_id in item.categorical_values
        }
        missing_review_roles = [
            role_id
            for role_id in rule.human_review_roles
            if role_id not in completed_review_roles
        ]
        missing.extend(
            requirement for requirement in forbidden_missing if requirement not in missing
        )
        missing.extend(
            f"human_review_role={role_id}"
            for role_id in missing_review_roles
            if f"human_review_role={role_id}" not in missing
        )
    risk_level = _risk_level(claim)
    support_ids = [item.evidence_id for item in supporting]
    contradiction_ids = [item.evidence_id for item in contradicting]

    if _has_positive_overclaim_language(claim) and missing:
        return VerificationResult(
            claim_id=claim.claim_id,
            status="overclaimed",
            reason=(
                "High-risk readiness or deployment language is missing required evidence: "
                + ", ".join(missing)
                + "."
            ),
            risk_level="high",
            suggested_revision=(
                "Remove readiness/deployment language or add independently reviewable external validation "
                "and a documented human-review decision."
            ),
            missing_evidence=missing,
            supporting_evidence_ids=support_ids,
            contradicting_evidence_ids=contradiction_ids,
        )

    if claim.source_kind in DERIVED_SOURCE_KINDS:
        derived_missing = [*missing]
        if "source_inspection" not in derived_missing:
            derived_missing.append("source_inspection")
        return VerificationResult(
            claim_id=claim.claim_id,
            status="needs_human_review",
            reason=(
                "The claim was extracted from OCR-derived text. A human must inspect the "
                "original source before this claim can be treated as supported."
            ),
            risk_level="high" if risk_level == "high" else "low",
            suggested_revision=(
                "Verify the transcription against the original page, then rerun the audit "
                "with direct source text or a documented human-review record."
            ),
            missing_evidence=derived_missing,
            supporting_evidence_ids=support_ids,
            contradicting_evidence_ids=contradiction_ids,
        )

    if forbidden_missing or missing_review_roles:
        details = []
        if forbidden_missing:
            details.append("forbidden-without conditions missing: " + ", ".join(forbidden_missing))
        if missing_review_roles:
            details.append("human review roles incomplete: " + ", ".join(missing_review_roles))
        return VerificationResult(
            claim_id=claim.claim_id,
            status="needs_human_review",
            reason="Evidence contract requires human review; " + "; ".join(details) + ".",
            risk_level="high" if risk_level == "high" else "low",
            suggested_revision=(
                "Do not present the claim as contract-compliant until the forbidden-without conditions "
                "and named human-review roles are satisfied."
            ),
            missing_evidence=missing,
            supporting_evidence_ids=support_ids,
            contradicting_evidence_ids=contradiction_ids,
        )

    if risk_level == "high" and (missing or not strong or contradicting):
        details = []
        if missing:
            details.append("missing required evidence: " + ", ".join(missing))
        if not strong:
            details.append("no independently verifiable strong evidence")
        if contradicting:
            details.append("contradictory evidence: " + ", ".join(contradiction_ids))
        return VerificationResult(
            claim_id=claim.claim_id,
            status="needs_human_review",
            reason="High-risk claim requires human review; " + "; ".join(details) + ".",
            risk_level="high",
            suggested_revision=(
                "Do not present this as validated until the missing evidence and contradiction checks are "
                "reviewed by a qualified human."
            ),
            missing_evidence=missing,
            supporting_evidence_ids=support_ids,
            contradicting_evidence_ids=contradiction_ids,
        )

    if contradicting:
        return VerificationResult(
            claim_id=claim.claim_id,
            status="needs_human_review",
            reason="Provided evidence conflicts with the claim: " + ", ".join(contradiction_ids) + ".",
            risk_level=risk_level,
            suggested_revision="Resolve the conflicting evidence or narrow the claim before publication.",
            missing_evidence=missing,
            supporting_evidence_ids=support_ids,
            contradicting_evidence_ids=contradiction_ids,
        )

    if missing:
        return VerificationResult(
            claim_id=claim.claim_id,
            status="weakly_supported" if supporting or related else "unsupported",
            reason="Required evidence is missing: " + ", ".join(missing) + ".",
            risk_level=risk_level,
            suggested_revision="Add the missing evidence or narrow the wording to the evidence available.",
            missing_evidence=missing,
            supporting_evidence_ids=support_ids,
            contradicting_evidence_ids=contradiction_ids,
        )

    if strong:
        return VerificationResult(
            claim_id=claim.claim_id,
            status="supported",
            reason=(
                f"All evidence requirements are met with {len(strong)} independently verifiable strong "
                "evidence item(s)."
            ),
            risk_level=risk_level,
            suggested_revision="No revision needed within the evidenced scope.",
            missing_evidence=[],
            supporting_evidence_ids=support_ids,
            contradicting_evidence_ids=[],
        )

    if supporting or related:
        return VerificationResult(
            claim_id=claim.claim_id,
            status="weakly_supported",
            reason="Only narrative or topically related evidence is available; no strong relation was verified.",
            risk_level=risk_level,
            suggested_revision="Add verifiable evidence or narrow the wording.",
            missing_evidence=[],
            supporting_evidence_ids=support_ids,
            contradicting_evidence_ids=[],
        )

    return VerificationResult(
        claim_id=claim.claim_id,
        status="unsupported",
        reason="No supporting evidence was found in the provided manuscript, tables, or references.",
        risk_level=risk_level,
        suggested_revision="Remove the claim or add explicit supporting evidence.",
        missing_evidence=[],
        supporting_evidence_ids=[],
        contradicting_evidence_ids=[],
    )


def _risk_level(claim: Claim) -> str:
    if claim.claim_type in {"clinical_claim", "deployment_claim"}:
        return "high"
    return "high" if any(contains_term(claim.text, term) for term in HIGH_RISK_TERMS) else "low"


def _has_positive_overclaim_language(claim: Claim) -> bool:
    if claim.polarity == "negative":
        return False
    return any(
        contains_term(claim.text, term) and not term_is_negated(claim.text, term)
        for term in OVERCLAIM_TERMS
    )


def _canonical_requirement(requirement: str) -> str:
    return re.sub(r"[\s-]+", "_", requirement.strip().lower())


def _missing_requirements(
    claim: Claim,
    supporting: list[EvidenceItem],
    related: list[EvidenceItem],
    strong: list[EvidenceItem],
    *,
    requirements: list[str] | None = None,
) -> list[str]:
    missing = []
    strong_ids = {item.evidence_id for item in strong}
    eligible_supporting = [
        item for item in supporting if item.locator.source_kind not in DERIVED_SOURCE_KINDS
    ]
    eligible_related = [
        item for item in related if item.locator.source_kind not in DERIVED_SOURCE_KINDS
    ]
    for raw_requirement in claim.requires_evidence if requirements is None else requirements:
        requirement = _canonical_requirement(raw_requirement)
        if requirement == "table":
            satisfied = any(
                item.locator.source_kind == "table" and item.evidence_id in strong_ids
                for item in supporting
            )
        elif requirement == "ablation":
            satisfied = any(
                item.evidence_type == "ablation_result" and item.evidence_id in strong_ids
                for item in supporting
            )
        elif requirement == "trace":
            satisfied = any(item.evidence_type == "workflow_trace" for item in eligible_supporting)
        elif requirement == "result_text":
            satisfied = any(item.evidence_type == "result_text" for item in eligible_supporting)
        elif requirement == "external_validation":
            satisfied = any(
                item.evidence_type == "external_validation" and item.evidence_id in strong_ids
                for item in eligible_supporting
            )
        elif requirement == "human_review":
            satisfied = any(item.evidence_type == "human_review" for item in eligible_supporting)
        elif requirement == "robustness_test":
            satisfied = any(
                item.evidence_type == "robustness_test" and item.evidence_id in strong_ids
                for item in eligible_supporting
            )
        elif requirement == "citation":
            satisfied = any(
                item.evidence_type == "citation"
                for item in [*eligible_supporting, *eligible_related]
            )
        elif requirement == "manuscript_context":
            satisfied = any(
                item.locator.source_kind == "manuscript" for item in eligible_supporting
            )
        elif requirement == "source_inspection":
            satisfied = any(
                item.evidence_type == "human_review"
                and item.locator.source_kind not in DERIVED_SOURCE_KINDS
                for item in eligible_supporting
            )
        else:
            satisfied = False
        if not satisfied:
            missing.append(requirement)
    return missing


def _has_verifiable_table_relation(claim: Claim, table_items: list[EvidenceItem]) -> bool:
    if not table_items:
        return False

    items_by_source: dict[str, list[EvidenceItem]] = defaultdict(list)
    for item in table_items:
        items_by_source[item.locator.source_name].append(item)

    is_comparison = any(contains_term(claim.text, term) for term in COMPARISON_TERMS)
    if not is_comparison:
        if claim.claim_type != "performance_claim" and not _number_mentions(claim.text):
            return True
        return any(
            _source_has_valid_measurement(claim, source_items)
            for source_items in items_by_source.values()
        )

    return any(
        _source_has_valid_comparison(claim, source_items)
        for source_items in items_by_source.values()
    )


def _source_has_valid_measurement(claim: Claim, items: list[EvidenceItem]) -> bool:
    metrics = _explicit_metrics(claim, items)
    numbers = _number_mentions(claim.text)
    if not metrics or len(metrics) != len(numbers):
        return False
    targets = _maximally_mentioned_items(claim.text, items)
    if len(targets) != 1:
        return False
    target = targets[0]
    return all(
        metric in target.numeric_values
        and _numeric_matches(target.numeric_values[metric], number)
        for metric, number in zip(metrics, numbers)
    )


def _source_has_valid_comparison(claim: Claim, items: list[EvidenceItem]) -> bool:
    if len(items) < 2:
        return False
    target_items = _target_items(claim, items)
    if len(target_items) != 1:
        return False
    target = target_items[0]

    metrics = _explicit_metrics(claim, items)
    if not metrics or any(metric not in target.numeric_values for metric in metrics):
        return False

    target_ids = {target.evidence_id}
    non_targets = [item for item in items if item.evidence_id not in target_ids]
    explicit_baselines = _explicit_baseline_items(claim, non_targets)

    from_to_pairs = _from_to_pairs(claim.text)
    versus_pairs = _versus_pairs(claim.text)
    deltas = _delta_values(claim.text)
    if from_to_pairs and versus_pairs:
        return False

    if from_to_pairs or versus_pairs:
        pairs = from_to_pairs or versus_pairs
        if len(pairs) != len(metrics):
            return False
        candidate_baselines = explicit_baselines or non_targets
        baselines = _baselines_matching_pairs(
            target,
            candidate_baselines,
            metrics,
            pairs,
            from_to=bool(from_to_pairs),
        )
        if explicit_baselines:
            if {item.evidence_id for item in baselines} != {
                item.evidence_id for item in explicit_baselines
            }:
                return False
        elif len(baselines) != 1:
            # Without an explicit name, a numeric pair must identify one
            # unambiguous baseline row.
            return False
    else:
        baselines = explicit_baselines
        if not baselines and deltas:
            matching = [
                item
                for item in non_targets
                if _directions_hold(claim, target, [item], metrics)
                and _deltas_hold(target, [item], metrics, deltas)
            ]
            if len(matching) != 1:
                return False
            baselines = matching
        if not baselines:
            return False

    if not _directions_hold(claim, target, baselines, metrics):
        return False
    if deltas and not _deltas_hold(target, baselines, metrics, deltas):
        return False
    return _all_numbers_accounted_for(claim.text, target, baselines, metrics, deltas)


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
        for match in re.finditer(pattern, text)
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
        phrase = _normalized_phrase(column)
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


def _baselines_matching_pairs(
    target: EvidenceItem,
    candidates: list[EvidenceItem],
    metrics: list[str],
    pairs: list[NumberPair],
    *,
    from_to: bool,
) -> list[EvidenceItem]:
    matches = []
    for baseline in candidates:
        valid = True
        for metric, pair in zip(metrics, pairs):
            if metric not in baseline.numeric_values:
                valid = False
                break
            first, second = pair
            target_spec, baseline_spec = (second, first) if from_to else (first, second)
            if not _numeric_matches(target.numeric_values[metric], target_spec) or not _numeric_matches(
                baseline.numeric_values[metric], baseline_spec
            ):
                valid = False
                break
        if valid:
            matches.append(baseline)
    return matches


def _directions_hold(
    claim: Claim,
    target: EvidenceItem,
    baselines: list[EvidenceItem],
    metrics: list[str],
) -> bool:
    return all(
        metric in baseline.numeric_values
        and _direction_holds(
            target.numeric_values[metric],
            baseline.numeric_values[metric],
            _expected_direction(claim, metric),
        )
        for baseline in baselines
        for metric in metrics
    )


def _deltas_hold(
    target: EvidenceItem,
    baselines: list[EvidenceItem],
    metrics: list[str],
    deltas: list[DeltaSpec],
) -> bool:
    if len(deltas) != len(metrics):
        return False
    return all(
        metric in baseline.numeric_values
        and _delta_matches(
            target.numeric_values[metric],
            baseline.numeric_values[metric],
            delta,
        )
        for baseline in baselines
        for metric, delta in zip(metrics, deltas)
    )


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
    for value in item.categorical_values:
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
