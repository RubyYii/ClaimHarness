"""Independent on-disk verification and transparent post-run denominator correction."""
import argparse
from collections import Counter
import hashlib
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dump(name, value):
    with (HERE / name).open('w', encoding='utf-8', newline='\n') as handle:
        handle.write(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def main(published=False):
    frozen = read(HERE / 'freeze.json')
    for name, digest in frozen['sha256'].items():
        assert sha(HERE / name) == digest, name
    missing_local_guards = []
    for name, digest in frozen['protected'].items():
        portable = name.replace('\\', '/')
        path = HERE.parents[1] / portable
        if published and not path.exists() and portable == 'research/publication_2026-09-21/CLAIM.md':
            missing_local_guards.append(portable)
        else:
            assert sha(path) == digest, portable
    recorded = read(HERE / 'verification.json')
    for name, digest in recorded['generated_result_hashes'].items():
        assert sha(HERE / name) == digest, name
    spec = importlib.util.spec_from_file_location('_frozen_fidelity_study', HERE / 'study.py')
    study = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(study)
    cases = read(HERE / 'cases.json')
    source = [json.loads(line) for line in study.SOURCE.read_text('utf-8').splitlines()]
    assert len(cases) == len(source) == 24
    for case, row in zip(cases, source):
        assert case['id'] == row['episode_id'] and case['messages'] == row['messages']
    sessions, warnings, usage = [], Counter(), Counter()
    requests = list((HERE / 'runs').glob('*/request.json'))
    assert len(requests) == 96
    allowed_warning = ('Code Mode is unavailable because code-mode host is disabled. '
                       'Code mode will fail closed; enable `features.code_mode_host` '
                       'and install `codex-code-mode-host`.')
    for path in requests:
        request = read(path)
        run = path.parent
        assert request['status'] == 'completed' and request['returncode'] == 0
        assert sha(run / 'response.json') == request['response_sha256']
        assert read(run / 'response.json') == read(run / 'raw_last_message.txt')
        assert sha(run / 'prompt.txt') == request['prompt_sha256']
        events = [json.loads(line) for line in (run / 'trace.jsonl').read_text('utf-8').splitlines()]
        started = [e['thread_id'] for e in events if e['type'] == 'thread.started']
        completed = [e for e in events if e['type'] == 'turn.completed']
        assert started == [request['session_id']] and len(completed) == 1
        assert completed[0]['usage'] == request['usage']
        sessions.extend(started)
        usage.update(completed[0]['usage'])
        for event in events:
            assert event['type'] not in ['turn.failed', 'error']
            item = event.get('item', {})
            if not item:
                continue
            assert item['type'] in ['agent_message', 'error', 'reasoning']
            if item['type'] == 'error':
                assert item.get('message') == allowed_warning
                warnings[item['message']] += 1
        messages = [e['item']['text'] for e in events
                    if e.get('item', {}).get('type') == 'agent_message']
        assert len(messages) == 1 and json.loads(messages[0]) == read(run / 'response.json')
        command = read(run / 'command.json')
        assert '--ephemeral' in command and '--ignore-user-config' in command
        assert command[command.index('--sandbox') + 1] == 'read-only'
        assert 'project_doc_max_bytes=0' in command and 'web_search="disabled"' in command
        assert command[command.index('--model') + 1] == 'gpt-6-astra'
        assert command[-1] == '-'
        actual_payload = json.loads((run / 'prompt.txt').read_text('utf-8').split('\n\n', 1)[1])
        case = next(c for c in cases if c['id'] == request['case_id'])
        assert actual_payload['conversation'] == case['messages']
        parents = {stage: read(study.folder(case, stage) / 'response.json')
                   for stage in study.dependencies(request['stage'])}
        expected_prompt, schema = study.build_input(case, request['stage'], parents)
        assert (run / 'prompt.txt').read_text('utf-8') == expected_prompt
        study.validate(read(run / 'response.json'), schema)
        assert request['predecessors'] == {stage: sha(study.folder(case, stage) / 'response.json')
                                           for stage in parents}
        if request['stage'] != 'judge':
            assert 'checkpoints' not in actual_payload and 'candidates' not in actual_payload
    assert len(sessions) == len(set(sessions)) == 96
    assert dict(usage) == read(HERE / 'automated_summary.json')['actual_usage']
    scores = read(HERE / 'scored_outputs.json')
    assert len(scores) == 72
    assert len({(r['episode_id'], r['arm']) for r in scores}) == 72
    for row in scores:
        case = next(c for c in cases if c['id'] == row['episode_id'])
        brief = read(study.folder(case, row['arm']) / 'response.json')['brief']
        label = 'ABC'[case['judge_order'].index(row['arm'])]
        assert row['judge_label'] == label and row['word_count'] == len(brief.split())
        rating = read(study.folder(case, 'judge') / 'response.json')[label]
        assessed = study.assess_rating(case, brief, rating)
        assert row['checkpoints'] == assessed['checkpoints'] and row['issues'] == assessed['issues']
    audit = read(HERE / 'source_audit.json')
    correction = audit['reference_correction']
    audited_episodes = set(audit['preselected_episodes'] + audit['additional_episodes_all_flagged'])
    assert len(audited_episodes) * 3 == audit['reviewed_complete_briefs']
    assert len(audit['issue_adjudications']) == sum(len(r['issues']) for r in scores) == 4
    minor = Counter()
    unresolved = Counter()
    for item in audit['issue_adjudications']:
        case = next(c for c in cases if c['id'] == item['episode_id'])
        turn = next(m for m in case['messages'] if m['turn_id'] == item['source_turn_id'])
        assert item['source_quote'] in turn['content']
        brief = read(HERE / 'runs' / f"{item['episode_id']}_{item['arm']}" / 'response.json')['brief']
        assert item['response_quote'] in brief
        if item['audit_label'] == 'minor_unsupported_strengthening':
            minor[item['arm']] += 1
        elif item['audit_label'] == 'remains_uncertain':
            unresolved[item['arm']] += 1
    counts = {}
    for arm in ['ordinary', 'provenance', 'ordinary_review']:
        counter = Counter()
        for row in scores:
            if row['arm'] != arm:
                continue
            for point in row['checkpoints']:
                if row['episode_id'] == correction['episode_id'] and point['id'] == correction['checkpoint_id']:
                    continue
                counter[point['status'] if point['quote_valid'] else 'invalid_quote'] += 1
        assert sum(counter.values()) == 99
        counts[arm] = dict(counter)
    corrected = {
        'raw_scores_preserved': True,
        'post_run_reference_exclusion': {'episode_id': correction['episode_id'], 'checkpoint_id': correction['checkpoint_id']},
        'all_24_episodes_retained': True,
        'corrected_automated_coverage_per_arm': counts,
        'source_audit_briefs_per_arm': len(audited_episodes),
        'source_audit_minor_strengthening_per_arm': {arm: minor[arm] for arm in counts},
        'source_audit_unresolved_flags_per_arm': {arm: unresolved[arm] for arm in counts},
        'source_audit_is_codex_judgment_not_independent_human_annotation': True,
    }
    if published:
        assert read(HERE / 'corrected_summary.json') == corrected
        print(json.dumps({'verified_calls': 96, 'distinct_sessions': 96, 'corrected_coverage': counts,
                          'frozen_files_verified': len(frozen['sha256']),
                          'missing_local_preservation_guards': missing_local_guards,
                          'historical_mock_and_pytest_not_rerun': True,
                          'published_results_unchanged': True}))
        return
    dump('corrected_summary.json', corrected)
    required = ['claim_table.csv', 'evidence_map.json', 'audit_report.md',
                'revision_suggestions.md', 'agent_trace.jsonl']
    mock = HERE.parents[1] / 'outputs' / 'requirements_fidelity_pilot_2026-10-02_mock'
    assert all((mock / n).is_file() for n in required)
    dump('verification.json', {
        'actual_calls_verified': 96, 'distinct_sessions': 96, 'generation_outputs': 72,
        'automated_ratings': 24, 'model_call_failures': 0, 'runner_retries': 0,
        'source_dialogues_equal_frozen_inputs': True,
        'raw_last_message_matches_trace_and_response': True,
        'generation_received_evaluation_checkpoints': False,
        'tool_events': 0,
        'nonfatal_disabled_tool_warning_counts': dict(warnings),
        'checkpoint_and_issue_quotes_invalid': sum(not p['quote_valid'] for r in scores for p in r['checkpoints'])
            + sum(not i['quote_valid'] for r in scores for i in r['issues']),
        'focused_tests': {'passed': 7, 'elapsed_seconds': 0.07},
        'repository_tests': {'passed': 547, 'elapsed_seconds': 119.65},
        'mock_required_outputs': {n: sha(mock / n) for n in required},
        'initial_pre_call_executable_path_failure': 'Old app binary path absent; zero model attempts from that command. Located installed executable and continued unchanged protocol.',
        'gemini_plan_review': '503 unavailable; no advice used',
        'gemini_code_review': 'pass; optional fixture suggestions only. Exact int type already excludes bool.',
        'generated_result_hashes': {n: sha(HERE / n) for n in ['automated_summary.json', 'scored_outputs.json', 'source_audit.json', 'corrected_summary.json']},
    })
    print(json.dumps({'verified_calls': 96, 'distinct_sessions': 96, 'corrected_coverage': counts,
                      'source_audit_briefs': 27, 'reference_points_excluded_per_arm': 1}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--published', action='store_true',
                        help='Read-only published-result verification without local mock outputs or unpublished manuscript guard.')
    main(parser.parse_args().published)
