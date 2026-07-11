import json
from collections import Counter
from importlib import resources
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Optional

import typer
from rich.console import Console

from . import __version__
from .audit_logger import AuditLogger
from .claim_extractor import extract_claims
from .context_manager import build_context
from .evidence_retriever import retrieve_evidence
from .llm import (
    LLMProviderError,
    MissingProviderConfig,
    resolve_provider_config,
    summarize_audit_with_llm,
    validate_provider,
)
from .loader import load_manuscript, load_references, load_tables
from .report_generator import write_outputs
from .report_viewer import MissingAuditOutput, render_report_viewer
from .run_records import MANIFEST_NAME, SUMMARY_LOG_NAME, write_run_records
from .verifier import verify_claims


app = typer.Typer(help="ClaimHarness command-line interface.")
console = Console(width=1000)

CORE_OUTPUTS = (
    "claim_table.csv",
    "evidence_map.json",
    "audit_report.md",
    "revision_suggestions.md",
    "agent_trace.jsonl",
)
OWNED_GENERATED_OUTPUTS = (
    *CORE_OUTPUTS,
    "llm_review.json",
    "index.html",
    MANIFEST_NAME,
    SUMMARY_LOG_NAME,
)


@app.callback()
def callback() -> None:
    """ClaimHarness command-line interface."""


@app.command()
def run(
    manuscript: Optional[Path] = typer.Option(None, help="Path to manuscript.md."),
    tables: Optional[Path] = typer.Option(None, help="Path to a folder of CSV tables."),
    references: Optional[Path] = typer.Option(None, help="Path to references.md."),
    out: Path = typer.Option(Path("outputs/run"), help="Output directory."),
    llm: str = typer.Option(
        "mock",
        help=(
            "LLM provider: mock, openai, openai-compatible, qwen, deepseek, groq, "
            "mistral, openrouter, xai, ollama, gemini, or anthropic. "
            "mock is deterministic and local."
        ),
    ),
) -> None:
    """Run a ClaimHarness audit."""
    try:
        provider = validate_provider(llm)
        provider_config = resolve_provider_config(provider)
    except MissingProviderConfig as exc:
        raise typer.BadParameter(str(exc), param_hint="--llm") from exc
    except ValueError as exc:
        raise typer.BadParameter(str(exc), param_hint="--llm") from exc

    missing = [
        name
        for name, value in (
            ("--manuscript", manuscript),
            ("--tables", tables),
        )
        if value is None
    ]
    if missing:
        raise typer.BadParameter(
            f"audit run requires {', '.join(missing)}",
            param_hint=", ".join(missing),
        )
    _validate_input_paths(manuscript, tables, references)

    _run_audit(manuscript, tables, references, out, provider, provider_config)


def _validate_input_paths(manuscript: Path, tables: Path, references: Path | None) -> None:
    if not manuscript.is_file():
        raise typer.BadParameter(f"manuscript file not found: {manuscript}", param_hint="--manuscript")
    if not tables.is_dir():
        raise typer.BadParameter(f"tables directory not found: {tables}", param_hint="--tables")
    if not list(tables.glob("*.csv")):
        raise typer.BadParameter(f"tables directory contains no CSV files: {tables}", param_hint="--tables")
    if references is not None and not references.is_file():
        raise typer.BadParameter(f"references file not found: {references}", param_hint="--references")


