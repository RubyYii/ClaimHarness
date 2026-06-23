import csv
import html
import json
from collections import Counter
from pathlib import Path
from typing import Any


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
    payload = _load_audit_package(run_path)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(_render_html(payload, run_path), encoding="utf-8")
    return output_path


def _load_audit_package(run_dir: Path) -> dict[str, Any]:
    missing = [name for name in REQUIRED_OUTPUTS if not (run_dir / name).exists()]
    if missing:
        raise MissingAuditOutput(
            f"Missing required ClaimHarness output file(s): {', '.join(missing)}"
        )

    llm_review_path = run_dir / "llm_review.json"
    llm_review = None
    if llm_review_path.exists():
        llm_review = json.loads(llm_review_path.read_text(encoding="utf-8"))

    return {
        "claims": _read_claim_rows(run_dir / "claim_table.csv"),
        "evidence_map": json.loads((run_dir / "evidence_map.json").read_text(encoding="utf-8")),
        "audit_report": (run_dir / "audit_report.md").read_text(encoding="utf-8"),
        "revision_suggestions": (run_dir / "revision_suggestions.md").read_text(encoding="utf-8"),
        "trace": _read_trace(run_dir / "agent_trace.jsonl"),
        "llm_review": llm_review,
    }


def _read_claim_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _read_trace(path: Path) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
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
            f"<p>{_e(str(run_dir))}</p>",
            '<p class="notice">Advisory review surface only. ClaimHarness does not guarantee factual correctness, clinical validity, or publication readiness.</p>',
            "</div>",
            "</header>",
            '<main class="wrap">',
            '<section class="summary-grid" aria-label="Audit summary">',
            _metric("Claims audited", len(claims)),
            _metric("Evidence items", len(evidence)),
            _metric("Supported", status_counts.get("supported", 0)),
            _metric("Weak or worse", weak_or_worse),
            _metric("Trace events", len(trace)),
            "</section>",
            _render_status_breakdown(status_counts),
            _render_high_risk_claims(high_risk_claims),
            _render_claim_table(claims, payload["evidence_map"].get("claims", [])),
            _render_evidence_table(evidence),
            _render_markdown_block("Revision suggestions", payload["revision_suggestions"]),
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


def _metric(label: str, value: int) -> str:
    return f'<div class="metric"><span>{_e(label)}</span><strong>{value}</strong></div>'


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
        rows.append(
            f'<tr data-claim-row data-status="{_e(row.get("status", ""))}" data-risk="{_e(row.get("risk_level", ""))}">'
            f'<td class="mono">{_e(claim_id)}</td>'
            f'<td><span class="{_status_class(row.get("status", ""))}">{_e(row.get("status", ""))}</span></td>'
            f'<td>{_e(row.get("risk_level", ""))}</td>'
            f'<td>{_e(row.get("claim_type", ""))}</td>'
            f'<td class="mono">{_e(row.get("source_line", ""))}</td>'
            f'<td class="claim-text">{_e(row.get("text", ""))}</td>'
            f'<td class="mono">{_e(evidence_ids)}</td>'
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
        "<thead><tr><th>ID</th><th>Status</th><th>Risk</th><th>Type</th><th>Line</th><th>Claim</th><th>Evidence</th><th>Match reason</th><th>Suggested revision</th></tr></thead>"
        "<tbody>"
        + "".join(rows)
        + "</tbody></table></div></section>"
    )


def _render_evidence_table(evidence: list[dict[str, Any]]) -> str:
    rows = []
    for item in evidence:
        linked = ", ".join(item.get("linked_claim_ids", []))
        rows.append(
            "<tr>"
            f'<td class="mono">{_e(item.get("evidence_id", ""))}</td>'
            f'<td>{_e(item.get("source", ""))}</td>'
            f'<td>{_e(item.get("evidence_type", ""))}</td>'
            f'<td class="mono">{_e(linked)}</td>'
            f'<td>{_e(json.dumps(item.get("claim_link_reasons", {}), ensure_ascii=False))}</td>'
            f'<td class="claim-text">{_e(item.get("text", ""))}</td>'
            "</tr>"
        )
    return (
        '<section><h2>Evidence map</h2><div class="table-wrap"><table>'
        "<thead><tr><th>ID</th><th>Source</th><th>Type</th><th>Claims</th><th>Match reason</th><th>Evidence text</th></tr></thead>"
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


def _e(value: Any) -> str:
    return html.escape(str(value), quote=True)
