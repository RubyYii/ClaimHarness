from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from .schemas import ClaimType, EvidenceSourceKind, EvidenceType


EVIDENCE_CONTRACT_SCHEMA_VERSION = 2
KNOWN_CLAIM_TYPES = (
    "clinical_claim",
    "deployment_claim",
    "performance_claim",
    "novelty_claim",
    "robustness_claim",
    "workflow_claim",
    "general_claim",
)
DERIVED_SOURCE_KINDS = frozenset({"ocr", "derived_text"})
CONSERVATIVE_STRONG_EVIDENCE_TYPES = frozenset(
    {
        "quantitative_result",
        "ablation_result",
        "external_validation",
        "robustness_test",
    }
)

EvidenceRequirement = Literal[
    "table",
    "ablation",
    "trace",
    "result_text",
    "external_validation",
    "human_review",
    "robustness_test",
    "citation",
    "manuscript_context",
    "source_inspection",
]


class EvidenceContractError(ValueError):
    """Raised when an evidence contract cannot be parsed or validated."""


class ClaimEvidenceRule(BaseModel):
    """Executable evidence requirements for one ClaimHarness claim type."""

    model_config = ConfigDict(extra="forbid", strict=True)

    minimum_evidence_count: int = Field(ge=0, le=10_000)
    required_evidence: list[EvidenceRequirement] = Field(max_length=100)
    forbidden_without: list[EvidenceRequirement] = Field(max_length=100)
    human_review_roles: list[str] = Field(max_length=100)

    @model_validator(mode="after")
    def validate_unique_values(self) -> "ClaimEvidenceRule":
        for field_name in ("required_evidence", "forbidden_without", "human_review_roles"):
            values = getattr(self, field_name)
            if len(values) != len(set(values)):
                raise ValueError(f"{field_name} must not contain duplicate values")
        return self


class EvidenceContract(BaseModel):
    """Versioned, fail-closed policy for claim-evidence verification."""

    model_config = ConfigDict(extra="forbid", strict=True)

    schema_version: Literal[EVIDENCE_CONTRACT_SCHEMA_VERSION]
    project_id: str
    contract_id: str
    source_kinds: list[EvidenceSourceKind] = Field(min_length=1, max_length=100)
    strong_evidence_types: list[EvidenceType] = Field(min_length=1, max_length=100)
    human_review_roles: dict[str, str]
    claim_rules: dict[ClaimType, ClaimEvidenceRule]

    @model_validator(mode="after")
    def validate_contract_graph(self) -> "EvidenceContract":
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", self.project_id):
            raise ValueError("project_id must be a safe stable project identifier")
        if not re.fullmatch(r"contract-[0-9a-f]{24}", self.contract_id):
            raise ValueError("contract_id must be a content-derived contract identifier")
        if len(self.source_kinds) != len(set(self.source_kinds)):
            raise ValueError("source_kinds must not contain duplicate values")
        if len(self.strong_evidence_types) != len(set(self.strong_evidence_types)):
            raise ValueError("strong_evidence_types must not contain duplicate values")
        unsafe_strong_types = sorted(
            set(self.strong_evidence_types) - CONSERVATIVE_STRONG_EVIDENCE_TYPES
        )
        if unsafe_strong_types:
            raise ValueError(
                "Narrative, citation, and human-review evidence cannot be promoted to strong evidence: "
                + ", ".join(unsafe_strong_types)
            )

        actual_claim_types = set(self.claim_rules)
        expected_claim_types = set(KNOWN_CLAIM_TYPES)
        if actual_claim_types != expected_claim_types:
            missing = sorted(expected_claim_types - actual_claim_types)
            unexpected = sorted(actual_claim_types - expected_claim_types)
            details = []
            if missing:
                details.append("missing claim rules: " + ", ".join(missing))
            if unexpected:
                details.append("unknown claim rules: " + ", ".join(unexpected))
            raise ValueError("; ".join(details))

        for role_id, description in self.human_review_roles.items():
            if not re.fullmatch(r"[a-z][a-z0-9_]{0,63}", role_id):
                raise ValueError(
                    "human-review role identifiers must use lower_snake_case and start with a letter"
                )
            if not description.strip():
                raise ValueError(f"human-review role {role_id!r} must have a description")

        declared_roles = set(self.human_review_roles)
        for claim_type, rule in self.claim_rules.items():
            unknown_roles = sorted(set(rule.human_review_roles) - declared_roles)
            if unknown_roles:
                raise ValueError(
                    f"claim rule {claim_type!r} references unknown human-review roles: "
                    + ", ".join(unknown_roles)
                )
            if claim_type in {"clinical_claim", "deployment_claim"}:
                mandatory = {"external_validation", "human_review"}
                if not mandatory.issubset(rule.required_evidence) or not mandatory.issubset(
                    rule.forbidden_without
                ):
                    raise ValueError(
                        f"{claim_type} cannot weaken the mandatory external_validation + "
                        "human_review safety baseline"
                    )
                if rule.minimum_evidence_count < 2:
                    raise ValueError(
                        f"{claim_type} minimum_evidence_count must be at least 2"
                    )
        expected_contract_id = evidence_contract_id(self.model_dump(mode="json"))
        if self.contract_id != expected_contract_id:
            raise ValueError(
                "contract_id does not match the executable contract content"
            )
        return self


