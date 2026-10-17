"""Install the two portable skills without replacing unrelated or edited files."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import uuid


REPOSITORY = Path(__file__).resolve().parents[1]
SKILLS = ("problem-bridge", "claim-harness")
SOURCE_FILES = ("SKILL.md", "agents/openai.yaml", "references/commands.md", "scripts/run.py")
MANIFEST = ".claimharness-install.json"
OWNER = "ClaimHarness agent skills"


def safe_path(path: Path) -> Path:
    """Do not inspect, replace or remove through symlinks or Windows junctions."""
    path = path.absolute()
    for item in (path, *path.parents):
        try:
            info = item.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400):
            raise ValueError(f"Linked paths are not supported: {item}")
    return path


def inventory(directory: Path) -> dict[str, str]:
    result = {}
    for path in directory.rglob("*"):
        safe_path(path)
        if path.is_file() and path.relative_to(directory).as_posix() != MANIFEST:
            result[path.relative_to(directory).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def verify_destination(destination: Path, upgrade: bool) -> None:
    safe_path(destination)
    if not destination.exists():
        return
    if not destination.is_dir() or not (destination / MANIFEST).is_file():
        raise ValueError(f"Refusing to overwrite an unmanaged skill: {destination}")
    safe_path(destination / MANIFEST)
    manifest = json.loads((destination / MANIFEST).read_text(encoding="utf-8"))
    if manifest.get("owner") != OWNER or manifest.get("schema_version") != 1:
        raise ValueError(f"Unknown installation manifest: {destination}")
    if inventory(destination) != manifest.get("files"):
        raise ValueError(f"Skill has local changes; preserve them before reinstalling: {destination}")
    if not upgrade:
        raise ValueError(f"Already installed; use --upgrade for this unchanged managed skill: {destination}")


def payload(skill: str, python: Path) -> dict[str, bytes]:
    result = {}
    for name in SOURCE_FILES:
        path = safe_path(REPOSITORY / "skills" / skill / name)
        result[name] = path.read_bytes()
    result["references/runtime.json"] = (json.dumps({"schema_version": 1, "repository": str(REPOSITORY),
                                                    "python": str(python)}, indent=2) + "\n").encode("utf-8")
    return result


def remove_owned_temporary(path: Path, parent: Path) -> None:
    safe_path(path)
    if path.parent != parent or not path.name.startswith(".claimharness-"):
        raise ValueError("Refusing cleanup outside the installer staging directory.")
    if path.exists():
        inventory(path)  # Check descendants before recursive removal.
        shutil.rmtree(path)


def install(destination: Path, files: dict[str, bytes], upgrade: bool) -> None:
    verify_destination(destination, upgrade)
    destination.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".claimharness-stage-", dir=destination.parent))
    backup = destination.parent / (".claimharness-backup-" + uuid.uuid4().hex)
    moved = False
    try:
        for name, content in files.items():
            path = stage / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        (stage / MANIFEST).write_text(json.dumps({"owner": OWNER, "schema_version": 1,
                                                 "files": inventory(stage)}, indent=2) + "\n", encoding="utf-8")
        # Recheck just before replacement, including edits during preparation.
        verify_destination(destination, upgrade)
        if destination.exists():
            destination.rename(backup)
            moved = True
        try:
            stage.rename(destination)
        except OSError:
            if moved:
                backup.rename(destination)
                moved = False
            raise
        if moved:
            remove_owned_temporary(backup, destination.parent)
    finally:
        remove_owned_temporary(stage, destination.parent)


def check_runtime(python: Path) -> None:
    result = subprocess.run([str(python), "-X", "utf8", "-c",
                             "from pathlib import Path; import problem_bridge.agent_cli as p; "
                             "import claim_harness.agent_inspect; print(Path(p.__file__).resolve().parents[1])"],
                            cwd=REPOSITORY, capture_output=True, text=True, encoding="utf-8",
                            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
    if result.returncode or result.stdout.strip() != str(REPOSITORY):
        raise ValueError("Backend dependencies are unavailable in the selected Python. "
                         "Install this checkout with pip install -c requirements/constraints.txt -e .\n" + result.stderr)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--client", required=True, choices=("codex", "claude", "both"))
    parser.add_argument("--scope", choices=("user", "project"), default="user")
    parser.add_argument("--project", type=Path, help="Required target directory with --scope project.")
    parser.add_argument("--python", type=Path, default=Path(sys.executable), help="Python with the backend dependencies installed.")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--upgrade", action="store_true")
    args = parser.parse_args(argv)
    try:
        if (args.scope == "project") != (args.project is not None):
            raise ValueError("Pass --project only and always with --scope project.")
        base = safe_path(args.project.expanduser() if args.project else Path.home())
        if not base.is_dir():
            raise ValueError("The target home/project directory must already exist.")
        python = args.python.expanduser().absolute()
        if not python.is_file():
            raise ValueError("--python must name an existing interpreter file.")
        clients = ("codex", "claude") if args.client == "both" else (args.client,)
        plan = [(base / (".agents" if client == "codex" else ".claude") / "skills" / skill, payload(skill, python))
                for client in clients for skill in SKILLS]
        # All destinations are checked before the first write, including dry runs.
        for destination, _ in plan:
            verify_destination(destination, args.upgrade)
        check_runtime(python)
        for destination, files in plan:
            if not args.dry_run:
                install(destination, files, args.upgrade)
            print(json.dumps({"action": "would_install" if args.dry_run else "installed", "path": str(destination)}))
        return 0
    except (OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