def _run_audit(
    manuscript: Path,
    tables: Path,
    references: Path | None,
    out: Path,
    provider: str,
    provider_config,
) -> tuple[int, int, int]:

    out.mkdir(parents=True, exist_ok=True)
    _remove_owned_generated_outputs(out)
    logger = AuditLogger(out / "agent_trace.jsonl")
    logger.log("cli", "Started ClaimHarness run", {"llm": provider, "out": out.name})

    manuscript_sections = load_manuscript(manuscript)
    loaded_tables = load_tables(tables)
    reference_text = load_references(references) if references is not None else ""
    context = build_context(manuscript_sections, loaded_tables, reference_text)
    logger.log(
        "loader",
        "Loaded inputs",
        {"sections": len(context.manuscript_sections), "tables": sorted(context.tables)},
    )

    claims = extract_claims(context.manuscript_sections)
    logger.log("claim_extractor", "Extracted claims", {"claims": len(claims)})

    evidence = retrieve_evidence(
        claims,
        context.manuscript_sections,
        context.tables,
        context.references,
    )
    logger.log("evidence_retriever", "Retrieved evidence", {"evidence_items": len(evidence)})

    results = verify_claims(claims, evidence)
    counts = Counter(result.status for result in results)
    logger.log("verifier", "Verified claims", {"status_counts": dict(counts)})

    write_outputs(out, claims, evidence, results)
    logger.log("report_generator", "Wrote audit package", {"out": out.name})

    provider_status = "not_requested"
    provider_error: LLMProviderError | None = None
    if provider_config.api_style != "mock":
        try:
            llm_review = summarize_audit_with_llm(provider_config, claims, results, evidence)
        except LLMProviderError as exc:
            provider_status = "failed"
            provider_error = exc
            logger.log(
                "llm",
                "Advisory LLM review failed",
                {"provider": provider, "error": "provider request failed"},
            )
        else:
            provider_status = "completed"
            (out / "llm_review.json").write_text(
                json.dumps(llm_review, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            logger.log(
                "llm",
                "Wrote advisory LLM review",
                {"provider": provider, "out": "llm_review.json"},
            )

    logger.log(
        "cli",
        "Finalized deterministic audit package",
        {"provider_status": provider_status},
    )
    write_run_records(
        out,
        run_id=logger.run_id,
        started_at=logger.started_at,
        tool_version=__version__,
        provider=provider,
        provider_status=provider_status,
        manuscript=manuscript,
        tables=tables,
        references=references,
        claims=claims,
        results=results,
        artifact_names=[*CORE_OUTPUTS, "llm_review.json"],
    )

    if provider_error is not None:
        typer.echo(
            "Error: Deterministic audit outputs were written; run records were also written, but the advisory "
            f"LLM review failed: {provider_error}",
            err=True,
        )
        raise typer.Exit(code=1) from provider_error

    weak_or_worse = sum(
        counts.get(status, 0)
        for status in ("weakly_supported", "unsupported", "overclaimed", "needs_human_review")
    )
    console.print("[green]ClaimHarness audit complete.[/green]")
    console.print(f"claims={len(claims)}")
    console.print(f"supported={counts.get('supported', 0)}")
    console.print(f"weak_or_worse={weak_or_worse}")
    console.print(f"out={out}")
    return len(claims), counts.get("supported", 0), weak_or_worse


def _remove_owned_generated_outputs(out: Path) -> None:
    """Remove only files owned by ClaimHarness before replacing a run."""
    for filename in OWNED_GENERATED_OUTPUTS:
        path = out / filename
        if path.is_file() or path.is_symlink():
            path.unlink()


@app.command()
def view(
    run: Path = typer.Option(..., help="Audit output directory containing ClaimHarness files."),
    out: Optional[Path] = typer.Option(None, help="HTML file to write. Defaults to <run>/index.html."),
) -> None:
    """Generate a static HTML viewer for an audit package."""
    try:
        html_path = render_report_viewer(run, out)
    except MissingAuditOutput as exc:
        raise typer.BadParameter(str(exc), param_hint="--run") from exc

    console.print(f"[green]Report viewer written:[/green] {html_path}")


@app.command()
def demo(
    out: Path = typer.Option(Path("outputs/lab_report_audit_demo_run"), help="Demo output directory."),
    viewer: bool = typer.Option(True, help="Generate static HTML viewer after the audit."),
) -> None:
    """Run the bundled synthetic lab-report audit demo."""
    provider = validate_provider("mock")
    provider_config = resolve_provider_config(provider)
    with TemporaryDirectory(prefix="claimharness-demo-") as temporary:
        manuscript, tables, references = _materialize_demo(Path(temporary))
        _validate_input_paths(manuscript, tables, references)
        _run_audit(manuscript, tables, references, out, provider, provider_config)
    if viewer:
        html_path = render_report_viewer(out)
        console.print(f"[green]Report viewer written:[/green] {html_path}")
    console.print("[green]Demo audit complete.[/green]")


def _materialize_demo(root: Path) -> tuple[Path, Path, Path]:
    """Copy package resources to temporary Paths required by the loaders."""

    package_root = resources.files("claim_harness").joinpath("demo_data")
    manuscript = root / "manuscript.md"
    references_path = root / "references.md"
    tables = root / "tables"
    tables.mkdir(parents=True, exist_ok=True)
    manuscript.write_bytes(package_root.joinpath("manuscript.md").read_bytes())
    references_path.write_bytes(package_root.joinpath("references.md").read_bytes())
    packaged_tables = package_root.joinpath("tables")
    for filename in ("table1_metrics.csv", "table2_ablation.csv"):
        (tables / filename).write_bytes(packaged_tables.joinpath(filename).read_bytes())
    return manuscript, tables, references_path


def main() -> None:
    app()
