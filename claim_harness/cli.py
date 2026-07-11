import hashlib
import json
from collections import Counter
from importlib import resources
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Optional
from urllib.parse import urlsplit

import typer
from rich.console import Console

from problem_bridge.project_lifecycle import (
    ProjectLifecycleError,
    RunContext,
    prepare_run_directory,
)

from . import __version__
from .audit_logger import AuditLogger
from .claim_extractor import extract_claims
from .context_manager import build_context
from .evidence_contract import (
    EvidenceContractError,
    LoadedEvidenceContract,
    load_evidence_contract,
)
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
from .run_records import (
    MANIFEST_NAME,
    SUMMARY_LOG_NAME,
    capture_input_records,
    write_run_records,
)
from .verifier import verify_claims


app = typer.Typer(help="ClaimHarness command-line interface.")
console = Console(width=1000)

CORE_OUTPUTS = (
    "claim_table.csv",
    "evidence_map.json",
    "audit_report.md",
    "revision_suggestions.md",
    "audit_diagnostics.json",
    "human_review_queue.json",
    "agent_trace.jsonl",
)
APPLIED_CONTRACT_NAME = "applied_evidence_contract.json"
OWNED_GENERATED_OUTPUTS = (
    *CORE_OUTPUTS,
    "llm_review.json",
    APPLIED_CONTRACT_NAME,
    "index.html",
    MANIFEST_NAME,
    SUMMARY_LOG_NAME,
)
CLAIM_REQUIRED_ARTIFACTS = (*CORE_OUTPUTS, MANIFEST_NAME, SUMMARY_LOG_NAME)
CLAIM_OWNED_ARTIFACTS = (*CORE_OUTPUTS, "llm_review.json", MANIFEST_NAME)


@app.callback()
def callback() -> None:
    """ClaimHarness command-line interface."""


@app.command()
def run(
    manuscript: Optional[Path] = typer.Option(None, help="Path to manuscript.md."),
    tables: Optional[Path] = typer.Option(None, help="Path to a folder of CSV tables."),
    references: Optional[Path] = typer.Option(None, help="Path to references.md."),
    evidence_contract: Optional[Path] = typer.Option(
        None,
        help="Optional versioned evidence_contract.yaml from ProblemBridge.",
    ),
    out: Path = typer.Option(Path("outputs/run"), help="Output directory."),
    mode: str = typer.Option("new", help="Output lifecycle: new, resume, or replace."),
    project_id: Optional[str] = typer.Option(None, help="Stable project identity."),
    run_id: Optional[str] = typer.Option(None, help="Optional run ID for new mode."),
    expected_run_id: Optional[str] = typer.Option(
        None,
        help="Existing run ID required for resume or replace.",
    ),
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
    loaded_contract = None
    if evidence_contract is not None:
        try:
            loaded_contract = load_evidence_contract(evidence_contract)
        except EvidenceContractError as exc:
            raise typer.BadParameter(str(exc), param_hint="--evidence-contract") from exc

    input_records = capture_input_records(
        manuscript, tables, references, loaded_contract
    )

    run_context = _prepare_output_context(
        out,
        manuscript=manuscript,
        mode=mode,
        project_id=project_id,
        run_id=run_id,
        expected_run_id=expected_run_id,
        input_records=input_records,
        provider_config=provider_config,
        contract_project_id=(
            loaded_contract.contract.project_id if loaded_contract is not None else None
        ),
        has_evidence_contract=loaded_contract is not None,
    )

    _run_audit(
        manuscript,
        tables,
        references,
        out,
        provider,
        provider_config,
        loaded_contract,
        run_context,
        input_records,
    )


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
    evidence_contract: LoadedEvidenceContract | None = None,
    run_context: RunContext | None = None,
    input_records: dict[str, object] | None = None,
) -> tuple[int, int, int]:
    if run_context is None:
        raise ValueError("run_context is required for an identity-bound audit run")
    with run_context.transaction():
        outcome, provider_error = _run_audit_locked(
            manuscript,
            tables,
            references,
            out,
            provider,
            provider_config,
            evidence_contract,
            run_context,
            input_records,
        )

    if provider_error is not None:
        typer.echo(
            "Error: Deterministic audit outputs were written; run records were also written, but the advisory "
            f"LLM review failed: {provider_error}",
            err=True,
        )
        raise typer.Exit(code=1) from provider_error

    claim_count, supported_count, weak_or_worse = outcome
    console.print("[green]ClaimHarness audit complete.[/green]")
    console.print(f"claims={claim_count}")
    console.print(f"supported={supported_count}")
    console.print(f"weak_or_worse={weak_or_worse}")
    console.print(f"project_id={run_context.project_id}")
    console.print(f"run_id={run_context.run_id}")
    console.print(f"mode={run_context.mode}")
    console.print(f"out={out}")
    return outcome


