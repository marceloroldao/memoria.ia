import base64
import copy
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import trajectory_observer_rejection_probe as rejection
from mobile_region_replay import NativeProbe


@pytest.fixture
def library():
    path=Path(os.environ.get('MEMORIA_NATIVE_LIBRARY','build/trajectory-native/libmemoria_mobile.so'))
    if not path.exists():
        if 'MEMORIA_NATIVE_LIBRARY' in os.environ:
            pytest.fail('Explicit native BDR library is missing')
        pytest.skip('Native integration runs in pinned-BDR CI')
    return path


@pytest.fixture
def case(library,tmp_path):
    rows,region,query,entity,_=rejection.fresh.auth.controlled.prepare_rows(20270125)
    native=NativeProbe(library,tmp_path)
    rejection.persist(native,rows)
    request=dict(world_seed=20270125,entity=entity,tick=1,sensor_mode='lagged')
    frozen=rejection.fresh.auth.freeze_task(native,region,query,'f1','forecaster',request,'sensor-a','key-1',challenge='a'*64)
    rejection.fresh.freeze_policy(native,region,'f1',{'max_tick_lag':0})
    task=frozen['event']['receipt']['observation_context']
    keys={('sensor-a','key-1'):rejection.fresh.auth.TEST_KEY}
    envelope=rejection.fresh.auth.run_observer(task,rejection.fresh.auth.TEST_KEY)
    try:
        yield native,region,query,request,envelope,keys
    finally:
        native.close()


def changed_value(envelope):
    result=copy.deepcopy(envelope)
    packet=result['body']['packet'];packet['value']+=1
    packet['text']=rejection.fresh.world.render(packet['request']['entity'],packet['value'])
    packet['result_sha256']=rejection.fresh.world.digest({k:v for k,v in packet.items() if k!='result_sha256'})
    result['mac']=rejection.fresh.signer.mac(result['body'],rejection.fresh.auth.TEST_KEY)
    return result


def test_complete_stale_receipt_persists_separately_and_exact_retry_is_idempotent(case):
    native,region,_,_,envelope,keys=case
    before=rejection.snapshot(native,region)
    result=rejection.admit_with_rejections(native,region,'f1','r1',envelope,keys)
    assert result['status']=='NOT_ADMITTED' and result['link'] is None
    receipt=result['rejection']['receipt']
    assert receipt['envelope']==envelope and receipt['assessment']['status']=='STALE_DECLARED_TICK'
    saved=rejection.snapshot(native,region)
    assert saved['rows']==before['rows'] and saved['predictions']==before['predictions']
    assert saved['policies']==before['policies'] and len(saved['rejections'])==1
    assert rejection.fresh.audit.reconcile(native,region,'f1')['status']=='PENDING'
    native.reopen()
    assert rejection.snapshot(native,region)==saved
    assert rejection.admit_with_rejections(native,region,'f1','r1',envelope,keys)['rejection']['status']=='EXACT_REPLAY'
    assert rejection.snapshot(native,region)==saved


@pytest.mark.parametrize('change',['rename','payload'])
def test_receipt_identity_conflicts_reject_before_write(case,change):
    native,region,_,_,envelope,keys=case
    rejection.admit_with_rejections(native,region,'f1','r1',envelope,keys)
    before=rejection.snapshot(native,region)
    other=changed_value(envelope) if change=='payload' else envelope
    identity='r1' if change=='payload' else 'renamed'
    with pytest.raises(ValueError):
        rejection.admit_with_rejections(native,region,'f1',identity,other,keys)
    assert rejection.snapshot(native,region)==before


def test_multiple_authenticated_stale_reports_keep_order_and_conflict(case):
    native,region,_,_,envelope,keys=case
    first=rejection.record_rejection(native,region,'f1','r1',envelope,keys)
    second=rejection.record_rejection(native,region,'f1','r2',changed_value(envelope),keys)
    values=rejection.journal(native,region)
    assert len(values)==2 and values[0]['previous_sha256'] is None
    assert values[1]['previous_sha256']==first['receipt']['receipt_sha256']
    assert values[0]['envelope']['body']['packet']['value']!=values[1]['envelope']['body']['packet']['value']
    assert second['status']=='APPENDED'
    assert rejection.fresh.audit.reconcile(native,region,'f1')['status']=='PENDING'
    assert [x['status'] for x in rejection.review(native,region,keys)['receipts']]==['REVERIFIED_STALE']*2


