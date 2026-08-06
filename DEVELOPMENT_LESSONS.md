# Development Lessons

This note summarizes the development experience behind ProblemBridge + ClaimHarness. It is written as a reusable project reflection: what changed, what worked, what caused friction, and what should guide the next version.

## Core Takeaway

The project became more valuable when it stopped being only a claim checker and became a two-stage workflow:

```text
ProblemBridge: help people ask and align the right problem before AI work starts.
ClaimHarness: audit claim-evidence alignment after text or system output exists.
```

The strongest lesson is that many interdisciplinary AI projects do not fail first at model choice. They fail earlier, when a real domain workflow is compressed into the wrong AI task.

## Product Evolution

| Stage | What changed | Lesson |
| --- | --- | --- |
| v0.1 ClaimHarness | Built a deterministic claim-evidence audit pipeline with traceable outputs. | Start with a narrow, testable harness before adding UI or providers. |
| v0.2 ProblemBridge | Added pre-model workflow discovery, task specification, evidence contracts, and evaluation protocols. | The upstream problem-alignment step is as important as the downstream audit step. |
| v0.3 Guided interaction | Added a local web workbench for non-AI users. | Do not ask non-AI users to describe an AI task; ask about repeated work, judgement materials, pain points, and boundaries. |
| v0.3.2 Document intake and handoffs | Added document intake, question discovery, workflow handoff buttons, memory, exports, and optional OCR documentation. An API-settings UI experiment was later removed. | A useful prototype needs continuity between steps, but trust-boundary experiments must be retired when they are not fully reviewed. |
| Review packaging | Added portfolio brief, sample outputs, demo script, roadmap, release package, and GitHub visuals. | External users need to understand the project in minutes before they invest time running it. |

## Product Lessons

### 1. Positioning matters before implementation scale

The early version looked like a scientific writing checker. That was understandable, but too narrow. The project became clearer after the positioning shifted to:

```text
problem alignment before AI work + evidence audit after output
```

This made the relationship between ProblemBridge and ClaimHarness easier to explain, and it avoided the weaker framing of "another writing assistant."

### 2. The first user problem is often not "what model should I use?"

For non-AI users, the hard step is usually not choosing a model, provider, or prompt. The hard step is naming:

- what work they repeatedly do
- which judgement is difficult
- what materials they rely on
- who should be consulted
- what AI must not decide automatically

This is why Question Discovery became a central feature. It helps users produce better questions before discussing solutions.

### 3. Local-first mock mode is a product feature, not just a dev shortcut

The deterministic mock path made the prototype easier to test, demo, and share. It also matched the project's safety boundary:

- no API key needed for first use
- no external service calls by default
- no private data required
- stable outputs for tests and demos

Optional providers are useful, but they should remain advisory and privacy-aware.

### 4. Handoffs between steps are part of the user experience

The UI felt disconnected when users had to manually copy text from one step into the next. Adding explicit continuation buttons made the workflow more coherent:

```text
Document intake -> Question discovery -> Domain practitioner wizard -> AI practitioner wizard -> View outputs
```

The practical lesson: each step should produce an artifact that naturally seeds the next step.

### 5. File intake is extraction, not understanding

Supporting Word, PDF, webpages, images, and OCR can create unrealistic expectations. The safer framing is:

- extract text, tables, links, comments, highlights, and warnings
- preserve attention signals such as comments and highlighted spans
- avoid claiming figure understanding or professional judgement
- route uncertain material to human review

This distinction should stay visible in the UI and docs.

### 6. Optional OCR should not become a default dependency

OCR is useful, but it adds installation friction and quality uncertainty. Keeping OCR optional made the core app easier to run while still giving advanced users a path for image-only PDFs or scanned images.

The docs need to be visual and practical because OCR setup is where non-technical users often get stuck.

### 7. Model-provider support should stay behind a reviewed boundary

An early UI experiment exposed provider and API-key controls. That widened the workbench trust boundary without a complete consent, secret-lifecycle, endpoint-validation, and failure-handling design, so the controls were removed. The current pattern is:

- deterministic mock-only behavior in the Streamlit workbench
- direct advisory provider presets and allow-listed installed-client adapters through the ClaimHarness CLI only
- environment-variable configuration rather than UI key collection
- HTTPS for public endpoints, bounded responses, and rejected redirects
- isolated temporary working directories, disabled or bounded agent tools, stdin transport, structured-output validation, and live fixed-size process-output buffers that terminate the process tree on overflow or timeout
- a passive provider inventory that never executes detected clients, contacts endpoints, or prints secrets and absolute executable paths; real synthetic probes require a separate provider selection and confirmation flag
- detection-only labels for clients such as Kimi Code or third-party DeepSeek tools that do not yet meet the reviewed stdin, tool-isolation, and strict-output contract
- a clear warning that direct providers and cloud-backed installed clients receive the current inputs

### 8. Examples should be generic enough to travel

Examples that feel too personal can make the project look narrower than it is. Synthetic, general examples make it easier for outsiders to test the workflow without assuming it is built only for one thesis, domain, or personal project.

