"""One confirmed problem, immutable evidence runs, and traceable next questions.

No model calls and no generated alignment templates as empirical evidence.
The UI supplies material explicitly; the CLI's existing verifier does the audit.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from claim_harness.cli import CLAIM_REQUIRED_ARTIFACTS, write_local_audit
from claim_harness import __version__ as audit_version
from . import __version__ as bridge_version
from .handoff import HANDOFF_ARTIFACTS, NeedBrief, build_handoffs
from .project_lifecycle import (
    SYSTEM_OWNED_ARTIFACTS, allocate_run_directory, is_link_or_reparse, snapshot_completed_run,
)


PROBLEM_ARTIFACTS = ("problem_record.json", "problem_record.md", *HANDOFF_ARTIFACTS)
FOLLOW_UP_ARTIFACTS = ("follow_up.json", "follow_up.md")
FRAME_FIELDS = ("question", "observation", "observation_source", "desired_change", "hypothesis", "human_boundary")
MAX_FILE_BYTES = 2 * 1024 * 1024
MAX_TOTAL_BYTES = 10 * 1024 * 1024


class RunReference(BaseModel):
    model_config = ConfigDict(extra="forbid")
    run_name: str
    run_id: str


class FollowUpAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid")
    audit_run_id: str
    question_id: str
    answer: str
    recorded_at: str
    status: str = "user_reported_not_verified"


class ProblemRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: int = 1
    problem_id: str
    project_id: str
    revision: int = Field(ge=1)
    question: str
    observation: str = ""
    observation_source: str = ""
    desired_change: str = ""
    hypothesis: str = ""
    human_boundary: str = ""
    brief: NeedBrief | None = None
    interview_answers: dict[str, str] = Field(default_factory=dict)
    framing_sha256: str
    confirmed_at: str
    previous: RunReference | None = None
    audit: RunReference | None = None
    responses: list[FollowUpAnswer] = Field(default_factory=list)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _digest(value: object) -> str:
    return hashlib.sha256(_json(value).encode("utf-8")).hexdigest()


def _safe_root(root: Path) -> Path:
    root = root.absolute()
    for path in (root, *root.parents):
        if (path.exists() or path.is_symlink()) and is_link_or_reparse(path):
            raise ValueError("Linked workbench directories are not allowed.")
    return root.resolve()


def _snapshot(root: Path, out: Path, project_id: str) -> tuple[dict[str, bytes], RunReference]:
    root = _safe_root(root)
    candidate = out.absolute()
    if candidate.parent != root or is_link_or_reparse(candidate):
        raise ValueError("The result is outside this workbench.")
    files = snapshot_completed_run(candidate)
    identity = json.loads(files["run_identity.json"])
    if identity["project_id"] != project_id:
        raise ValueError("The result belongs to another project.")
    return files, RunReference(run_name=candidate.name, run_id=identity["run_id"])


def load_problem(root: Path, out: Path, project_id: str) -> ProblemRecord:
    files, _ = _snapshot(root, out, project_id)
    record = ProblemRecord.model_validate_json(files["problem_record.json"])
    if record.project_id != project_id:
        raise ValueError("The problem belongs to another project.")
    if record.schema_version not in (1, 2) or (record.schema_version == 1 and record.brief is not None):
        raise ValueError("Unsupported problem record version.")
    framing = {key: getattr(record, key) for key in FRAME_FIELDS}
    if record.schema_version == 2:
        framing["brief"] = record.brief.model_dump(mode="json") if record.brief else None
    if record.framing_sha256 != _digest(framing):
        raise ValueError("The problem framing does not match its recorded fingerprint.")
    return record


def _allocate(root: Path, record: ProblemRecord, kind: str, *, audit: bool = False, payload=None):
    artifacts = (*PROBLEM_ARTIFACTS, *FOLLOW_UP_ARTIFACTS)
    if audit:
        artifacts = (*artifacts, *CLAIM_REQUIRED_ARTIFACTS)
    return allocate_run_directory(
        _safe_root(root), project_id=record.project_id, prefix=kind,
        owned_artifacts=tuple(name for name in artifacts if name in SYSTEM_OWNED_ARTIFACTS), required_artifacts=artifacts,
        snapshot_directories=("source_files",) if audit else (),
        workflow_type=f"problem_bridge.{kind}",
        run_spec_sha256=_digest({"record": record.model_dump(mode="json"), "inputs": payload,
                                "problem_bridge_version": bridge_version, "claim_harness_version": audit_version}),
    )


def _write_record(out: Path, record: ProblemRecord) -> None:
    (out / "problem_record.json").write_text(_json(record.model_dump(mode="json")), encoding="utf-8")
    labels = {
        "question": "Question / 问题", "observation": "Reported observation / 用户报告的观察",
        "observation_source": "Observation source / 观察来源", "desired_change": "Desired change / 希望改变",
        "hypothesis": "Unverified hypothesis / 待验证假设", "human_boundary": "Human judgement / 人工判断边界",
    }
    lines = ["# Problem record / 问题记录", "", f"Problem: {record.problem_id}", f"Revision: {record.revision}"]
    for key, label in labels.items():
        lines.extend(["", f"## {label}", getattr(record, key) or "Not specified / 未填写"])
    lines.extend(["", "Reported observations, hypotheses and follow-up answers are not independent validation.",
                  "观察、假设与追问回答均不自动构成独立验证。", "", "## Follow-up answers / 追问回答"])
    for response in record.responses:
        lines.extend([f"- {response.audit_run_id} / {response.question_id}: {response.answer}"])
    (out / "problem_record.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    for name, content in build_handoffs(record).items():
        (out / name).write_bytes(content.encode("utf-8"))


def _write_follow_up(out: Path, payload: dict) -> None:
    (out / "follow_up.json").write_text(_json(payload), encoding="utf-8")
    lines = ["# Next questions / 下一步问题", "", "Answers record next steps; they do not change audit verdicts.",
             "回答仅记录后续行动，不改变核查结论。"]
    for item in payload["questions"]:
        lines.extend(["", f"## {item['question_id']} · {item.get('claim_id') or 'coverage'}",
                      item["question_zh"], item["question_en"], item.get("claim_text", ""),
                      f"Reason: {item.get('reason', '')}", f"Next action: {item.get('suggested_revision', '')}"])
    (out / "follow_up.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def confirm_problem(root: Path, project_id: str, fields: dict[str, str], *,
                    previous: Path | None = None, interview_answers: dict[str, str] | None = None,
                    brief: NeedBrief | None = None) -> Path:
    cleaned = {key: str(fields.get(key, "")).strip() for key in FRAME_FIELDS}
    if not cleaned["question"]:
        raise ValueError("Write the question you want to investigate first.")
    if any(len(value) > 20000 for value in cleaned.values()):
        raise ValueError("Each problem field must contain at most 20,000 characters.")
    parent = load_problem(root, previous, project_id) if previous else None
    brief = brief if brief is not None else (parent.brief if parent else None)
    framing = {**cleaned, "brief": brief.model_dump(mode="json")} if brief is not None else cleaned
    reference = _snapshot(root, previous, project_id)[1] if previous else None
    record = ProblemRecord(
        problem_id=parent.problem_id if parent else f"problem-{uuid.uuid4().hex}", project_id=project_id,
        revision=parent.revision + 1 if parent else 1, **cleaned, framing_sha256=_digest(framing),
        schema_version=2 if brief is not None else 1, brief=brief,
        confirmed_at=_now(), previous=reference, responses=parent.responses if parent else [],
        interview_answers=interview_answers if interview_answers is not None else (parent.interview_answers if parent else {}),
    )
    context = _allocate(root, record, "problem")
    with context.transaction():
        _write_record(context.path, record)
        _write_follow_up(context.path, {"schema_version": 1, "problem_id": record.problem_id, "questions": []})
    return context.path


def _validate_materials(manuscript: str, tables: dict[str, bytes], references: str) -> None:
    if not manuscript.strip():
        raise ValueError("Add the text whose claims you want to check.")
    if not tables or len(tables) > 20:
        raise ValueError("Supply between 1 and 20 CSV result tables.")
    sizes = [len(manuscript.encode("utf-8")), len(references.encode("utf-8")), *(len(data) for data in tables.values())]
    if max(sizes) > MAX_FILE_BYTES or sum(sizes) > MAX_TOTAL_BYTES:
        raise ValueError("Each input must be at most 2 MB, and the total at most 10 MB.")
    seen = set()
    for name, data in tables.items():
        stem = name.split(".")[0].upper()
        if (not name.lower().endswith(".csv") or name in {".", ".."} or
            re.search(r'[\\/:*?"<>|\x00-\x1f]', name) or len(name) > 120 or
            stem in {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(10)), *(f"LPT{i}" for i in range(10))}):
            raise ValueError("Use a plain CSV filename without path components.")
        if name.casefold() in seen:
            raise ValueError("CSV filenames must be unique, ignoring case.")
        seen.add(name.casefold())
        try:
            rows = list(csv.reader(io.StringIO(data.decode("utf-8-sig")), strict=True))
        except (UnicodeError, csv.Error) as exc:
            raise ValueError(f"{name}: use a UTF-8 CSV table.") from exc
        if len(rows) < 2 or not rows[0] or any(not cell.strip() for cell in rows[0]):
            raise ValueError(f"{name}: supply column names and at least one data row.")
        if len(set(rows[0])) != len(rows[0]) or any(len(row) != len(rows[0]) for row in rows[1:]):
            raise ValueError(f"{name}: column names must be unique and every row must have the same width.")


def _make_follow_up(out: Path, record: ProblemRecord, run_id: str) -> dict:
    with (out / "claim_table.csv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    evidence_map = json.loads((out / "evidence_map.json").read_text(encoding="utf-8"))
    evidence = {item["evidence_id"]: item for item in evidence_map.get("evidence", [])}
    questions = []
    for row in rows:
        if row["status"] == "supported" and row["human_review_required"] != "true":
            continue
        conflicting = [item for item in row["contradicting_evidence_ids"].split(";") if item]
        supporting = [item for item in row["supporting_evidence_ids"].split(";") if item]
        if conflicting:
            kind, en, zh = "conflict", "Which source/version explains the discrepancy, and what should be corrected?", "哪份来源或版本能解释这处不一致？应更正正文还是表格？"
        elif row["human_review_required"] == "true":
            kind, en, zh = "human_review", "Who should review this claim, and what material or scope limitation do they need?", "这句话需要谁复核？还应提供哪些材料，或收窄到什么范围？"
        else:
            kind, en, zh = "evidence_gap", "What independent result would support this claim? If unavailable, how should its scope change?", "要支持这句话，还缺哪项独立结果？如果暂时没有，应该怎样收窄表述？"
        # Include linked evidence even if the verifier judged it only related.
        claim_entry = next((item for item in evidence_map.get("claims", []) if item["claim_id"] == row["claim_id"]), {})
        related = claim_entry.get("evidence_ids", [])
        locators = {link["evidence_id"]: link["locator"] for link in claim_entry.get("evidence_links", [])}
        ids = list(dict.fromkeys([*conflicting, *supporting, *related]))
        questions.append({
            "question_id": f"follow-{row['claim_id']}", "claim_id": row["claim_id"], "kind": kind,
            "question_en": en, "question_zh": zh, "claim_text": row["text"], "status": row["status"],
            "reason": row["reason"], "missing_evidence": row["missing_evidence"].split(";") if row["missing_evidence"] else [],
            "suggested_revision": row["suggested_revision"], "evidence_ids": ids,
            "evidence": [{"evidence_id": eid, "relation": evidence[eid].get("claim_link_relations", {}).get(row["claim_id"], "related"),
                          "locator": locators.get(eid, evidence[eid].get("locator")),
                          "text": evidence[eid].get("text", "")} for eid in ids if eid in evidence],
        })
    # Coverage remains unknown even when all extracted statements are supported.
    questions.append({"question_id": "coverage-review", "claim_id": None, "kind": "coverage",
                      "question_en": "Which important statements were missed? Compare the extracted list with the original text.",
                      "question_zh": "原文里还有哪些重要表述没有被提取？请对照原文和声明清单人工检查。",
                      "claim_text": "", "reason": "Extraction coverage is unknown.", "evidence_ids": [], "evidence": []})
    return {"schema_version": 1, "problem_id": record.problem_id, "audit_run_id": run_id,
            "framing_sha256": record.framing_sha256, "claim_count": len(rows), "questions": questions}


def audit_problem(root: Path, project_id: str, previous: Path, *, manuscript: str,
                  tables: dict[str, bytes], references: str = "") -> Path:
    _validate_materials(manuscript, tables, references)
    parent = load_problem(root, previous, project_id)
    reference = _snapshot(root, previous, project_id)[1]
    record = parent.model_copy(update={"revision": parent.revision + 1, "previous": reference, "audit": None})
    inputs = {"manuscript": _digest(manuscript), "references": _digest(references),
              "tables": {name: hashlib.sha256(data).hexdigest() for name, data in tables.items()}}
    context = _allocate(root, record, "problem_audit", audit=True, payload=inputs)
    record.audit = RunReference(run_name=context.path.name, run_id=context.run_id)
    with context.transaction():
        sources = context.path / "source_files"
        table_dir = sources / "tables"
        table_dir.mkdir(parents=True)
        manuscript_path = sources / "manuscript.md"
        manuscript_path.write_text(manuscript, encoding="utf-8")
        for name, data in tables.items():
            (table_dir / name).write_bytes(data)
        reference_path = None
        if references.strip():
            reference_path = sources / "references.md"
            reference_path.write_text(references, encoding="utf-8")
        write_local_audit(manuscript_path, table_dir, reference_path, context)
        _write_record(context.path, record)
        _write_follow_up(context.path, _make_follow_up(context.path, record, context.run_id))
    return context.path


def load_audit(root: Path, record: ProblemRecord) -> tuple[dict[str, bytes], dict]:
    if record.audit is None:
        raise ValueError("This framing has not been checked yet.")
    files, reference = _snapshot(root, root / record.audit.run_name, record.project_id)
    if reference != record.audit:
        raise ValueError("The linked audit identity has changed.")
    feedback = json.loads(files["follow_up.json"])
    if (feedback["framing_sha256"] != record.framing_sha256 or feedback["problem_id"] != record.problem_id
            or feedback["audit_run_id"] != record.audit.run_id):
        raise ValueError("The audit does not belong to this problem framing.")
    return files, feedback


def answer_follow_up(root: Path, project_id: str, previous: Path, question_id: str, answer: str) -> Path:
    if not answer.strip() or len(answer) > 20000:
        raise ValueError("Write a follow-up answer of 1–20,000 characters.")
    parent = load_problem(root, previous, project_id)
    _, feedback = load_audit(root, parent)
    if not any(item["question_id"] == question_id for item in feedback["questions"]):
        raise ValueError("This follow-up question is not part of the linked audit.")
    reference = _snapshot(root, previous, project_id)[1]
    response = FollowUpAnswer(audit_run_id=parent.audit.run_id, question_id=question_id,
                              answer=answer.strip(), recorded_at=_now())
    record = parent.model_copy(update={"revision": parent.revision + 1, "previous": reference,
                                       "responses": [*parent.responses, response]})
    context = _allocate(root, record, "problem_follow_up")
    with context.transaction():
        _write_record(context.path, record)
        _write_follow_up(context.path, feedback)
    return context.path
