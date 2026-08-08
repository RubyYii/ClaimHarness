# Release Package Guide

This guide explains how to package ProblemBridge + ClaimHarness for external testing without turning it into an online service or Windows executable.

## local web app package

The recommended package is:

```text
ProblemBridge-ClaimHarness-v0.4.0-local-webapp.zip
```

It contains the repository source, examples, docs, guided UI, and launch scripts. After unzipping, a tester can double-click:

```text
RUN_PROBLEMBRIDGE_WINDOWS.bat
```

This starts the local Streamlit guided UI through the existing script in `scripts/`.

Most guided UI steps use deterministic local workflows. The dedicated
Evidence-Gated Build page can explicitly select either local `mock` or the
official OpenAI GPT-5.6 path. The UI has no API-key field and does not accept,
collect, display, or store credentials; remote mode reads `OPENAI_API_KEY` only
from the launch environment and warns before transmission.

The local web app package requires Python because its first-run setup creates `.venv`, installs the tested `.[dev,ui]` set under `requirements/constraints.txt`, and runs the Streamlit app locally. Third-party dependencies must resolve to prebuilt wheels; setup fails with a direct package-index/platform message instead of attempting an unbounded local source build. Normal daily launches reuse that environment and do not reinstall dependencies. It is not an online deployment.

## Build Week judge bundle

For the competition, use a judge bundle around the verified local application
package:

```text
ProblemBridge-ClaimHarness-v0.4.0-build-week-2026-judge-bundle.zip
```

It contains:

- `START_HERE.md`
- the tested local application ZIP, manifest, and SHA-256 under `release/`
- a pre-generated deterministic package under `mock_demo_output/`
- submission, delta, demo, and provider documents under `documents/`
- `BUNDLE_CONTENT_MANIFEST.json` with per-file SHA-256 values
- optional, deliberately narrow non-secret evidence from a real synthetic
  GPT-5.6 run under `gpt56_runtime_evidence/`

Build it from a clean committed checkout:

```powershell
.\scripts\build_build_week_judge_bundle_powershell.ps1
```

After completing a real synthetic GPT-5.6 run, add only its bounded runtime
evidence:

```powershell
.\scripts\build_build_week_judge_bundle_powershell.ps1 `
  -Gpt56RunPath "outputs\build_week_gpt56_demo"
```

The script first runs the normal build-and-test release gate. It refuses a dirty
tree through that gate, generates the bundled mock output locally, verifies that
the mock record says `gpt_5_6_used: false`, and accepts optional GPT-5.6
evidence only when the record identifies the official OpenAI provider, a
GPT-5.6-family response, and `contains_api_key: false`.

## static showcase package

A static showcase package can include:

```text
README.md
README.zh-CN.md
docs/static_showcase/index.html
docs/static_showcase/en.html
docs/static_showcase/zh-CN.html
docs/sample_outputs/
```

The static showcase has a language landing page plus two standalone interfaces. Open `docs/static_showcase/en.html` for the English interface or `docs/static_showcase/zh-CN.html` for the Chinese interface. It does not require Python if the viewer only opens the static HTML pages and reads the linked sample outputs.

The static showcase does not run the interactive wizard, does not generate new ProblemBridge packages, and does not run ClaimHarness.

Static HTML is best for viewing examples only. Use the local web app package when reviewers need to fill the workflow wizard or generate new outputs.

## if the Windows launcher does not load

Check that Python 3.10 or newer is installed. If the launcher window closes too quickly, run it from a terminal:

```powershell
.\RUN_PROBLEMBRIDGE_WINDOWS.bat
```

If the browser does not open automatically, visit:

```text
http://127.0.0.1:8501
```

## what requires Python

Python is required for:

- Running the guided Streamlit UI.
- Filling the workflow wizard.
- Generating new ProblemBridge alignment packages.
- Running ClaimHarness demos or audits.
- Running tests.

ProblemBridge alignment packages include `project_record.json` and `project_summary_log.md`; `revision_history.jsonl` appears after the first `record-revision` command. A stable target is limited to three revision rounds. The revision CLI requires either at least one repeatable `--output-artifact` or a mutually exclusive `--no-artifact-hash-reason`; a reason records the missing-hash boundary but is not integrity evidence.

ClaimHarness audit packages include `run_manifest.json` and `project_summary_log.md` for machine-readable and human-readable run provenance. When `--evidence-contract` is used, they also include governed `applied_evidence_contract.json`, a normalized snapshot of the exact validated contract; inspect it for sensitive project wording before sharing. Public provider provenance contains provider name, API style, model, JSON mode, and endpoint origin only. API keys, URL credentials, endpoint paths, and query strings are not persisted, while the private endpoint configuration remains bound through the run-specification hash.

Lifecycle-governed ProblemBridge runs also include `run_identity.json` and `run_complete.json`. Share ZIPs created in the UI exclude `source_files/` by default and contain `share_manifest.json`; original uploads are included only after explicit confirmation.

The packaged UI offers OCR language choices `eng`, `chi_sim`, and `eng+chi_sim`; the matching local Tesseract packs must be installed, and the default is not automatic language detection. Mixed text/scanned PDFs fail closed: direct text is retained, no-text pages are listed for review, and the tool does not silently OCR-and-merge ambiguous pages. With OCR enabled, this condition is recorded as `mixed_pdf_requires_page_review`. Testers should split confirmed scanned pages into a scan-only PDF or image files and review OCR separately.

## first setup versus daily launch

Run setup explicitly after first download or an intentional version change:

```powershell
.\scripts\setup_problembridge_windows.ps1
```

The normal launcher checks the version marker and skips installation when the tested environment is already present:

```powershell
.\RUN_PROBLEMBRIDGE_WINDOWS.bat
```

## what does not require Python

Python is not required for:

- Reading README files and guides.
- Opening `docs/static_showcase/index.html`, `docs/static_showcase/en.html`, or `docs/static_showcase/zh-CN.html`.
- Reviewing committed sample outputs under `docs/sample_outputs/`.

## build the local web app package

From the repository root:

```powershell
.\scripts\build_release_zip_powershell.ps1
```

If PowerShell blocks local scripts on your machine, run:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build_release_zip_powershell.ps1
```