def test_invalid_authentication_never_enters_rejection_journal(case):
    native,region,_,_,envelope,keys=case
    altered=changed_value(envelope);altered['mac']=envelope['mac']
    before=rejection.snapshot(native,region)
    with pytest.raises(ValueError,match='authentication failed'):
        rejection.admit_with_rejections(native,region,'f1','r1',altered,keys)
    assert rejection.snapshot(native,region)==before


def test_revocation_blocks_retry_but_preserves_original_receipt_and_readonly_review(case):
    native,region,_,_,envelope,keys=case
    rejection.admit_with_rejections(native,region,'f1','r1',envelope,keys)
    before=rejection.snapshot(native,region)
    with pytest.raises(ValueError,match='not currently trusted'):
        rejection.admit_with_rejections(native,region,'f1','r1',envelope,{})
    reviewed=rejection.review(native,region,{})
    assert reviewed['receipts'][0]['status']=='CURRENT_VERIFICATION_FAILED'
    assert reviewed['receipts'][0]['assessment'] is None
    assert rejection.snapshot(native,region)==before
    assert rejection.review(native,region,keys)['receipts'][0]['status']=='REVERIFIED_STALE'


def test_old_receipt_remains_readable_when_worker_version_changes(case,monkeypatch):
    native,region,_,_,envelope,keys=case
    rejection.record_rejection(native,region,'f1','r1',envelope,keys)
    before=rejection.snapshot(native,region)
    versions=rejection.fresh.signer.versions()
    monkeypatch.setattr(rejection.fresh.signer,'versions',lambda:dict(versions,worker='0'*64))
    assert rejection.journal(native,region)==before['rejections']
    assert rejection.review(native,region,keys)['receipts'][0]['status']=='CURRENT_VERIFICATION_FAILED'
    assert rejection.snapshot(native,region)==before


def test_history_prefix_change_is_not_hidden_by_stored_authentication(case):
    native,region,_,_,envelope,keys=case
    rejection.record_rejection(native,region,'f1','r1',envelope,keys)
    rejection.persist(native,[dict(hierarchy_id=region,source_id='injected-old-row',sequence=0,
                                  text='R[zz]=1.',source_kind='user_turn')])
    before=rejection.snapshot(native,region)
    result=rejection.review(native,region,keys)
    assert result['receipts'][0]['status']=='CURRENT_VERIFICATION_FAILED'
    assert rejection.snapshot(native,region)==before


def test_fresh_envelope_cannot_be_labeled_as_stale_in_journal(case):
    native,region,query,request,_,keys=case
    frozen=rejection.fresh.auth.freeze_task(native,region,query,'f2','forecaster',dict(request,sensor_mode='faithful'),
                                            'sensor-a','key-1',challenge='b'*64)
    rejection.fresh.freeze_policy(native,region,'f2',{'max_tick_lag':0})
    envelope=rejection.fresh.auth.run_observer(frozen['event']['receipt']['observation_context'],rejection.fresh.auth.TEST_KEY)
    before=rejection.snapshot(native,region)
    with pytest.raises(ValueError,match='only authenticated stale'):
        rejection.record_rejection(native,region,'f2','r1',envelope,keys)
    assert rejection.snapshot(native,region)==before
    assert rejection.admit_with_rejections(native,region,'f2','o1',envelope,keys)['status']=='ADMITTED'
    assert rejection.journal(native,region)==[]


def test_original_freshness_api_stays_without_rejection_persistence(case):
    native,region,_,_,envelope,keys=case
    before=rejection.snapshot(native,region)
    assert rejection.fresh.admit(native,region,'f1','r1',envelope,keys)['status']=='NOT_ADMITTED'
    assert rejection.snapshot(native,region)==before


def test_rejection_path_never_uses_world_truth_or_promotes_facts(case,monkeypatch):
    native,region,_,_,envelope,keys=case
    def forbidden(*args):
        raise AssertionError('world value is not a rejection oracle')
    monkeypatch.setattr(rejection.fresh.world,'world_value',forbidden)
    result=rejection.admit_with_rejections(native,region,'f1','r1',envelope,keys)
    assert result['rejection']['receipt']['assessment']['truth_established'] is False
    assert rejection.review(native,region,keys)['learning_applied'] is False
    assert rejection.fresh.audit.reconcile(native,region,'f1')['qualified'] is False


