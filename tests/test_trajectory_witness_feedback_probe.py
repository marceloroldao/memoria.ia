import copy
import os
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from mobile_region_replay import NativeProbe
from trajectory_addressed_feedback_probe import (
    addressed_read, operations, record_addressed, withdraw_addressed, witness_occurrence_map,
)
from trajectory_feedback_ledger_probe import canonical
from trajectory_question_frame_probe import collect, persist
from trajectory_witness_feedback_probe import choose, fixture, probe, witness_read, witness_request


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


def prepare(native, name='reject_extra_witness'):
    rows, region, source, query, _ = fixture(name, 20270113, False)
    persist(native, rows)
    coverage = 'ALTERNATIVE' if name == 'alternate_witnesses' else 'SHARED' if name == 'shared_required_witness' else None
    binding, target = choose(native, region, source, repeated=name == 'other_occurrence', coverage=coverage)
    return rows, region, source, query, binding, target


def oppose(native, binding, target, event='one', stance='oppose'):
    return record_addressed(native, binding, event, 'caller', stance, target)


def test_exact_pair_rejection_masks_dependent_frame_without_rewriting_observations(native):
    rows, region, _, query, binding, target = prepare(native)
    before = witness_read(native, region, query, enabled=True)
    oppose(native, binding, target)
    after = witness_read(native, region, query, enabled=True)
    assert after['raw_view'] == before['raw_view']
    assert collect(native, [region]) == rows
    assert len(after['available_candidates']) == len(after['withheld_candidates']) == 1
    assert len(after['rejected_occurrences']) == 1 and after['witness_blocked_frames']
    assert after['answer'] is None and not after['qualified']
    native.reopen()
    assert witness_read(native, region, query, enabled=True) == after


def test_one_of_two_native_occurrences_survives_until_both_are_rejected(native):
    _, region, _, query, binding, target = prepare(native, 'other_occurrence')
    pairs = witness_occurrence_map(collect(native, [region]), region)[canonical(target['witness'])]
    assert len(pairs) == 2
    assert pairs[0]['source']['text'] == pairs[1]['source']['text']
    oppose(native, binding, target)
    first = witness_read(native, region, query, enabled=True)
    assert not first['witness_blocked_frames'] and len(first['available_candidates']) == 2
    second_target = witness_request(target['frame_id'], target['witness'], pairs[1])
    oppose(native, binding, second_target, 'two')
    assert len(witness_read(native, region, query, enabled=True)['available_candidates']) == 1
    withdraw_addressed(native, region, 'undo-first', 'caller', 'one')
    assert len(witness_read(native, region, query, enabled=True)['available_candidates']) == 2


def test_other_frames_preserve_candidate_but_shared_required_witness_is_not_independent(native):
    _, region, _, query, binding, target = prepare(native, 'alternate_witnesses')
    oppose(native, binding, target)
    view = witness_read(native, region, query, enabled=True)
    assert view['witness_blocked_frames']
    assert any(d['witness_blocked_frame_ids'] and d['surviving_frame_ids'] for d in view['witness_decisions'])
    assert len(view['available_candidates']) == 2


def test_shared_required_witness_blocks_all_applicable_frames(native):
    _, region, _, query, binding, target = prepare(native, 'shared_required_witness')
    oppose(native, binding, target)
    view = witness_read(native, region, query, enabled=True)
    blocked_candidate = view['withheld_candidates'][0]
    assert len(blocked_candidate['frame_ids']) > 1
    assert set(blocked_candidate['frame_ids']) <= set(view['witness_blocked_frames'])


def test_wrong_rejection_loses_correct_content_and_withdrawal_reverses(native):
    _, region, _, query, binding, target = prepare(native, 'reject_correct_witness')
    oppose(native, binding, target)
    assert not witness_read(native, region, query, enabled=True)['available_candidates']
    log = operations(native, region)
    withdraw_addressed(native, region, 'undo', 'caller', 'one')
    assert witness_read(native, region, query, enabled=True)['available_candidates']
    assert operations(native, region)[0] == log[0]
    assert oppose(native, binding, target)['status'] == 'EXACT_REPLAY'
    assert witness_read(native, region, query, enabled=True)['available_candidates']


