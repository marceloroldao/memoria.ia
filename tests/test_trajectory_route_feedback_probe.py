import copy
import os
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from trajectory_feedback_ledger_probe import events, receipt, record
from trajectory_feedback_withdrawal_probe import withdraw
from trajectory_question_frame_probe import collect, persist
from trajectory_route_feedback_probe import make_fixture, probe, route_feedback_read, learn_penalties
from mobile_region_replay import NativeProbe


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


def prepare(native, name='extra_route'):
    rows, region, source, heldout, _ = make_fixture(name, 20270109, False)
    persist(native, rows)
    view = route_feedback_read(native, region, source, enabled=True)['raw_view']
    candidate = (next(c for c in view['candidates'] if any(o[1] == 'added-map-target' for o in c['origins']))
                 if name in ('extra_route', 'alternate_frame_survives') else view['candidates'][0])
    binding = receipt(native, region, source, candidate['payload_id'])
    record(native, binding, 'opposition', 'caller', 'oppose')
    return rows, region, source, heldout, binding


def test_unique_frame_transfers_to_unaddressed_query_and_different_root(native):
    _, region, source, heldout, binding = prepare(native)
    assert heldout != source
    view = route_feedback_read(native, region, heldout, enabled=True)
    assert len(view['available_candidates']) == len(view['withheld_candidates']) == 1
    assert all(c['payload_id'] != binding['candidate']['payload_id'] for c in view['raw_view']['candidates'])
    assert view['blocked_frames']
    assert view['answer'] is None and not view['selection_used'] and not view['qualified']
    assert len(route_feedback_read(native, region, heldout)['available_candidates']) == 2


def test_ambiguous_source_is_not_attributed_to_all_frames(native):
    _, region, _, heldout, binding = prepare(native, 'ambiguous_attribution')
    assert len(binding['candidate']['frame_ids']) > 1
    view = route_feedback_read(native, region, heldout, enabled=True)
    assert view['route_penalties'][0]['reason'] == 'AMBIGUOUS_FRAME_ATTRIBUTION'
    assert not view['blocked_frames'] and not view['withheld_candidates']


def test_candidate_with_another_surviving_frame_remains(native):
    _, region, _, heldout, _ = prepare(native, 'alternate_frame_survives')
    view = route_feedback_read(native, region, heldout, enabled=True)
    assert view['blocked_frames']
    decision = view['route_decisions'][0]
    assert decision['penalized_frame_ids'] and decision['surviving_frame_ids']
    assert not decision['withheld'] and view['available_candidates']


def test_wrong_feedback_propagates_loss_and_withdrawal_reverses_it(native):
    _, region, _, heldout, _ = prepare(native, 'wrong_feedback')
    view = route_feedback_read(native, region, heldout, enabled=True)
    assert not view['available_candidates'] and view['withheld_candidates']
    original = events(native, region)
    withdraw(native, region, 'withdraw', 'caller', original[0])
    restored = route_feedback_read(native, region, heldout, enabled=True)
    assert restored['available_candidates'] and not restored['blocked_frames']
    assert events(native, region) == original
    native.reopen()
    assert route_feedback_read(native, region, heldout, enabled=True) == restored


def test_witness_occurrence_change_invalidates_transfer(native):
    rows, region, _, heldout, _ = prepare(native)
    before = route_feedback_read(native, region, heldout, enabled=True)
    penalty = next(p for p in before['route_penalties'] if p['eligible'])
    witness = next(iter(penalty['witness_provenance'].values()))
    appended = dict(hierarchy_id=region, source_id='witness-repeated',
                    sequence=max(r['sequence'] for r in rows) + 1,
                    text=witness['text'], source_kind='user_turn')
    persist(native, [appended])
    after = route_feedback_read(native, region, heldout, enabled=True)
    assert not after['blocked_frames']
    assert len(after['available_candidates']) == 2
    assert before['raw_view']['candidates'] == after['raw_view']['candidates']


def test_historical_prefix_or_receipt_change_prevents_learning(native):
    _, region, _, _, _ = prepare(native)
    rows, ledger = collect(native, [region]), events(native, region)
    assert learn_penalties(rows, ledger)[0]['eligible']
    assert not learn_penalties(rows[1:], ledger)[0]['eligible']
    changed = copy.deepcopy(ledger)
    changed[0]['event']['receipt']['view_sha256'] = 'altered'
    assert learn_penalties(rows, changed)[0]['reason'] == 'HISTORICAL_RECEIPT_NOT_REPRODUCIBLE'


def test_support_does_not_cancel_opposition_or_qualify_candidates(native):
    _, region, _, heldout, binding = prepare(native)
    record(native, binding, 'support', 'other', 'support')
    before = route_feedback_read(native, region, heldout, enabled=True)
    assert before['withheld_candidates'] and len(before['route_penalties']) == 1
    other = region + '-other'
    assert not route_feedback_read(native, other, heldout, enabled=True)['route_penalties']
    assert not before['qualified']


def test_other_frame_in_same_route_category_is_not_penalized(native):
    rows, region, _, _, _ = prepare(native)
    # Uppercase demonstrations belong to another symbol-transform frame.
    # The lower-case erroneous map must not blacklist that whole route family.
    question = 'QUAL É A COR DO DRONE?'
    disabled = route_feedback_read(native, region, question)
    enabled = route_feedback_read(native, region, question, enabled=True)
    assert disabled['available_candidates']
    assert enabled['available_candidates'] == disabled['available_candidates']
    assert not any(d['route_withheld'] for d in enabled['route_decisions'])


def test_generated_and_unrelated_append_do_not_expire_frame_penalty(native):
    rows, region, _, heldout, _ = prepare(native)
    before = route_feedback_read(native, region, heldout, enabled=True)
    witness = next(p for p in before['route_penalties'] if p['eligible'])['witness_provenance']
    example = next(iter(witness.values()))['text']
    for index, (body, kind) in enumerate(((example, 'assistant_generated'),
                                         ('Observação isolada posterior.', 'user_turn'))):
        persist(native, [dict(hierarchy_id=region, source_id=f'unrelated-{index}',
                              sequence=max(r['sequence'] for r in rows) + index + 1,
                              text=body, source_kind=kind)])
    after = route_feedback_read(native, region, heldout, enabled=True)
    assert after['blocked_frames'] == before['blocked_frames']
    assert after['withheld_candidates'] == before['withheld_candidates']


def test_both_correlated_seeds_keep_positive_and_negative_results(native):
    library = Path(os.environ.get('MEMORIA_NATIVE_LIBRARY', 'build/trajectory-native/libmemoria_mobile.so'))
    for seed in (20270109, 20270110):
        report = probe(library, seed)
        assert report['integrity_status'] == 'PASS'
        assert report['effects']['extra_route']['transferred_score']['exact_set']
        assert report['effects']['wrong_feedback']['transferred_score']['false_negative'] == 1
        assert report['effects']['hidden_reference_twin']['transferred_score']['false_negative'] == 1
        assert report['effects']['alternate_frame_survives']['transferred_score']['exact_set']
