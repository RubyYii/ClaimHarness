# ClaimHarness Architecture

ClaimHarness is a CLI-first Agent Harness for scientific claim-evidence auditing. It keeps the first implementation small, deterministic, and auditable.

## Pipeline

```mermaid
flowchart TD
    A["Task Spec"] --> B["Input Loader"]
    B --> C["Context Manager"]
    C --> D["Claim Extractor"]
    D --> E["Evidence Retriever"]
    E --> F["Verifier"]
    F --> G["Report Generator"]
    G --> H["Audit Package"]
    C --> I["Audit Logger"]
    D --> I
    E --> I
    F --> I
    G --> I
```

## Modules

`claim_harness.cli` orchestrates the run command. It validates `--llm mock`, loads inputs, calls the pipeline modules, writes outputs, and prints a concise summary.

`claim_harness.loader` reads Markdown manuscript sections, CSV tables, and references.

`claim_harness.context_manager` packages loaded inputs into an `AuditContext`.

`claim_harness.claim_extractor` uses deterministic keyword rules to extract claim-like sentences and assign `C001`, `C002`, and later IDs.

`claim_harness.evidence_retriever` converts table rows, Results text, Discussion limitations, and references into evidence items.

`claim_harness.verifier` assigns support labels: `supported`, `weakly_supported`, `unsupported`, `overclaimed`, or `needs_human_review`.

`claim_harness.report_generator` writes the audit package.

`claim_harness.audit_logger` records replayable JSONL trace events in `agent_trace.jsonl`.

## Data Objects

The shared schemas are:

- `ManuscriptSection`
- `Claim`
- `EvidenceItem`
- `VerificationResult`
- `AuditEvent`

These objects make intermediate state explicit. That explicit state is the main difference between this harness and a prompt-only review.

## Output Package

The output package contains:

- `claim_table.csv`: claim-level status table.
- `evidence_map.json`: evidence-to-claim links.
- `audit_report.md`: human-readable audit summary.
- `revision_suggestions.md`: rewrite suggestions for risky or weak claims.
- `agent_trace.jsonl`: replayable step trace.
