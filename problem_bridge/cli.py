import hashlib
import json
from importlib import resources
from pathlib import Path

import typer
from rich.console import Console

from claim_harness.llm import (
    LLMProviderConfig,
    MissingProviderConfig,
    resolve_provider_config,
)

from . import __version__
from .build_contract import (
    BUILD_CONTRACT_RUN_ARTIFACTS,
    BUILD_CONTRACT_SNAPSHOT_DIRECTORIES,
    generate_evidence_gated_build,
)
from .generator import build_alignment_package
from .project_lifecycle import (
    ProjectLifecycleError,
    prepare_run_directory,
)
from .revision_governance import (
    DIAGNOSIS_CATEGORIES,
    REVISION_STATUSES,
    RevisionConflictError,
    RevisionLimitReached,
    migrate_legacy_revision_history,
    pending_revision_recovery,
    record_revision,
)
from .writer import ALIGNMENT_RUN_ARTIFACTS, write_alignment_package


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
    mode: str = typer.Option("new", help="Output lifecycle: new, resume, or replace."),
    project_id: str | None = typer.Option(None, help="Stable project identity; reused on resume/replace."),
    run_id: str | None = typer.Option(None, help="Optional run ID for new mode."),
    expected_run_id: str | None = typer.Option(
        None,
        help="Required previous run identity check when resuming or replacing shared output paths.",
    ),
) -> None:
    """Generate a Problem Alignment Package."""
    _validate_provider(llm)
    if not brief.is_file():
        raise typer.BadParameter(f"problem brief not found: {brief}", param_hint="--brief")

    problem_text = brief.read_text(encoding="utf-8")
    package = build_alignment_package(problem_text)
    context = _prepare_output_context(
        out,
        problem_text=problem_text,
        mode=mode,
        project_id=project_id,
        run_id=run_id,
        expected_run_id=expected_run_id,
    )
    with context.transaction():
        write_alignment_package(package, out, project_id=context.project_id)

    console.print("[green]ProblemBridge alignment complete.[/green]")
    console.print(f"profile={package.profile}")
    console.print(f"project_name={package.project_name}")
    console.print(f"project_id={context.project_id}")
    console.print(f"run_id={context.run_id}")
    console.print(f"mode={context.mode}")
    console.print(f"out={out}")


@app.command()
def demo(
    out: Path = typer.Option(Path("outputs/problem_bridge_quality_inspection_demo"), help="Demo output directory."),
    mode: str = typer.Option("new", help="Output lifecycle: new, resume, or replace."),
    project_id: str | None = typer.Option(None, help="Stable project identity; reused on resume/replace."),
    run_id: str | None = typer.Option(None, help="Optional run ID for new mode."),
    expected_run_id: str | None = typer.Option(None, help="Expected existing run ID."),
) -> None:
    """Run the bundled quality-inspection ProblemBridge demo."""
    problem_text = (
        resources.files("problem_bridge")
        .joinpath("demo_data")
        .joinpath("problem.md")
        .read_text(encoding="utf-8")
    )
    package = build_alignment_package(problem_text)
    context = _prepare_output_context(
        out,
        problem_text=problem_text,
        mode=mode,
        project_id=project_id,
        run_id=run_id,
        expected_run_id=expected_run_id,
    )
    with context.transaction():
        write_alignment_package(package, out, project_id=context.project_id)

    console.print("[green]ProblemBridge demo complete.[/green]")
    console.print(f"profile={package.profile}")
    console.print(f"project_name={package.project_name}")
    console.print(f"project_id={context.project_id}")
    console.print(f"run_id={context.run_id}")
    console.print(f"mode={context.mode}")
    console.print(f"out={out}")