def _run_audit_locked(
    manuscript: Path,
    tables: Path,
    references: Path | None,
    out: Path,
    provider: str,
    provider_config,
    evidence_contract: LoadedEvidenceContract | None,
    run_context: RunContext,
    input_records: dict[str, object] | None,
) -> tuple[tuple[int, int, int], LLMProviderError | None]:
    if run_context.mode in {"resume", "replace"}:
        _remove_owned_generated_outputs(out)
    logger = AuditLogger(out / "agent_trace.jsonl", run_id=run_context.run_id)
    logger.log("cli", "Started ClaimHarness run", {"llm": provider, "out": out.name})
    if evidence_contract is not None:
        logger.log(
            "evidence_contract",
            "Loaded versioned evidence contract",
            {
                "path": evidence_contract.safe_path,
                "sha256": evidence_contract.sha256,
                "schema_version": evidence_contract.contract.schema_version,
                "project_id": evidence_contract.contract.project_id,
                "contract_id": evidence_contract.contract.contract_id,
            },
        )
        (out / APPLIED_CONTRACT_NAME).write_text(
            json.dumps(
                evidence_contract.contract.model_dump(mode="json"),
                indent=2,
                ensure_ascii=False,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )

    manuscript_sections = load_manuscript(manuscript)
    loaded_tables = load_tables(tables)
    reference_text = load_references(references) if references is not None else ""
    if input_records is not None:
        current_inputs = capture_input_records(
            manuscript, tables, references, evidence_contract
        )
        if current_inputs != input_records:
            raise RuntimeError(
                "Input files changed after the run specification was captured; "
                "the run remains incomplete. Start a replace run from a stable input snapshot."
            )
    context = build_context(manuscript_sections, loaded_tables, reference_text)
    logger.log(
        "loader",
        "Loaded inputs",
        {"sections": len(context.manuscript_sections), "tables": sorted(context.tables)},
    )

    claims = extract_claims(
        context.manuscript_sections,
        evidence_contract.contract if evidence_contract is not None else None,
    )
    logger.log("claim_extractor", "Extracted claims", {"claims": len(claims)})

    evidence = retrieve_evidence(
        claims,
        context.manuscript_sections,
        context.tables,
        context.references,
        references_file=references.name if references is not None else None,
    )
    logger.log("evidence_retriever", "Retrieved evidence", {"evidence_items": len(evidence)})

    results = verify_claims(
        claims,
        evidence,
        evidence_contract.contract if evidence_contract is not None else None,
    )
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
        artifact_names=[*CORE_OUTPUTS, "llm_review.json", APPLIED_CONTRACT_NAME],
        evidence_contract=evidence_contract,
        project_id=run_context.project_id,
        input_records=input_records,
        provider_details=_provider_public_details(provider_config),
        run_spec_sha256=run_context.run_spec_sha256,
    )

    weak_or_worse = sum(
        counts.get(status, 0)
        for status in ("weakly_supported", "unsupported", "overclaimed", "needs_human_review")
    )
    return (len(claims), counts.get("supported", 0), weak_or_worse), provider_error


def _remove_owned_generated_outputs(out: Path) -> None:
    """Remove only files owned by ClaimHarness before replacing a run."""
    for filename in OWNED_GENERATED_OUTPUTS:
        path = out / filename
        if path.is_file() or path.is_symlink():
            path.unlink()


