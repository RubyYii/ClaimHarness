from pathlib import Path

from claim_harness.claim_extractor import extract_claims
from claim_harness.evidence_retriever import retrieve_evidence
from claim_harness.loader import load_manuscript, load_references, load_tables
from claim_harness.verifier import verify_claims


DEMO_MANUSCRIPT = Path("examples/oocyte_demo/manuscript.md")
DEMO_TABLES = Path("examples/oocyte_demo/tables")
DEMO_REFERENCES = Path("examples/oocyte_demo/references.md")


def test_demo_status_distribution_snapshot():
    sections = load_manuscript(DEMO_MANUSCRIPT)
    claims = extract_claims(sections)
    evidence = retrieve_evidence(
        claims,
        sections,
        load_tables(DEMO_TABLES),
        load_references(DEMO_REFERENCES),
    )
    results = verify_claims(claims, evidence)
    status_counts = {status: 0 for status in ("supported", "weakly_supported", "overclaimed")}
    for result in results:
        if result.status in status_counts:
            status_counts[result.status] += 1

    assert len(claims) == 18
    assert len(evidence) == 26
    assert status_counts == {
        "supported": 15,
        "weakly_supported": 1,
        "overclaimed": 2,
    }
