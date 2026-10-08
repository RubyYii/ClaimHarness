"""Conservative, source-bound comparison of complete audit episodes.

Claim IDs and evidence IDs are local to one run. No fuzzy match is a decision,
and absence from an extraction is never treated as a repaired evidence gap.
"""
from __future__ import annotations

import csv
import difflib
import hashlib
import io
import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from problem_bridge.project_lifecycle import snapshot_completed_run, prepare_run_directory, is_link_or_reparse
from .claim_extractor import sentences_with_lines
from .continuity_store import Journal, digest
from .loader import parse_manuscript


BOUNDARY = ("Changes describe two saved screenings, not scientific validation or proof that a problem is fixed. "
            "Deletion is not added evidence; extraction coverage remains unknown.")
OUTPUTS = ("audit_changes.json", "audit_changes.md", "pending_questions.md")


def normalize(text: str) -> str:
    # Only layout whitespace. Preserve case, punctuation, numbers, units and negation.
    return re.sub(r"\s+", " ", text).strip()


@dataclass
class AuditRun:
    path: Path
    identity: dict = field(default_factory=dict)
    manifest: dict = field(default_factory=dict)
    claims: list[dict] = field(default_factory=list)
    evidence: dict = field(default_factory=dict)
    snapshot: dict | None = None
    problem: dict | None = None
    limitations: list[str] = field(default_factory=list)
    integrity: str = "invalid"

    @property
    def ref(self) -> dict:
        return {"run_name": self.path.name, "run_id": self.identity.get("run_id", self.manifest.get("run_id")),
                "project_id": self.identity.get("project_id", self.manifest.get("project_id")),
                "manifest_sha256": digest(self.manifest), "integrity": self.integrity}

    @property
    def text(self) -> str | None:
        return self.snapshot["manuscript"]["text"] if self.snapshot else None


def load_audit_run(path: Path) -> AuditRun:
    """Legacy packages stay inspectable, with no fabricated identity or snapshot."""
    run = AuditRun(Path(path))
    path = run.path
    if any((p.exists() or p.is_symlink()) and is_link_or_reparse(p) for p in (path, *path.absolute().parents)):
        run.limitations.append("Linked audit directories are not accepted.")
        return run
    try:
        files = snapshot_completed_run(path)
        run.identity = json.loads(files["run_identity.json"])
        run.integrity = "verified"
    except (OSError, ValueError, RuntimeError) as exc:
        if (path / "run_identity.json").exists() or (path / "run_complete.json").exists():
            run.limitations.append(f"Incomplete or invalid package: {exc}")
            return run
        try:
            # Only named legacy outputs, never a directory-wide crawl.
            names = ("run_manifest.json", "claim_table.csv", "evidence_map.json")
            if any(is_link_or_reparse(path / name) for name in names):
                raise OSError("Missing or linked legacy report files.")
            files = {name: (path / name).read_bytes() for name in names}
            run.integrity = "legacy_unverified"
            run.limitations.append("Legacy package: completion and identity cannot be verified.")
        except OSError:
            run.limitations.append("Missing audit identity and required reports.")
            return run
    try:
        run.manifest = json.loads(files["run_manifest.json"])
        if run.manifest.get("schema_version") not in (1, 2):
            raise ValueError("Unsupported run manifest version.")
        if run.integrity == "verified" and any(run.manifest.get(k) != run.identity.get(k) for k in ("run_id", "project_id")):
            raise ValueError("Manifest and lifecycle identities disagree.")
        for item in run.manifest.get("outputs", []):
            name = item["name"]
            if name in files and hashlib.sha256(files[name]).hexdigest() != item["sha256"]:
                raise ValueError(f"Manifest hash mismatch: {name}")
        evidence_map = json.loads(files["evidence_map.json"])
        rows = list(csv.DictReader(io.StringIO(files["claim_table.csv"].decode("utf-8-sig"))))
        by_id = {r["claim_id"]: r for r in rows}
        if len(by_id) != len(rows) or len({c["claim_id"] for c in evidence_map["claims"]}) != len(evidence_map["claims"]):
            raise ValueError("Duplicate claim IDs inside a run.")
        if set(by_id) != {c["claim_id"] for c in evidence_map["claims"]}:
            raise ValueError("Claim table and evidence map disagree.")
        run.claims = [{**by_id[c["claim_id"]], **c} for c in evidence_map["claims"]]
        run.evidence = {e["evidence_id"]: e for e in evidence_map["evidence"]}
        if "problem_record.json" in files:
            run.problem = json.loads(files["problem_record.json"])
        if "audit_snapshot.json" in files and run.integrity == "verified":
            run.snapshot = json.loads(files["audit_snapshot.json"])
            if run.snapshot.get("schema_version") != 1:
                raise ValueError("Unsupported audit snapshot version.")
            for source in [run.snapshot["manuscript"], *run.snapshot["tables"], run.snapshot.get("references")]:
                if source and source.get("text_sha256") and hashlib.sha256(source["text"].encode("utf-8")).hexdigest() != source["text_sha256"]:
                    raise ValueError("Snapshot text hash disagrees.")
            inputs = run.manifest["inputs"]
            for key in ("manuscript", "references"):
                value = run.snapshot[key]
                if (value and {k: value[k] for k in ("name", "sha256", "size_bytes")}) != inputs.get(key):
                    raise ValueError(f"Snapshot input identity disagrees: {key}")
            if [{k: t[k] for k in ("name", "sha256", "size_bytes")} for t in run.snapshot["tables"]] != inputs["tables"]:
                raise ValueError("Table snapshot identities disagree.")
        else:
            run.limitations.append("Original source/rule snapshot is missing; absence cannot establish deletion or addition.")
    except (ValueError, KeyError, TypeError, UnicodeError) as exc:
        run.integrity = "invalid"
        run.claims = []
        run.snapshot = None
        run.limitations.append(f"Unreadable or inconsistent audit: {exc}")
    return run


