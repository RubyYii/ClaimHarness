"""Run the deterministic ClaimHarness synthetic evaluation from the repository root."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from claim_harness.evaluation import (  # noqa: E402
    default_gold_path,
    evaluate_gold_set,
    suite_gold_path,
    regression_failure_count,
    write_evaluation_outputs,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Evaluate the deterministic ClaimHarness pipeline on a versioned synthetic gold set."
    )
    parser.add_argument(
        "--gold",
        type=Path,
        default=None,
        help="Path to a JSONL gold set (default: packaged synthetic set).",
    )
    parser.add_argument('--suite', choices=['baseline','development','challenge','all'], default='baseline', help='Versioned synthetic suite, or all three separately.')
    parser.add_argument('--check', action='store_true', help='Return nonzero if any frozen expected claim/status differs. This is a synthetic regression gate.')
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
    if args.gold is not None and args.suite != 'baseline':
        parser.error('--gold cannot be combined with a non-default --suite')

    if args.suite == 'all':
        summary = {'boundary': 'Synthetic regression only. Development and challenge labels are provisional and not human validated; the challenge set was authored by the same implementation agent.', 'suites': {}}
        for suite in ('baseline', 'development', 'challenge'):
            metrics = evaluate_gold_set(suite_gold_path(suite), evidence_ks=tuple(args.evidence_k))
            write_evaluation_outputs(metrics, args.out / suite)
            summary['suites'][suite] = {'records': metrics['record_count'], 'claims': metrics['claim_extraction']['gold'], 'regression_failures': regression_failure_count(metrics), 'gold_set_sha256': metrics['gold_set_sha256'], 'risk': metrics['risk'], 'negative_examples': metrics['negative_examples']}
        args.out.mkdir(parents=True, exist_ok=True)
        (args.out/'evaluation_summary.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
        print(json.dumps(summary, indent=2))
        return 1 if args.check and any(item['regression_failures'] for item in summary['suites'].values()) else 0

    metrics = evaluate_gold_set(args.gold or suite_gold_path(args.suite), evidence_ks=tuple(args.evidence_k))
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
    return 1 if args.check and regression_failure_count(metrics) else 0


if __name__ == "__main__":
    raise SystemExit(main())
