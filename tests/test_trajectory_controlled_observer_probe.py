import copy
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import controlled_symbol_observer as world
import trajectory_controlled_observer_probe as controlled
import trajectory_prediction_audit as audit
from mobile_region_replay import NativeProbe
from trajectory_question_frame_probe import collect, persist


@pytest.mark.parametrize('extra', ['hypothesis', 'candidates', 'memory_path'])
def test_worker_process_refuses_hypothesis_or_memory_input(extra):
    request = dict(world_seed=20270119, entity='ab', tick=1, sensor_mode='faithful')
    request[extra] = 'forbidden input'
    result = subprocess.run([sys.executable, str(controlled.WORKER)], input=json.dumps(request) + '\n',
                            capture_output=True, text=True, check=True)
    assert json.loads(result.stdout)['ok'] is False


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
    rows, region, query, entity, past = controlled.prepare_rows(20270119)
    native = NativeProbe(library, tmp_path)
    persist(native, rows)
    request = dict(world_seed=20270119, entity=entity, tick=1, sensor_mode='faithful')
    first = controlled.freeze_task(native, region, query, 'f1', 'forecaster', request)
    try:
        yield native, region, query, request, past, first
    finally:
        native.close()


def test_separate_observer_result_and_complete_receipt_survive_reopen(case):
    native, region, _, _, _, _ = case
    result = controlled.observe_task(native, region, 'f1', 'o1')
    comparison = audit.reconcile(native, region, 'f1')
    assert comparison['status'] == 'OUTSIDE_FROZEN_SET'
    assert comparison['comparisons'][0]['outcome']['event']['source_receipt'] == result['packet']
    before_rows, before_log = collect(native, [region]), audit.journal(native, region)
    native.reopen()
    assert audit.reconcile(native, region, 'f1') == comparison
    assert controlled.ingest_result(native, region, 'f1', 'o1', result['packet'])['status'] == 'EXACT_REPLAY'
    assert collect(native, [region]) == before_rows and audit.journal(native, region) == before_log


def test_fixed_worker_request_is_invariant_to_changed_memory_hypotheses(library):
    result = controlled.independence_intervention(library, 20270119)
    assert all(result['checks'].values())
    assert result['runs'][0]['forecast']['event']['receipt']['snapshot_sha256'] != result['runs'][1]['forecast']['event']['receipt']['snapshot_sha256']
    assert result['runs'][0]['worker']['packet'] == result['runs'][1]['worker']['packet']


def test_bridge_does_not_use_simulated_truth_as_a_learning_oracle(case, monkeypatch):
    native, region, _, _, _, _ = case
    def forbidden(*args):
        raise AssertionError('parent evaluator world truth must not enter ingestion')
    monkeypatch.setattr(world, 'world_value', forbidden)
    controlled.observe_task(native, region, 'f1', 'o1')
    assert audit.reconcile(native, region, 'f1')['status'] == 'OUTSIDE_FROZEN_SET'


def test_lagged_sensor_can_match_stale_hypotheses_without_being_true_at_requested_tick(case):
    native, region, query, request, _, _ = case
    request = dict(request, sensor_mode='lagged')
    controlled.freeze_task(native, region, query, 'lagged', 'forecaster', request)
    observed = controlled.observe_task(native, region, 'lagged', 'lagged-result')
    result = audit.reconcile(native, region, 'lagged')
    assert result['status'] == 'MATCHES_ONE_OF_MULTIPLE'
    assert observed['packet']['value'] != world.world_value(request['world_seed'], request['entity'], request['tick'])
    assert result['provenance_independence'] == 'NOT_ESTABLISHED' and not result['qualified']


def test_stable_world_repeated_measurement_is_only_recurrence(case):
    native, region, query, request, _, _ = case
    request = dict(request, tick=0)
    controlled.freeze_task(native, region, query, 'stable', 'forecaster', request)
    controlled.observe_task(native, region, 'stable', 'stable-result')
    result = audit.reconcile(native, region, 'stable')
    assert result['status'] == 'MATCHES_ONE_OF_MULTIPLE' and not result['learning_applied']