The script writes the zip under `dist/` using tracked Git files from `HEAD`. It refuses to build while tracked or untracked working-tree changes are present, preventing an older `HEAD` from being mislabeled as the current candidate. The version is derived from `pyproject.toml`; both package `__version__` values must match it, and an explicitly supplied `-Version` must be the same `vX.Y.Z` value.

It also writes `<zip>.manifest.json` with the version, Git commit, archive root, entry count, SHA-256, and the project/run identity plus completion-record hash for each committed sample. Before publishing that manifest, the builder opens the ZIP and verifies every sample artifact named by `run_complete.json`. A conventional `<zip>.sha256` file is written beside it. Release-facing text uses LF through `.gitattributes` so hashes remain stable across Windows and Linux checkouts.

## test before sharing

After building:

```powershell
.\scripts\test_release_zip_powershell.ps1
```

If PowerShell blocks local scripts on your machine, run:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\test_release_zip_powershell.ps1
```

If the checkout has no repository `.venv` and neither `py` nor `python` on
`PATH` resolves to a usable interpreter, provide an existing Python 3.10+
executable by absolute path:

```powershell
.\scripts\test_release_zip_powershell.ps1 -PythonExe "<absolute-path-to-python.exe>"
```

This extracts the zip into a temporary folder, compiles every packaged Python file, creates a brand-new temporary venv, and installs the extracted `.[dev,ui]` package under `requirements/constraints.txt`. The local package is built without isolation from the explicitly installed build tools, while every indexed third-party dependency must resolve to a prebuilt wheel. This prevents an index inconsistency from silently starting a compiler toolchain; a missing wheel fails the gate with a package-index/platform diagnostic. It verifies the constrained Typer/Click pair, runs `pip check`, validates the committed sample completion hashes, and then runs the ClaimHarness demo, ProblemBridge demo, Build Week mock demo, and synthetic evaluation from an unrelated working directory. The Build Week smoke also checks the Codex handoff and no-key runtime truth boundary. The temporary venv does not inherit repository-installed packages and is deleted after the gate. Dependency installation may use the configured package index when wheels are not already cached; the gate does not start Streamlit automatically.

The constraints file pins every project/build/test/UI/OCR direct dependency and the compatibility-critical Click transitive dependency. Update `pyproject.toml`, `requirements/constraints.txt`, and CI together when changing that set.

For the complete build, hash verification, and smoke test in one command, use:

```powershell
.\scripts\build_and_test_release_powershell.ps1
```

The combined gate accepts the same explicit interpreter override:

```powershell
.\scripts\build_and_test_release_powershell.ps1 -PythonExe "<absolute-path-to-python.exe>"
```

## do not include

Release packages should not include:

- `.venv`
- `.git`
- `.pytest_cache`
- temporary outputs
- API keys
- passwords or tokens
- private data
- real patient data
- confidential manuscripts
- sensitive unpublished materials

Credential sanitization in provider provenance is not content redaction. Audit inputs, `llm_review.json`, `applied_evidence_contract.json`, optional original uploads, and other generated reports may still contain sensitive wording; inspect the exact ZIP contents and manifest before distribution.
