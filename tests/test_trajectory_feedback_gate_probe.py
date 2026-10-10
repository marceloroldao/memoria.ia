import copy
import os
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from mobile_region_replay import NativeProbe
from trajectory_feedback_gate_probe import decision, gated_read, probe
from trajectory_feedback_ledger_probe import events, ledger_region, receipt, record
from trajectory_question_frame_probe import collect, persist
from trajectory_route_relation_probe import fixture, read


@pytest.fixture
def native_case(tmp_path):
    library = Path(os.environ.get('MEMORIA_NATIVE_LIBRARY', 'build/trajectory-native/libmemoria_mobile.so'))
    if not library.exists(): pytest.skip('native library required')
    native = NativeProbe(library, tmp_path)
    rows, region, queries = fixture('partial_overlap', 20270103)
    persist(native, rows)
    query = next(q for q in queries if q['name'] == 'literal_cue')
    raw = read(collect(native, [region]), region, query['text'])
    target = next(c for c in raw['candidates'] if any(o[1]=='added-map-target' for o in c['origins']))
    binding = receipt(native, region, query['text'], target['payload_id'])
    try: yield native, rows, region, query, raw, target, binding
    finally: native.close()


def test_explicit_veto_removes_only_addressed_extra_and_preserves_raw(native_case):
    native, _, region, query, raw, target, binding = native_case
    rows = collect(native, [region])
    record(native, binding, 'opposition', 'a', 'oppose')
    result = gated_read(native, region, query['text'], enabled=True)
    assert result['raw_view'] == raw
    assert result['withheld_candidates'] == [target]
    assert {c['text'] for c in result['available_candidates']} == set(query['expected'])
    assert collect(native, [region]) == rows
    assert result['answer'] is None and not result['qualified'] and not result['selection_used']
    assert result['proposal_payload_id'] is None


def test_twenty_support_events_cannot_outvote_opposition(native_case):
    native, _, region, query, _, target, binding = native_case
    record(native, binding, 'oppose', 'a', 'oppose')
    for i in range(20): record(native, binding, f'support-{i}', 'b', 'support')
    ledger = events(native, region)
    result = gated_read(native, region, query['text'], enabled=True)
    item = next(d for d in result['decisions'] if d['payload_id']==target['payload_id'])
    assert item['status'] == 'DISPUTED' and item['withheld']
    assert len(item['feedback']) == 21 and events(native, region) == ledger
    native.reopen()
    assert gated_read(native, region, query['text'], enabled=True) == result


def test_support_and_default_disabled_do_not_qualify_or_promote(native_case):
    native, _, region, query, raw, _, binding = native_case
    record(native, binding, 'support', 'a', 'support')
    supported = gated_read(native, region, query['text'], enabled=True)
    assert supported['available_candidates'] == raw['candidates']
    assert not supported['withheld_candidates'] and not supported['qualified']
    record(native, binding, 'opposed', 'a', 'oppose')
    disabled = gated_read(native, region, query['text'])
    assert disabled['available_candidates'] == raw['candidates']
    assert all(d['status']=='DISABLED' for d in disabled['decisions'])
    assert not disabled['candidate_filter_used']
    for enabled in (False, True):
        with pytest.raises(ValueError, match='learning region'):
            gated_read(native, ledger_region(region), query['text'], enabled=enabled)


def test_exact_query_and_scope_binding_do_not_transfer_veto(native_case):
    native, rows, region, query, raw, _, binding = native_case
    record(native, binding, 'oppose', 'a', 'oppose')
    variant = 'Contexto: ' + query['text']
    result = gated_read(native, region, variant, enabled=True)
    assert result['raw_view']['candidates'] == raw['candidates']
    assert not result['withheld_candidates']
    other = 'conversation:other'
    persist(native, [dict(r, hierarchy_id=other) for r in rows])
    assert not gated_read(native, other, query['text'], enabled=True)['withheld_candidates']


def test_generated_append_expires_veto_but_preserves_feedback(native_case):
    native, rows, region, query, _, _, binding = native_case
    record(native, binding, 'oppose', 'a', 'oppose')
    ledger = events(native, region)
    persist(native, [dict(hierarchy_id=region, source_id='generated-next', sequence=max(r['sequence'] for r in rows)+1,
                          text='Gerado.', source_kind='assistant_generated')])
    result = gated_read(native, region, query['text'], enabled=True)
    assert result['available_candidates'] and not result['withheld_candidates']
    assert events(native, region) == ledger


def test_decision_cannot_use_similar_or_stale_receipt_feedback(native_case):
    native, _, region, _, _, _, binding = native_case
    record(native, binding, 'oppose', 'a', 'oppose')
    ledger = events(native, region)
    for key in ('receipt_id', 'snapshot_sha256', 'query', 'view_sha256'):
        changed = copy.deepcopy(binding); changed[key] += 'different'
        assert decision(changed, ledger)['status'] == 'NO_FEEDBACK'
    before = copy.deepcopy(ledger)
    assert decision(binding, ledger)['status'] == 'OPPOSED'
    assert ledger == before


def test_full_probe_preserves_positive_and_negative_feedback_effects():
    library = Path(os.environ.get('MEMORIA_NATIVE_LIBRARY', 'build/trajectory-native/libmemoria_mobile.so'))
    if not library.exists(): pytest.skip('native library required')
    result = probe(library, 20270103)
    assert result['integrity_status'] == 'PASS'
    assert result['integrity_total'] == result['integrity_passed'] == 113
    effects = result['effects']
    assert effects['correct_veto']['before']['false_positive'] == 1
    assert effects['correct_veto']['after']['exact_set']
    assert effects['wrong_veto']['before']['exact_set']
    assert effects['wrong_veto']['after']['false_negative'] == 1
    assert effects['disputed_veto']['after']['exact_set']
    assert effects['wrong_support']['before'] == effects['wrong_support']['after']
    assert effects['wrong_support']['after']['false_positive'] == 1
    assert result['general_learning_status'] == 'NOT_ESTABLISHED'
