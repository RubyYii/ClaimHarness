# Project Summary Log

## Project

- Name: ClaimHarness repository remediation
- Goal: Repair evidence semantics, local security boundaries, revision governance, provenance, packaging, and project history without expanding the v1 scope.
- Revision rule: maximum 3 rounds for the stable `repository-remediation` target; no fourth local patch.
- Final status: accepted after round 3/3.

## Revision History

### Round 1/3 — structural mismatch

- Rebuilt claim extraction, evidence locators and relations, comparison checks, conservative verification, and exact source-line handling.
- Outcome: core tests passed, but security, state, and release boundaries still required consolidation.

### Round 2/3 — version contamination

- Removed unwired UI provider controls; hardened provider and URL intake; fixed Windows native-command exits; aligned version metadata.
- Outcome: targeted safety tests passed, but provenance, packaging, and independent semantic review were still incomplete.

### Round 3/3 — evidence gap

- Added canonical three-round governance, `run_manifest.json`, `project_summary_log.md`, package-internal demos, strict multi-metric/value verification, URL pinning and redaction, release smoke gates, refreshed samples, and synchronized documentation.
- Independent reviews reproduced and closed DNS rebinding, URL metadata leakage, incomplete comparison verification, duplicate-claim self-support, revision-target aliasing, and release-gate false positives.
- Outcome: accepted; no remaining P0–P2 findings.

## Final Verification

- Full test suite: `196 passed`.
- Required audit command: passed with 16 claims, 3 supported, and 13 weak-or-worse.
- Required output package: five core audit files plus `run_manifest.json` and `project_summary_log.md`.
- Manifest run ID and all recorded output SHA-256 values: verified.
- Wheel: version `0.3.3`; both bundled demos ran from an unrelated working directory.
- Python compilation and `git diff --check`: passed.

## Release Boundary

The working tree contains the completed but uncommitted remediation. The release builder now rejects a dirty tree, so a release ZIP must be built only after the intended files are reviewed, staged, and committed. The unrelated pre-existing `.tmp_academic_writing_toolkit/` directory was not modified.

## Interpretation Boundary

This log records engineering work and verification. It is not scientific evidence, peer review, clinical approval, or proof that heuristic extraction is semantically complete.