def test_new_occurrence_in_another_stream_can_restore_previously_rejected_error(native):
    rows, region, _, query, binding, target = prepare(native)
    first = oppose(native, binding, target)
    assert len(witness_read(native, region, query, enabled=True)['available_candidates']) == 1
    pair = first['event']['target']['occurrence']
    for index, role in enumerate(('source', 'target')):
        persist(native, [dict(hierarchy_id=region, source_id='new-demo-' + role,
                              sequence=max(r['sequence'] for r in rows) + index + 1,
                              text=pair[role]['text'], source_kind='user_turn')])
    view = witness_read(native, region, query, enabled=True)
    assert view['rejected_occurrences'] and view['witness_blocked_frames']
    assert len(view['available_candidates']) == 2


@pytest.mark.parametrize('change', ['source', 'target', 'swapped', 'scope', 'generated', 'witness', 'frame'])
def test_unobserved_nonadjacent_or_generated_targets_never_write(native, change):
    rows, region, _, _, binding, target = prepare(native)
    bad = copy.deepcopy(target)
    if change in ('source', 'target'):
        bad[change + '_address'][2] += 1000
    elif change == 'swapped':
        bad['source_address'], bad['target_address'] = bad['target_address'], bad['source_address']
    elif change == 'scope':
        bad['source_address'][0] += '-foreign'
    elif change == 'generated':
        row = next(r for r in rows if r['source_kind'] == 'assistant_generated')
        bad['source_address'] = [region, row['source_id'], row['sequence']]
    elif change == 'witness':
        bad['witness'] = ['missing', 'roots', 'stream']
    else:
        bad['frame_id'] = 'missing'
    with pytest.raises(ValueError):
        oppose(native, binding, bad)
    assert operations(native, region) == [] and collect(native, [region]) == rows


def test_old_enabled_reader_refuses_active_witness_controls_but_disabled_reads_raw(native):
    _, region, _, query, binding, target = prepare(native)
    oppose(native, binding, target)
    with pytest.raises(ValueError, match='witness-aware'):
        addressed_read(native, region, query, enabled=True)
    assert len(addressed_read(native, region, query)['available_candidates']) == 2
    withdraw_addressed(native, region, 'undo', 'caller', 'one')
    assert addressed_read(native, region, query, enabled=True)['available_candidates']


def test_frame_and_witness_rejections_remain_independent(native):
    _, region, _, query, binding, target = prepare(native)
    oppose(native, binding, target)
    oppose(native, binding, dict(kind='FRAME', frame_id=target['frame_id']), 'frame')
    withdraw_addressed(native, region, 'undo-witness', 'caller', 'one')
    view = witness_read(native, region, query, enabled=True)
    assert view['blocked_frames'] and not view['rejected_occurrences']
    assert len(view['available_candidates']) == 1


def test_support_is_not_rejection_and_does_not_qualify(native):
    _, region, _, query, binding, target = prepare(native)
    oppose(native, binding, target, stance='support')
    view = witness_read(native, region, query, enabled=True)
    assert not view['rejected_occurrences'] and len(view['available_candidates']) == 2
    assert not view['qualified'] and not view['selection_used']


def test_both_seeds_keep_wrong_rejection_extra_and_hidden_reference_controls(native):
    library = Path(os.environ.get('MEMORIA_NATIVE_LIBRARY', 'build/trajectory-native/libmemoria_mobile.so'))
    for seed in (20270113, 20270114):
        result = probe(library, seed)
        assert result['integrity_status'] == 'PASS'
        assert result['effects']['reject_extra_witness']['after_score']['exact_set']
        assert result['effects']['reject_correct_witness']['after_score']['false_negative'] == 1
        assert result['effects']['alternate_witnesses']['after_score']['false_positive'] == 1
        assert result['effects']['other_occurrence']['after_score']['false_positive'] == 1
        assert result['effects']['hidden_reference_twin']['after_score']['false_negative'] == 1
