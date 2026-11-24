import copy
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import authenticated_symbol_observer as signer
import controlled_symbol_observer as world
import trajectory_authenticated_observer_probe as auth
import trajectory_prediction_audit as audit
from mobile_region_replay import NativeProbe
from trajectory_question_frame_probe import collect, persist


def task():
    return dict(format=signer.FORMAT, region='region-a', forecast_id='f1', query='Q[ab]?',
                source_id='sensor-a', key_id='key-1', challenge='a'*64,
                request=dict(world_seed=20270121, entity='ab', tick=1, sensor_mode='faithful'),
                versions=signer.versions())


def test_worker_never_echoes_secret_on_success_or_error():
    secret = b'x'*32
    for value in (dict(task=task(), key_hex=secret.hex()),
                  dict(task=task(), key_hex=secret.hex(), candidates=['forbidden'])):
        r = subprocess.run([sys.executable, str(auth.WORKER)], input=json.dumps(value)+'\n', text=True,
                           capture_output=True, check=True)
        assert secret.hex() not in r.stdout+r.stderr
        result = json.loads(r.stdout)
        assert result['ok'] == ('candidates' not in value)
        if result['ok']:
            assert signer.verify(result['envelope'], task(), secret)['request'] == task()['request']


@pytest.mark.parametrize('field,value', [('region','region-b'), ('forecast_id','f2'), ('source_id','sensor-b'),
                                       ('key_id','key-2'), ('challenge','b'*64)])
def test_mac_binds_full_task_scope(field, value):
    t = task(); envelope = signer.issue(t, auth.TEST_KEY)
    other = dict(t, **{field:value})
    with pytest.raises(ValueError):
        signer.verify(envelope, other, auth.TEST_KEY)


@pytest.mark.parametrize('key', [b'', b'x'*31, 'x'*32])
def test_short_or_nonbyte_keys_rejected(key):
    with pytest.raises(ValueError):
        signer.issue(task(), key)


@pytest.fixture
def library():
    path = Path(os.environ.get('MEMORIA_NATIVE_LIBRARY', 'build/trajectory-native/libmemoria_mobile.so'))
    if not path.exists():
        if 'MEMORIA_NATIVE_LIBRARY' in os.environ:
            pytest.fail('Explicit native BDR library is missing')
        pytest.skip('Native integration runs in pinned-BDR CI')
    return path


@pytest.fixture
def case(library, tmp_path):
    rows, region, query, entity, _ = auth.controlled.prepare_rows(20270121)
    native = NativeProbe(library, tmp_path)
    persist(native, rows)
    request = dict(world_seed=20270121, entity=entity, tick=1, sensor_mode='faithful')
    frozen = auth.freeze_task(native, region, query, 'f1', 'forecaster', request, 'sensor-a', 'key-1', challenge='a'*64)
    keyring = {('sensor-a','key-1'):auth.TEST_KEY}
    try:
        yield native, region, query, request, frozen['event']['receipt']['observation_context'], keyring
    finally:
        native.close()


def snapshot(native, region):
    return collect(native, [region]), audit.journal(native, region)


@pytest.mark.parametrize('change', ['value', 'key', 'source', 'challenge', 'revocation', 'version', 'unsigned'])
def test_bad_or_untrusted_envelopes_rejected_before_native_write(case, change):
    native, region, _, _, t, keyring = case
    envelope = auth.run_observer(t, auth.TEST_KEY)
    if change == 'value':
        packet = envelope['body']['packet']; packet['value'] += 1
        packet['text'] = world.render(packet['request']['entity'], packet['value'])
        packet['result_sha256'] = world.digest({k:v for k,v in packet.items() if k!='result_sha256'})
    elif change == 'key':
        keyring = {('sensor-a','key-1'):b'z'*32}
    elif change in ('source', 'challenge'):
        t = dict(t, **({'source_id':'sensor-b'} if change=='source' else {'challenge':'b'*64}))
        envelope = auth.run_observer(t, auth.TEST_KEY)
    elif change == 'revocation':
        keyring = {}
    elif change == 'version':
        envelope['body']['task']['versions']['worker'] = '0'*64
    elif change == 'unsigned':
        envelope = envelope['body']['packet']
    before = snapshot(native, region)
    with pytest.raises(ValueError):
        auth.ingest_result(native, region, 'f1', 'bad', envelope, keyring)
    assert snapshot(native, region) == before


