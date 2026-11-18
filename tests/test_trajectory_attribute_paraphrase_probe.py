from collections import Counter
import os
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from trajectory_attribute_paraphrase_probe import DOMAINS, evaluate, fixture


def test_learning_taught_wording_from_aligned_examples_on_native_bdr():
    library = Path(os.environ.get('MEMORIA_NATIVE_LIBRARY',
                                  'build/trajectory-native/libmemoria_mobile.so'))
    if not library.is_file():
        if 'MEMORIA_NATIVE_LIBRARY' in os.environ:
            pytest.fail('Explicit native BDR library is missing')
        pytest.skip('Native integration runs in pinned-BDR CI')

    for domain in DOMAINS:
        _, aligned = fixture(domain, 'aligned')
        _, shuffled = fixture(domain, 'shuffled')
        assert Counter(row['text'] for row in aligned) == Counter(row['text'] for row in shuffled)
        assert aligned != shuffled

    results = evaluate(library)
    totals = {arm: tuple(sum(case[key] for case in cases)
                         for key in ('exact_set', 'true_positive', 'false_positive', 'false_negative'))
              for arm, cases in results.items()}
    assert totals == {
        'no_alternative': (6, 2, 0, 8),
        'aligned': (10, 8, 0, 2),
        'shuffled': (6, 2, 0, 8),
        'wrong_attribute': (5, 2, 3, 8),
        'mixed_one': (7, 8, 3, 2),
        'mixed_all': (7, 8, 3, 2),
        'wrong_both': (3, 0, 5, 10),
    }
    for case in results['aligned']:
        view = case['view']
        if case['category'] == 'conflict':
            assert len(view['candidates']) == 2 and view['proposal_payload_id'] is None
        if case['category'] == 'new_entity':
            candidate, = view['candidates']
            assert len(candidate['witnesses']) == 3
        if case['category'] in {'unseen_form', 'absent_attribute', 'absent_entity'}:
            assert not view['candidates'] and not view['absence_proven']

    cautious = evaluate(library, require_agreement=True)
    for arm, cases in results.items():
        suppressed = []
        for before, after in zip(cases, cautious[arm], strict=True):
            original, guarded = before['view'], after['view']
            assert original['candidates'] == guarded['candidates']
            assert original['observation_sha256'] == guarded['observation_sha256']
            if original['proposal_payload_id'] != guarded['proposal_payload_id']:
                assert guarded['proposal_payload_id'] is None
                assert guarded['reason'] == 'UNSUPPORTED_MATCHING_FRAMES'
                assert guarded['frame_agreement']['unsupported_frame_ids']
                suppressed.append((after['domain'], after['category']))
        assert suppressed == ([('names', 'absent_attribute')] if arm.startswith('mixed_') else [])

    compared = evaluate(library, require_agreement=True, compare_forms=True)
    for arm, cases in cautious.items():
        removed = []
        for before, after in zip(cases, compared[arm], strict=True):
            initial, checked = before['view'], after['view']
            assert initial['candidates'] == checked['candidates']
            assert initial['observation_sha256'] == checked['observation_sha256']
            if initial['proposal_payload_id'] != checked['proposal_payload_id']:
                assert checked['proposal_payload_id'] is None
                assert not before['exact_set']
                removed.append(checked['comparison']['status'])
        assert Counter(removed) == (
            {'DIFFERENT_PROPOSALS': 2, 'COMPARISON_UNRESOLVED': 1}
            if arm == 'wrong_attribute' else {})
    for arm in ('aligned', 'wrong_both'):
        transferred = [case for case in compared[arm] if case['category'] == 'new_entity']
        assert all(case['view']['comparison']['status'] == 'MATCHING_PROPOSALS'
                   and case['view']['proposal_payload_id'] is not None for case in transferred)
        assert all(case['exact_set'] == (arm == 'aligned') for case in transferred)
