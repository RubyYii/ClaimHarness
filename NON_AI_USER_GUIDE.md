# ProblemBridge Guide for Domain Practitioners

This guide is for people who have a real workflow, research problem, or domain pain point, but do not want to start by learning AI vocabulary.

ProblemBridge does not ask you to define a model, prompt, RAG system, or benchmark first. It asks plain-language questions about your work, then produces a package that can help you talk to AI practitioners.

## Document intake

Use `Document intake` when your starting point is a local document, public static webpage, image, or copied text instead of a clean problem description.

Supported inputs:

- `.docx` Word documents; legacy `.doc` uploads return local conversion guidance rather than silently pretending to extract them
- text-based `.pdf` files, plus image-only/scanned PDFs when optional local OCR is enabled
- saved `.html` / `.htm` pages
- public static `http(s)` webpage URLs (no login, JavaScript execution, or crawling)
- `.txt`, `.md`, and `.csv`
- `.png`, `.jpg`, `.jpeg`, `.tif`, `.tiff`, and `.bmp` images when optional local OCR is enabled
- text pasted into the fallback box when upload is unavailable

Document intake produces:

- `extracted_text.md`
- `extracted_tables/`
- `source_manifest.json`
- `ocr_quality_report.json`
- `extraction_warnings.md`
- `problem_seed.md`

Check `extraction_warnings.md` and `ocr_quality_report.json` before using the result. Optional local OCR can derive text from images or image-only PDFs when its extra dependencies and system tools are installed. OCR has byte, page, character, timeout, PDF-DPI, and per-page-pixel limits; it is marked `derived_text/ocr`, is not strong evidence by default, and does not provide image, chart, or figure understanding. Claims extracted from OCR input require a person to inspect the original source before approval. If extraction looks incomplete, inspect the source and rewrite the important parts in plain language before continuing.
## Start by discovering questions

If you cannot describe the problem clearly yet, start with `Question discovery` instead of the full workflow form.

This mode helps you produce:

- `question_brief.md`: what you are trying to understand and the questions to validate.
- `stakeholder_map.md`: who to ask and why each person matters.
- `expert_interview_guide.md`: a first conversation guide for domain experts.
- `unknowns_to_validate.md`: what must be checked before solution design.
- `discussion_plan.md`: a safe order for the first discussion.

Use this package to talk with professional domain people first. Do not propose a solution yet. After the questions are clearer, return to `Domain practitioner wizard` and generate the ProblemBridge alignment package.

## You do not need to describe an AI task

Most domain practitioners do not start with an AI task. That is normal.

Do not worry about terms such as classification, RAG, agent, benchmark, model, or prompt.

Start with your real workflow:

1. What is one task you repeatedly do?
2. Which step is slow, annoying, error-prone, or expert-dependent?
3. Who currently makes the judgement?
4. What materials do you use?
5. What should AI never decide automatically?
6. What kind of assistant output would be useful?

ProblemBridge will translate this workflow description into a more technical package for AI practitioners.

## who this is for

Use ProblemBridge if:

- You are a domain practitioner, researcher, educator, designer, lab worker, reviewer, or project lead.
- You have a workflow that feels repetitive, slow, hard to explain, or easy to misinterpret.
- You want to know where AI might help without letting AI make final professional decisions.
- You need a clearer way to communicate your problem to an AI engineer or data scientist.

## what it does

ProblemBridge helps you:

- Describe the real workflow before anyone turns it into an AI task.
- Identify repeated, time-consuming, or error-prone steps.
- Separate possible AI support from decisions that must remain human-led.
- Turn your answers into a Problem Alignment Package.
- Give AI practitioners a clearer starting point for task design, evidence needs, evaluation, and risk boundaries.

The generated package can include a workflow map, pain-point table, concept alignment table, AI task description, evidence expectations, evaluation protocol, risk report, human-review plan, `project_record.json`, and `project_summary_log.md`.

If you revise one stable target, use `problem-bridge record-revision` to append schema-v3 `revision_history.jsonl`. Stop after at most three rounds: round three must be accepted or escalated instead of followed by a fourth local patch. Old v1/v2 histories require an explicit project-ID-confirmed migration; they are not silently read or upgraded.

## what it does not do

ProblemBridge does not:

- Replace a doctor, teacher, lawyer, expert reviewer, supervisor, or professional decision-maker.
- Make clinical, legal, educational, or operational decisions.
- Guarantee that an AI solution is feasible or safe.
- Prove that the generated package is correct.
- Remove the need for human domain review.

ClaimHarness is the companion tool for a later stage. After text or AI outputs exist, ClaimHarness checks whether claims are supported by the provided evidence.

## what to prepare

Before using the guided UI, prepare simple notes about:

- Your field or project context.
- A workflow you want to improve.
- Which steps are repeated, slow, or frustrating.
- Which steps require expert judgement.
- What materials you already have, such as notes, tables, reports, records, images, or text.
- Which decisions AI should not make automatically.
- What a useful assistant output would look like.

You do not need private data for first testing. Synthetic or anonymized descriptions are enough.

## safety and privacy

Start with the bundled synthetic examples.

Do not upload or paste:

- Private patient data.
- Confidential manuscripts.
- API keys, passwords, tokens, or secrets.
- Sensitive unpublished project materials.
- Data that your institution, collaborator, supervisor, or client has not approved for local tool testing.

The current prototype is local-first and intended for usability testing, not deployment in high-risk settings.

## run the guided UI

On Windows, from the repository root:

```powershell
.\scripts\run_problembridge_ui_powershell.ps1
```

Or double-click:

```text
scripts/run_problembridge_ui_windows.bat
```

When the browser opens:

1. Start with `Explore examples`.
2. Use `Document intake` if your starting point is a Word, text-based PDF, TXT, Markdown, or CSV file.
3. Use `Question discovery` if you do not yet know what to ask or who to ask.
4. Generate a synthetic example package.
5. Read the friendly summary first.
6. Try `Domain practitioner wizard` with a non-sensitive workflow description.
7. Download the project package only after checking that it contains no private material. The ZIP uses a generated-file allow-list and excludes original uploads and unknown files by default; enable original inclusion only when every source file is approved for sharing. Check `share_manifest.json` for the exact included paths, sizes, and SHA-256 hashes.

Use `Start a new project` in the sidebar when changing to a different task or dataset. This creates a new project identity and clears the active draft/output pointers without deleting earlier local runs.

If earlier runs and uploads must be removed, use `Delete this project` and type the exact current project ID. This permanently deletes every local run associated with that project, including original uploads; it is not secure erasure of backups or storage media.
