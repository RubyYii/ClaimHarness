"""Portable launcher; installation binds a separate, locally owned backend."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys


SKILL_ROOT = Path(__file__).resolve().parents[1]
PREFIXES = {"problem-bridge": ["problem_bridge", "task"], "claim-harness": ["claim_harness"]}
PATH_FLAGS = {
    "problem-bridge": {"--workspace", "--request"},
    "claim-harness": {"--manuscript", "--tables", "--references", "--out", "--evidence-contract",
                      "--previous", "--current", "--run", "--mappings", "--rerun", "--workspace"},
}


def runtime() -> tuple[Path, Path]:
    config = SKILL_ROOT / "references" / "runtime.json"
    if config.exists():
        if config.stat().st_size > 16384:
            raise ValueError("Invalid runtime configuration size.")
        value = json.loads(config.read_text(encoding="utf-8"))
        if set(value) != {"schema_version", "repository", "python"} or value["schema_version"] != 1:
            raise ValueError("Unsupported runtime configuration. Reinstall the skill.")
        root, python = Path(value["repository"]), Path(value["python"])
        if not root.is_absolute() or not python.is_absolute():
            raise ValueError("Installed runtime paths must be absolute. Reinstall the skill.")
    else:
        root = SKILL_ROOT.parents[1]
        python = root / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        if not python.is_file():
            python = Path(sys.executable)
    if not all((root / name).is_file() for name in ("pyproject.toml", "problem_bridge/agent_cli.py", "claim_harness/agent_inspect.py")):
        raise ValueError("Backend checkout is missing or too old. Install from an updated ClaimHarness checkout.")
    if not python.is_file():
        raise ValueError("Backend Python is missing. Reinstall with an existing --python interpreter.")
    return root, python


def arguments(values: list[str], cwd: Path) -> list[str]:
    result = list(values)
    flags = PATH_FLAGS[SKILL_ROOT.name]
    index = 0
    while index < len(result):
        flag, separator, value = result[index].partition("=")
        if flag in flags:
            if separator:
                if not value:
                    raise ValueError(f"Missing path after {flag}.")
                result[index] = flag + "=" + str((cwd / Path(value).expanduser()).absolute())
            else:
                index += 1
                if index >= len(result) or result[index].startswith("--") or not result[index]:
                    raise ValueError(f"Missing path after {flag}.")
                result[index] = str((cwd / Path(result[index]).expanduser()).absolute())
        index += 1
    return result


def main() -> int:
    try:
        root, python = runtime()
        values = arguments(sys.argv[1:], Path.cwd())
        command = [str(python), "-X", "utf8"]
        if values == ["--check"]:
            command += ["-c", "import json; from pathlib import Path; import problem_bridge.agent_cli as p; "
                        "import claim_harness.agent_inspect; import claim_harness; "
                        "print(json.dumps({'ready': True, 'version': claim_harness.__version__, "
                        "'repository': str(Path(p.__file__).resolve().parents[1])}))"]
        else:
            command += ["-m", *PREFIXES[SKILL_ROOT.name], *values]
        # No shell interpolation. The host client's normal execution permissions still apply.
        env = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}
        return subprocess.run(command, cwd=root, env=env).returncode
    except (OSError, ValueError, KeyError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=True), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
