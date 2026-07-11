# Limitations

ClaimHarness is a small engineering demo, not a scientific review authority.

## Current Limits

- ClaimHarness does not guarantee factual correctness.
- It only checks the manuscript, tables, and references passed to the command.
- High-risk biomedical claims require human review unless the required strong external evidence is present; clinical claims follow the same conservative default.
- Mock mode is deterministic and not semantically complete.
- Keyword claim extraction can miss claims or over-detect explanatory sentences.
- Evidence linking remains deterministic and heuristic. Results prose is candidate context and cannot automatically provide strong evidence for the same claim; table support requires a verifiable metric/value relationship.
- Source lines and evidence locators support navigation, but they are not formal citation anchors.
- Evidence match reasons explain retrieval heuristics; they are not proof that the evidence scientifically supports the claim.
- The verifier is conservative but rule-based.
- Optional LLM review output may be wrong and is advisory only.
- Remote providers are available only through the ClaimHarness CLI. The local Streamlit UI is mock-only and does not accept, collect, or store API keys. Public provenance omits API keys, URL credentials, endpoint paths, and query strings, but it intentionally reveals the provider/model/API style and endpoint origin (scheme/host/port). This sanitization does not prevent `llm_review.json` or the submitted inputs from containing sensitive project text.
- `run_manifest.json` and `project_summary_log.md` provide provenance and navigation; they are not scientific evidence, peer review, or approval records.
- ProblemBridge revision governance limits one stable target to three rounds. The limit prevents repeated local patching, but it cannot determine whether a revised specification is scientifically correct. The CLI requires `--output-artifact` or `--no-artifact-hash-reason`; an omission reason documents why no hash exists but supplies no artifact-integrity evidence. Current records use schema v3; legacy v1/v2 histories require an explicit, project-ID-confirmed migration and are rejected by normal reads/appends.
- `run_complete.json` is written last and verifies an exact snapshot of the declared generated artifacts. Document-intake snapshots include nested table and original-upload hashes, but unknown root files are deliberately outside the governed set. This filesystem workflow is not a database transaction and cannot guarantee recovery from storage-device failure.
- A lifecycle identity binds the workflow and run-specification hash; CLI run specifications include the tool version. This detects accidental `resume` drift but does not make old binaries trustworthy, secure the host filesystem, or replace source control and backups.
- Evidence-contract schema v2 binds `project_id` and content-derived `contract_id` and constrains deterministic checks; it does not prove that the contract itself is scientifically adequate. When supplied, the normalized full contract is copied into `applied_evidence_contract.json` for auditability, so reviewers must inspect the contract for sensitive project wording before sharing the package.
- OCR is optional text derivation. Defaults bound each operation to 30 seconds, render PDFs at 150 DPI, cap a page at 20 million pixels, and also cap bytes, pages, and characters. These limits reduce resource risk but do not guarantee OCR accuracy or sandbox hostile files. The UI language selector only passes `eng`, `chi_sim`, or `eng+chi_sim` to installed Tesseract packs; it does not detect language or validate Chinese audit performance. OCR text is not strong evidence by default, claims extracted from it require source inspection and human review, and the system does not understand figures or charts.
- Mixed text/scanned PDFs are not page-selectively OCR-merged. Direct text is retained and no-text pages are listed for review; with OCR enabled the report fails closed as `mixed_pdf_requires_page_review`. A reported no-text page may be a scan, an intentional blank, or an extraction failure, so the warning cannot classify the page or recover its content automatically.
- Share ZIPs use a generated-artifact allow-list and exclude original uploads and unknown files by default. Explicitly including originals can still disclose sensitive content; `share_manifest.json` is an integrity/content receipt, not automatic redaction or data-loss prevention. Project-level deletion removes all locally governed runs for the confirmed project ID but is not secure erasure of storage media or backups.
- PDF and figure understanding are future work; current PDF support extracts text and tables only.
- The bundled evaluation set is small, synthetic, English-first, and intended only for regression testing. It reports high-risk miss and unsafe high-risk decision rates, but it is not a complete gold evaluation and does not establish real-world, multilingual, cross-domain, or clinical validity.
- The bilingual interface does not imply validated Chinese claim extraction or verification.

## What The Demo Can Show

The demo shows how to turn a manuscript review task into an auditable episode package. It is useful for explaining task decomposition, evidence traceability, intermediate state, and inspectable ordered logs.

## What The Demo Should Not Claim

The demo should not be presented as a medical device, clinical review tool, diagnostic system, or publication-quality scientific reviewer. Any biomedical or clinical claim should be routed to human review unless supported by strong external evidence.

If a remote `--llm` provider is used through the ClaimHarness CLI, `llm_review.json` should be treated as an extra reviewer note. It does not override deterministic claim statuses, evidence links, or the need for human scientific review. Remote provider calls may send the current audit inputs to the selected third-party service, so they should not be used with private or confidential material.
