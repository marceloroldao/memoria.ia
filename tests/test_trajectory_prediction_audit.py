import copy
import os
from pathlib import Path
import sys
import json
import subprocess

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import trajectory_prediction_audit as audit
from mobile_region_replay import NativeProbe
from trajectory_feedback_transfer_stress import workload
from trajectory_question_frame_probe import collect, persist
from trajectory_route_relation_probe import read


@pytest.fixture
def library():
    path = Path(os.environ.get('MEMORIA_NATIVE_LIBRARY', 'build/trajectory-native/libmemoria_mobile.so'))
    if not path.exists():
        if 'MEMORIA_NATIVE_LIBRARY' in os.environ:
            pytest.fail('Explicit native BDR library is missing')
        pytest.skip('Native integration runs in the dedicated pinned-BDR job')
    return path


@pytest.fixture
def case(library, tmp_path):
    rows, region, queries = workload(20270117, 'brackets', 'minimal')
    native = NativeProbe(library, tmp_path)
    persist(native, rows)
    query = queries[0]['text']
    first = audit.forecast(native, region, query, 'f1', 'forecaster')
    try:
        yield native, rows, region, query, first
    finally:
        native.close()


def later(native, region, text, source='later', kind='user_turn'):
    row = dict(hierarchy_id=region, source_id=source,
               sequence=1 + max((r['sequence'] for r in collect(native, [region])), default=-1),
               text=text, source_kind=kind)
    persist(native, [row])
    return row


def test_freezing_hypotheses_does_not_ingest_query_or_candidate_outputs(case):
    native, rows, region, query, first = case
    assert collect(native, [region]) == rows
    assert query not in {r['text'] for r in rows}
    assert len(first['event']['receipt']['view']['candidates']) == 2
    result = audit.reconcile(native, region, 'f1')
    assert result['status'] == 'PENDING' and not result['learning_applied']
    assert result['answer'] is None and not result['qualified']


def test_later_match_is_persisted_without_choosing_a_fact(case):
    native, _, region, _, first = case
    text = first['event']['receipt']['view']['candidates'][0]['text']
    row = later(native, region, text)
    before = collect(native, [region])
    audit.observe_outcome(native, region, 'f1', 'o1', 'observer', audit.address(row))
    result = audit.reconcile(native, region, 'f1')
    assert result['status'] == 'MATCHES_ONE_OF_MULTIPLE'
    assert collect(native, [region]) == before
    assert result['provenance_independence'] == 'NOT_ESTABLISHED'
    assert not result['caller_reliability_estimated'] and not result['selection_used']
    native.reopen()
    assert audit.reconcile(native, region, 'f1') == result


def test_later_observation_must_be_explicitly_linked(case):
    native, _, region, _, first = case
    later(native, region, first['event']['receipt']['view']['candidates'][0]['text'])
    assert audit.reconcile(native, region, 'f1')['status'] == 'PENDING'


def test_new_recoverable_content_never_rewrites_the_frozen_forecast(case):
    native, _, region, query, first = case
    old = first['event']['receipt']['view']['candidates'][0]['text']
    novel = old[:-1] + '9' + old[-1]
    row = later(native, region, novel)
    assert any(c['text'] == novel for c in read(collect(native, [region]), region, query)['candidates'])
    audit.observe_outcome(native, region, 'f1', 'o1', 'observer', audit.address(row))
    assert audit.reconcile(native, region, 'f1')['status'] == 'OUTSIDE_FROZEN_SET'
    retry = audit.forecast(native, region, query, 'f1', 'forecaster')
    assert retry['status'] == 'EXACT_REPLAY' and retry['event'] == first['event']
    assert all(c['text'] != novel for c in retry['event']['receipt']['view']['candidates'])


@pytest.mark.parametrize('kind', ['old', 'generated', 'missing', 'foreign'])
def test_invalid_observation_links_do_not_append(case, kind):
    native, rows, region, _, first = case
    if kind == 'old':
        pointer = audit.address(next(r for r in rows if r['source_id'] == 'expected-anchor'))
    else:
        row = later(native, region, first['event']['receipt']['view']['candidates'][0]['text'],
                    kind='assistant_generated' if kind == 'generated' else 'user_turn')
        pointer = audit.address(row)
        if kind == 'missing':
            pointer[2] += 1000
        if kind == 'foreign':
            pointer[0] += '-foreign'
    before = audit.journal(native, region)
    with pytest.raises(ValueError):
        audit.observe_outcome(native, region, 'f1', 'bad', 'observer', pointer)
    assert audit.journal(native, region) == before


def test_divergent_later_observations_are_not_resolved_by_repetition(case):
    native, _, region, _, first = case
    candidates = first['event']['receipt']['view']['candidates']
    for i, text in enumerate([candidates[0]['text']] * 4 + [candidates[1]['text']]):
        row = later(native, region, text, source='later-' + str(i))
        audit.observe_outcome(native, region, 'f1', 'o' + str(i), 'observer', audit.address(row))
    result = audit.reconcile(native, region, 'f1')
    assert result['status'] == 'DIVERGENT_LATER_OBSERVATIONS'
    assert result['distinct_later_contents'] == 2 and len(result['comparisons']) == 5
    assert not result['qualified'] and result['answer'] is None


def test_idempotent_outcome_and_duplicate_occurrence_rejection(case):
    native, _, region, _, first = case
    row = later(native, region, first['event']['receipt']['view']['candidates'][0]['text'])
    audit.observe_outcome(native, region, 'f1', 'o1', 'observer', audit.address(row))
    log = audit.journal(native, region)
    assert audit.observe_outcome(native, region, 'f1', 'o1', 'observer', audit.address(row))['status'] == 'EXACT_REPLAY'
    with pytest.raises(ValueError, match='already linked'):
        audit.observe_outcome(native, region, 'f1', 'o2', 'observer', audit.address(row))
    with pytest.raises(ValueError, match='reused'):
        audit.observe_outcome(native, region, 'f1', 'o1', 'other-observer', audit.address(row))
    assert audit.journal(native, region) == log


