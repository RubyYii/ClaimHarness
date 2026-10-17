"""Read-only, source-bound inspection for local agent clients."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer

from .comparison import load_audit_run
from .handling import audit_journal


def inspect_command(
    run: Path = typer.Option(..., "--run"),
    workspace: Optional[Path] = typer.Option(None, "--workspace", help="Read annotations from this explicit workspace."),
) -> None:
    """Print saved claims, source text and the observed journal revision as JSON."""
    try:
        audit = load_audit_run(run)
        if audit.integrity == "invalid":
            raise ValueError("; ".join(audit.limitations))
        history = audit_journal(workspace, audit).read() if workspace is not None else None
        value = {"schema_version": 1, "run": audit.ref, "limitations": audit.limitations,
                 "claims": audit.claims, "evidence": audit.evidence,
                 "manuscript": audit.snapshot["manuscript"] if audit.snapshot else None,
                 "offset_units": "zero-based Python Unicode code points; end is exclusive",
                 "journal_revision": history["revision"] if history is not None else None,
                 "history": history}
        typer.echo(json.dumps(value, ensure_ascii=False, indent=2))
    except (OSError, ValueError, RuntimeError) as exc:
        typer.echo(json.dumps({"error": str(exc)}, ensure_ascii=False), err=True)
        raise typer.Exit(code=1) from exc