@app.command("build-contract")
def build_contract_command(
    brief: Path = typer.Option(..., help="Path to a Markdown domain problem brief."),
    out: Path = typer.Option(
        Path("outputs/evidence_gated_build"), help="Output directory."
    ),
    llm: str = typer.Option(
        "mock",
        help="Runtime proposal provider: mock or openai. openai uses GPT-5.6 Responses API.",
    ),
    mode: str = typer.Option("new", help="Output lifecycle: new, resume, or replace."),
    project_id: str | None = typer.Option(None, help="Stable project identity."),
    run_id: str | None = typer.Option(None, help="Optional run ID for new mode."),
    expected_run_id: str | None = typer.Option(None, help="Expected existing run ID."),
) -> None:
    """Create an evidence-gated build contract and Codex Handoff Pack."""

    if not brief.is_file():
        raise typer.BadParameter(f"problem brief not found: {brief}", param_hint="--brief")
    problem_text = brief.read_text(encoding="utf-8")
    provider_config = _resolve_build_provider(llm)
    _run_evidence_gated_contract(
        problem_text,
        out=out,
        provider_config=provider_config,
        mode=mode,
        project_id=project_id,
        run_id=run_id,
        expected_run_id=expected_run_id,
    )


@app.command("build-week-demo")
def build_week_demo(
    out: Path = typer.Option(
        Path("outputs/build_week_quality_inspection_demo"), help="Demo output directory."
    ),
    llm: str = typer.Option(
        "mock",
        help="Runtime proposal provider: mock or openai. openai uses GPT-5.6 Responses API.",
    ),
    mode: str = typer.Option("new", help="Output lifecycle: new, resume, or replace."),
    project_id: str | None = typer.Option(None, help="Stable project identity."),
    run_id: str | None = typer.Option(None, help="Optional run ID for new mode."),
    expected_run_id: str | None = typer.Option(None, help="Expected existing run ID."),
) -> None:
    """Run the judge-ready synthetic Build Week flow."""

    problem_text = (
        resources.files("problem_bridge")
        .joinpath("demo_data")
        .joinpath("problem.md")
        .read_text(encoding="utf-8")
    )
    provider_config = _resolve_build_provider(llm)
    _run_evidence_gated_contract(
        problem_text,
        out=out,
        provider_config=provider_config,
        mode=mode,
        project_id=project_id,
        run_id=run_id,
        expected_run_id=expected_run_id,
    )


