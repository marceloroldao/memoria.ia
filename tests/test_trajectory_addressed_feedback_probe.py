import copy
import os
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from mobile_region_replay import NativeProbe
from trajectory_addressed_feedback_probe import (
    addressed_read, journal_region, operations, probe, projection, record_addressed, withdraw_addressed,
)
from trajectory_feedback_ledger_probe import receipt, record, ledger_region
from trajectory_feedback_withdrawal_probe import withdrawal_region
from trajectory_question_frame_probe import collect, persist
from trajectory_route_feedback_probe import make_fixture


@pytest.fixture
def native(tmp_path):
    library = Path(os.environ.get('MEMORIA_NATIVE_LIBRARY', 'build/trajectory-native/libmemoria_mobile.so'))
    if not library.exists():
        if 'MEMORIA_NATIVE_LIBRARY' in os.environ:
            pytest.fail('Explicit native BDR library is missing')
        pytest.skip('Native integration runs in the dedicated pinned-BDR job')
    native = NativeProbe(library, tmp_path)
    try:
        yield native
    finally:
        native.close()


def prepare(native, case='extra_route'):
    rows, region, source, query, _ = make_fixture(case, 20270111, False)
    persist(native, rows)
    view = addressed_read(native, region, source, enabled=True)['raw_view']
    candidate = (next(c for c in view['candidates'] if any(o[1] == 'added-map-target' for o in c['origins']))
                 if case == 'extra_route' else view['candidates'][0])
    binding = receipt(native, region, source, candidate['payload_id'])
    return rows, region, source, query, binding


def add(native, binding, kind, event_id='one', stance='oppose'):
    target = dict(kind=kind)
    if kind == 'FRAME':
        target['frame_id'] = binding['candidate']['frame_ids'][0]
    return record_addressed(native, binding, event_id, 'caller', stance, target)


def test_content_opposition_is_local_and_does_not_infer_frame_fault(native):
    _, region, source, query, binding = prepare(native)
    baseline = addressed_read(native, region, query, enabled=True)
    add(native, binding, 'CONTENT')
    local = addressed_read(native, region, source, enabled=True)
    other = addressed_read(native, region, query, enabled=True)
    assert local['withheld_candidates'] and not other['blocked_frames']
    assert other['available_candidates'] == baseline['available_candidates']
    assert not other['frame_feedback']


def test_explicit_frame_transfers_without_local_content_blame(native):
    _, region, source, query, binding = prepare(native)
    add(native, binding, 'FRAME')
    view = addressed_read(native, region, query, enabled=True)
    assert len(view['available_candidates']) == len(view['withheld_candidates']) == 1
    assert view['blocked_frames']
    assert all(not d['content_decision']['withheld'] for d in view['addressed_decisions'])
    assert view['answer'] is None and not view['qualified']


def test_explicit_choice_is_allowed_with_ambiguous_candidate_but_other_frames_survive(native):
    _, region, source, query, binding = prepare(native, 'ambiguous_attribution')
    assert len(binding['candidate']['frame_ids']) > 1
    add(native, binding, 'FRAME')
    view = addressed_read(native, region, source, enabled=True)
    assert len(view['blocked_frames']) == 1
    assert not view['withheld_candidates']
    assert any(d['penalized_frame_ids'] and d['surviving_frame_ids'] for d in view['addressed_decisions'])


def test_old_candidate_feedback_never_becomes_explicit_frame_feedback(native):
    _, region, source, query, binding = prepare(native)
    record(native, binding, 'legacy', 'caller', 'oppose')
    local = addressed_read(native, region, source, enabled=True)
    other = addressed_read(native, region, query, enabled=True)
    assert local['withheld_candidates']
    assert not other['blocked_frames'] and not other['frame_feedback']
    assert len(other['available_candidates']) == 2
    assert operations(native, region) == []


@pytest.mark.parametrize('kind', ['CONTENT', 'FRAME'])
def test_support_does_not_suspend_or_qualify(native, kind):
    _, region, _, query, binding = prepare(native)
    add(native, binding, kind, stance='support')
    view = addressed_read(native, region, query, enabled=True)
    assert not view['withheld_candidates'] and not view['blocked_frames']
    assert not view['qualified'] and not view['selection_used']


@pytest.mark.parametrize('target', [None, {}, {'kind': 'ROUTE'}, {'kind': 'FRAME', 'frame_id': 'missing'},
                                    {'kind': 'CONTENT', 'frame_id': 'extra'}])
def test_invalid_target_never_writes(native, target):
    rows, region, _, _, binding = prepare(native)
    with pytest.raises(ValueError):
        record_addressed(native, binding, 'bad', 'caller', 'oppose', target)
    assert operations(native, region) == []
    assert collect(native, [region]) == rows


