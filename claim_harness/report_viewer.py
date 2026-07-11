import csv
import html
import io
import json
import os
import uuid
from collections import Counter
from pathlib import Path
from typing import Any

from problem_bridge.project_lifecycle import (
    RUN_IDENTITY_NAME,
    ProjectLifecycleError,
    snapshot_completed_run,
)


REQUIRED_OUTPUTS = [
    "claim_table.csv",
    "evidence_map.json",
    "audit_report.md",
    "revision_suggestions.md",
    "agent_trace.jsonl",
]


class MissingAuditOutput(FileNotFoundError):
    pass


def render_report_viewer(run_dir: str | Path, out_file: str | Path | None = None) -> Path:
    run_path = Path(run_dir)
    output_path = Path(out_file) if out_file is not None else run_path / "index.html"
    _validate_viewer_output_path(run_path, output_path)
    payload = _load_audit_package(run_path)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    rendered = _render_html(payload, run_path)
    for _ in range(32):
        temporary = output_path.with_name(f".v-{uuid.uuid4().hex[:8]}")
        created = False
        try:
            with temporary.open("x", encoding="utf-8", newline="") as handle:
                created = True
                handle.write(rendered)
            os.replace(temporary, output_path)
            created = False
            break
        except FileExistsError:
            continue
        finally:
            if created:
                temporary.unlink(missing_ok=True)
    else:
        raise MissingAuditOutput("Could not allocate a short viewer temporary file.")
    return output_path


def _load_audit_package(run_dir: Path) -> dict[str, Any]:
    governed = (run_dir / RUN_IDENTITY_NAME).is_file()
    if governed:
        try:
            files = snapshot_completed_run(run_dir)
        except (OSError, ProjectLifecycleError, ValueError) as exc:
            raise MissingAuditOutput(
                f"Governed run failed lifecycle integrity validation: {exc}"
            ) from exc
    else:
        files = {
            path.name: path.read_bytes()
            for path in run_dir.iterdir()
            if path.is_file() and not path.is_symlink()
        }
    missing = [name for name in REQUIRED_OUTPUTS if name not in files]
    if missing:
        raise MissingAuditOutput(
            f"Missing required ClaimHarness output file(s): {', '.join(missing)}"
        )

    llm_review = (
        json.loads(files["llm_review.json"].decode("utf-8"))
        if "llm_review.json" in files
        else None
    )
    project_summary = (
        files["project_summary_log.md"].decode("utf-8")
        if "project_summary_log.md" in files
        else None
    )
    audit_diagnostics = (
        json.loads(files["audit_diagnostics.json"].decode("utf-8"))
        if "audit_diagnostics.json" in files
        else None
    )
    human_review_queue = (
        json.loads(files["human_review_queue.json"].decode("utf-8"))
        if "human_review_queue.json" in files
        else None
    )

    return {
        "claims": _read_claim_rows_text(files["claim_table.csv"].decode("utf-8")),
        "evidence_map": json.loads(files["evidence_map.json"].decode("utf-8")),
        "audit_report": files["audit_report.md"].decode("utf-8"),
        "revision_suggestions": files["revision_suggestions.md"].decode("utf-8"),
        "trace": _read_trace_text(files["agent_trace.jsonl"].decode("utf-8")),
        "llm_review": llm_review,
        "project_summary": project_summary,
        "audit_diagnostics": audit_diagnostics,
        "human_review_queue": human_review_queue,
        "integrity_status": (
            "Verified governed run: lifecycle identity and artifact hashes passed."
            if governed
            else "Unverified legacy package: no run_identity.json was present."
        ),
    }


def _validate_viewer_output_path(run_path: Path, output_path: Path) -> None:
    resolved_run = run_path.resolve()
    resolved_output = output_path.resolve()
    default_output = (run_path / "index.html").resolve()
    if resolved_output == default_output:
        return
    try:
        resolved_output.relative_to(resolved_run)
    except ValueError:
        return
    if resolved_output.exists():
        raise MissingAuditOutput(
            f"Refusing to overwrite an existing audit-package file: {output_path}"
        )


def _read_claim_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _read_claim_rows_text(text: str) -> list[dict[str, str]]:
    return [dict(row) for row in csv.DictReader(io.StringIO(text, newline=""))]


def _read_trace(path: Path) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            events.append(json.loads(line))
    return events


def _read_trace_text(text: str) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for line in text.splitlines():
        if line.strip():
            events.append(json.loads(line))
    return events