def source_units(run: AuditRun) -> list[dict]:
    if not run.text or not run.text.strip():
        return []
    return [{"text": text, "source_line": line, "source_section": section.name, "source_kind": section.source_kind}
            for section in parse_manuscript(run.text, run.snapshot["manuscript"]["name"])
            for text, line in sentences_with_lines(section)]


def _anchor(claim: dict, units: list[dict]) -> tuple | None:
    found = [i for i, u in enumerate(units) if normalize(u["text"]) == normalize(claim["text"])
             and u["source_line"] == claim.get("source_line") and u["source_section"] == claim.get("source_section")]
    if len(found) != 1:
        return None
    i = found[0]
    return (units[i]["source_section"], normalize(units[i - 1]["text"]) if i else "<start>",
            normalize(units[i + 1]["text"]) if i + 1 < len(units) else "<end>")


def _evidence(run: AuditRun, claim: dict) -> list[dict]:
    result = []
    for link in claim.get("evidence_links", []):
        entry = run.evidence.get(link["evidence_id"], {})
        result.append({"relation": link.get("relation", "related"), "locator": link.get("locator"),
                       "text": entry.get("text", ""), "type": entry.get("evidence_type")})
    return sorted(result, key=lambda x: json.dumps(x, sort_keys=True))


def _claim_view(run: AuditRun, claim: dict) -> dict:
    return {**claim, "run_id": run.ref["run_id"], "evidence": _evidence(run, claim)}


def _result_key(claim: dict) -> tuple:
    return tuple(str(claim.get(k, "")) for k in ("status", "risk_level", "human_review_required", "missing_evidence"))


def _material_changes(old: AuditRun, new: AuditRun) -> list[dict]:
    def records(run):
        inputs = run.manifest.get("inputs", {})
        return {**{f"table:{t['name']}": t for t in inputs.get("tables", [])},
                "manuscript": inputs.get("manuscript"), "references": inputs.get("references")}
    left, right = records(old), records(new)
    changes = []
    for key in sorted(left.keys() | right.keys()):
        a, b = left.get(key), right.get(key)
        if (a or {}).get("sha256") == (b or {}).get("sha256"):
            continue
        item = {"source": key, "previous": a, "current": b, "cells": []}
        if key.startswith("table:") and old.snapshot and new.snapshot:
            name = key[6:]
            av = next((t for t in old.snapshot["tables"] if t["name"] == name), None)
            bv = next((t for t in new.snapshot["tables"] if t["name"] == name), None)
            if av and bv:
                ar, br = list(csv.reader(io.StringIO(av["text"]))), list(csv.reader(io.StringIO(bv["text"])))
                # Positional differences are deliberately not asserted to be the same entity.
                for r in range(max(len(ar), len(br))):
                    aa, bb = ar[r] if r < len(ar) else [], br[r] if r < len(br) else []
                    for c in range(max(len(aa), len(bb))):
                        va, vb = aa[c] if c < len(aa) else None, bb[c] if c < len(bb) else None
                        if va != vb:
                            item["cells"].append({"row": r + 1, "column": c + 1, "previous": va, "current": vb})
                item["cell_boundary"] = "CSV row/column coordinates; row identity is not inferred after reordering."
        changes.append(item)
    return changes


