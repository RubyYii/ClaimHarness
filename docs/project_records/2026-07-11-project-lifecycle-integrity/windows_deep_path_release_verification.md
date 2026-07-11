# Windows Deep-Path Release Verification

## Scope

This verification is a new governance target, separate from the accepted
three-round `project-lifecycle-integrity-v0.4.0` target. It covers defects that
were observable only from a deeply nested clean Windows clone after that
target was sealed.

## Verified changes

- Short, collision-safe atomic record names for lifecycle, governance, run
  manifests, and report viewers.
- Owner-bound sibling transaction staging, hard-exit recovery, safe replace
  cleanup, and short deletion tombstones.
- Short governed run directory names that leave path budget for nested source
  files while preserving authoritative creation time in `run_identity.json`.
- UI history ordered by verified UTC identity time, with an explicit
  modification-time fallback for `legacy` folders.
- Release scripts accept an explicit Python executable and do not depend on an
  ambiguous Windows application alias in clean clones.

## Evidence

- Main workspace regression: `329 passed, 2 skipped`.
- Deep-path clean-clone regression at Git commit
  `5e9096929d4258baa5e835a80e356bf74296845f`: `331 passed`, no skips.
- The documented ClaimHarness mock audit command completed from the clean
  clone and produced the five required audit artifacts with a verified
  lifecycle completion record.
- Strict release gate completed from tracked Git `HEAD`: clean-venv install,
  `pip check`, four committed sample completion checks, both packaged demos,
  and the synthetic evaluation all passed.
- Release archive:
  `dist/ProblemBridge-ClaimHarness-v0.4.0-local-webapp.zip`.
- Release archive SHA-256:
  `47e936be46217fcb4183fe2fc256f6db8682868b0b8fdae072ef129d14800f1b`.
- Final Gemini diff reviews passed with no missing tests or unsafe claims.
- Independent code review found no remaining reproducible P0-P2 issue.

## Result

Accepted. The Windows deep-path and clean-release findings are closed without
adding a fourth revision to the already accepted three-round lifecycle target.
