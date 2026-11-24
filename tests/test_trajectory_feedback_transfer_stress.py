import copy
import gzip
import json
import os
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import trajectory_feedback_transfer_stress as stress
from trajectory_feedback_ledger_probe import canonical


@pytest.fixture
def library():
    path = Path(os.environ.get('MEMORIA_NATIVE_LIBRARY', 'build/trajectory-native/libmemoria_mobile.so'))
    if not path.exists():
        if 'MEMORIA_NATIVE_LIBRARY' in os.environ:
            pytest.fail('Explicit native BDR library is missing')
        pytest.skip('Native integration runs in the dedicated pinned-BDR job')
    return path


@pytest.mark.parametrize('family', stress.FAMILIES)
def test_new_variable_queries_are_not_training_demonstrations(family):
    for regime in stress.REGIMES:
        rows, _, queries = stress.workload(20270115, family, regime)
        assert [r['sequence'] for r in rows] == list(range(1, len(rows) + 1))
        assert all(q['text'] not in {r['text'] for r in rows} for q in queries)
        assert len([q for q in queries if q['role'] == 'heldout']) == 3
        assert len([q for q in queries if q['role'] == 'absence']) == 2
        assert len(rows) <= 64


@pytest.mark.parametrize('regime', stress.REGIMES)
@pytest.mark.parametrize('policy', stress.POLICIES)
@pytest.mark.parametrize('action', stress.FEEDBACK)
def test_policy_quality_and_redundancy_matrix_retains_losses_and_extras(library, regime, policy, action):
    result = stress.trial(library, 20270115, 'brackets', regime, policy, action)
    assert all(result['checks'].values())
    for output in result['queries']:
        if output['query']['role'] == 'heldout':
            before, after = output['before_score'], output['after_score']
            assert (before['true_positive'], before['false_positive'], before['false_negative']) == (1, 1, 0)
            if policy == 'CONTENT':
                assert after == before
            elif action == 'reject_extra' and regime == 'minimal':
                assert after['exact_set']
            elif action == 'reject_expected' and regime != 'both_redundant':
                assert (after['true_positive'], after['false_positive'], after['false_negative']) == (0, 1, 1)
            else:
                assert after == before
    # The anchor is deliberately excluded from held-out transfer claims.
    anchor = next(o for o in result['queries'] if o['query']['role'] == 'anchor')
    if policy == 'CONTENT':
        assert anchor['after_score']['false_negative'] == (1 if action == 'reject_expected' else 0)
        assert anchor['after_score']['false_positive'] == (0 if action == 'reject_extra' else 1)


def test_evaluator_references_cannot_change_target_operation_or_complete_reads(library, monkeypatch):
    original = stress.trial(library, 20270115, 'delimited', 'minimal', 'WITNESS', 'reject_extra')
    real_workload = stress.workload
    def changed(*args):
        rows, region, queries = real_workload(*args)
        altered = copy.deepcopy(queries)
        for q in altered:
            q['expected'] = ['Evaluator-only content never observed.']
            q['opposite_reference'] = []
        return rows, region, altered
    monkeypatch.setattr(stress, 'workload', changed)
    altered = stress.trial(library, 20270115, 'delimited', 'minimal', 'WITNESS', 'reject_extra')
    assert original['operation'] == altered['operation']
    assert original['rows'] == altered['rows']
    for a, b in zip(original['queries'], altered['queries']):
        assert a['before'] == b['before'] and a['after'] == b['after']
    assert original['queries'][1]['after_score'] != altered['queries'][1]['after_score']


def test_compression_retains_full_native_packets_and_is_filename_independent(library, tmp_path):
    result = stress.trial(library, 20270115, 'brackets', 'minimal', 'CONTENT', 'reject_extra')
    first, second = tmp_path / 'one.json.gz', tmp_path / 'two.json.gz'
    stress.write_report(first, result)
    stress.write_report(second, result)
    assert first.read_bytes() == second.read_bytes()
    restored = json.loads(gzip.decompress(first.read_bytes()))
    assert canonical(restored) == canonical(result)
    assert restored['queries'][0]['after']['raw_view']['frames']
