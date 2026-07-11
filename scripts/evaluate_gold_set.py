"""Run the deterministic ClaimHarness synthetic evaluation from the repository root."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from claim_harness.evaluation import (  # noqa: E402
    default_gold_path,
    evaluate_gold_set,
    write_evaluation_outputs,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Evaluate the deterministic ClaimHarness pipeline on a versioned synthetic gold set."
    )
    parser.add_argument(
        "--gold",
        type=Path,
        default=default_gold_path(),
        help="Path to a JSONL gold set (default: packaged synthetic set).",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("outputs") / "synthetic_evaluation",
        help="Output directory for evaluation_metrics.json and evaluation_report.md.",
    )
    parser.add_argument(
        "--evidence-k",
        type=int,
        nargs="+",
        default=[1, 3, 5],
        help="Positive retrieval cutoffs used for evidence recall.",
    )
    args = parser.parse_args()

    metrics = evaluate_gold_set(args.gold, evidence_ks=tuple(args.evidence_k))
    json_path, markdown_path = write_evaluation_outputs(metrics, args.out)
    print(f"Wrote {json_path}")
    print(f"Wrote {markdown_path}")
    print(
        "Claim F1={:.6f}; status macro-F1={:.6f}; high-risk miss rate={:.6f}".format(
            metrics["claim_extraction"]["f1"],
            metrics["status"]["macro_f1"],
            metrics["risk"]["high_risk_miss_rate"],
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