@app.command("record-revision")
def record_revision_command(
    project: Path = typer.Option(..., help="Generated project directory containing project_record.json."),
    target: str = typer.Option(..., help="Stable issue or module name being revised."),
    diagnosis: str = typer.Option(..., help="Revision diagnosis category."),
    summary: str = typer.Option(..., help="Concise description of what changed."),
    verification: str = typer.Option(..., help="Test or review evidence for this round."),
    status: str = typer.Option("needs_revision", help="accepted, needs_revision, or escalated."),
    changed_file: list[str] | None = typer.Option(None, "--changed-file", help="Changed file; repeat as needed."),
    base_artifact: list[Path] | None = typer.Option(
        None, "--base-artifact", help="Pre-revision artifact to hash; repeat as needed."
    ),
    output_artifact: list[Path] | None = typer.Option(
        None, "--output-artifact", help="Post-revision artifact to hash; repeat as needed."
    ),
    no_artifact_hash_reason: str | None = typer.Option(
        None,
        "--no-artifact-hash-reason",
        help="Explicit reason when this round has no hashable output artifact.",
    ),
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
    if not output_artifact and not (no_artifact_hash_reason or "").strip():
        raise typer.BadParameter(
            "Provide at least one --output-artifact, or explicitly record "
            "--no-artifact-hash-reason.",
            param_hint="--output-artifact",
        )
    if output_artifact and (no_artifact_hash_reason or "").strip():
        raise typer.BadParameter(
            "Do not combine --output-artifact with --no-artifact-hash-reason.",
            param_hint="--output-artifact",
        )
    recorded_verification = verification
    if no_artifact_hash_reason:
        recorded_verification += (
            " Artifact hash omission (explicit): " + no_artifact_hash_reason.strip()
        )
    try:
        record = record_revision(
            project,
            target=target,
            diagnosis=normalized_diagnosis,
            summary=summary,
            verification=recorded_verification,
            status=normalized_status,
            changed_files=changed_file or [],
            base_artifacts=base_artifact or [],
            output_artifacts=output_artifact or [],
        )
    except (RevisionLimitReached, ValueError) as exc:
        raise typer.BadParameter(str(exc), param_hint="--target") from exc

    console.print(
        f"[green]Revision recorded:[/green] target={record.target} "
        f"round={record.round_number}/3 status={record.status}"
    )
    pending = pending_revision_recovery(project)
    if pending is not None:
        console.print(
            "[yellow]Warning:[/yellow] revision history is committed, but the project summary "
            f"is pending automatic recovery (phase={pending['phase']})."
        )
    console.print(f"summary={project / 'project_summary_log.md'}")


@app.command("migrate-revision-history")
def migrate_revision_history_command(
    project: Path = typer.Option(
        ..., help="Generated project directory containing project_record.json."
    ),
    project_id: str = typer.Option(
        ...,
        help="Exact immutable project_id to confirm before binding a legacy v1/v2 history.",
    ),
) -> None:
    """Explicitly migrate one homogeneous legacy revision history to schema v3."""

    if not project.is_dir():
        raise typer.BadParameter(f"project directory not found: {project}", param_hint="--project")
    try:
        records = migrate_legacy_revision_history(
            project,
            expected_project_id=project_id,
        )
    except (RevisionConflictError, ValueError) as exc:
        raise typer.BadParameter(str(exc), param_hint="--project") from exc

    console.print(
        f"[green]Revision history migrated:[/green] schema=v3 records={len(records)} "
        f"project_id={project_id}"
    )
    console.print(f"receipt={project / 'revision_history_migration.json'}")


def _validate_provider(llm: str) -> None:
    if llm != "mock":
        raise typer.BadParameter("ProblemBridge MVP supports only --llm mock.", param_hint="--llm")


def _resolve_build_provider(llm: str) -> LLMProviderConfig:
    normalized = llm.strip().lower()
    if normalized not in {"mock", "openai"}:
        raise typer.BadParameter(
            "Evidence-Gated Build supports --llm mock or --llm openai.",
            param_hint="--llm",
        )
    try:
        return resolve_provider_config(normalized)
    except (MissingProviderConfig, ValueError) as exc:
        raise typer.BadParameter(str(exc), param_hint="--llm") from exc


def _run_evidence_gated_contract(
    problem_text: str,
    *,
    out: Path,
    provider_config: LLMProviderConfig,
    mode: str,
    project_id: str | None,
    run_id: str | None,
    expected_run_id: str | None,
) -> None:
    package = build_alignment_package(problem_text)
    context = _prepare_build_contract_context(
        out,
        problem_text=problem_text,
        provider_config=provider_config,
        mode=mode,
        project_id=project_id,
        run_id=run_id,
        expected_run_id=expected_run_id,
    )
    with context.transaction():
        (context.path / "problem.md").write_text(problem_text, encoding="utf-8")
        write_alignment_package(package, context.path, project_id=context.project_id)
        result = generate_evidence_gated_build(
            package,
            context.path,
            provider_config=provider_config,
            project_id=context.project_id,
        )

    status_counts: dict[str, int] = {}
    for decision in result.decisions:
        status_counts[decision.status] = status_counts.get(decision.status, 0) + 1
    console.print("[green]Evidence-gated build contract complete.[/green]")
    console.print(f"project_id={context.project_id}")
    console.print(f"run_id={context.run_id}")
    console.print(f"provider={provider_config.provider}")
    console.print(f"model={result.runtime_record['model']}")
    console.print(f"gpt_5_6_used={result.runtime_record['gpt_5_6_used']}")
    console.print(f"status_counts={json.dumps(status_counts, sort_keys=True)}")
    console.print(f"out={context.path}")


def _prepare_build_contract_context(
    out: Path,
    *,
    problem_text: str,
    provider_config: LLMProviderConfig,
    mode: str,
    project_id: str | None,
    run_id: str | None,
    expected_run_id: str | None,
):
    normalized_mode = mode.strip().lower()
    if normalized_mode in {"resume", "replace"} and not expected_run_id:
        raise typer.BadParameter(
            "--expected-run-id is required for resume or replace.",
            param_hint="--expected-run-id",
        )
    if normalized_mode in {"resume", "replace"} and not project_id:
        raise typer.BadParameter(
            "--project-id is required for resume or replace.",
            param_hint="--project-id",
        )
    resolved_project_id = project_id or (
        "project-" + hashlib.sha256(problem_text.encode("utf-8")).hexdigest()[:16]
    )
    run_spec_sha256 = hashlib.sha256(
        json.dumps(
            {
                "workflow_type": "problem_bridge.build_contract",
                "problem_text_sha256": hashlib.sha256(
                    problem_text.encode("utf-8")
                ).hexdigest(),
                "provider": provider_config.provider,
                "api_style": provider_config.api_style,
                "model": provider_config.model,
                "tool_version": __version__,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    try:
        return prepare_run_directory(
            out,
            project_id=resolved_project_id,
            mode=normalized_mode,
            run_id=run_id,
            expected_run_id=expected_run_id,
            owned_artifacts=tuple(
                [*ALIGNMENT_RUN_ARTIFACTS, *BUILD_CONTRACT_RUN_ARTIFACTS]
            ),
            required_artifacts=tuple(
                [
                    *ALIGNMENT_RUN_ARTIFACTS,
                    *BUILD_CONTRACT_RUN_ARTIFACTS,
                    "problem.md",
                ]
            ),
            snapshot_directories=BUILD_CONTRACT_SNAPSHOT_DIRECTORIES,
            workflow_type="problem_bridge.build_contract",
            run_spec_sha256=run_spec_sha256,
        )
    except (ProjectLifecycleError, ValueError) as exc:
        raise typer.BadParameter(str(exc), param_hint="--mode") from exc


def _prepare_output_context(
    out: Path,
    *,
    problem_text: str,
    mode: str,
    project_id: str | None,
    run_id: str | None,
    expected_run_id: str | None,
):
    normalized_mode = mode.strip().lower()
    if normalized_mode in {"resume", "replace"} and not expected_run_id:
        raise typer.BadParameter(
            "--expected-run-id is required for resume or replace; read it from run_identity.json.",
            param_hint="--expected-run-id",
        )
    if normalized_mode in {"resume", "replace"} and not project_id:
        raise typer.BadParameter(
            "--project-id is required for resume or replace; do not trust an editable identity file as authority.",
            param_hint="--project-id",
        )
    resolved_project_id = project_id
    if resolved_project_id is None:
        digest = hashlib.sha256(problem_text.encode("utf-8")).hexdigest()[:16]
        resolved_project_id = f"project-{digest}"
    try:
        run_spec_sha256 = hashlib.sha256(
            json.dumps(
                {
                    "workflow_type": "problem_bridge.alignment",
                    "problem_text_sha256": hashlib.sha256(
                        problem_text.encode("utf-8")
                    ).hexdigest(),
                    "provider": "mock",
                    "tool_version": __version__,
                },
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        return prepare_run_directory(
            out,
            project_id=resolved_project_id,
            mode=normalized_mode,
            run_id=run_id,
            expected_run_id=expected_run_id,
            owned_artifacts=ALIGNMENT_RUN_ARTIFACTS,
            required_artifacts=ALIGNMENT_RUN_ARTIFACTS,
            workflow_type="problem_bridge.alignment",
            run_spec_sha256=run_spec_sha256,
        )
    except (ProjectLifecycleError, ValueError) as exc:
        raise typer.BadParameter(str(exc), param_hint="--mode") from exc


def main() -> None:
    app()
