import json
import hashlib
from pathlib import Path

import pandas as pd
import pytest

from claim_harness.claim_extractor import extract_claims
from claim_harness.evaluation import (
    evaluate_gold_set, load_gold_records, regression_failure_count,
    run_current_pipeline, suite_gold_path,
)
from claim_harness.evidence_retriever import retrieve_evidence
from claim_harness.schemas import ManuscriptSection
from claim_harness.verifier import verify_claims


DEVELOPMENT = Path('claim_harness/eval_data/development_claims.jsonl')


@pytest.mark.parametrize('record', load_gold_records(DEVELOPMENT), ids=lambda r: r['record_id'])
def test_development_claim_boundaries(record):
    predictions = run_current_pipeline([record])[record['record_id']]
    gold = record['gold_claims']
    assert len(predictions) == len(gold)
    for actual, expected in zip(predictions, gold):
        assert actual['text'] == expected['text']
        assert actual['status'] == expected['status']
        assert (actual['risk_level'] == 'high') == expected['high_risk']
        if expected['high_risk'] or expected['status'] == 'needs_human_review':
            assert actual['human_review_required'] is True
            assert actual['release_allowed'] is False


def test_contradiction_contains_wrong_value_observation_and_exact_cell(tmp_path):
    sections = [ManuscriptSection(name='Summary', text='Alpha improves precision from 0.76 to 0.95.', start_line=1, content_start_line=1)]
    frame = pd.DataFrame([{'model':'Beta','precision':0.76}, {'model':'Alpha','precision':0.86}])
    frame.attrs['source_file'] = 'results.csv'
    claims = extract_claims(sections)
    evidence = retrieve_evidence(claims, sections, {'metrics':frame}, '')
    result = verify_claims(claims, evidence)[0]
    assert result.status == 'needs_human_review'
    assert result.contradicting_evidence_ids
    conflicts = [item for item in evidence if item.evidence_id in result.contradicting_evidence_ids]
    reasons = ' '.join(item.claim_link_reasons[claims[0].claim_id] for item in conflicts)
    assert '0.95' in reasons and '0.86' in reasons and 'precision' in reasons
    cells = [cell for item in conflicts for cell in item.claim_link_locators[claims[0].claim_id].cells]
    assert any(cell.cell == 'B3' and cell.value == '0.86' for cell in cells)
    from claim_harness.report_generator import write_outputs
    from claim_harness.report_viewer import _render_claim_table
    import csv

    write_outputs(tmp_path, claims, evidence, [result])
    report = (tmp_path / 'audit_report.md').read_text(encoding='utf-8')
    assert 'Next action:' in report and 'Finding: Evidence conflict' in report
    assert 'Extraction completeness: unknown' in report
    assert '0.95' in report and '0.86' in report and 'B3' in report
    with (tmp_path / 'claim_table.csv').open(encoding='utf-8', newline='') as handle:
        claim_rows = list(csv.DictReader(handle))
    links = json.loads((tmp_path / 'evidence_map.json').read_text(encoding='utf-8'))
    rendered = _render_claim_table(claim_rows, links['claims'])
    visible_before_details = rendered.split('<details class="row-details">')[0]
    assert 'Evidence conflict' in visible_before_details
    assert 'Next action:' in visible_before_details and 'B3' in visible_before_details
    diagnostics = json.loads((tmp_path / 'audit_diagnostics.json').read_text(encoding='utf-8'))
    assert diagnostics['extraction_coverage']['completeness'] == 'unknown'
    assert diagnostics['extraction_coverage']['recall'] is None


def test_challenge_cases_are_separate_frozen_synthetic_records():
    development = load_gold_records(DEVELOPMENT)
    challenge = load_gold_records('claim_harness/eval_data/challenge_claims.jsonl')
    assert not {r['record_id'] for r in development} & {r['record_id'] for r in challenge}
    assert len(development) >= 30 and len(challenge) >= 20
    assert all(r['label_status'] == 'provisional_synthetic_not_human_validated' for r in development + challenge)
    manifest = json.loads(DEVELOPMENT.with_name('corpus_manifest.json').read_text(encoding='utf-8'))
    for name, frozen in manifest['files'].items():
        assert hashlib.sha256(DEVELOPMENT.with_name(name).read_bytes()).hexdigest() == frozen['sha256']


def test_frozen_challenge_regression_and_risk_gates():
    metrics = evaluate_gold_set(suite_gold_path('challenge'))
    assert regression_failure_count(metrics) == 0
    assert metrics['negative_examples']['false_positive_claims'] == 0
    assert metrics['risk']['unhandled_high_risk_claims'] == 0


@pytest.mark.parametrize(('text','rows'), [
    ('Gamma achieved precision of 0.86.', [{'model':'Alpha','precision':0.86}]),
    ('Precision was 0.86.', [{'model':'Alpha','precision':0.86},{'model':'Beta','precision':0.86}]),
    ('Alpha achieved precision of 0.86 on test.', [{'model':'Alpha','split':'train','precision':0.86}]),
    ('Alpha achieved latency of 50.', [{'model':'Alpha','latency':50,'unit':'ms'}]),
    ('Alpha achieved latency of 50 ms.', [{'model':'Alpha','latency':50}]),
    ('Alpha achieved precision of at least 0.86.', [{'model':'Alpha','precision':0.86}]),
])
def test_ambiguous_or_unparsed_measurements_cannot_be_supported(text, rows):
    sections=[ManuscriptSection(name='Summary',text=text,start_line=1)]
    claims=extract_claims(sections)
    evidence=retrieve_evidence(claims,sections,{'metrics':pd.DataFrame(rows)},'')
    result=verify_claims(claims,evidence)[0]
    assert result.status == 'needs_human_review'
    assert not result.release_allowed
    assert not result.contradicting_evidence_ids


def test_metric_header_can_supply_an_explicit_matching_unit():
    sections=[ManuscriptSection(name='Summary',text='Alpha achieved latency of 50 ms.',start_line=1)]
    claims=extract_claims(sections)
    evidence=retrieve_evidence(claims,sections,{'metrics':pd.DataFrame([{'model':'Alpha','latency_ms':50}])},'')
    assert verify_claims(claims,evidence)[0].status == 'supported'


def test_document_triage_is_not_automatically_a_clinical_claim():
    sections=[ManuscriptSection(name='Summary',text='Alpha improves document triage accuracy from 0.70 to 0.80.',start_line=1)]
    claims=extract_claims(sections)
    assert claims[0].claim_type == 'performance_claim'
    assert verify_claims(claims,[])[0].risk_level == 'low'


@pytest.mark.parametrize('measurement', ['86%', '86 percent', '86 PER CENT'])
def test_equivalent_percentage_spellings_do_not_create_false_conflicts(measurement):
    sections = [ManuscriptSection(
        name='Results', text=f'Alpha achieved precision of {measurement}.', start_line=1,
    )]
    claims = extract_claims(sections)
    table = pd.DataFrame([{'model': 'Alpha', 'precision': 0.86}])
    evidence = retrieve_evidence(claims, sections, {'metrics': table}, '')
    result = verify_claims(claims, evidence)[0]
    assert result.status == 'supported'
    assert not result.contradicting_evidence_ids
