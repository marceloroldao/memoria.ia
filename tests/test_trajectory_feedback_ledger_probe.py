import copy
import os
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import trajectory_feedback_ledger_probe as feedback_module
from mobile_region_replay import NativeProbe
from trajectory_feedback_ledger_probe import (
    addressed_feedback, events, ledger_region, probe, receipt, record,
)
from trajectory_question_frame_probe import collect, persist
from trajectory_route_relation_probe import fixture, read


@pytest.fixture
def native_case(tmp_path):
    library = Path(os.environ.get('MEMORIA_NATIVE_LIBRARY', 'build/trajectory-native/libmemoria_mobile.so'))
    if not library.exists():
        pytest.skip('native library required')
    native = NativeProbe(library, tmp_path)
    rows, region, queries = fixture('same_root_two_routes', 20261231)
    persist(native, rows)
    query = next(q['text'] for q in queries if q['name'] == 'literal_cue')
    view = read(collect(native, [region]), region, query)
    binding = receipt(native, region, query, view['candidates'][0]['payload_id'])
    try:
        yield native, rows, region, query, binding
    finally:
        native.close()


def test_two_opposed_callers_and_retries_preserve_exact_retrieval(native_case):
    native, _, region, query, binding = native_case
    raw = collect(native, [region]); view = read(raw, region, query)
    a = record(native, binding, 'same-id', 'a', 'support')
    b = record(native, binding, 'other-id', 'b', 'oppose')
    assert a['address'] != b['address']
    assert record(native, binding, 'same-id', 'a', 'support')['status'] == 'EXACT_REPLAY'
    assert len(events(native, region)) == 2
    assert collect(native, [region]) == raw
    assert read(raw, region, query) == view
    feedback = addressed_feedback(native, binding)
    assert feedback['active_for_current_snapshot']
    assert [e['event']['stance'] for e in feedback['events']] == ['support', 'oppose']
    assert feedback['answer'] is None and not feedback['qualified'] and not feedback['selection_used']


@pytest.mark.parametrize('change', ['query', 'region', 'root', 'witness', 'snapshot', 'extra'])
def test_tampered_or_misdirected_receipts_cannot_append(native_case, change):
    native, _, region, _, binding = native_case
    altered = copy.deepcopy(binding)
    if change == 'query': altered['query'] += ' '
    if change == 'region': altered['region'] = 'other-region'
    if change == 'root': altered['candidate']['payload_id'] = 'unknown'
    if change == 'witness': altered['candidate']['witnesses'] = []
    if change == 'snapshot': altered['snapshot_sha256'] = '0' * 64
    if change == 'extra': altered['trusted'] = True
    with pytest.raises(ValueError):
        record(native, altered, 'event', 'a', 'support')
    assert events(native, region) == []
    assert events(native, 'other-region') == []


def test_event_identity_is_per_region_and_conflicting_reuse_rejects(native_case):
    native, rows, region, query, binding = native_case
    record(native, binding, 'id', 'a', 'support')
    for actor, stance in [('a', 'oppose'), ('b', 'support')]:
        with pytest.raises(ValueError, match='identity reused'):
            record(native, binding, 'id', actor, stance)
    other = 'other-region'
    persist(native, [dict(r, hierarchy_id=other) for r in rows])
    second = receipt(native, other, query, binding['candidate']['payload_id'])
    record(native, second, 'id', 'a', 'oppose')
    assert len(events(native, region)) == len(events(native, other)) == 1
    assert ledger_region(region) != ledger_region(other)


