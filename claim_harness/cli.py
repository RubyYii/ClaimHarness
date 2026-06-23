import json
from pathlib import Path
from typing import Optional
from collections import Counter

import typer
from rich.console import Console

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
from .verifier import verify_claims


app = typer.Typer(help="ClaimHarness command-line interface.")
console = Console()

DEMO_MANUSCRIPT = Path("examples/oocyte_demo/manuscript.md")
DEMO_TABLES = Path("examples/oocyte_demo/tables")
DEMO_REFERENCES = Path("examples/oocyte_demo/references.md")


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
        help="LLM provider to use: mock or openai-compatible. mock is deterministic and local.",
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
            ("--references", references),
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


def _validate_input_paths(manuscript: Path, tables: Path, references: Path) -> None:
    if not manuscript.is_file():
        raise typer.BadParameter(f"manuscript file not found: {manuscript}", param_hint="--manuscript")
    if not tables.is_dir():
        raise typer.BadParameter(f"tables directory not found: {tables}", param_hint="--tables")
    if not list(tables.glob("*.csv")):
        raise typer.BadParameter(f"tables directory contains no CSV files: {tables}", param_hint="--tables")
    if not references.is_file():
        raise typer.BadParameter(f"references file not found: {references}", param_hint="--references")


def _run_audit(
    manuscript: Path,
    tables: Path,
    references: Path,
    out: Path,
    provider: str,
    provider_config,
) -> tuple[int, int, int]:

    out.mkdir(parents=True, exist_ok=True)
    logger = AuditLogger(out / "agent_trace.jsonl")
    logger.log("cli", "Started ClaimHarness run", {"llm": provider, "out": str(out)})

    manuscript_sections = load_manuscript(manuscript)
    loaded_tables = load_tables(tables)
    reference_text = load_references(references)
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
    logger.log("report_generator", "Wrote audit package", {"out": str(out)})

    if provider == "openai-compatible":
        try:
            llm_review = summarize_audit_with_llm(provider_config, claims, results, evidence)
        except LLMProviderError as exc:
            logger.log("llm", "OpenAI-compatible review failed", {"error": str(exc)})
            raise typer.ClickException(str(exc)) from exc

        (out / "llm_review.json").write_text(
            json.dumps(llm_review, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        logger.log("llm", "Wrote advisory LLM review", {"out": str(out / "llm_review.json")})

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
    out: Path = typer.Option(Path("outputs/oocyte_demo_run"), help="Demo output directory."),
    viewer: bool = typer.Option(True, help="Generate static HTML viewer after the audit."),
) -> None:
    """Run the bundled synthetic oocyte demo."""
    provider = validate_provider("mock")
    provider_config = resolve_provider_config(provider)
    _validate_input_paths(DEMO_MANUSCRIPT, DEMO_TABLES, DEMO_REFERENCES)
    _run_audit(DEMO_MANUSCRIPT, DEMO_TABLES, DEMO_REFERENCES, out, provider, provider_config)
    if viewer:
        html_path = render_report_viewer(out)
        console.print(f"[green]Report viewer written:[/green] {html_path}")
    console.print("[green]Demo audit complete.[/green]")


def main() -> None:
    app()
