# ClaimHarness 0.4.1 audit core optimization

The audit now separates a numerical conflict from missing evidence and an
unresolved comparison. Findings include the claimed and observed values when
the table context can be bound, plus source row/cell locations and a next action.

## Changes

- Shared `claim_language.py` rules let extraction recognize explicit clinical
  safety assertions and scalar metric statements without requiring an
  improvement verb. Questions, quotations and research intentions are screened
  out by bounded lexical patterns. Document triage alone is not clinical risk.
- Shared `table_relations.py` rules serve retrieval and verification. A matching
  metric is only a candidate until the entity, comparator, table and available
  experiment/split context are resolved. Exact scalar values, from/to or versus
  pairs, direction and absolute/relative changes can be checked. Conflicts retain
  evidence IDs and claim-specific locations.
- Ambiguous rows, absent experiment context, mismatched/missing units, negated
  numerical statements and unsupported numerical qualifiers require human
  clarification. There is no automatic unit conversion or general statistical
  interpretation. These lexical rules remain incomplete.
- Markdown and HTML reports show the finding, reason and next action. Conflict
  locations are visible before expanding details. Reports and diagnostics state
  that extraction completeness is unknown: unlisted sentences are not verified.
- Version 0.4.1 distinguishes these rules in run provenance. Previous 0.4.0 runs
  remain separate runs. Historical sample outputs and showcase captures retain
  their original versions and hashes.

## Reproducible regression checks

```powershell
.venv\Scripts\python.exe scripts\evaluate_gold_set.py --suite all --check --out outputs\synthetic_evaluation
.venv\Scripts\python.exe -m pytest
```

The original seven baseline records were kept unchanged. Before implementing
the new rules, 36 development records and 20 separate challenge records were
frozen. Their byte hashes and provenance are in
`claim_harness/eval_data/corpus_manifest.json`; the tests enforce those hashes.

| Suite | Records | Expected claims | Negative examples | Failed regression checks |
| --- | ---: | ---: | ---: | ---: |
| Baseline | 7 | 7 | 0 | 0 |
| Development | 36 | 24 | 12 | 0 |
| Challenge | 20 | 14 | 6 | 0 |

The upgraded baseline extracts 7/7 expected claims, compared with 5/7 in the
initial project check. Its missed high-risk claims fall from 1/3 to 0/3. Across
the three suites, all 15 expected high-risk claims are routed with human review
required and release blocked; the 18 negative examples produce no claims.

These are **synthetic regression results**, not independent or human validation.
Development and challenge labels were authored by the same implementation agent
and remain provisional. The challenge file is separate and frozen, but that does
not make it a blinded evaluation. The old seven-record set is a regression
baseline, not a general performance estimate.

Each suite has its own `evaluation_metrics.json` and `evaluation_report.md`;
`evaluation_summary.json` indexes all three. `--check` fails for missed/spurious
claims, status discrepancies, or unhandled high-risk claims. The latter includes
missing extraction, risk flags and review/release gates. A missed high-risk
claim may fail both an extraction check and a risk check. Macro-F1 still averages
all five status labels, including zero F1 for absent labels; inspect the per-class
counts rather than comparing that score across differently composed suites.

## Inspect a numerical conflict

```powershell
.venv\Scripts\python.exe -m claim_harness run --manuscript examples/general_demo/manuscript.md --tables examples/general_demo/tables --references examples/general_demo/references.md --out outputs/general_demo_v041 --llm mock
.venv\Scripts\python.exe -m claim_harness view --run outputs/general_demo_v041
```

The four-claim synthetic document-triage demo produces two supported findings,
one unsupported cross-domain assertion, and one numerical conflict requiring
human review. C004 claims precision improves from 0.76 to 0.95; the target row
contains 0.86. The report identifies `results.csv`, data row 2, cell C3.

## Release verification

The release smoke script requires the shared rule modules and all corpus files,
installs from the extracted ZIP into a new environment, runs `pip check`, executes
the packaged demos and all three suites with `--check`, and validates the output
files. A dependency-resolution failure is a failure; tests skip only a concrete
package-index connection failure. Successful local checks do not imply a remote
release, submission, reviewer approval or validation on real manuscripts.

The remaining useful evaluation step is a separately authored, human-reviewed
set of permitted manuscript excerpts, including missed assertions and ambiguous
table contexts. Its labels should be fixed before tuning further rules.
