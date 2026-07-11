# Release Package Guide

This guide explains how to package ProblemBridge + ClaimHarness for external testing without turning it into an online service or Windows executable.

## local web app package

The recommended package is:

```text
ProblemBridge-ClaimHarness-v0.3.3-local-webapp.zip
```

It contains the repository source, examples, docs, guided UI, and launch scripts. After unzipping, a tester can double-click:

```text
RUN_PROBLEMBRIDGE_WINDOWS.bat
```

This starts the local Streamlit guided UI through the existing script in `scripts/`.

The guided UI runs deterministic mock workflows only. It has no remote-provider or API-key controls and does not accept, collect, or store API keys. Optional remote providers are available only through the ClaimHarness CLI.

The local web app package requires Python because it creates `.venv`, installs `.[dev,ui]`, and runs the Streamlit app locally. It is not an online deployment.

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

ProblemBridge alignment packages include `project_record.json` and `project_summary_log.md`; `revision_history.jsonl` appears after the first `record-revision` command. A stable target is limited to three revision rounds. ClaimHarness audit packages include `run_manifest.json` and `project_summary_log.md` for machine-readable and human-readable run provenance.

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

The script writes the zip under `dist/` using tracked Git files from `HEAD`. It refuses to build while tracked or untracked working-tree changes are present, preventing an older `HEAD` from being mislabeled as the current candidate.

## test before sharing

After building:

```powershell
.\scripts\test_release_zip_powershell.ps1
```

If PowerShell blocks local scripts on your machine, run:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\test_release_zip_powershell.ps1
```

This extracts the zip into a temporary folder, compiles every packaged Python file, then uses the already-installed local interpreter and dependencies to run both packaged demos from an unrelated working directory. Imports are pinned to the extracted package, and the gate checks the expected ClaimHarness and ProblemBridge outputs. It does not install dependencies, access the network, or start Streamlit automatically.

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
