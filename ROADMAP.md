# Roadmap

## v0.1 ClaimHarness

Scientific claim-evidence audit demo with deterministic mock mode, synthetic lab-report example, structured outputs, static viewer, and trace logging.

## v0.2 ProblemBridge MVP

Problem alignment package for interdisciplinary AI projects. Current examples cover quality inspection review alignment, cultural archive interpretation alignment, and training policy response alignment.

## v0.3 Stable Auditable Baseline (complete)

Deterministic evidence retrieval and verification, provider boundaries, document intake, project summary logs, three-round governance, safe output handling, and release smoke tests.

## v0.4 Evidence Contract and Project Lifecycle (current)

ProblemBridge-generated schema-v2 `evidence_contract.yaml` files can be executed directly by ClaimHarness with project/content identity binding. Runs have workflow/run-spec/tool-version-bound identities, explicit lifecycle modes, exact completion snapshots, privacy-preserving allow-list share packages, project-bound schema-v3 three-round revision records, bounded OCR quality reports, a synthetic evaluation gate that includes unsafe high-risk decision rate, Windows CI, and release hashes.

Target chain:

```text
alignment package -> evidence contract -> claim audit
```

## v0.5 Bounded Repository Pilot

Pilot alignment and evidence audit inside one approved research repository while keeping private data and unpublished confidential material out of examples and share packages.

## v0.6 Human Review and Chinese Gold Sets

Ask domain practitioners and AI practitioners to evaluate problem clarity, task formulation, evidence standards, evaluation design, review workload, and agreement. Add Chinese claim-audit support only after a versioned Chinese gold set passes explicit gates.

## v0.7 FDE Pilot

Apply the workflow inside one real interdisciplinary project and document before/after changes in task definition, evidence contract, evaluation protocol, and review workload.

## Non-Goals For The Current Prototype

- No hosted service or multi-tenant deployment.
- No automatic semantic figure understanding; document intake extracts text and tables only.
- OCR remains optional and does not imply reliable image understanding.
- No real clinical data.
- No automatic literature search.
- No clinical, legal, educational, or cultural deployment authority.
