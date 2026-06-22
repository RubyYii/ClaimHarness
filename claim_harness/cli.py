from pathlib import Path
from typing import Optional

import typer
from rich.console import Console


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
    console.print("[yellow]ClaimHarness skeleton is installed.[/yellow]")
    console.print("The full audit pipeline will be implemented in a later task.")
    console.print(f"llm={llm}")
    console.print(f"out={out}")


def main() -> None:
    app()