def test_forecast_identity_cannot_silently_change_request(case):
    native, _, region, query, _ = case
    before = audit.journal(native, region)
    for new_query, actor in ((query + '!', 'forecaster'), (query, 'other')):
        with pytest.raises(ValueError, match='reused'):
            audit.forecast(native, region, new_query, 'f1', actor)
    assert audit.journal(native, region) == before


def test_missing_or_control_scope_forecasts_reject(case):
    native, _, region, query, _ = case
    with pytest.raises(ValueError, match='not found'):
        audit.observe_outcome(native, region, 'missing', 'o', 'observer', [region, 's', 99])
    with pytest.raises(ValueError, match='not found'):
        audit.reconcile(native, region + '-other', 'f1')
    with pytest.raises(ValueError, match='learning region'):
        audit.forecast(native, audit.field(region), query, 'f2', 'forecaster')


def test_unavailable_historical_prefix_never_yields_a_verified_match(case, monkeypatch):
    native, _, region, _, first = case
    row = later(native, region, first['event']['receipt']['view']['candidates'][0]['text'])
    audit.observe_outcome(native, region, 'f1', 'o', 'observer', audit.address(row))
    original = audit.collect
    monkeypatch.setattr(audit, 'collect', lambda n, scopes: original(n, scopes)[1:])
    result = audit.reconcile(native, region, 'f1')
    assert result['status'] == 'UNVERIFIABLE_HISTORY'
    assert not result['historical_prefix_verified'] and not result['qualified']


def test_codec_preserves_literal_operation_and_actor_identities(case):
    native, _, region, query, _ = case
    fid, actor = 'f-"é"\n\\literal', 'ator-"é"\n\\literal'
    original = audit.forecast(native, region, query, fid, actor)
    native.reopen()
    retry = audit.forecast(native, region, query, fid, actor)
    assert retry['event'] == original['event'] and retry['status'] == 'EXACT_REPLAY'


def test_journal_rejects_corrupted_receipt(case, monkeypatch):
    native, _, region, _, _ = case
    original = audit.journal(native, region)[0]
    changed = copy.deepcopy(original['event'])
    changed['receipt']['query'] += '!'
    # Exercise the journal's validation with an altered decoded native row.
    import base64
    from trajectory_feedback_ledger_probe import canonical
    import trajectory_window_consistency_probe
    real_snapshot = trajectory_window_consistency_probe.window_snapshot
    def altered_snapshot(n, scope):
        result = real_snapshot(n, scope)
        if scope == audit.field(region):
            result = copy.deepcopy(result)
            result['rows'][0]['text'] = audit.CODEC + base64.b64encode(canonical(changed).encode()).decode()
        return result
    monkeypatch.setattr(trajectory_window_consistency_probe, 'window_snapshot', altered_snapshot)
    with pytest.raises(ValueError, match='receipt'):
        audit.reconcile(native, region, 'f1')


def test_both_seed_reports_keep_recurrence_distinct_from_confirmation(library):
    for seed in (20270117, 20270118):
        result = audit.probe(library, seed)
        assert result['integrity_status'] == 'PASS'
        assert result['integrity_passed'] == result['integrity_total'] == 67
        assert result['statuses']['single_match'] == 'MATCHES_ONLY_CANDIDATE'
        assert result['statuses']['ambiguous_match'] == result['statuses']['self_copy_as_user'] == 'MATCHES_ONE_OF_MULTIPLE'
        assert result['statuses']['outside_set'] == 'OUTSIDE_FROZEN_SET'
        assert result['statuses']['generated'] == result['statuses']['old_occurrence'] == 'PENDING'
        assert result['statuses']['empty_set'] == 'NO_CANDIDATES_AT_CUTOFF'


def test_native_journal_and_comparison_survive_three_separate_processes(library, tmp_path):
    driver = '''
import sys,json
from pathlib import Path
sys.path.insert(0,sys.argv[1])
from mobile_region_replay import NativeProbe
from trajectory_feedback_transfer_stress import workload
from trajectory_question_frame_probe import collect,persist
from trajectory_prediction_audit import forecast,journal,observe_outcome,reconcile,address
n=NativeProbe(Path(sys.argv[2]),Path(sys.argv[3]))
rows,region,queries=workload(20270117,'brackets','minimal')
try:
    if sys.argv[4]=='start':
        persist(n,rows)
        forecast(n,region,queries[0]['text'],'f1','forecaster')
    elif sys.argv[4]=='outcome':
        frozen=journal(n,region)[0]['event']['receipt']
        row=dict(hierarchy_id=region,source_id='later-subprocess',
                 sequence=max(r['sequence'] for r in collect(n,[region]))+1,
                 text=frozen['view']['candidates'][0]['text'],source_kind='user_turn')
        persist(n,[row])
        observe_outcome(n,region,'f1','o1','observer',address(row))
    print(json.dumps(reconcile(n,region,'f1'),ensure_ascii=False))
finally:
    n.close()
'''
    scripts = Path(__file__).resolve().parents[1] / 'scripts'
    def run(mode):
        result = subprocess.run([sys.executable, '-c', driver, str(scripts), str(library.resolve()), str(tmp_path), mode],
                                capture_output=True, text=True, check=True)
        return json.loads(result.stdout)
    assert run('start')['status'] == 'PENDING'
    observed = run('outcome')
    assert observed['status'] == 'MATCHES_ONE_OF_MULTIPLE'
    assert run('read') == observed
