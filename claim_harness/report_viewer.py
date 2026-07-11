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
            '<body id="top">',
            '<a class="skip-link" href="#main-content">Skip to report</a>',
            '<header class="topbar">',
            '<div class="wrap">',
            "<h1>ClaimHarness Report Viewer</h1>",
            f"<p>{_e(run_dir.name)}</p>",
            '<p class="notice">Advisory review surface only. ClaimHarness does not guarantee factual correctness, clinical validity, or publication readiness.</p>',
            "</div>",
            "</header>",
            _render_quick_nav(payload),
            '<div id="copy-status" class="sr-status" role="status" aria-live="polite"></div>',
            '<main id="main-content" class="wrap" tabindex="-1">',
            _render_markdown_block(
                "Integrity status", payload["integrity_status"], section_id="integrity"
            ),
            '<section id="overview" class="summary-grid anchor-target" aria-label="Audit summary">',
            _metric("Claims audited", len(claims)),
            _metric("Evidence items", len(evidence)),
            _metric("Supported", status_counts.get("supported", 0)),
            _metric("Weak or worse", weak_or_worse),
            _metric("Trace events", len(trace)),
            "</section>",
            _render_status_breakdown(status_counts),
            _render_diagnostics(payload["audit_diagnostics"]),
            _render_human_review_queue(
                payload["human_review_queue"],
                {row.get("claim_id", "") for row in claims},
            ),
            _render_high_risk_claims(high_risk_claims),
            _render_claim_table(claims, payload["evidence_map"].get("claims", [])),
            _render_evidence_table(evidence),
            _render_markdown_block(
                "Revision suggestions",
                payload["revision_suggestions"],
                section_id="revisions",
            ),
            (
                _render_markdown_block(
                    "Project summary log",
                    payload["project_summary"],
                    section_id="project-summary",
                    collapsible=True,
                )
                if payload["project_summary"] is not None
                else ""
            ),
            _render_llm_review(payload["llm_review"]),
            _render_trace(trace),
            "</main>",
            '<a class="back-to-top" href="#top" aria-label="Back to top">↑ Top</a>',
            f"<script>{_script()}</script>",
            "</body>",
            "</html>",
        ]
    )


def _render_quick_nav(payload: dict[str, Any]) -> str:
    links = [
        ("Overview", "overview"),
        ("Priority", "priority"),
        ("Claims", "claims"),
        ("Evidence", "evidence"),
        ("Revisions", "revisions"),
        ("Trace", "trace"),
    ]
    if payload.get("audit_diagnostics") is not None:
        links.insert(1, ("Diagnostics", "diagnostics"))
    if payload.get("human_review_queue") is not None:
        insert_at = 2 if payload.get("audit_diagnostics") is not None else 1
        links.insert(insert_at, ("Review queue", "review-queue"))
    rendered = "".join(
        f'<a href="#{_e(section_id)}">{_e(label)}</a>' for label, section_id in links
    )
    return (
        '<nav class="quick-nav" aria-label="Report sections"><div class="wrap">'
        + rendered
        + "</div></nav>"
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
  --weak: #8a5a12;
  --over: #b42318;
  --human: #6d28d9;
  --accent: #2557a7;
}
* { box-sizing: border-box; }
html { scroll-behavior: smooth; }
body {
  margin: 0;
  overflow-x: hidden;
  background: var(--bg);
  color: var(--ink);
  font: 14px/1.5 system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}