def _render_html(payload: dict[str, Any], run_dir: Path) -> str:
    claims = payload["claims"]
    evidence = payload["evidence_map"].get("evidence", [])
    trace = payload["trace"]
    status_counts = Counter(row.get("status", "unknown") for row in claims)
    weak_or_worse = sum(
        status_counts.get(status, 0)
        for status in ("weakly_supported", "unsupported", "overclaimed", "needs_human_review")
    )
    high_risk_claims = [
        row
        for row in claims
        if row.get("risk_level") == "high" or row.get("status") in {"overclaimed", "needs_human_review"}
    ]

    return "\n".join(
        [
            "<!doctype html>",
            '<html lang="en">',
            "<head>",
            '<meta charset="utf-8">',
            '<meta name="viewport" content="width=device-width, initial-scale=1">',
            "<title>ClaimHarness Report Viewer</title>",
            f"<style>{_css()}</style>",
            "</head>",
            "<body>",
            '<header class="topbar">',
            '<div class="wrap">',
            "<h1>ClaimHarness Report Viewer</h1>",
            f"<p>{_e(run_dir.name)}</p>",
            '<p class="notice">Advisory review surface only. ClaimHarness does not guarantee factual correctness, clinical validity, or publication readiness.</p>',
            "</div>",
            "</header>",
            '<main class="wrap">',
            _render_markdown_block("Integrity status", payload["integrity_status"]),
            '<section class="summary-grid" aria-label="Audit summary">',
            _metric("Claims audited", len(claims)),
            _metric("Evidence items", len(evidence)),
            _metric("Supported", status_counts.get("supported", 0)),
            _metric("Weak or worse", weak_or_worse),
            _metric("Trace events", len(trace)),
            "</section>",
            _render_status_breakdown(status_counts),
            _render_diagnostics(payload["audit_diagnostics"]),
            _render_human_review_queue(payload["human_review_queue"]),
            _render_high_risk_claims(high_risk_claims),
            _render_claim_table(claims, payload["evidence_map"].get("claims", [])),
            _render_evidence_table(evidence),
            _render_markdown_block("Revision suggestions", payload["revision_suggestions"]),
            (
                _render_markdown_block("Project summary log", payload["project_summary"])
                if payload["project_summary"] is not None
                else ""
            ),
            _render_llm_review(payload["llm_review"]),
            _render_trace(trace),
            "</main>",
            f"<script>{_script()}</script>",
            "</body>",
            "</html>",
        ]
    )


def _css() -> str:
    return """
:root {
  --bg: #f4f6f8;
  --ink: #18202a;
  --muted: #5f6b7a;
  --line: #d8dee6;
  --panel: #ffffff;
  --supported: #0f766e;
  --weak: #b7791f;
  --over: #b42318;
  --human: #6d28d9;
  --accent: #2557a7;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  background: var(--bg);
  color: var(--ink);
  font: 14px/1.5 system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}
.wrap { width: min(1180px, calc(100% - 32px)); margin: 0 auto; }
.topbar { background: #101820; color: #fff; border-bottom: 4px solid var(--accent); }
.topbar .wrap { padding: 24px 0 20px; }
h1 { margin: 0 0 6px; font-size: 26px; font-weight: 700; letter-spacing: 0; }
h2 { margin: 0 0 12px; font-size: 19px; letter-spacing: 0; }
h3 { margin: 0 0 8px; font-size: 15px; letter-spacing: 0; }
p { margin: 0 0 8px; }
.notice { color: #dce5ef; max-width: 860px; }
.boundary { color: var(--muted); border-left: 4px solid var(--weak); padding-left: 10px; }
main { padding: 20px 0 36px; }
section {
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 6px;
  margin: 0 0 16px;
  padding: 16px;
}
.summary-grid {
  display: grid;
  grid-template-columns: repeat(5, minmax(130px, 1fr));
  gap: 10px;
}
.metric {
  border-left: 4px solid var(--accent);
  background: #f9fafb;
  padding: 10px 12px;
  min-height: 72px;
}
.metric span { display: block; color: var(--muted); font-size: 12px; }
.metric strong { display: block; margin-top: 4px; font-size: 24px; }
.status-list { display: flex; flex-wrap: wrap; gap: 8px; }
.filter-bar { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 12px; }
.filter-button {
  border: 1px solid var(--line);
  border-radius: 6px;
  background: #fff;
  color: var(--ink);
  cursor: pointer;
  padding: 6px 10px;
  font: inherit;
}
.filter-button[aria-pressed="true"] { border-color: var(--accent); color: var(--accent); font-weight: 700; }
.status-pill {
  border: 1px solid var(--line);
  border-radius: 999px;
  padding: 5px 10px;
  background: #f9fafb;
}
.status-supported { color: var(--supported); font-weight: 700; }
.status-weakly_supported, .status-unsupported { color: var(--weak); font-weight: 700; }
.status-overclaimed { color: var(--over); font-weight: 700; }
.status-needs_human_review { color: var(--human); font-weight: 700; }
.table-wrap { overflow-x: auto; border: 1px solid var(--line); border-radius: 6px; }
table { width: 100%; border-collapse: collapse; min-width: 760px; background: #fff; }
th, td { border-bottom: 1px solid var(--line); padding: 8px 10px; text-align: left; vertical-align: top; }
th { background: #eef2f6; color: #27313d; font-size: 12px; text-transform: uppercase; }
tr:last-child td { border-bottom: 0; }
.claim-text { min-width: 300px; }
.mono { font-family: "Cascadia Mono", Consolas, monospace; font-size: 12px; }
.risk-list { display: grid; gap: 10px; }
.risk-item { border-left: 4px solid var(--over); padding: 10px 12px; background: #fff7f5; }
pre {
  margin: 0;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  background: #f9fafb;
  border: 1px solid var(--line);
  border-radius: 6px;
  padding: 12px;
}
.trace-data { color: var(--muted); }
@media (max-width: 760px) {
  .wrap { width: min(100% - 20px, 1180px); }
  h1 { font-size: 22px; }
  .summary-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  section { padding: 12px; }
}
"""


