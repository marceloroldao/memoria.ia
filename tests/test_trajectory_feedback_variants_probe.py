import os
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from trajectory_feedback_variants_probe import additions, corpus, evaluate, ARMS


def test_variant_examples_do_not_contain_target_questions_or_evaluator_labels():
    for split in ('development', 'reserved'):
        for fixture in corpus(split):
            queries = {q['text'] for q in fixture['queries'][:3]}
            targets = set(fixture['queries'][0]['expected'])
            for arm in ARMS:
                rows = additions(fixture, arm)
                assert all(set(r) <= {'event_id', 'text', 'source_kind'} for r in rows)
                assert not queries.intersection(r['text'] for r in rows)
                assert not targets.intersection(r['text'] for r in rows)
            assert len(additions(fixture, 'baseline')) == 0
            assert len(additions(fixture, 'uppercase')) == len(additions(fixture, 'paraphrase')) == 9
            assert len(additions(fixture, 'both')) == 18


def test_reserved_catalogue_is_disjoint_and_preserves_uppercase_relation():
    for development, reserved in zip(corpus('development'), corpus('reserved')):
        assert development['scope'] == reserved['scope']
        assert not set(development['queries'][0]['expected']).intersection(reserved['queries'][0]['expected'])
        assert reserved['queries'][2]['text'] == reserved['queries'][0]['text'].upper()
        assert reserved['queries'][1]['text'] != development['queries'][1]['text']
        assert all(not q['expected'] for q in reserved['queries'][3:])


@pytest.mark.parametrize('arm', ARMS)
def test_native_variant_arm_preserves_reopen_and_negative_controls(arm):
    library = Path(os.environ.get('MEMORIA_NATIVE_LIBRARY', 'build/trajectory-native/libmemoria_mobile.so'))
    if not library.exists():
        pytest.skip('native library required')
    trial = evaluate(library, 'reserved', arm, corpus('reserved')[0])
    assert all(trial['checks'].values())
    assert all(c['score']['extra'] == 0 for c in trial['cases'][3:])
    assert all(c['view']['general_learning_status'] == 'NOT_ESTABLISHED' for c in trial['cases'])