def compare_runs(previous: Path | AuditRun, current: Path | AuditRun, *, same_task: bool = False,
                 mappings: list[dict] | None = None, workspace: Path | None = None) -> dict:
    old = previous if isinstance(previous, AuditRun) else load_audit_run(previous)
    new = current if isinstance(current, AuditRun) else load_audit_run(current)
    limitations = [*("Previous: " + s for s in old.limitations), *("Current: " + s for s in new.limitations)]
    result = {"schema_version": 1, "previous": old.ref, "current": new.ref,
              "same_task_confirmed": same_task, "boundary": BOUNDARY, "limitations": limitations,
              "comparability": "limited", "materials": [], "rules": {}, "changes": [], "pending": []}
    if not same_task:
        limitations.append("Confirm that these runs are the intended same task before comparing.")
    if "invalid" in (old.integrity, new.integrity) or not same_task:
        result["comparability"] = "blocked"
        result["pending"] = [{"kind": "comparability", "question": s} for s in limitations]
        return result
    if old.ref["project_id"] != new.ref["project_id"]:
        limitations.append("Different project identities; same-task correspondence is user asserted.")
    if old.problem and new.problem and old.problem["framing_sha256"] != new.problem["framing_sha256"]:
        limitations.append("Confirmed requirements changed; the earlier audit is historical, not a verdict on the current goal.")
    a_rules = old.snapshot.get("rules") if old.snapshot else None
    b_rules = new.snapshot.get("rules") if new.snapshot else None
    rule_state = "unknown" if a_rules is None or b_rules is None else "unchanged" if a_rules == b_rules else "changed"
    result["rules"] = {"state": rule_state, "previous": a_rules, "current": b_rules}
    if rule_state != "unchanged":
        limitations.append("Checking rules changed or are unknown; changed verdicts cannot be attributed solely to a user repair.")
    result["materials"] = _material_changes(old, new)
    old_units, new_units = source_units(old), source_units(new)
    old_counts, new_counts = Counter(normalize(u["text"]) for u in old_units), Counter(normalize(u["text"]) for u in new_units)
    old_by, new_by = {c["claim_id"]: c for c in old.claims}, {c["claim_id"]: c for c in new.claims}
    used_old, used_new, relations = set(), set(), []
    for mapping in mappings or []:
        oi, ni = mapping.get("previous_ids", []), mapping.get("current_ids", [])
        if (not oi or not ni or not mapping.get("reason", "").strip() or
                len(set(oi)) != len(oi) or len(set(ni)) != len(ni) or
                not set(oi) <= old_by.keys() or not set(ni) <= new_by.keys() or
                used_old.intersection(oi) or used_new.intersection(ni)):
            raise ValueError("Mappings need existing, non-overlapping IDs on both sides and a user reason.")
        relations.append((oi, ni, "user_confirmed", mapping["reason"]))
        used_old.update(oi)
        used_new.update(ni)
    left, right = defaultdict(list), defaultdict(list)
    for c in old.claims:
        if c["claim_id"] not in used_old:
            left[(normalize(c["text"]), c.get("source_kind"))].append(c)
    for c in new.claims:
        if c["claim_id"] not in used_new:
            right[(normalize(c["text"]), c.get("source_kind"))].append(c)
    # Only source-backed exact text can be automatically associated.
    for key in left.keys() & right.keys():
        aa, bb = left[key], right[key]
        if old.text is None or new.text is None:
            continue
        pairs = []
        if len(aa) == len(bb) == 1 and old_counts[key[0]] == new_counts[key[0]] == 1:
            pairs = [(aa[0], bb[0], "unique_exact")]
        else:
            ac, bc = defaultdict(list), defaultdict(list)
            for c in aa:
                ac[_anchor(c, old_units)].append(c)
            for c in bb:
                bc[_anchor(c, new_units)].append(c)
            for anchor in ac.keys() & bc.keys():
                if anchor is not None and len(ac[anchor]) == len(bc[anchor]) == 1:
                    pairs.append((ac[anchor][0], bc[anchor][0], "unique_context"))
        for a, b, method in pairs:
            used_old.add(a["claim_id"])
            used_new.add(b["claim_id"])
            relations.append(([a["claim_id"]], [b["claim_id"]], method, "Exact text; unique source correspondence."))

    def add(kind, aa, bb, reason, **extra):
        item = {"change_id": f"change-{len(result['changes']) + 1:03d}", "kind": kind,
                "previous": [_claim_view(old, c) for c in aa], "current": [_claim_view(new, c) for c in bb],
                "reason": reason, "resolved": False, **extra}
        result["changes"].append(item)
        if kind != "unchanged" or any(c.get("status") != "supported" or c.get("human_review_required") == "true" for c in bb):
            result["pending"].append({"kind": kind, "change_id": item["change_id"], "question": reason})

    for oi, ni, method, note in relations:
        aa, bb = [old_by[i] for i in oi], [new_by[i] for i in ni]
        tags = []
        if len(aa) != 1 or len(bb) != 1:
            tags.append("split_or_merge")
        if [normalize(c["text"]) for c in aa] != [normalize(c["text"]) for c in bb]:
            tags.append("text_modified")
        if [_result_key(c) for c in aa] != [_result_key(c) for c in bb]:
            tags.append("result_changed")
        if [_evidence(old, c) for c in aa] != [_evidence(new, c) for c in bb]:
            tags.append("evidence_changed")
        if rule_state != "unchanged":
            tags.append("rules_" + rule_state)
        reason = note + (" Changes: " + ", ".join(tags) + ". Review the current result and source before deciding the next action." if tags else " Statement, result, linked evidence and rules are unchanged.")
        add(tags[0] if tags else "unchanged", aa, bb, reason, match_method=method, tags=tags,
            text_diff="\n".join(difflib.unified_diff([c["text"] for c in aa], [c["text"] for c in bb], fromfile="previous", tofile="current", lineterm="")))
    for c in old.claims:
        if c["claim_id"] in used_old:
            continue
        norm = normalize(c["text"])
        candidates = [b["claim_id"] for b in new.claims if b["claim_id"] not in used_new and normalize(b["text"]) == norm]
        if new.text is None or old.text is None:
            kind, reason = "unable_to_compare", "Original source snapshots are missing; this unmatched extraction cannot establish deletion."
        elif candidates or new_counts[norm] > 1 or old_counts[norm] > 1:
            kind, reason = "correspondence_pending", "Repeated or ambiguous original text needs a user-confirmed correspondence."
        elif new_counts[norm] == 1:
            kind, reason = "not_extracted", "The original sentence is still present but was not extracted in the current run; check a possible extraction omission."
        else:
            kind, reason = "text_removed", "The original sentence no longer occurs verbatim (deleted or rewritten). This does not establish that its evidence gap is resolved; map rewrites explicitly."
        add(kind, [c], [], reason, candidate_ids=candidates)
    for c in new.claims:
        if c["claim_id"] in used_new:
            continue
        norm = normalize(c["text"])
        if old.text is None:
            kind, reason = "unable_to_compare", "The earlier source snapshot is missing; this is a newly observed extraction, not a confirmed new sentence."
        elif old_counts[norm]:
            kind, reason = "correspondence_pending", "This sentence already appeared in the earlier source; confirm duplicate correspondence or a changed extraction."
        else:
            kind, reason = "new_statement", "New verbatim wording in this source; it may be a rewrite. Review its current verdict or map it to the earlier statement."
        add(kind, [], [c], reason)
    for item in result["materials"]:
        name = item["source"].removeprefix("table:")
        item["affected_changes"] = [c["change_id"] for c in result["changes"] if
            any((e.get("locator") or {}).get("source_file") == name for side in ("previous", "current")
                for claim in c[side] for e in claim["evidence"])]
    if not new.claims:
        result["pending"].append({"kind": "coverage", "question": "Zero extracted statements is not a full-text pass; inspect and annotate the source."})
    result["pending"].extend({"kind": "comparability", "question": s} for s in limitations)
    result["handling_history"] = {}
    if workspace is not None:
        for side, run in (("previous", old), ("current", new)):
            if run.integrity == "verified":
                history = Journal(workspace, {"kind": "audit_handling", "run": run.ref}).read()
                result["handling_history"][side] = history
                for event in history["events"]:
                    if event["kind"] == "manual_claim":
                        item = event["payload"]
                        result["pending"].append({"kind": "not_evaluated", "side": side,
                            "manual_id": item["manual_id"], "source": item["source"], "text": item["text"],
                            "question": item["question"], "candidate_evidence_ids": item["candidate_evidence_ids"]})
    result["comparability"] = "limited" if limitations else "comparable"
    return result