def _script() -> str:
    return """
const buttons = document.querySelectorAll('[data-filter]');
const rows = document.querySelectorAll('[data-claim-row]');
function visibleForFilter(row, filter) {
  const status = row.dataset.status;
  const risk = row.dataset.risk;
  if (filter === 'all') return true;
  if (filter === 'weak-or-worse') {
    return ['weakly_supported', 'unsupported', 'overclaimed', 'needs_human_review'].includes(status);
  }
  if (filter === 'high-risk') return risk === 'high';
  return status === filter;
}
buttons.forEach((button) => {
  button.addEventListener('click', () => {
    const filter = button.dataset.filter;
    buttons.forEach((item) => item.setAttribute('aria-pressed', String(item === button)));
    rows.forEach((row) => {
      row.hidden = !visibleForFilter(row, filter);
    });
  });
});
"""


def _metric(label: str, value: int | str) -> str:
    return f'<div class="metric"><span>{_e(label)}</span><strong>{_e(value)}</strong></div>'


def _render_status_breakdown(status_counts: Counter[str]) -> str:
    pills = [
        f'<span class="status-pill"><span class="{_status_class(status)}">{_e(status)}</span>: {count}</span>'
        for status, count in sorted(status_counts.items())
    ]
    return (
        '<section><h2>Status breakdown</h2><div class="status-list">'
        + "".join(pills)
        + "</div></section>"
    )


def _render_diagnostics(diagnostics: dict[str, Any] | None) -> str:
    if diagnostics is None:
        return ""
    metrics = diagnostics.get("metrics", {})
    cards = [
        ("Any link coverage", "any_link_coverage"),
        ("Support relation", "support_relation_coverage"),
        ("No support relation", "no_support_relation"),
        ("Needs human review", "needs_human_review"),
        ("Contradiction claims", "contradiction_claims"),
    ]
    rendered_cards = "".join(
        _metric(label, _format_ratio(metrics.get(key, {}))) for label, key in cards
    )
    gaps = diagnostics.get("requirement_gap_counts", {})
    gap_text = ", ".join(f"{key}: {value}" for key, value in sorted(gaps.items())) or "none"
    return (
        '<section><h2>Structural diagnostics</h2>'
        f'<p class="boundary">{_e(diagnostics.get("boundary", ""))}</p>'
        f'<div class="summary-grid">{rendered_cards}</div>'
        f'<p><strong>Missing requirement counts:</strong> {_e(gap_text)}</p>'
        "</section>"
    )