def test_new_snapshot_keeps_history_and_does_not_transfer_support(native_case):
    native, rows, region, query, binding = native_case
    record(native, binding, 'id', 'a', 'support')
    persist(native, [dict(hierarchy_id=region, source_id='later', sequence=max(r['sequence'] for r in rows)+1,
                          text='Observação posterior.', source_kind='user_turn')])
    with pytest.raises(ValueError, match='stale'):
        record(native, binding, 'new-id', 'a', 'oppose')
    assert record(native, binding, 'id', 'a', 'support')['status'] == 'EXACT_REPLAY'
    assert not addressed_feedback(native, binding)['active_for_current_snapshot']
    current = receipt(native, region, query, binding['candidate']['payload_id'])
    assert addressed_feedback(native, current)['events'] == []
    native.reopen()
    assert len(addressed_feedback(native, binding)['events']) == 1
    assert addressed_feedback(native, current)['active_for_current_snapshot']
    assert addressed_feedback(native, current)['events'] == []


def test_paged_ledger_reopens_without_feedback_becoming_observed_facts(native_case):
    native, _, region, query, binding = native_case
    before = collect(native, [region])
    for i in range(67):
        record(native, binding, f'event-{i}', 'a', 'oppose' if i % 2 else 'support')
    saved = events(native, region)
    assert len(saved) == 67
    assert [e['address']['sequence'] for e in saved] == list(range(1, 68))
    native.reopen()
    assert events(native, region) == saved
    assert collect(native, [region]) == before
    assert read(collect(native, [region]), region, query) == read(before, region, query)
    assert len(addressed_feedback(native, binding)['events']) == 67


def test_generated_barrier_append_also_invalidates_snapshot_without_transferring_feedback(native_case):
    native, rows, region, query, binding = native_case
    record(native, binding, 'id', 'a', 'support')
    persist(native, [dict(hierarchy_id=region, source_id='generated-later',
                          sequence=max(r['sequence'] for r in rows)+1,
                          text='Resposta gerada.', source_kind='assistant_generated')])
    with pytest.raises(ValueError, match='stale'):
        record(native, binding, 'new-id', 'a', 'oppose')
    current = receipt(native, region, query, binding['candidate']['payload_id'])
    assert current['snapshot_sha256'] != binding['snapshot_sha256']
    assert addressed_feedback(native, current)['events'] == []
    assert not addressed_feedback(native, binding)['active_for_current_snapshot']


def test_feedback_region_cannot_be_used_as_learning_scope(native_case):
    native, _, region, query, binding = native_case
    with pytest.raises(ValueError, match='learning region'):
        receipt(native, ledger_region(region), query, binding['candidate']['payload_id'])
    for event_id, actor, stance in [('', 'a', 'support'), ('id', '', 'support'), ('id', 'a', 'true')]:
        with pytest.raises(ValueError):
            record(native, binding, event_id, actor, stance)
    assert events(native, region) == []


def test_feedback_codec_preserves_literal_unicode_quotes_and_newlines(native_case):
    native, _, region, _, binding = native_case
    actor = 'Roldão "apoio"\n\\literal'
    event_id = 'retorno\n"é"\\'
    record(native, binding, event_id, actor, 'support')
    native.reopen()
    saved = events(native, region)[0]['event']
    assert saved['actor_id'] == actor and saved['event_id'] == event_id
    assert saved['receipt'] == binding
    assert record(native, binding, event_id, actor, 'support')['status'] == 'EXACT_REPLAY'


def test_probe_is_reproducible_without_evaluator_reference_learning(monkeypatch):
    library = Path(os.environ.get('MEMORIA_NATIVE_LIBRARY', 'build/trajectory-native/libmemoria_mobile.so'))
    if not library.exists(): pytest.skip('native library required')
    report = probe(library, 20261231)
    assert report['integrity_status'] == 'PASS'
    assert report['integrity_passed'] == report['integrity_total'] == 132
    assert report['retrieval_improvement_status'] == 'NOT_IMPLEMENTED'
    assert report['factual_quality_status'] == 'NOT_EVALUATED'
    assert len(report['cases']) == 6
    original = feedback_module.fixture
    def masked(*args, **kwargs):
        rows, region, queries = original(*args, **kwargs)
        for query in queries:
            query['expected'] = ['Evaluator metadata must not become feedback.']
        return rows, region, queries
    monkeypatch.setattr(feedback_module, 'fixture', masked)
    assert probe(library, 20261231) == report