def render_comparison(value: dict) -> str:
    lines = ["# Audit changes / 核查变化", "", BOUNDARY, "", f"Comparability: {value['comparability']}",
             f"Previous: {value['previous']['run_id']}", f"Current: {value['current']['run_id']}", "",
             "## Limitations / 比较限制", *["- " + s for s in value["limitations"]], "",
             "## Rule changes / 核查规则变化", "```json", json.dumps(value["rules"], ensure_ascii=False, indent=2), "```",
             "", "## Material changes / 材料变化", "```json", json.dumps(value["materials"], ensure_ascii=False, indent=2), "```"]
    for item in value["changes"]:
        lines += ["", f"## {item['change_id']} · {item['kind']}", "", item["reason"]]
        for side in ("previous", "current"):
            for c in item[side]:
                lines += ["", f"**{side} · {c['claim_id']} · {c['status']}**",
                          f"Source: {c.get('source_section')} / line {c.get('source_line')}",
                          "\n".join("> " + line for line in c["text"].splitlines()),
                          "Reason: " + c.get("reason", ""), "Evidence: " + json.dumps(c["evidence"], ensure_ascii=False)]
        if item.get("text_diff"):
            lines += ["", "```diff", item["text_diff"], "```"]
    if any(h["events"] for h in value.get("handling_history", {}).values()):
        lines += ["", "## Separate user actions and attributed opinions / 独立保存的处理与人工意见",
                  "These records never replace a program verdict; reviewer identity and qualifications are not authenticated.",
                  "```json", json.dumps(value["handling_history"], ensure_ascii=False, indent=2), "```"]
    return "\n".join(lines) + "\n"