def _render_human_review_queue(queue: dict[str, Any] | None) -> str:
    if queue is None:
        return ""
    items = queue.get("items", [])
    if not items:
        body = "<p>No pending human-review work items in this run.</p>"
    else:
        rows = []
        for item in items:
            rows.append(
                "<tr>"
                f'<td class="mono">{_e(item.get("review_item_id", ""))}</td>'
                f'<td class="mono">{_e(item.get("claim_id", ""))}</td>'
                f'<td>{_e(item.get("required_role", ""))}</td>'
                f'<td>{_e(item.get("verification_status", ""))}</td>'
                f'<td>{_e(item.get("risk_level", ""))}</td>'
                f'<td>{_e(", ".join(item.get("trigger_codes", [])))}</td>'
                f'<td>{_e(item.get("state", "pending"))}</td>'
                "</tr>"
            )
        body = (
            '<div class="table-wrap"><table>'
            "<thead><tr><th>Review item</th><th>Claim</th><th>Required role</th>"
            "<th>Deterministic status</th><th>Risk</th><th>Triggers</th><th>State</th></tr></thead>"
            "<tbody>" + "".join(rows) + "</tbody></table></div>"
        )
    return (
        '<section><h2>Pending human review</h2>'
        f'<p class="boundary">{_e(queue.get("boundary", ""))}</p>'
        f'<p>{_e(queue.get("role_boundary", ""))}</p>'
        + body
        + "</section>"
    )


def _render_high_risk_claims(claims: list[dict[str, str]]) -> str:
    if not claims:
        return "<section><h2>Highest-risk claims</h2><p>No high-risk claims in this audit package.</p></section>"
    items = []
    for row in claims:
        items.append(
            '<div class="risk-item">'
            f'<h3>{_e(row.get("claim_id", ""))}: <span class="{_status_class(row.get("status", ""))}">{_e(row.get("status", ""))}</span></h3>'
            f'<p>{_e(row.get("text", ""))}</p>'
            f'<p class="mono">risk={_e(row.get("risk_level", ""))} source={_e(row.get("source_section", ""))}</p>'
            "</div>"
        )
    return '<section><h2>Highest-risk claims</h2><div class="risk-list">' + "".join(items) + "</div></section>"


def _render_claim_table(claims: list[dict[str, str]], evidence_links: list[dict[str, Any]]) -> str:
    evidence_by_claim = {
        item.get("claim_id", ""): item.get("evidence_ids", [])
        for item in evidence_links
    }
    reasons_by_claim = {
        item.get("claim_id", ""): item.get("evidence_links", [])
        for item in evidence_links
    }
    rows = []
    for row in claims:
        claim_id = row.get("claim_id", "")
        evidence_ids = ", ".join(evidence_by_claim.get(claim_id, []))
        match_reasons = "; ".join(
            f'{link.get("evidence_id", "")}: {link.get("match_reason", "linked by retrieval rule")}'
            for link in reasons_by_claim.get(claim_id, [])
        )
        if not match_reasons and evidence_ids:
            match_reasons = "Linked by retrieval rule"
        locations = "; ".join(
            f'{link.get("evidence_id", "")}: {_format_locator_dict(link.get("locator"))}'
            for link in reasons_by_claim.get(claim_id, [])
        )
        rows.append(
            f'<tr data-claim-row data-status="{_e(row.get("status", ""))}" data-risk="{_e(row.get("risk_level", ""))}">'
            f'<td class="mono">{_e(claim_id)}</td>'
            f'<td><span class="{_status_class(row.get("status", ""))}">{_e(row.get("status", ""))}</span></td>'
            f'<td>{_e(row.get("risk_level", ""))}</td>'
            f'<td>{_e(row.get("claim_type", ""))}</td>'
            f'<td class="mono">{_e(row.get("source_line", ""))}</td>'
            f'<td class="claim-text">{_e(row.get("text", ""))}</td>'
            f'<td class="mono">{_e(evidence_ids)}</td>'
            f'<td>{_e(locations)}</td>'
            f'<td>{_e(match_reasons)}</td>'
            f'<td>{_e(row.get("suggested_revision", ""))}</td>'
            "</tr>"
        )
    return (
        '<section><h2>Claim table</h2>'
        '<div class="filter-bar" aria-label="Claim filters">'
        '<button class="filter-button" type="button" data-filter="all" aria-pressed="true">All</button>'
        '<button class="filter-button" type="button" data-filter="weak-or-worse" aria-pressed="false">Weak or worse</button>'
        '<button class="filter-button" type="button" data-filter="high-risk" aria-pressed="false">High risk</button>'
        '<button class="filter-button" type="button" data-filter="supported" aria-pressed="false">Supported</button>'
        '<button class="filter-button" type="button" data-filter="overclaimed" aria-pressed="false">Overclaimed</button>'
        '</div><div class="table-wrap"><table>'
        "<thead><tr><th>ID</th><th>Status</th><th>Risk</th><th>Type</th><th>Line</th><th>Claim</th><th>Evidence</th><th>Location</th><th>Match reason</th><th>Suggested revision</th></tr></thead>"
        "<tbody>"
        + "".join(rows)
        + "</tbody></table></div></section>"
    )