def _prepare_output_context(
    out: Path,
    *,
    manuscript: Path,
    mode: str,
    project_id: str | None,
    run_id: str | None,
    expected_run_id: str | None,
    input_records: dict[str, object],
    provider_config,
    contract_project_id: str | None = None,
    has_evidence_contract: bool = False,
) -> RunContext:
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
        if contract_project_id is not None:
            resolved_project_id = contract_project_id
        else:
            manuscript_record = input_records.get("manuscript", {})
            digest = str(manuscript_record.get("sha256", ""))[:16]
            resolved_project_id = f"project-{digest}"
    if contract_project_id is not None and contract_project_id != resolved_project_id:
        raise typer.BadParameter(
            "Evidence contract project mismatch: "
            f"contract project_id={contract_project_id!r}, requested project_id={resolved_project_id!r}.",
            param_hint="--evidence-contract",
        )
    run_spec_sha256 = _claim_run_spec_sha256(input_records, provider_config)
    owned_artifacts = (
        (*CLAIM_OWNED_ARTIFACTS, APPLIED_CONTRACT_NAME)
        if has_evidence_contract
        else CLAIM_OWNED_ARTIFACTS
    )
    required_artifacts = (
        (*CLAIM_REQUIRED_ARTIFACTS, APPLIED_CONTRACT_NAME)
        if has_evidence_contract
        else CLAIM_REQUIRED_ARTIFACTS
    )
    try:
        return prepare_run_directory(
            out,
            project_id=resolved_project_id,
            mode=normalized_mode,
            run_id=run_id,
            expected_run_id=expected_run_id,
            owned_artifacts=owned_artifacts,
            required_artifacts=required_artifacts,
            workflow_type="claim_harness.audit",
            run_spec_sha256=run_spec_sha256,
        )
    except (ProjectLifecycleError, ValueError) as exc:
        raise typer.BadParameter(str(exc), param_hint="--mode") from exc


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
    mode: str = typer.Option("new", help="Output lifecycle: new, resume, or replace."),
    project_id: Optional[str] = typer.Option(None, help="Stable project identity."),
    run_id: Optional[str] = typer.Option(None, help="Optional run ID for new mode."),
    expected_run_id: Optional[str] = typer.Option(None, help="Existing run ID."),
) -> None:
    """Run the bundled synthetic lab-report audit demo."""
    provider = validate_provider("mock")
    provider_config = resolve_provider_config(provider)
    with TemporaryDirectory(prefix="claimharness-demo-") as temporary:
        manuscript, tables, references = _materialize_demo(Path(temporary))
        _validate_input_paths(manuscript, tables, references)
        run_context = _prepare_output_context(
            out,
            manuscript=manuscript,
            mode=mode,
            project_id=project_id,
            run_id=run_id,
            expected_run_id=expected_run_id,
            input_records=capture_input_records(manuscript, tables, references),
            provider_config=provider_config,
            contract_project_id=None,
            has_evidence_contract=False,
        )
        input_records = capture_input_records(manuscript, tables, references)
        _run_audit(
            manuscript,
            tables,
            references,
            out,
            provider,
            provider_config,
            run_context=run_context,
            input_records=input_records,
        )
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


def _claim_run_spec_sha256(input_records: dict[str, object], provider_config) -> str:
    payload = {
        "workflow_type": "claim_harness.audit",
        "tool_version": __version__,
        "inputs": input_records,
        "provider": _provider_hash_spec(provider_config),
    }
    canonical = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _provider_public_details(provider_config) -> dict[str, object]:
    endpoint_origin = None
    if provider_config.base_url:
        parsed = urlsplit(provider_config.base_url)
        host = parsed.hostname
        if host and ":" in host and not host.startswith("["):
            host = f"[{host}]"
        port = f":{parsed.port}" if parsed.port is not None else ""
        endpoint_origin = (
            f"{parsed.scheme}://{host}{port}"
            if parsed.scheme and host
            else None
        )
    return {
        "name": provider_config.provider,
        "api_style": provider_config.api_style,
        "endpoint_origin": endpoint_origin,
        "json_mode": provider_config.json_mode,
        "model": provider_config.model,
    }


def _provider_hash_spec(provider_config) -> dict[str, object]:
    details = _provider_public_details(provider_config)
    details["endpoint_config_sha256"] = (
        hashlib.sha256(provider_config.base_url.encode("utf-8")).hexdigest()
        if provider_config.base_url
        else None
    )
    return details


def main() -> None:
    app()