def test_cold_reopen_revalidates_with_current_trust_and_revocation(case):
    native, region, _, _, _, keyring = case
    linked = auth.observe_task(native, region, 'f1', 'o1', keyring)
    result = auth.authenticate_history(native, region, 'f1', keyring)
    before = snapshot(native, region)
    native.reopen()
    assert auth.authenticate_history(native, region, 'f1', keyring) == result
    assert auth.ingest_result(native, region, 'f1', 'o1', linked['envelope'], keyring)['status']=='EXACT_REPLAY'
    with pytest.raises(ValueError, match='not currently trusted'):
        auth.authenticate_history(native, region, 'f1', {})
    with pytest.raises(ValueError, match='not currently trusted'):
        auth.ingest_result(native, region, 'f1', 'o1', linked['envelope'], {})
    assert snapshot(native, region)==before
    assert audit.reconcile(native, region, 'f1')['provenance_independence']=='NOT_ESTABLISHED'


def test_new_task_and_mac_cannot_make_same_packet_later(case):
    native, region, query, request, _, keyring = case
    first = auth.observe_task(native, region, 'f1', 'o1', keyring)
    before = snapshot(native, region)
    with pytest.raises(ValueError, match='already linked'):
        auth.ingest_result(native, region, 'f1', 'renamed', first['envelope'], keyring)
    assert snapshot(native, region)==before
    auth.freeze_task(native, region, query, 'f2', 'forecaster', request, 'sensor-a', 'key-1', challenge='b'*64)
    before = snapshot(native, region)
    with pytest.raises(ValueError, match='not later'):
        auth.observe_task(native, region, 'f2', 'o2', keyring)
    assert snapshot(native, region)==before


def test_outcome_identity_conflict_cannot_append_a_new_observation(case):
    native, region, query, request, _, keyring = case
    auth.observe_task(native, region, 'f1', 'o1', keyring)
    auth.freeze_task(native, region, query, 'f2', 'forecaster', dict(request,tick=2), 'sensor-a', 'key-1', challenge='b'*64)
    t,_ = auth.frozen_task(native, region, 'f2')
    envelope = auth.run_observer(t, auth.TEST_KEY)
    before = snapshot(native, region)
    with pytest.raises(ValueError,match='identity reused'):
        auth.ingest_result(native, region, 'f2', 'o1', envelope, keyring)
    assert snapshot(native, region)==before


def test_signed_but_inconsistent_packet_rejected_before_write(case):
    native, region, _, _, t, keyring = case
    envelope = auth.run_observer(t, auth.TEST_KEY)
    envelope['body']['packet']['text'] = 'invalid'
    envelope['mac'] = signer.mac(envelope['body'],auth.TEST_KEY)
    before = snapshot(native, region)
    with pytest.raises(ValueError):
        auth.ingest_result(native, region, 'f1', 'bad', envelope, keyring)
    assert snapshot(native, region)==before


def test_worker_hash_mismatch_rejects_before_write(case, monkeypatch):
    native, region, _, _, t, keyring = case
    envelope = auth.run_observer(t, auth.TEST_KEY)
    current = signer.versions()
    monkeypatch.setattr(signer,'versions',lambda:dict(current,worker='0'*64))
    before = snapshot(native, region)
    with pytest.raises(ValueError,match='version mismatch'):
        auth.ingest_result(native, region, 'f1', 'o1', envelope, keyring)
    assert snapshot(native, region)==before


def test_authenticated_reports_preserve_wrong_sensor_and_keyholder_forgery(library):
    for seed in (20270121,20270122):
        result = auth.probe(library,seed)
        assert result['integrity_status']=='PASS'
        cases = {c['scenario']:c for c in result['cases']}
        for name in ('lagged','authorized_false_report'):
            assert cases[name]['authentication']['authenticated_outcomes']==1
            assert cases[name]['evaluator']['linked_reports_agree_with_world']==[False]
            assert cases[name]['result']['qualified'] is False
        assert cases['unsigned_forgery']['rejection'] is not None


def test_generic_audit_is_not_an_authentication_enforcement_boundary(case):
    native, region, _, request, _, keyring = case
    rows = collect(native, [region])
    packet = world.observe(request)
    row = dict(hierarchy_id=region, source_id='generic-bypass',
               sequence=max(r['sequence'] for r in rows)+1, text=packet['text'], source_kind='user_turn')
    persist(native,[row])
    audit.observe_outcome(native,region,'f1','direct','caller',audit.address(row))
    before = snapshot(native,region)
    # Generic audit remains available, but an explicit authentication check rejects it.
    assert audit.reconcile(native,region,'f1')['provenance_independence']=='NOT_ESTABLISHED'
    with pytest.raises(ValueError,match='authenticated envelope'):
        auth.authenticate_history(native,region,'f1',keyring)
    assert snapshot(native,region)==before
