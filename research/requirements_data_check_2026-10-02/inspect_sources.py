"""Download pinned public text data and inspect it; never call a model.

Run from the repository root. Raw data remains a local, ignored cache.
This is a development data suitability check, not an efficacy experiment.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
SOURCES = {
    "in3": {
        "repo": "OpenBMB/Tell_Me_More",
        "commit": "654fcec4da3b3465536d57b0d1995e8699a5a8f0",
        "files": {
            "README.md": "README.md",
            "LICENSE": "LICENSE",
            "test.jsonl": "data/IN3/test.jsonl",
            "user_records_gpt4.jsonl": "data/user_interaction_records/user_interaction_record_gpt4.jsonl",
        },
    },
    "reqelicitgym": {
        "repo": "jdm4pku/ReqElicitBench",
        "commit": "6ef5dfd92056b4c31157f82be43a293bf4eb441b",
        "files": {"README.md": "README.md", "test.json": "ReqElicitGym/data/test.json"},
    },
    "ccpe": {
        "repo": "google-research-datasets/ccpe",
        "commit": "2c9cd30f33f3a154b5a27d015333679262ff36f5",
        "files": {"README.md": "README.md", "data.json": "data.json"},
    },
    "areas_lab": {
        "repo": "cpengshan/AREAs-Lab",
        "commit": "dd0b2079dd872c2b632376e29068f571fdf208d9",
        "files": {"README.md": "README.md"},
    },
}


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fetch_one(item, expected=None):
    name, local_name, repo, commit, remote_path = item
    path = ROOT / "raw" / name / local_name
    url = f"https://raw.githubusercontent.com/{repo}/{commit}/{remote_path}"
    cached = path.exists()
    if cached:
        data = path.read_bytes()
    else:
        request = Request(url, headers={"User-Agent": "ClaimHarness-public-data-check"})
        with urlopen(request, timeout=30) as response:
            data = response.read(10_000_001)
        if len(data) > 10_000_000:
            raise ValueError(f"Source exceeds the 10 MB per-file limit: {url}")
        if local_name.endswith(".json"):
            json.loads(data)
        elif local_name.endswith(".jsonl"):
            for line in data.decode("utf-8").splitlines():
                if line.strip():
                    json.loads(line)
    record = {
        "dataset": name, "path": path.relative_to(ROOT).as_posix(),
        "url": url, "commit": commit, "bytes": len(data), "sha256": digest(data),
    }
    if expected is not None and record != expected:
        raise ValueError(f"Source mismatch: {record['path']}")
    if not cached:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    return record


def fetch():
    manifest_path = ROOT / "source_manifest.json"
    jobs = [(name, local, spec["repo"], spec["commit"], remote)
            for name, spec in SOURCES.items() for local, remote in spec["files"].items()]
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        expected = {record["path"]: record for record in manifest["files"]}
        paths = {f"raw/{job[0]}/{job[1]}" for job in jobs}
        if set(expected) != paths or len(expected) != len(manifest["files"]):
            raise ValueError("The saved snapshot and configured source list differ.")
        with ThreadPoolExecutor(max_workers=4) as pool:
            records = list(pool.map(lambda item: fetch_one(item, expected[f"raw/{item[0]}/{item[1]}"]), jobs))
        print(json.dumps({"restored_or_cached_files": len(records), "snapshot_unchanged": True}))
        return
    with ThreadPoolExecutor(max_workers=4) as pool:
        records = list(pool.map(fetch_one, jobs))
    manifest = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "purpose": "development_data_suitability_check",
        "model_calls": 0, "new_human_participants": 0,
        "files": records,
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"downloaded_files": len(records), "bytes": sum(r["bytes"] for r in records)}))


def verify():
    manifest = json.loads((ROOT / "source_manifest.json").read_text(encoding="utf-8"))
    for record in manifest["files"]:
        data = (ROOT / record["path"]).read_bytes()
        if len(data) != record["bytes"] or digest(data) != record["sha256"]:
            raise ValueError(f"Source mismatch: {record['path']}")
    print(json.dumps({"verified_files": len(manifest["files"])}))


def inspect():
    verify()
    result = {}
    for name, spec in SOURCES.items():
        for local_name in spec["files"]:
            path = ROOT / "raw" / name / local_name
            if local_name.endswith(".jsonl"):
                values = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
            elif local_name.endswith(".json"):
                values = json.loads(path.read_text(encoding="utf-8"))
            else:
                continue
            entry = {"type": type(values).__name__, "length": len(values)}
            if isinstance(values, list) and values:
                first = values[0]
                entry["item_type"] = type(first).__name__
                if isinstance(first, dict):
                    entry["first_item_fields"] = {
                        key: {"type": type(value).__name__, "length": len(value) if isinstance(value, (list, dict, str)) else None}
                        for key, value in first.items()
                    }
            elif isinstance(values, dict):
                entry["keys"] = list(values)[:30]
            result[f"{name}/{local_name}"] = entry
    (ROOT / "schema_check.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["fetch", "verify", "inspect"])
    args = parser.parse_args()
    {"fetch": fetch, "verify": verify, "inspect": inspect}[args.action]()
