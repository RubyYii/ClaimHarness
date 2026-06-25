from pathlib import Path

import typer
from rich.console import Console

from .generator import build_alignment_package
from .writer import write_alignment_package


app = typer.Typer(help="ProblemBridge command-line interface.")
console = Console(width=1000)

DEMO_BRIEF = Path("examples/problem_bridge/hsg/problem.md")


@app.callback()
def callback() -> None:
    """ProblemBridge command-line interface."""


@app.command()
def align(
    brief: Path = typer.Option(..., help="Path to a Markdown domain problem brief."),
    out: Path = typer.Option(Path("outputs/problem_bridge_alignment"), help="Output directory."),
    llm: str = typer.Option("mock", help="LLM provider to use. MVP supports mock only."),
) -> None:
    """Generate a Problem Alignment Package."""
    _validate_provider(llm)
    if not brief.is_file():
        raise typer.BadParameter(f"problem brief not found: {brief}", param_hint="--brief")

    problem_text = brief.read_text(encoding="utf-8")
    package = build_alignment_package(problem_text)
    write_alignment_package(package, out)

    console.print("[green]ProblemBridge alignment complete.[/green]")
    console.print(f"profile={package.profile}")
    console.print(f"project_name={package.project_name}")
    console.print(f"out={out}")


@app.command()
def demo(
    out: Path = typer.Option(Path("outputs/problem_bridge_hsg_demo"), help="Demo output directory."),
) -> None:
    """Run the bundled HSG ProblemBridge demo."""
    if not DEMO_BRIEF.is_file():
        raise typer.BadParameter(f"demo brief not found: {DEMO_BRIEF}", param_hint="--brief")

    problem_text = DEMO_BRIEF.read_text(encoding="utf-8")
    package = build_alignment_package(problem_text)
    write_alignment_package(package, out)

    console.print("[green]ProblemBridge demo complete.[/green]")
    console.print(f"profile={package.profile}")
    console.print(f"project_name={package.project_name}")
    console.print(f"out={out}")


def _validate_provider(llm: str) -> None:
    if llm != "mock":
        raise typer.BadParameter("ProblemBridge MVP supports only --llm mock.", param_hint="--llm")


def main() -> None:
    app()