def render_pending(value: dict, *, research: bool = False) -> str:
    title = "Research discussion input / 后续研究讨论输入" if research else "Pending questions / 待复查清单"
    lines = ["# " + title, "", BOUNDARY,
             "These are evidence-planning inputs; they do not judge the value of the entire research direction.",
             "", f"Runs: {value['previous']['run_id']} → {value['current']['run_id']}"]
    for item in value["pending"]:
        lines += ["", f"- {item.get('change_id', 'scope')} [{item['kind']}]: {item['question']}"]
        if "text" in item:
            lines += ["> " + item["text"], "Source: " + json.dumps(item.get("source"), ensure_ascii=False)]
        change = next((c for c in value["changes"] if c["change_id"] == item.get("change_id")), None)
        if change:
            for side in ("previous", "current"):
                for c in change[side]:
                    lines += [f"  {side} / {c['run_id']} / {c['claim_id']} / {c.get('source_section')} / line {c.get('source_line')}",
                              "  " + c["text"], f"  Current recorded status: {c['status']}; missing: {c.get('missing_evidence') or 'not specified'}"]
    if research:
        for change in value["changes"]:
            for c in change["current"]:
                if c.get("status") == "supported" and c.get("human_review_required") != "true":
                    continue
                lines += ["", f"## {c['claim_id']} / {c.get('source_section')} / {c.get('source_line')}",
                          c["text"], f"Current support: {c['status']}; {c.get('reason', '')}",
                          f"Missing evidence: {c.get('missing_evidence') or 'Not specified'}",
                          "Source locations: " + json.dumps(c["evidence"], ensure_ascii=False),
                          "Conditions for acquiring evidence: to be established by the researcher.",
                          "Researcher decision: obtain evidence, narrow the claim, or request specialist review."]
    return "\n".join(lines) + "\n"


def export_comparison(value: dict, out: Path, *, research: bool = False) -> Path:
    names = (*OUTPUTS, "research_questions.md") if research else OUTPUTS
    context = prepare_run_directory(out, project_id=value["current"].get("project_id") or "comparison",
                                    required_artifacts=names, workflow_type="claim_harness.compare",
                                    run_spec_sha256=digest(value))
    with context.transaction():
        (out / "audit_changes.json").write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (out / "audit_changes.md").write_text(render_comparison(value), encoding="utf-8")
        (out / "pending_questions.md").write_text(render_pending(value), encoding="utf-8")
        if research:
            (out / "research_questions.md").write_text(render_pending(value, research=True), encoding="utf-8")
    return out
