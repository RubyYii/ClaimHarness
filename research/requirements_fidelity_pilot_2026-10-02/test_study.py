import importlib.util
import json
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('requirements_fidelity_study', HERE / 'study.py')
study = importlib.util.module_from_spec(spec)
spec.loader.exec_module(study)


def test_generation_has_no_reference_or_historical_summary_leakage():
    case = study.read(HERE / 'cases.json')[0]
    for stage in ['ordinary', 'provenance']:
        text, _ = study.build_input(case, stage, {})
        payload = json.loads(text.split('\n\n', 1)[1])
        assert set(payload) == {'dialogue_type', 'conversation'}
        assert payload['conversation'] == case['messages']
        assert 'recorded_assistant_summaries' not in text


def test_all_six_judge_orders_balanced_and_all_source_turns_preserved():
    cases = study.read(HERE / 'cases.json')
    source = [json.loads(line) for line in study.SOURCE.read_text('utf-8').splitlines()]
    counts = study.Counter(tuple(c['judge_order']) for c in cases)
    assert len(counts) == 6 and set(counts.values()) == {4}
    assert len(cases) == 24
    for case, row in zip(cases, source):
        assert case['id'] == row['episode_id']
        assert case['messages'] == row['messages']
        by_turn = {m['turn_id']: m for m in case['messages']}
        for point in case['checkpoints']:
            for anchor in point['source']:
                assert anchor['quote'] == by_turn[anchor['turn_id']]['content']


def test_generic_review_uses_actual_draft_only():
    case = study.read(HERE / 'cases.json')[0]
    text, _ = study.build_input(case, 'ordinary_review', {'ordinary': {'brief': 'ACTUAL_DRAFT_SENTINEL'}})
    payload = json.loads(text.split('\n\n', 1)[1])
    assert payload['draft'] == 'ACTUAL_DRAFT_SENTINEL'
    assert 'checkpoints' not in payload
    assert 'provenance' not in payload


def test_quote_check_rejects_invented_evidence_and_wrong_turn():
    case = {'checkpoints': [{'id': 'C1'}], 'messages': [{'turn_id': 2, 'content': 'Maybe I like it.'}]}
    rating = {'checkpoints': [{'id': 'C1', 'status': 'covered', 'response_quote': 'nonexistent', 'reason': 'x'}],
              'issues': [{'kind': 'meaning_change', 'source_turn_id': 9, 'source_quote': 'Maybe I like it.',
                          'response_quote': 'They like it.', 'reason': 'x'}]}
    result = study.assess_rating(case, 'They like it.', rating)
    assert not result['checkpoints'][0]['quote_valid']
    assert not result['issues'][0]['quote_valid']
    assert not study.exact_quote('', 'some words')
    assert study.exact_quote('two  words', 'Here are two\nwords.')


def test_duplicate_or_missing_checkpoints_rejected():
    case = {'checkpoints': [{'id': 'C1'}, {'id': 'C2'}], 'messages': []}
    rating = {'checkpoints': [{'id': 'C1'}, {'id': 'C1'}], 'issues': []}
    with pytest.raises(ValueError, match='checkpoint'):
        study.assess_rating(case, 'any', rating)


def test_frozen_inputs_fail_closed_when_modified(tmp_path, monkeypatch):
    monkeypatch.setattr(study, 'HERE', tmp_path)
    (tmp_path / 'source.txt').write_text('original', encoding='utf-8')
    study.dump(tmp_path / 'freeze.json', {'sha256': {'source.txt': study.sha(tmp_path / 'source.txt')}, 'protected': {}})
    study.verify()
    (tmp_path / 'source.txt').write_text('changed', encoding='utf-8')
    with pytest.raises(ValueError, match='Frozen file changed'):
        study.verify()


def test_schema_rejects_bool_as_turn_id_and_extra_fields():
    with pytest.raises(ValueError):
        study.validate(True, {'type': 'integer'})
    with pytest.raises(ValueError):
        study.validate({'brief': 'ok', 'extra': 'bad'}, study.BRIEF_SCHEMA)