The shared pattern matters more than the exact domain:

```text
visual output is not the same as final professional judgement
object recognition is not the same as interpretation
fluent text is not the same as evidence-aligned guidance
```

### 9. Presentation is part of trust

The GitHub page needed to explain the project quickly and visually. The flat comic-style hero worked better than a 3D visual because it matched the product tone: approachable, local-first, workflow-oriented, and not over-polished.

Good external review packaging included:

- one-sentence summary
- bilingual entry points
- screenshots or diagrams
- sample outputs
- demo script
- roadmap
- safety boundaries
- runnable local package

## Engineering Lessons

### 1. Keep the harness modular

The system stayed manageable because the core pieces were kept separate:

- loading and document intake
- question discovery
- guided workflow alignment
- task specification
- evidence retrieval
- verification
- report generation
- audit logging
- provider integration

This made it possible to add features without turning the codebase into a general agent framework.

### 2. Persist intermediate artifacts

CSV, JSON, YAML, Markdown, HTML, and JSONL outputs were easier to inspect than opaque app state. They also made the system more auditable and easier to test.

For this project, traceability is not decoration. It is the product's core claim.

### 3. Test docs, launchers, and release packaging

The project is not only Python functions. It includes README instructions, Windows launchers, Streamlit UI flow, release zip scripts, provider docs, and sample outputs. Tests that check those files caught real regressions.

Release readiness tests were especially useful because external users interact with the package, not just the internal modules.

### 4. Windows friction is real

Important Windows issues appeared during development:

- PowerShell execution policy can block scripts.
- Double-click `.bat` launchers need visible errors and `pause`.
- Streamlit may run even when the browser does not auto-open.
- Terminal encoding can make correct UTF-8 Chinese look garbled.
- CRLF warnings can appear even when content is fine.

The fix was not to hide these issues, but to document fallback paths clearly.

### 5. UI state needs memory, but memory needs privacy boundaries

Saving the recent output path and draft form fields improves usability. Provider settings and API keys do not belong in the current UI memory; API keys, tokens, passwords, and secrets must not be written there.

The memory feature also needs a "clear before sharing" warning because drafts may contain sensitive workflow details.

### 6. Defensive imports and fallback input paths matter

During development, stale module imports and upload failures caused confusing UI errors. The app became more robust after adding:

- stale import recovery
- manual paste fallback when upload fails
- clearer extraction warnings
- tests that simulate the failure paths

These are small features, but they matter because they protect the user's first experience.

## Mistakes And Corrections

| Issue | Correction |
| --- | --- |
| The project initially sounded like only a claim checker. | Reframed it as a two-stage interdisciplinary AI harness. |
| Non-AI users were expected to describe problems too directly. | Added guided questions and Question Discovery. |
| Workflow steps felt isolated. | Added continuation buttons and state handoffs. |
| Bilingual UI looked odd when shown as mixed text. | Moved toward separate English and Chinese interfaces. |
| File upload failures blocked users. | Added manual paste fallback and clearer document intake outputs. |
| Unreviewed API settings expanded the UI trust boundary. | Removed them; remote providers remain ClaimHarness CLI-only. |
| OCR expectations were too broad. | Made OCR optional and documented installation and limits. |
| README visuals were too 3D and product-like. | Replaced them with a flatter comic workflow image. |
| GitHub alone did not equal usability. | Added local release zip packaging and test scripts. |

## What To Preserve

Keep these principles stable in later versions:

- Default to local deterministic mode.
- Treat remote LLMs as optional advisory reviewers.
- Avoid private, clinical, confidential, or unpublished data in examples.
- Keep ProblemBridge and ClaimHarness connected but not over-coupled.
- Preserve intermediate artifacts and trace logs.
- Ask better questions before proposing AI solutions.
- Do not claim professional authority in medicine, law, education, policy, or cultural interpretation.

## Next Development Priorities

The most useful next step is not to add a large new feature. It is to validate the guided workflow with real testers using non-sensitive examples.

High-value next work:

- collect usability feedback from domain practitioners and AI practitioners
- improve question routing based on user confusion
- connect `evidence_contract.yaml` more directly into ClaimHarness audits
- make output packages easier to compare across examples
- strengthen OCR quality warnings without making OCR required

Low-priority for now:

- hosted deployment
- login system
- database
- automatic literature search
- complex RAG
- multi-agent debate
- clinical or policy deployment claims

## Reusable Checklist For Similar Projects

Before adding a feature, ask:

1. Does this help users clarify the real workflow or evidence boundary?
2. Does it preserve local-first testing?
3. Does it create an auditable artifact?
4. Does it make the next step easier to continue?
5. Does it avoid sending sensitive data by default?
6. Does it need a test, a doc update, or a release-package check?
7. Would a non-AI user understand why this feature exists?

The best version of this project is not the one with the most model integrations. It is the one that helps people ask the right question, talk to the right expert, define the right AI task, and audit the output before it is trusted.