@dataclass(frozen=True)
class LoadedEvidenceContract:
    contract: EvidenceContract
    path: Path
    sha256: str
    size_bytes: int

    @property
    def safe_path(self) -> str:
        """Return a share-safe path label without exposing local directories."""

        return self.path.name


def load_evidence_contract(path: str | Path) -> LoadedEvidenceContract:
    """Parse and validate a JSON-compatible YAML evidence contract.

    JSON is valid YAML 1.2 and is the format emitted by ProblemBridge. A small,
    deterministic YAML subset is also accepted for hand-authored contracts so
    the core package does not require an optional YAML library.
    """

    contract_path = Path(path)
    if not contract_path.is_file():
        raise EvidenceContractError(f"evidence contract file not found: {contract_path}")
    try:
        raw_bytes = contract_path.read_bytes()
        raw = raw_bytes.decode("utf-8")
    except (OSError, UnicodeError) as exc:
        raise EvidenceContractError(f"could not read evidence contract: {exc}") from exc

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        try:
            data = _parse_yaml_subset(raw)
        except ValueError as exc:
            raise EvidenceContractError(f"invalid evidence contract syntax: {exc}") from exc

    if not isinstance(data, dict):
        raise EvidenceContractError("evidence contract root must be an object")
    try:
        contract = EvidenceContract.model_validate(data)
    except ValidationError as exc:
        details = "; ".join(
            f"{'.'.join(str(part) for part in error['loc'])}: {error['msg']}"
            for error in exc.errors(include_url=False)
        )
        raise EvidenceContractError(f"invalid evidence contract: {details}") from exc

    return LoadedEvidenceContract(
        contract=contract,
        path=contract_path,
        sha256=hashlib.sha256(raw_bytes).hexdigest(),
        size_bytes=len(raw_bytes),
    )


def default_evidence_contract(
    *,
    project_id: str = "project-unbound",
    human_review_roles: dict[str, str] | None = None,
    role_claim_types: set[str] | None = None,
) -> EvidenceContract:
    """Build the conservative project-bound contract used by exports."""

    roles = human_review_roles or {}
    governed_types = role_claim_types or set()
    required_by_type: dict[str, list[str]] = {
        "clinical_claim": ["external_validation", "human_review"],
        "deployment_claim": ["external_validation", "human_review"],
        "performance_claim": ["table"],
        "novelty_claim": ["citation"],
        "robustness_claim": ["robustness_test"],
        "workflow_claim": ["trace"],
        "general_claim": ["manuscript_context"],
    }
    rules = {
        claim_type: ClaimEvidenceRule(
            minimum_evidence_count=max(1, len(requirements)),
            required_evidence=requirements,
            forbidden_without=(
                ["external_validation", "human_review"]
                if claim_type in {"clinical_claim", "deployment_claim"}
                else []
            ),
            human_review_roles=(list(roles) if claim_type in governed_types else []),
        )
        for claim_type, requirements in required_by_type.items()
    }
    payload = {
        "schema_version": EVIDENCE_CONTRACT_SCHEMA_VERSION,
        "project_id": project_id,
        "source_kinds": [
            "table",
            "manuscript",
            "references",
            "external",
            "ocr",
            "derived_text",
        ],
        "strong_evidence_types": [
            "quantitative_result",
            "ablation_result",
            "external_validation",
            "robustness_test",
        ],
        "human_review_roles": roles,
        "claim_rules": {
            claim_type: rule.model_dump(mode="json")
            for claim_type, rule in rules.items()
        },
    }
    payload["contract_id"] = evidence_contract_id(payload)
    return EvidenceContract.model_validate(payload)