def _render_evidence_table(evidence: list[dict[str, Any]]) -> str:
    rows = []
    for item in evidence:
        linked = ", ".join(item.get("linked_claim_ids", []))
        location = _format_locator_dict(item.get("locator"), item.get("source", ""))
        rows.append(
            "<tr>"
            f'<td class="mono">{_e(item.get("evidence_id", ""))}</td>'
            f'<td>{_e(item.get("source", ""))}</td>'
            f'<td>{_e(item.get("evidence_type", ""))}</td>'
            f'<td>{_e(location)}</td>'
            f'<td class="mono">{_e(linked)}</td>'
            f'<td>{_e(json.dumps(item.get("claim_link_reasons", {}), ensure_ascii=False))}</td>'
            f'<td class="claim-text">{_e(item.get("text", ""))}</td>'
            "</tr>"
        )
    return (
        '<section><h2>Evidence map</h2><div class="table-wrap"><table>'
        "<thead><tr><th>ID</th><th>Source</th><th>Type</th><th>Base location</th><th>Claims</th><th>Match reason</th><th>Evidence text</th></tr></thead>"
        "<tbody>"
        + "".join(rows)
        + "</tbody></table></div></section>"
    )


def _render_markdown_block(title: str, text: str) -> str:
    return f"<section><h2>{_e(title)}</h2><pre>{_e(text)}</pre></section>"


def _render_llm_review(review: dict[str, Any] | None) -> str:
    if review is None:
        return ""
    return (
        "<section>"
        "<h2>Advisory LLM review</h2>"
        "<p>This optional section is advisory only and does not override deterministic verification.</p>"
        f"<pre>{_e(json.dumps(review, indent=2, ensure_ascii=False))}</pre>"
        "</section>"
    )


def _render_trace(trace: list[dict[str, Any]]) -> str:
    rows = []
    for event in trace:
        rows.append(
            "<tr>"
            f'<td class="mono">{_e(str(event.get("step", "")))}</td>'
            f'<td>{_e(event.get("module", ""))}</td>'
            f'<td>{_e(event.get("message", ""))}</td>'
            f'<td class="trace-data mono">{_e(json.dumps(event.get("data", {}), ensure_ascii=False))}</td>'
            "</tr>"
        )
    return (
        '<section><h2>Audit trace</h2><div class="table-wrap"><table>'
        "<thead><tr><th>Step</th><th>Module</th><th>Message</th><th>Data</th></tr></thead>"
        "<tbody>"
        + "".join(rows)
        + "</tbody></table></div></section>"
    )


def _status_class(status: str) -> str:
    safe = "".join(ch if ch.isalnum() or ch == "_" else "_" for ch in status)
    return f"status-{safe}"


def _format_ratio(metric: dict[str, Any]) -> str:
    numerator = metric.get("numerator", 0)
    denominator = metric.get("denominator", 0)
    rate = metric.get("rate")
    if rate is None:
        return f"{numerator}/{denominator} (n/a)"
    return f"{numerator}/{denominator} ({float(rate) * 100:.1f}%)"


def _format_locator_dict(
    locator: dict[str, Any] | None,
    fallback: str = "location unavailable",
) -> str:
    if not locator:
        return fallback or "location unavailable"
    parts = [locator.get("source_file") or locator.get("source_name") or fallback]
    if locator.get("page_number") is not None:
        parts.append(f'page {locator["page_number"]}')
    if locator.get("line") is not None:
        parts.append(f'line {locator["line"]}')
    if locator.get("row") is not None:
        parts.append(f'data row {locator["row"]}')
    cells = locator.get("cells", [])
    if cells:
        parts.append(
            "cells "
            + ", ".join(
                f'{cell.get("column", "")}={cell.get("value", "")}'
                + (f' ({cell.get("cell")})' if cell.get("cell") else "")
                for cell in cells
            )
        )
    return ", ".join(str(part) for part in parts if part)


def _e(value: Any) -> str:
    return html.escape(str(value), quote=True)