@pytest.mark.parametrize('change', ['request', 'checksum', 'schema'])
def test_wrong_context_and_altered_packets_never_write(case, change):
    native, region, _, request, _, _ = case
    packet = controlled.run_observer(dict(request, entity='zz') if change == 'request' else request)
    if change == 'checksum':
        packet['value'] += 1
        packet['text'] = world.render(packet['request']['entity'], packet['value'])
    elif change == 'schema':
        packet['hypothesis'] = 'extra input'
    rows, log = collect(native, [region]), audit.journal(native, region)
    with pytest.raises(ValueError):
        controlled.ingest_result(native, region, 'f1', 'bad', packet)
    assert collect(native, [region]) == rows and audit.journal(native, region) == log


def test_self_consistent_forgery_is_not_source_authenticated(case):
    native, region, _, request, past, _ = case
    packet = controlled.run_observer(request)
    packet['value'] = past['value']
    packet['text'] = world.render(request['entity'], packet['value'])
    packet['result_sha256'] = world.digest({k: v for k, v in packet.items() if k != 'result_sha256'})
    controlled.ingest_result(native, region, 'f1', 'forged', packet)
    result = audit.reconcile(native, region, 'f1')
    assert result['status'] == 'MATCHES_ONE_OF_MULTIPLE'
    assert not result['qualified'] and result['provenance_independence'] == 'NOT_ESTABLISHED'
    assert packet['value'] != world.world_value(request['world_seed'], request['entity'], request['tick'])


def test_replayed_packet_cannot_manufacture_new_native_observation_or_future_time(case):
    native, region, query, request, _, _ = case
    observed = controlled.observe_task(native, region, 'f1', 'o1')
    rows, log = collect(native, [region]), audit.journal(native, region)
    with pytest.raises(ValueError, match='already linked'):
        controlled.ingest_result(native, region, 'f1', 'o2', observed['packet'])
    assert collect(native, [region]) == rows and audit.journal(native, region) == log
    controlled.freeze_task(native, region, query, 'f2', 'forecaster', request)
    before = audit.journal(native, region)
    with pytest.raises(ValueError, match='not later'):
        controlled.ingest_result(native, region, 'f2', 'o3', observed['packet'])
    assert collect(native, [region]) == rows and audit.journal(native, region) == before


def test_frozen_context_cannot_be_changed_on_forecast_retry(case):
    native, region, query, request, _, first = case
    with pytest.raises(ValueError, match='reused'):
        controlled.freeze_task(native, region, query, 'f1', 'forecaster', dict(request, tick=2))
    assert audit.journal(native, region)[0]['event'] == first['event']


def test_observer_code_version_mismatch_rejects_before_ingestion(case, monkeypatch):
    native, region, _, request, _, _ = case
    packet = controlled.run_observer(request)
    rows, log = collect(native, [region]), audit.journal(native, region)
    monkeypatch.setattr(controlled, 'code_digest', lambda: 'different-version')
    with pytest.raises(ValueError, match='frozen task'):
        controlled.ingest_result(native, region, 'f1', 'bad', packet)
    assert collect(native, [region]) == rows and audit.journal(native, region) == log


@pytest.mark.parametrize('bad', [{'number': float('nan')}, {'data': 'x' * 4097}])
def test_optional_audit_metadata_is_bounded_json_before_write(case, bad):
    native, region, query, _, _, _ = case
    log = audit.journal(native, region)
    with pytest.raises(ValueError):
        audit.forecast(native, region, query, 'bad-context', 'forecaster', observation_context=bad)
    assert audit.journal(native, region) == log


def test_reports_keep_independence_separate_from_accuracy_and_authentication(library):
    for seed in (20270119, 20270120):
        result = controlled.probe(library, seed)
        assert result['integrity_status'] == 'PASS' and result['integrity_total'] == 82
        by_name = {c['scenario']: c for c in result['cases']}
        assert by_name['state_changed']['result']['status'] == 'OUTSIDE_FROZEN_SET'
        assert by_name['state_changed']['evaluator']['linked_reports_agree_with_world'] == [True]
        assert by_name['lagged']['evaluator']['linked_reports_agree_with_world'] == [False]
        assert by_name['self_consistent_forgery']['evaluator']['linked_reports_agree_with_world'] == [False]
        assert by_name['conflicting_reports']['result']['status'] == 'DIVERGENT_LATER_OBSERVATIONS'
        assert result['source_authentication'] == 'NOT_ESTABLISHED'