def evidence_contract_id(payload: dict[str, object]) -> str:
    """Return the deterministic identifier for executable contract content."""

    content = dict(payload)
    content.pop("contract_id", None)
    canonical = json.dumps(
        content, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return "contract-" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:24]


@dataclass(frozen=True)
class _YamlLine:
    indent: int
    text: str
    number: int


def _parse_yaml_subset(raw: str) -> object:
    lines: list[_YamlLine] = []
    for number, original in enumerate(raw.splitlines(), start=1):
        if "\t" in original:
            raise ValueError(f"line {number}: tabs are not supported")
        stripped = original.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(original) - len(original.lstrip(" "))
        if indent % 2:
            raise ValueError(f"line {number}: indentation must use multiples of two spaces")
        lines.append(_YamlLine(indent=indent, text=original[indent:], number=number))

    if not lines:
        raise ValueError("contract is empty")
    if lines[0].indent != 0:
        raise ValueError(f"line {lines[0].number}: root must start at indentation zero")
    value, next_index = _parse_yaml_node(lines, 0, 0)
    if next_index != len(lines):
        line = lines[next_index]
        raise ValueError(f"line {line.number}: unexpected content")
    return value


def _parse_yaml_node(
    lines: list[_YamlLine],
    index: int,
    indent: int,
) -> tuple[object, int]:
    line = lines[index]
    if line.indent != indent:
        raise ValueError(f"line {line.number}: unexpected indentation")
    if line.text.startswith("-"):
        return _parse_yaml_list(lines, index, indent)
    if ":" in line.text:
        return _parse_yaml_mapping(lines, index, indent)
    return _parse_yaml_scalar(line.text, line.number), index + 1


def _parse_yaml_mapping(
    lines: list[_YamlLine],
    index: int,
    indent: int,
) -> tuple[dict[str, object], int]:
    result: dict[str, object] = {}
    while index < len(lines) and lines[index].indent == indent:
        line = lines[index]
        if line.text.startswith("-"):
            break
        key, separator, remainder = line.text.partition(":")
        if not separator or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_-]*", key):
            raise ValueError(f"line {line.number}: invalid mapping key")
        if key in result:
            raise ValueError(f"line {line.number}: duplicate key {key!r}")
        remainder = remainder.strip()
        index += 1
        if remainder:
            result[key] = _parse_yaml_scalar(remainder, line.number)
            continue
        if index >= len(lines) or lines[index].indent <= indent:
            raise ValueError(f"line {line.number}: key {key!r} has no value")
        if lines[index].indent != indent + 2:
            raise ValueError(f"line {lines[index].number}: unexpected indentation")
        result[key], index = _parse_yaml_node(lines, index, indent + 2)
    return result, index


def _parse_yaml_list(
    lines: list[_YamlLine],
    index: int,
    indent: int,
) -> tuple[list[object], int]:
    result: list[object] = []
    while index < len(lines) and lines[index].indent == indent:
        line = lines[index]
        if not line.text.startswith("-"):
            break
        remainder = line.text[1:].strip()
        index += 1
        if remainder:
            result.append(_parse_yaml_scalar(remainder, line.number))
            continue
        if index >= len(lines) or lines[index].indent != indent + 2:
            raise ValueError(f"line {line.number}: list item has no value")
        value, index = _parse_yaml_node(lines, index, indent + 2)
        result.append(value)
    return result, index


def _parse_yaml_scalar(text: str, line_number: int) -> object:
    if text.startswith(("&", "*", "!", "|", ">")):
        raise ValueError(f"line {line_number}: YAML tags, anchors, and block scalars are unsupported")
    if text.startswith(('"', "'", "[", "{")):
        if text.startswith("'"):
            if not text.endswith("'"):
                raise ValueError(f"line {line_number}: unterminated quoted scalar")
            return text[1:-1].replace("''", "'")
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError(f"line {line_number}: invalid flow-style value") from exc
    lowered = text.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if lowered in {"null", "~"}:
        return None
    if re.fullmatch(r"[-+]?\d+", text):
        return int(text)
    if re.fullmatch(r"[-+]?(?:\d+\.\d*|\.\d+)(?:[eE][-+]?\d+)?", text):
        return float(text)
    if " #" in text:
        text = text.split(" #", 1)[0].rstrip()
    return text
