from importlib import resources
from pathlib import Path

import typer
from rich.console import Console

from .generator import build_alignment_package
from .revision_governance import (
    DIAGNOSIS_CATEGORIES,
    REVISION_STATUSES,
    RevisionLimitReached,
    record_revision,
)
from .writer import write_alignment_package


app = typer.Typer(help="ProblemBridge command-line interface.")
console = Console(width=1000)

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
    out: Path = typer.Option(Path("outputs/problem_bridge_quality_inspection_demo"), help="Demo output directory."),
) -> None:
    """Run the bundled quality-inspection ProblemBridge demo."""
    problem_text = (
        resources.files("problem_bridge")
        .joinpath("demo_data")
        .joinpath("problem.md")
        .read_text(encoding="utf-8")
    )
    package = build_alignment_package(problem_text)
    write_alignment_package(package, out)

    console.print("[green]ProblemBridge demo complete.[/green]")
    console.print(f"profile={package.profile}")
    console.print(f"project_name={package.project_name}")
    console.print(f"out={out}")


@app.command("record-revision")
def record_revision_command(
    project: Path = typer.Option(..., help="Generated project directory containing project_record.json."),
    target: str = typer.Option(..., help="Stable issue or module name being revised."),
    diagnosis: str = typer.Option(..., help="Revision diagnosis category."),
    summary: str = typer.Option(..., help="Concise description of what changed."),
    verification: str = typer.Option(..., help="Test or review evidence for this round."),
    status: str = typer.Option("needs_revision", help="accepted, needs_revision, or escalated."),
    changed_file: list[str] | None = typer.Option(None, "--changed-file", help="Changed file; repeat as needed."),
) -> None:
    """Record one of at most three revision rounds and refresh the project summary log."""

    if not project.is_dir():
        raise typer.BadParameter(f"project directory not found: {project}", param_hint="--project")
    normalized_diagnosis = diagnosis.strip().lower()
    normalized_status = status.strip().lower()
    if normalized_diagnosis not in DIAGNOSIS_CATEGORIES:
        allowed = ", ".join(sorted(DIAGNOSIS_CATEGORIES))
        raise typer.BadParameter(f"diagnosis must be one of: {allowed}", param_hint="--diagnosis")
    if normalized_status not in REVISION_STATUSES:
        allowed = ", ".join(sorted(REVISION_STATUSES))
        raise typer.BadParameter(f"status must be one of: {allowed}", param_hint="--status")
    try:
        record = record_revision(
            project,
            target=target,
            diagnosis=normalized_diagnosis,
            summary=summary,
            verification=verification,
            status=normalized_status,
            changed_files=changed_file or [],
        )
    except (RevisionLimitReached, ValueError) as exc:
        raise typer.BadParameter(str(exc), param_hint="--target") from exc

    console.print(
        f"[green]Revision recorded:[/green] target={record.target} "
        f"round={record.round_number}/3 status={record.status}"
    )
    console.print(f"summary={project / 'project_summary_log.md'}")


def _validate_provider(llm: str) -> None:
    if llm != "mock":
        raise typer.BadParameter("ProblemBridge MVP supports only --llm mock.", param_hint="--llm")


def main() -> None:
    app()