@pytest.mark.parametrize('change',['digest','order','chain','identity'])
def test_journal_corruption_fails_closed(case,monkeypatch,change):
    native,region,_,_,envelope,keys=case
    rejection.record_rejection(native,region,'f1','r1',envelope,keys)
    rows=copy.deepcopy(rejection.window_snapshot(native,rejection.field(region))['rows'])
    if change in ('digest','chain'):
        value=json.loads(base64.b64decode(rows[0]['text'][len(rejection.CODEC):]).decode())
        if change=='digest':
            value['receipt_sha256']='0'*64
        else:
            value['previous_sha256']='0'*64
            value['receipt_sha256']=rejection.fingerprint({k:v for k,v in value.items() if k!='receipt_sha256'})
        rows[0]['text']=rejection.CODEC+base64.b64encode(rejection.fresh.world.canonical(value).encode()).decode()
    elif change=='order':
        rows[0]['sequence']+=1
    else:
        rows[0]['source_id']='wrong-id'
    monkeypatch.setattr(rejection,'window_snapshot',lambda *args:{'rows':rows})
    with pytest.raises(ValueError):
        rejection.journal(native,region)


def test_corrupt_control_journal_blocks_even_fresh_route_before_main_write(case):
    native,region,query,request,_,keys=case
    rejection.persist(native,[dict(hierarchy_id=rejection.field(region),source_id='bad',sequence=1,
                                   source_kind='user_turn',text='bad-control')])
    frozen=rejection.fresh.auth.freeze_task(native,region,query,'f2','forecaster',dict(request,sensor_mode='faithful'),
                                            'sensor-a','key-1',challenge='b'*64)
    rejection.fresh.freeze_policy(native,region,'f2',{'max_tick_lag':0})
    envelope=rejection.fresh.auth.run_observer(frozen['event']['receipt']['observation_context'],rejection.fresh.auth.TEST_KEY)
    before=rejection.collect(native,[region]),rejection.fresh.audit.journal(native,region)
    with pytest.raises(ValueError,match='encoding'):
        rejection.admit_with_rejections(native,region,'f2','o1',envelope,keys)
    assert (rejection.collect(native,[region]),rejection.fresh.audit.journal(native,region))==before


def test_rejection_receipt_survives_two_separate_processes(library,tmp_path):
    code='''
import json,sys
from pathlib import Path
sys.path.insert(0,'scripts')
import trajectory_observer_rejection_probe as r
n=r.NativeProbe(Path(sys.argv[2]),Path(sys.argv[3]))
try:
    rows,region,q,entity,_=r.fresh.auth.controlled.prepare_rows(20270125)
    keys={('sensor-a','key-1'):r.fresh.auth.TEST_KEY}
    if sys.argv[1]=='write':
        r.persist(n,rows)
        req=dict(world_seed=20270125,entity=entity,tick=1,sensor_mode='lagged')
        x=r.fresh.auth.freeze_task(n,region,q,'f1','forecaster',req,'sensor-a','key-1',challenge='a'*64)
        r.fresh.freeze_policy(n,region,'f1',{'max_tick_lag':0})
        env=r.fresh.auth.run_observer(x['event']['receipt']['observation_context'],r.fresh.auth.TEST_KEY)
        r.admit_with_rejections(n,region,'f1','r1',env,keys)
    print(json.dumps(dict(snapshot=r.snapshot(n,region),review=r.review(n,region,keys)),sort_keys=True))
finally:
    n.close()
'''
    outputs=[]
    for mode in ('write','read'):
        p=subprocess.run([sys.executable,'-c',code,mode,str(library.resolve()),str(tmp_path)],
                         cwd=Path(__file__).resolve().parents[1],capture_output=True,text=True,check=True)
        outputs.append(json.loads(p.stdout))
    assert outputs[0]==outputs[1]
    assert len(outputs[1]['snapshot']['rejections'])==1
    assert outputs[1]['review']['receipts'][0]['status']=='REVERIFIED_STALE'


def test_reports_preserve_refusals_revocation_and_false_fresh_values(library):
    for seed in (20270125,20270126):
        result=rejection.probe(library,seed)
        assert result['integrity_status']=='PASS' and result['integrity_total']==124
        cases={c['scenario']:c for c in result['cases']}
        assert len(cases['stale_retained']['quarantine'])==1
        assert cases['stale_retained']['comparison']['status']=='PENDING'
        assert cases['revoked_before_record']['quarantine']==[]
        assert cases['revoked_after_record']['review']['receipts'][0]['status']=='CURRENT_VERIFICATION_FAILED'
        false=cases['authorized_false_fresh']
        assert false['result']['status']=='ADMITTED' and false['quarantine']==[]
        assert false['evaluator']['linked_reports_agree_with_world']==[False]
        assert false['comparison']['qualified'] is False
