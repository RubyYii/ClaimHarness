from pathlib import Path
from typing import Optional
from collections import Counter

import typer
from rich.console import Console

from .audit_logger import AuditLogger
from .claim_extractor import extract_claims
from .context_manager import build_context
from .evidence_retriever import retrieve_evidence
from .llm import validate_provider
from .loader import load_manuscript, load_references, load_tables
from .report_generator import write_outputs
from .verifier import verify_claims


app = typer.Typer(help="ClaimHarness command-line interface.")
console = Console()


@app.callback()
def callback() -> None:
    """ClaimHarness command-line interface."""


@app.command()
def run(
    manuscript: Optional[Path] = typer.Option(None, help="Path to manuscript.md."),
    tables: Optional[Path] = typer.Option(None, help="Path to a folder of CSV tables."),
    references: Optional[Path] = typer.Option(None, help="Path to references.md."),
    out: Path = typer.Option(Path("outputs/run"), help="Output directory."),
    llm: str = typer.Option("mock", help="LLM provider to use. Currently only mock is supported."),
) -> None:
    """Run a ClaimHarness audit."""
    try:
        provider = validate_provider(llm)
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
            f"mock run requires {', '.join(missing)}",
            param_hint=", ".join(missing),
        )

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

    weak_or_worse = sum(
        counts.get(status, 0)
        for status in ("weakly_supported", "unsupported", "overclaimed", "needs_human_review")
    )
    console.print("[green]ClaimHarness mock audit complete.[/green]")
    console.print(f"claims={len(claims)}")
    console.print(f"supported={counts.get('supported', 0)}")
    console.print(f"weak_or_worse={weak_or_worse}")
    console.print(f"out={out}")


def main() -> None:
    app()
