# v0.3.1 Usability Test Plan

This plan checks whether ProblemBridge + ClaimHarness can be tested by people outside the core development workflow without adding major features or using private data.

## Goal

Validate whether:

- Non-AI users can understand the guided UI.
- Domain practitioners can express a real workflow through plain-language questions.
- AI practitioners can use the generated alignment package to avoid building the wrong task.
- Scientific writing users can understand where ClaimHarness fits after an output or manuscript exists.

All testing should use synthetic, public, anonymized, or deliberately simplified examples.

## Test setup

Ask each reviewer to:

1. Clone the repository or receive a local copy.
2. Run the Windows script or PowerShell script.
3. Start with `Explore examples`.
4. Generate one synthetic ProblemBridge output.
5. Try either the `Domain practitioner wizard`, the `AI practitioner wizard`, or the ClaimHarness demo.
6. Record feedback in `feedback/external_review_log_template.csv`.

## Domain practitioners

Use these questions with people from medicine, cultural heritage, education, social science, design, laboratory research, or other non-AI domains.

1. Can you understand what the home page is saying?
2. Do you know which entry point to choose?
3. Are the wizard questions easy to answer?
4. Does the generated workflow map resemble your real workflow?
5. Does the painpoint-opportunity matrix help you notice steps where AI support might be useful?
6. Which AI-support suggestions look useful?
7. Which suggestions look unreliable, too vague, or outside your domain boundary?
8. Which steps must remain under human review?
9. Could this output help you explain your problem to an AI practitioner?
10. What was the most confusing step?

## AI practitioners

Use these questions with AI engineers, data scientists, ML researchers, product builders, robotics builders, or people who translate domain problems into systems.

1. Does `ai_task_spec.yaml` help you understand the domain task?
2. Does `concept_alignment_table.csv` identify concepts that could be misunderstood?
3. Does `evidence_contract.yaml` help you think about data, evidence, and validation?
4. Does `evaluation_protocol.md` feel closer to the domain goal than generic accuracy, F1, or IoU?
5. Does `misalignment_risk_report.md` help you avoid a wrong modeling direction?
6. What information is still missing before you could build a prototype?
7. Is the package more useful than an ordinary domain brief?

## Scientific writing users

Use these questions with people testing ClaimHarness on synthetic or non-confidential writing.

1. Is it clear that ClaimHarness is for post-output claim-evidence auditing?
2. Can you run the demo without needing an API key?
3. Does `claim_table.csv` make the claims easier to inspect?
4. Does `audit_report.md` explain which claims are weakly supported, unsupported, overclaimed, or need human review?
5. Are `revision_suggestions.md` useful for revising cautious scientific wording?
6. Does `agent_trace.jsonl` make the process feel more reviewable?
7. What would stop you from using this before sharing or submitting a draft?

## Success signals

The validation pack is useful if reviewers can:

- Launch the UI with minimal help.
- Understand that synthetic examples should be used first.
- Explain the difference between ProblemBridge and ClaimHarness.
- Identify at least one useful output and one confusing output.
- Give concrete feedback that can inform v0.4's editable alignment loop.

## Non-goals

Do not test PDF parsing, RAG, online deployment, authentication, external API review, real clinical data, real education-policy decisions, or automated expert judgement.

