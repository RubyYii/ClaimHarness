# ClaimHarness Report Viewer Design

## Purpose

Task 7 adds a lightweight report-viewing surface for the existing ClaimHarness audit package. It is a presentation aid for demos and human review, not a new review engine and not a hosted web application.

The viewer should make the existing outputs easier to scan:

- `claim_table.csv`
- `evidence_map.json`
- `audit_report.md`
- `revision_suggestions.md`
- `agent_trace.jsonl`
- optional `llm_review.json`

## Chosen Approach

Use a generated static HTML file. The CLI command will be:

```bash
.venv\Scripts\python.exe -m claim_harness view --run outputs/oocyte_demo_run
```

By default it writes:

```text
outputs/oocyte_demo_run/index.html
```

This is the lowest-risk UI path for the repo because it keeps ClaimHarness CLI-first, works offline, avoids a dev server, avoids JavaScript frameworks, and can be opened directly in a browser.

## Alternatives Considered

1. Static generated HTML, recommended.
   - Pros: no new runtime dependency, portable, easy to test, simple to demo.
   - Cons: not interactive beyond browser-native scrolling and links.

2. Streamlit app.
   - Pros: faster to build rich controls.
   - Cons: requires a running server and adds a heavier UI dependency to a CLI-first repo.

3. Single-page JavaScript app.
   - Pros: could add filters and sorting.
   - Cons: adds frontend build complexity that does not serve the current demo.

## Information Architecture

The viewer should use a quiet technical dashboard layout:

- Top band: product name, audit directory, advisory limitation text.
- Summary strip: claims audited, evidence items, supported count, weak-or-worse count, trace events.
- Status breakdown: compact counts by verification status.
- Highest-risk claims: high-risk and overclaimed claims first.
- Claim table: claim ID, status, risk, type, text, evidence IDs, suggested revision.
- Evidence section: evidence ID, source, type, linked claims, text.
- Revision section: the existing revision suggestions rendered as readable text.
- Optional LLM section: only appears when `llm_review.json` exists and must be labeled advisory.
- Trace section: step, module, message, and compact event data.

## Visual Style

The UI should feel like an operational review tool:

- restrained palette with neutral background, white content bands, dark text, and status accents
- dense but readable tables
- no marketing hero
- no decorative gradients or floating cards
- no nested cards
- 8px or smaller radii
- responsive layout that remains readable on desktop and mobile

## Data Flow

`claim_harness.report_viewer` will:

1. Read the audit package directory.
2. Parse `claim_table.csv` with `csv.DictReader`.
3. Parse `evidence_map.json` with `json.loads`.
4. Parse `agent_trace.jsonl` line by line.
5. Read Markdown outputs as plain text and HTML-escape them.
6. Read optional `llm_review.json` when present.
7. Render a single self-contained HTML document with embedded CSS.

The viewer must not mutate audit data. It only writes the selected HTML output file.

## Error Handling

If required audit outputs are missing, the CLI should fail with a clear message naming the missing files. The renderer should use HTML escaping for all audit text so manuscript content cannot become executable HTML.

## Testing

Tests should cover:

- missing required files produce a clear error
- sample audit package renders an HTML file
- HTML contains escaped claim text, status counts, evidence IDs, trace events, and advisory language
- CLI `view` command writes `index.html`
- default mock demo still runs and does not require a UI server

## Scope Limits

The viewer will not:

- run a web server
- add Streamlit or frontend framework dependencies
- implement live filtering, sorting, or editing
- change claim statuses
- call any LLM provider
- claim clinical, publication, or factual correctness
