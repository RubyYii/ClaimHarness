# ProblemBridge Guide for Domain Practitioners

This guide is for people who have a real workflow, research problem, or domain pain point, but do not want to start by learning AI vocabulary.

ProblemBridge does not ask you to define a model, prompt, RAG system, or benchmark first. It asks plain-language questions about your work, then produces a package that can help you talk to AI practitioners.

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

The generated package can include a workflow map, pain-point table, concept alignment table, AI task description, evidence expectations, evaluation protocol, risk report, and human-review plan.

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
2. Generate a synthetic example package.
3. Read the friendly summary first.
4. Try `Domain practitioner wizard` with a non-sensitive workflow description.
5. Download the project package only after checking that it contains no private material.