.wrap { width: min(1180px, calc(100% - 32px)); margin: 0 auto; }
.skip-link {
  position: fixed;
  left: 12px;
  top: 8px;
  z-index: 100;
  transform: translateY(-160%);
  background: #fff;
  color: var(--accent);
  border: 2px solid var(--accent);
  border-radius: 6px;
  padding: 8px 12px;
}
.skip-link:focus { transform: translateY(0); }
.topbar { background: #101820; color: #fff; border-bottom: 4px solid var(--accent); }
.topbar .wrap { padding: 24px 0 20px; }
h1 { margin: 0 0 6px; font-size: 26px; font-weight: 700; letter-spacing: 0; }
h2 { margin: 0 0 12px; font-size: 19px; letter-spacing: 0; }
h3 { margin: 0 0 8px; font-size: 15px; letter-spacing: 0; }
p { margin: 0 0 8px; }
.notice { color: #dce5ef; max-width: 860px; }
.boundary { color: var(--muted); border-left: 4px solid var(--weak); padding-left: 10px; }
.quick-nav {
  position: sticky;
  top: 0;
  z-index: 30;
  background: rgba(255, 255, 255, .97);
  border-bottom: 1px solid var(--line);
  box-shadow: 0 4px 14px rgba(24, 32, 42, .06);
}
.quick-nav .wrap { display: flex; gap: 4px; overflow-x: auto; padding: 8px 0; }
.quick-nav a {
  flex: 0 0 auto;
  color: var(--ink);
  text-decoration: none;
  border-radius: 6px;
  padding: 6px 9px;
}
.quick-nav a:hover { background: #eef4fb; color: var(--accent); }
.anchor-target, tr[id] { scroll-margin-top: 68px; }
.sr-status {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}
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
.claim-tools {
  display: grid;
  grid-template-columns: minmax(220px, 1fr) auto;
  gap: 12px;
  align-items: end;
  margin-bottom: 12px;
}
.search-field { display: grid; gap: 5px; font-weight: 700; }
.search-field input {
  width: 100%;
  border: 1px solid var(--line);
  border-radius: 6px;
  padding: 9px 10px;
  color: var(--ink);
  background: #fff;
  font: inherit;
}
.result-count { color: var(--muted); font-size: 13px; padding-bottom: 9px; }
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
button:focus-visible, a:focus-visible, input:focus-visible, summary:focus-visible, .table-wrap:focus-visible {
  outline: 3px solid var(--accent);
  outline-offset: 2px;
}
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
th { position: sticky; top: 0; z-index: 2; background: #eef2f6; color: #27313d; font-size: 12px; text-transform: uppercase; }
caption { text-align: left; color: var(--muted); padding: 8px 10px; font-size: 12px; }
tr:last-child td { border-bottom: 0; }
.claim-table { min-width: 720px; }
.claim-table th:first-child, .claim-table td:first-child {
  position: sticky;
  left: 0;
  z-index: 3;
  background: #fff;
}
.claim-table th:first-child { background: #eef2f6; z-index: 4; }
.claim-text { min-width: 300px; }
.row-details summary, .advanced-section > summary { cursor: pointer; color: var(--accent); font-weight: 700; }
.row-details dl { display: grid; grid-template-columns: minmax(110px, 160px) 1fr; gap: 6px 12px; margin: 10px 0 0; }
.row-details dt { font-weight: 700; color: var(--muted); }
.row-details dd { margin: 0; overflow-wrap: anywhere; }
.review-list { display: grid; gap: 10px; }
.review-card { border: 1px solid var(--line); border-left: 4px solid var(--human); border-radius: 6px; padding: 12px; background: #fbf9ff; }
.review-card h3 { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
.review-meta { display: flex; flex-wrap: wrap; gap: 6px; margin: 8px 0; }
.review-meta span { border: 1px solid var(--line); border-radius: 999px; background: #fff; padding: 3px 8px; font-size: 12px; }
.review-actions { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 10px; }
.review-actions a, .copy-button { border: 1px solid var(--line); border-radius: 6px; background: #fff; color: var(--accent); padding: 6px 9px; text-decoration: none; font: inherit; cursor: pointer; }
.advanced-section > summary { display: flex; justify-content: space-between; gap: 12px; }
.advanced-section[open] > summary { margin-bottom: 12px; }
.empty-state { color: var(--muted); border: 1px dashed var(--line); border-radius: 6px; padding: 12px; }
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
.back-to-top {
  position: fixed;
  right: 18px;
  bottom: 18px;
  z-index: 20;
  background: var(--accent);
  color: #fff;
  text-decoration: none;
  border-radius: 999px;
  padding: 9px 12px;
  box-shadow: 0 6px 18px rgba(37, 87, 167, .24);
}
@media (max-width: 760px) {
  .wrap { width: min(100% - 20px, 1180px); }
  h1 { font-size: 22px; }
  .summary-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .claim-tools { grid-template-columns: 1fr; gap: 4px; }
  .result-count { padding-bottom: 4px; }
  .row-details dl { grid-template-columns: 1fr; gap: 3px; }
  .row-details dd { margin-bottom: 7px; }
  .quick-nav .wrap { width: calc(100% - 20px); }
  .back-to-top { right: 10px; bottom: 10px; }
  section { padding: 12px; }
}
@media (prefers-reduced-motion: reduce) { html { scroll-behavior: auto; } }
"""


def _script() -> str:
    return """
const buttons = document.querySelectorAll('[data-filter]');
const rows = document.querySelectorAll('[data-claim-row]');
const search = document.getElementById('claim-search');
const resultCount = document.getElementById('claim-results');
const emptyState = document.getElementById('claim-empty');
let activeFilter = 'all';
function visibleForFilter(row, filter) {
  const status = row.dataset.status;
  const risk = row.dataset.risk;
  if (filter === 'all') return true;
  if (filter === 'needs-action') return status !== 'supported';
  if (filter === 'priority-review') return row.dataset.priority === 'true';
  return status === filter;
}
function updateClaims() {
  const query = search ? search.value.trim().toLocaleLowerCase() : '';
  let visible = 0;
  rows.forEach((row) => {
    const matchesFilter = visibleForFilter(row, activeFilter);
    const matchesSearch = !query || (row.dataset.search || '').toLocaleLowerCase().includes(query);
    const show = matchesFilter && matchesSearch;
    row.hidden = !show;
    if (show) visible += 1;
  });
  if (resultCount) resultCount.textContent = `Showing ${visible} of ${rows.length} claims`;
  if (emptyState) emptyState.hidden = visible !== 0;
}
buttons.forEach((button) => {
  button.addEventListener('click', () => {
    activeFilter = button.dataset.filter;
    buttons.forEach((item) => item.setAttribute('aria-pressed', String(item === button)));
    updateClaims();
  });
});
if (search) search.addEventListener('input', updateClaims);

function fallbackCopy(text) {
  const area = document.createElement('textarea');
  area.value = text;
  area.setAttribute('readonly', '');
  area.style.position = 'fixed';
  area.style.opacity = '0';
  document.body.appendChild(area);
  area.select();
  const copied = document.execCommand('copy');
  area.remove();
  return copied;
}
async function copyReviewText(text) {
  if (navigator.clipboard && navigator.clipboard.writeText) {
    try {
      await navigator.clipboard.writeText(text);
      return true;
    } catch (_clipboardError) {
      // Local file viewers may block the Clipboard API; try the legacy path.
    }
  }
  try {
    return fallbackCopy(text);
  } catch (_fallbackError) {
    return false;
  }
}
document.querySelectorAll('[data-copy-text]').forEach((button) => {
  button.addEventListener('click', async () => {
    const text = button.dataset.copyText || '';
    const copied = await copyReviewText(text);
    const status = document.getElementById('copy-status');
    if (copied) {
      if (status) status.textContent = `Copied ${button.dataset.copyLabel || 'review item'}.`;
      button.textContent = 'Copied';
    } else {
      if (status) status.textContent = 'Copy failed; select the review text manually.';
      button.textContent = 'Copy failed';
    }
  });
});
updateClaims();
"""


def _metric(label: str, value: int | str) -> str:
    return f'<div class="metric"><span>{_e(label)}</span><strong>{_e(value)}</strong></div>'


def _render_status_breakdown(status_counts: Counter[str]) -> str:
    pills = [
        f'<span class="status-pill"><span class="{_status_class(status)}">{_e(_humanize_status(status))}</span>: {count}</span>'
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
        '<section id="diagnostics" class="anchor-target"><h2>Structural diagnostics</h2>'
        f'<p class="boundary">{_e(diagnostics.get("boundary", ""))}</p>'
        f'<div class="summary-grid">{rendered_cards}</div>'
        f'<p><strong>Missing requirement counts:</strong> {_e(gap_text)}</p>'
        "</section>"
    )


def _render_human_review_queue(
    queue: dict[str, Any] | None,
    known_claim_ids: set[str],
) -> str:
    if queue is None:
        return ""
    items = queue.get("items", [])
    if not items:
        body = "<p>No pending human-review work items in this run.</p>"
    else:
        cards = []
        for item in items:
            claim_id = str(item.get("claim_id", ""))
            review_id = str(item.get("review_item_id", ""))
            claim_reference = (
                f'<a href="#{_claim_anchor(claim_id)}">{_e(claim_id)}</a>'
                if claim_id in known_claim_ids
                else f'<span class="mono">{_e(claim_id)}</span>'
            )
            support_ids = item.get("candidate_supporting_evidence_ids", [])
            contradiction_ids = item.get("candidate_contradicting_evidence_ids", [])
            copy_text = "\n".join(
                [
                    f"Review item: {review_id}",
                    f"Claim: {claim_id} — {item.get('claim_text', '')}",
                    f"Required role: {item.get('required_role', '')}",
                    f"Deterministic status: {item.get('verification_status', '')}",
                    f"Risk: {item.get('risk_level', '')}",
                    f"Candidate evidence: {', '.join(support_ids) or 'none'}",
                    f"Contradictions: {', '.join(contradiction_ids) or 'none'}",
                ]
            )
            cards.append(
                '<article class="review-card">'
                f'<h3><span class="mono">{_e(review_id)}</span> · claim {claim_reference}</h3>'
                f'<p>{_e(item.get("claim_text", ""))}</p>'
                '<div class="review-meta">'
                f'<span>role: {_e(item.get("required_role", ""))}</span>'
                f'<span>status: {_e(_humanize_status(str(item.get("verification_status", ""))))}</span>'
                f'<span>risk: {_e(item.get("risk_level", ""))}</span>'
                f'<span>state: {_e(item.get("state", "pending"))}</span>'
                "</div>"
                '<details><summary>Triggers and candidate evidence</summary>'
                f'<p><strong>Triggers:</strong> {_e(", ".join(item.get("trigger_codes", [])) or "none")}</p>'
                f'<p><strong>Supporting candidates:</strong> {_e(", ".join(support_ids) or "none")}</p>'
                f'<p><strong>Contradictions:</strong> {_e(", ".join(contradiction_ids) or "none")}</p>'
                "</details>"
                '<div class="review-actions">'
                + (
                    f'<a href="#{_claim_anchor(claim_id)}">Review claim</a>'
                    if claim_id in known_claim_ids
                    else ""
                )
                + f'<button class="copy-button" type="button" data-copy-label="{_e(review_id)}" data-copy-text="{_e(copy_text)}">Copy review brief</button>'
                + "</div></article>"
            )
        body = '<div class="review-list">' + "".join(cards) + "</div>"
    return (
        '<section id="review-queue" class="anchor-target"><h2>Pending human review</h2>'
        f'<p class="boundary">{_e(queue.get("boundary", ""))}</p>'
        f'<p>{_e(queue.get("role_boundary", ""))}</p>'
        + body
        + "</section>"
    )


def _render_high_risk_claims(claims: list[dict[str, str]]) -> str:
    if not claims:
        return '<section id="priority" class="anchor-target"><h2>Priority review claims</h2><p>No priority-review claims in this audit package.</p></section>'
    items = []
    for row in claims:
        items.append(
            '<div class="risk-item">'
            f'<h3>{_e(row.get("claim_id", ""))}: <span class="{_status_class(row.get("status", ""))}">{_e(_humanize_status(row.get("status", "")))}</span></h3>'
            f'<p>{_e(row.get("text", ""))}</p>'
            f'<p class="mono">risk={_e(row.get("risk_level", ""))} source={_e(row.get("source_section", ""))}</p>'
            "</div>"
        )
    return '<section id="priority" class="anchor-target"><h2>Priority review claims</h2><div class="risk-list">' + "".join(items) + "</div></section>"


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
        linked_ids = evidence_by_claim.get(claim_id, [])
        evidence_ids = ", ".join(linked_ids)
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
        status = row.get("status", "")
        risk = row.get("risk_level", "")
        priority = risk == "high" or status in {"overclaimed", "needs_human_review"}
        search_text = " ".join(
            [
                claim_id,
                status,
                risk,
                row.get("claim_type", ""),
                row.get("text", ""),
                evidence_ids,
                locations,
                match_reasons,
                row.get("suggested_revision", ""),
            ]
        )
        details = (
            '<details class="row-details"><summary>Review evidence and action</summary><dl>'
            f'<dt>Type and source</dt><dd>{_e(row.get("claim_type", ""))} · '
            f'{_e(row.get("source_section", ""))}, line {_e(row.get("source_line", "unknown") or "unknown")}</dd>'
            f'<dt>Evidence IDs</dt><dd class="mono">{_e(evidence_ids or "none")}</dd>'
            f'<dt>Location</dt><dd>{_e(locations or "location unavailable")}</dd>'
            f'<dt>Match reason</dt><dd>{_e(match_reasons or "no linked evidence")}</dd>'
            f'<dt>Missing evidence</dt><dd>{_e(row.get("missing_evidence", "") or "none")}</dd>'
            f'<dt>Contradictions</dt><dd class="mono">{_e(row.get("contradicting_evidence_ids", "") or "none")}</dd>'
            f'<dt>Suggested revision</dt><dd>{_e(row.get("suggested_revision", ""))}</dd>'
            "</dl></details>"
        )
        rows.append(
            f'<tr id="{_claim_anchor(claim_id)}" data-claim-row data-status="{_e(status)}" '
            f'data-risk="{_e(risk)}" data-priority="{str(priority).lower()}" data-search="{_e(search_text)}">'
            f'<td class="mono">{_e(claim_id)}</td>'
            f'<td><span class="{_status_class(status)}">{_e(_humanize_status(status))}</span></td>'
            f'<td>{_e(risk)}</td>'
            f'<td class="claim-text">{_e(row.get("text", ""))}</td>'
            f'<td><span title="{_e(evidence_ids or "No linked evidence")}">{len(linked_ids)} linked</span></td>'
            f'<td>{details}</td>'
            "</tr>"
        )
    return (
        '<section id="claims" class="anchor-target"><h2 id="claims-title">Claim review</h2>'
        '<div class="claim-tools"><label class="search-field" for="claim-search">Search claims'
        '<input id="claim-search" type="search" placeholder="Claim ID, text, evidence, status…" aria-controls="claim-table-body">'
        '</label><span id="claim-results" class="result-count" role="status" aria-live="polite">'
        f'Showing {len(claims)} of {len(claims)} claims</span></div>'
        '<div class="filter-bar" role="group" aria-label="Claim filters">'
        '<button class="filter-button" type="button" data-filter="all" aria-controls="claim-table-body" aria-pressed="true">All</button>'
        '<button class="filter-button" type="button" data-filter="needs-action" aria-controls="claim-table-body" aria-pressed="false">Needs action</button>'
        '<button class="filter-button" type="button" data-filter="priority-review" aria-controls="claim-table-body" aria-pressed="false">Priority review</button>'
        '<button class="filter-button" type="button" data-filter="needs_human_review" aria-controls="claim-table-body" aria-pressed="false">Needs human review</button>'
        '<button class="filter-button" type="button" data-filter="unsupported" aria-controls="claim-table-body" aria-pressed="false">Unsupported</button>'
        '<button class="filter-button" type="button" data-filter="weakly_supported" aria-controls="claim-table-body" aria-pressed="false">Weak support</button>'
        '<button class="filter-button" type="button" data-filter="supported" aria-controls="claim-table-body" aria-pressed="false">Supported</button>'
        '<button class="filter-button" type="button" data-filter="overclaimed" aria-controls="claim-table-body" aria-pressed="false">Overclaimed</button>'
        '</div><div class="table-wrap" role="region" aria-labelledby="claims-title" tabindex="0"><table class="claim-table">'
        '<caption>Core claim information. Expand each row for evidence locations, match reasons, and revision guidance.</caption>'
        '<thead><tr><th scope="col">ID</th><th scope="col">Status</th><th scope="col">Risk</th><th scope="col">Claim</th><th scope="col">Evidence</th><th scope="col">Details</th></tr></thead>'
        '<tbody id="claim-table-body">'
        + "".join(rows)
        + '</tbody></table></div><p id="claim-empty" class="empty-state" hidden>No claims match the current search and filter.</p></section>'
    )


def _render_evidence_table(evidence: list[dict[str, Any]]) -> str:
    if not evidence:
        return '<section id="evidence" class="anchor-target"><h2>Evidence map</h2><p class="empty-state">No evidence items were collected.</p></section>'
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
        '<section id="evidence" class="anchor-target"><details class="advanced-section">'
        f'<summary><span id="evidence-title">Evidence map</span><span>{len(evidence)} items · expand</span></summary>'
        '<div class="table-wrap" role="region" aria-labelledby="evidence-title" tabindex="0"><table>'
        '<caption>All collected evidence items and their base locations.</caption>'
        '<thead><tr><th scope="col">ID</th><th scope="col">Source</th><th scope="col">Type</th><th scope="col">Base location</th><th scope="col">Claims</th><th scope="col">Match reason</th><th scope="col">Evidence text</th></tr></thead>'
        "<tbody>"
        + "".join(rows)
        + "</tbody></table></div></details></section>"
    )


def _render_markdown_block(
    title: str,
    text: str,
    *,
    section_id: str | None = None,
    collapsible: bool = False,
) -> str:
    id_attr = f' id="{_e(section_id)}"' if section_id else ""
    css_class = ' class="anchor-target"' if section_id else ""
    if collapsible:
        return (
            f"<section{id_attr}{css_class}><details class=\"advanced-section\">"
            f"<summary>{_e(title)}</summary><pre>{_e(text)}</pre></details></section>"
        )
    return f"<section{id_attr}{css_class}><h2>{_e(title)}</h2><pre>{_e(text)}</pre></section>"


def _render_llm_review(review: dict[str, Any] | None) -> str:
    if review is None:
        return ""
    return (
        '<section id="llm-review" class="anchor-target"><details class="advanced-section">'
        "<summary>Advisory LLM review</summary>"
        "<p>This optional section is advisory only and does not override deterministic verification.</p>"
        f"<pre>{_e(json.dumps(review, indent=2, ensure_ascii=False))}</pre>"
        "</details></section>"
    )


def _render_trace(trace: list[dict[str, Any]]) -> str:
    if not trace:
        return '<section id="trace" class="anchor-target"><h2>Audit trace</h2><p class="empty-state">No trace events were recorded.</p></section>'
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
        '<section id="trace" class="anchor-target"><details class="advanced-section">'
        f'<summary><span id="trace-title">Audit trace</span><span>{len(trace)} events · expand</span></summary>'
        '<div class="table-wrap" role="region" aria-labelledby="trace-title" tabindex="0"><table>'
        '<caption>Ordered deterministic audit events.</caption>'
        '<thead><tr><th scope="col">Step</th><th scope="col">Module</th><th scope="col">Message</th><th scope="col">Data</th></tr></thead>'
        "<tbody>"
        + "".join(rows)
        + "</tbody></table></div></details></section>"
    )


def _status_class(status: str) -> str:
    safe = "".join(ch if ch.isalnum() or ch == "_" else "_" for ch in status)
    return f"status-{safe}"


def _humanize_status(status: str) -> str:
    return status.replace("_", " ").strip().title() or "Unknown"


def _claim_anchor(claim_id: str) -> str:
    safe = "".join(
        char if char.isalnum() or char in {"_", "-"} else "-"
        for char in str(claim_id)
    ).strip("-")
    return f"claim-{safe or 'unknown'}"


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