def test_replays_and_identity_conflicts_preserve_original_target(native):
    _, region, _, _, binding = prepare(native)
    add(native, binding, 'CONTENT')
    original = operations(native, region)
    assert add(native, binding, 'CONTENT')['status'] == 'EXACT_REPLAY'
    with pytest.raises(ValueError, match='reused'):
        add(native, binding, 'FRAME')
    altered = copy.deepcopy(binding)
    altered['query'] += '!'
    with pytest.raises(ValueError):
        record_addressed(native, altered, 'new', 'caller', 'oppose', dict(kind='CONTENT'))
    assert operations(native, region) == original


def test_stale_new_feedback_rejects_but_exact_existing_retry_survives(native):
    rows, region, _, _, binding = prepare(native)
    add(native, binding, 'CONTENT')
    persist(native, [dict(hierarchy_id=region, source_id='later', sequence=max(r['sequence'] for r in rows) + 1,
                          text='Outra observação.', source_kind='user_turn')])
    with pytest.raises(ValueError, match='stale'):
        add(native, binding, 'FRAME', event_id='new')
    assert add(native, binding, 'CONTENT')['status'] == 'EXACT_REPLAY'


def test_content_and_frame_withdrawals_remain_independent(native):
    _, region, source, query, binding = prepare(native)
    add(native, binding, 'CONTENT', 'content')
    add(native, binding, 'FRAME', 'frame')
    withdraw_addressed(native, region, 'undo-frame', 'caller', 'frame')
    assert addressed_read(native, region, source, enabled=True)['withheld_candidates']
    assert not addressed_read(native, region, query, enabled=True)['blocked_frames']
    withdraw_addressed(native, region, 'undo-content', 'caller', 'content')
    assert not addressed_read(native, region, source, enabled=True)['withheld_candidates']
    assert len(operations(native, region)) == 4
    before = addressed_read(native, region, query, enabled=True)
    native.reopen()
    assert addressed_read(native, region, query, enabled=True) == before


def test_invalid_withdrawal_and_control_history_are_rejected(native):
    _, region, _, _, binding = prepare(native)
    add(native, binding, 'FRAME')
    original = operations(native, region)
    with pytest.raises(ValueError, match='mismatch'):
        withdraw_addressed(native, region, 'undo', 'other-actor', 'one')
    assert operations(native, region) == original
    withdraw_addressed(native, region, 'undo', 'caller', 'one')
    log = operations(native, region)
    with pytest.raises(ValueError, match='already'):
        withdraw_addressed(native, region, 'another', 'caller', 'one')
    assert withdraw_addressed(native, region, 'undo', 'caller', 'one')['status'] == 'EXACT_REPLAY'
    changed = copy.deepcopy(log)
    changed[-1]['event']['target_sha256'] = 'bad'
    with pytest.raises(ValueError, match='withdrawal'):
        projection(changed)
    assert operations(native, region) == log


def test_control_regions_cannot_be_used_as_learning_regions(native):
    _, region, _, query, _ = prepare(native)
    for scope in (journal_region(region), ledger_region(region), withdrawal_region(region)):
        with pytest.raises(ValueError):
            addressed_read(native, scope, query, enabled=True)


def test_corrupted_feedback_receipt_is_rejected_before_projection(native):
    _, region, _, _, binding = prepare(native)
    add(native, binding, 'FRAME')
    changed = copy.deepcopy(operations(native, region))
    changed[0]['event']['receipt']['query'] += '!'
    with pytest.raises(ValueError, match='receipt digest'):
        projection(changed)


def test_changed_witness_origins_expire_explicit_frame_transport(native):
    rows, region, _, query, binding = prepare(native)
    first = add(native, binding, 'FRAME')
    witness = next(iter(first['event']['target']['witness_provenance'].values()))
    persist(native, [dict(hierarchy_id=region, source_id='repeat-witness', sequence=max(r['sequence'] for r in rows) + 1,
                          text=witness['text'], source_kind='user_turn')])
    view = addressed_read(native, region, query, enabled=True)
    assert not view['blocked_frames'] and len(view['available_candidates']) == 2


def test_reports_retain_positive_wrong_frame_and_hidden_reference_failures(native):
    library = Path(os.environ.get('MEMORIA_NATIVE_LIBRARY', 'build/trajectory-native/libmemoria_mobile.so'))
    for seed in (20270111, 20270112):
        result = probe(library, seed)
        assert result['integrity_status'] == 'PASS'
        assert result['effects']['explicit_frame']['after_score']['exact_set']
        assert result['effects']['wrong_frame']['after_score']['false_negative'] == 1
        assert result['effects']['hidden_reference_twin']['after_score']['false_negative'] == 1
        assert result['effects']['content_only']['after_score'] == result['effects']['content_only']['before_score']
