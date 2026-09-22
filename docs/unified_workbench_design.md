# One problem, from clarification to evidence checks

The entry flow has since been updated to prioritize cross-disciplinary needs and portable collaborator/model handoffs. See [the current handoff design](cross_disciplinary_handoff.md). The audit and immutable-record design below remains the underlying optional evidence workflow.

The user requested that ProblemBridge and ClaimHarness become one workflow, with lower learning cost and a useful functional connection. The first implementation keeps one active problem per existing project. It does not introduce accounts, a database, remote providers or another agent framework.

## Interaction

The home page is the workbench: **1. Confirm the problem → 2. Check materials → 3. Decide the next action**. Existing interview, extraction and implementation tools remain available as optional helpers. Interview answers can seed the problem form, but only a user's explicit save confirms the problem framing. Reported observations and hypotheses retain their separate labels.

The evidence step accepts pasted text / Markdown and CSV uploads, with paste fallback and a synthetic example. It calls the same deterministic pipeline as the CLI. Generated alignment documents do not count as experimental evidence; they may supply context or a versioned contract only. Findings retain their source claim IDs, evidence locators and original verdicts. A user's follow-up answer records a proposed next step, never a new audit approval.

## Data and boundaries

Each confirmed problem revision, audit and follow-up is a new identity-bound snapshot. The problem ID remains stable within the project; revisions link to the preceding snapshot. Audit inputs are copied into a hashed source snapshot. Editing the framing starts a new revision and clears the current audit association. Old results remain historical. The saved workspace stores a validated pointer so the same problem can be resumed after reopening.

On narrow screens native Streamlit controls stack; the main action stays in the current stage. Details, previous tools and machine records are expandable. Both Chinese and English copy describe actual supported checks, including unknown extraction coverage.

## Checks and design review

Test interview seeding, revision continuity, audit contradictions, zero extracted claims, follow-up provenance, reopening, project isolation, failed writes and source tampering. Run the required synthetic CLI inputs in a fresh output folder and the full suite. Inspect real desktop and mobile browser screenshots.

Gemini received only the abstract design brief before implementation; the design-draft request returned HTTP 503 (model unavailable). A previous attempt in this session returned HTTP 429; external screenshot submission was rejected by automatic approval review. Use this local brief, local browser inspection and the local-only visual smoke check; do not claim an external visual review.
