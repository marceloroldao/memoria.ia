import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import authenticated_symbol_observer as signer
import trajectory_observer_freshness_probe as fresh
from mobile_region_replay import NativeProbe


@pytest.mark.parametrize('policy',[None,{}, {'max_tick_lag':True}, {'max_tick_lag':-1},
                                   {'max_tick_lag':1001}, {'max_tick_lag':0.5},
                                   {'max_tick_lag':0,'truth':True}])
def test_policy_requires_bounded_integer_and_no_truth_override(policy):
    with pytest.raises(ValueError):
        fresh.policy_value(policy)


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
    rows,region,query,entity,_=fresh.auth.controlled.prepare_rows(20270123)
    native=NativeProbe(library,tmp_path)
    fresh.persist(native,rows)
    request=dict(world_seed=20270123,entity=entity,tick=1,sensor_mode='lagged')
    frozen=fresh.auth.freeze_task(native,region,query,'f1','forecaster',request,'sensor-a','key-1',challenge='a'*64)
    task=frozen['event']['receipt']['observation_context']
    keyring={('sensor-a','key-1'):fresh.auth.TEST_KEY}
    envelope=fresh.auth.run_observer(task,fresh.auth.TEST_KEY)
    try:
        yield native,region,query,request,envelope,keyring
    finally:
        native.close()


def snapshot(native,region):
    return dict(rows=fresh.collect(native,[region]),log=fresh.audit.journal(native,region),policies=fresh.policies(native,region))


def test_strict_policy_excludes_stale_before_main_ingestion_and_survives_reopen(case):
    native,region,_,_,envelope,keyring=case
    fresh.freeze_policy(native,region,'f1',{'max_tick_lag':0})
    before=snapshot(native,region)
    result=fresh.admit(native,region,'f1','o1',envelope,keyring)
    assert result['status']=='NOT_ADMITTED' and result['link'] is None
    assert result['assessment']['status']=='STALE_DECLARED_TICK'
    assert result['assessment']['declared_tick_lag']==1
    assert snapshot(native,region)==before
    native.reopen()
    assert fresh.admit(native,region,'f1','o1',envelope,keyring)==result
    assert snapshot(native,region)==before
    assert fresh.audit.reconcile(native,region,'f1')['status']=='PENDING'


def test_policy_change_after_stale_result_is_rejected_without_writes(case):
    native,region,_,_,envelope,keyring=case
    fresh.freeze_policy(native,region,'f1',{'max_tick_lag':0})
    fresh.admit(native,region,'f1','o1',envelope,keyring)
    before=snapshot(native,region)
    with pytest.raises(ValueError,match='cannot be changed'):
        fresh.freeze_policy(native,region,'f1',{'max_tick_lag':1})
    assert snapshot(native,region)==before


def test_tolerant_policy_admits_stale_without_factual_promotion_and_is_idempotent(case):
    native,region,_,_,envelope,keyring=case
    binding=fresh.freeze_policy(native,region,'f1',{'max_tick_lag':1})
    fresh.admit(native,region,'f1','o1',envelope,keyring)
    before=snapshot(native,region)
    assert fresh.freeze_policy(native,region,'f1',{'max_tick_lag':1})['binding']==binding['binding']
    assert fresh.admit(native,region,'f1','o1',envelope,keyring)['link']['status']=='EXACT_REPLAY'
    assert snapshot(native,region)==before
    result=fresh.audit.reconcile(native,region,'f1')
    assert result['status']=='MATCHES_ONE_OF_MULTIPLE' and result['qualified'] is False
    assert fresh.assess_history(native,region,'f1',keyring)['truth_established'] is False


def test_missing_policy_rejected_before_writing(case):
    native,region,_,_,envelope,keyring=case
    before=snapshot(native,region)
    with pytest.raises(ValueError,match='not frozen'):
        fresh.admit(native,region,'f1','o1',envelope,keyring)
    assert snapshot(native,region)==before


@pytest.mark.parametrize('linked',[False,True])
def test_policy_cannot_be_added_after_raw_or_linked_observation(case,linked):
    native,region,_,_,envelope,keyring=case
    if linked:
        fresh.auth.ingest_result(native,region,'f1','outside-gate',envelope,keyring)
    else:
        rows=fresh.collect(native,[region])
        fresh.persist(native,[dict(hierarchy_id=region,source_id='late-raw',sequence=max(r['sequence'] for r in rows)+1,
                                   source_kind='user_turn',text=envelope['body']['packet']['text'])])
    before=snapshot(native,region)
    with pytest.raises(ValueError,match='before later observations'):
        fresh.freeze_policy(native,region,'f1',{'max_tick_lag':0})
    assert snapshot(native,region)==before


def test_bypass_is_detected_in_readonly_history_without_erasing_observation(case):
    native,region,_,_,envelope,keyring=case
    fresh.freeze_policy(native,region,'f1',{'max_tick_lag':0})
    fresh.auth.ingest_result(native,region,'f1','bypass',envelope,keyring)
    before=snapshot(native,region)
    history=fresh.assess_history(native,region,'f1',keyring)
    assert history['outcomes'][0]['assessment']['status']=='STALE_DECLARED_TICK'
    assert snapshot(native,region)==before


def test_revocation_checked_even_for_exact_replay(case):
    native,region,_,_,envelope,keyring=case
    fresh.freeze_policy(native,region,'f1',{'max_tick_lag':1})
    fresh.admit(native,region,'f1','o1',envelope,keyring)
    before=snapshot(native,region)
    for action in (lambda:fresh.admit(native,region,'f1','o1',envelope,{}),
                   lambda:fresh.assess_history(native,region,'f1',{})):
        with pytest.raises(ValueError,match='not currently trusted'):
            action()
    assert snapshot(native,region)==before


def test_assessment_does_not_consult_world_value_or_write_memory(case,monkeypatch):
    native,region,_,_,envelope,keyring=case
    fresh.freeze_policy(native,region,'f1',{'max_tick_lag':0})
    before=snapshot(native,region)
    def forbidden(*args):
        raise AssertionError('world truth must not be an admission oracle')
    monkeypatch.setattr(fresh.world,'world_value',forbidden)
    assert fresh.assess(native,region,'f1',envelope,keyring)['status']=='STALE_DECLARED_TICK'
    assert snapshot(native,region)==before


def test_task_policy_scope_cannot_be_reused_for_another_forecast(case):
    native,region,query,request,envelope,keyring=case
    fresh.freeze_policy(native,region,'f1',{'max_tick_lag':0})
    frozen=fresh.auth.freeze_task(native,region,query,'f2','forecaster',request,'sensor-a','key-1',challenge='b'*64)
    other=fresh.auth.run_observer(frozen['event']['receipt']['observation_context'],fresh.auth.TEST_KEY)
    before=snapshot(native,region)
    with pytest.raises(ValueError,match='not frozen'):
        fresh.admit(native,region,'f2','o2',other,keyring)
    assert snapshot(native,region)==before


def test_malformed_policy_row_fails_closed_without_writes(case):
    native,region,_,_,envelope,keyring=case
    fresh.persist(native,[dict(hierarchy_id=fresh.field(region),source_id='bad-control',sequence=1,
                               source_kind='user_turn',text='not-a-policy')])
    before=fresh.collect(native,[region]),fresh.audit.journal(native,region)
    with pytest.raises(ValueError,match='encoding'):
        fresh.admit(native,region,'f1','o1',envelope,keyring)
    assert (fresh.collect(native,[region]),fresh.audit.journal(native,region))==before


def test_process_restart_preserves_policy_and_complete_history(library,tmp_path):
    code='''
import json,sys
from pathlib import Path
sys.path.insert(0,'scripts')
import trajectory_observer_freshness_probe as f
n=f.NativeProbe(Path(sys.argv[2]),Path(sys.argv[3]))
try:
    rows,r,q,e,_=f.auth.controlled.prepare_rows(20270123)
    keys={('sensor-a','key-1'):f.auth.TEST_KEY}
    if sys.argv[1]=='write':
        f.persist(n,rows)
        req=dict(world_seed=20270123,entity=e,tick=1,sensor_mode='faithful')
        x=f.auth.freeze_task(n,r,q,'f1','forecaster',req,'sensor-a','key-1',challenge='a'*64)
        f.freeze_policy(n,r,'f1',{'max_tick_lag':0})
        env=f.auth.run_observer(x['event']['receipt']['observation_context'],f.auth.TEST_KEY)
        f.admit(n,r,'f1','o1',env,keys)
    print(json.dumps(dict(rows=f.collect(n,[r]),policies=f.policies(n,r),history=f.assess_history(n,r,'f1',keys),comparison=f.audit.reconcile(n,r,'f1')),sort_keys=True))
finally:
    n.close()
'''
    outputs=[]
    for mode in ('write','read'):
        p=subprocess.run([sys.executable,'-c',code,mode,str(library.resolve()),str(tmp_path)],
                         cwd=Path(__file__).resolve().parents[1],capture_output=True,text=True,check=True)
        outputs.append(json.loads(p.stdout))
    assert outputs[0]==outputs[1]


def test_reserved_reports_keep_declared_freshness_separate_from_truth(library):
    for seed in (20270123,20270124):
        result=fresh.probe(library,seed)
        assert result['integrity_status']=='PASS' and result['integrity_total']==86
        cases={c['scenario']:c for c in result['cases']}
        assert cases['lagged_strict']['result']['status']=='NOT_ADMITTED'
        assert cases['lagged_tolerated']['evaluator']['linked_reports_agree_with_world']==[False]
        fake=cases['authorized_false_current_tick']
        assert fake['result']['assessment']['status']=='MEETS_DECLARED_TICK_POLICY'
        assert fake['evaluator']['linked_reports_agree_with_world']==[False]
        assert fake['comparison']['qualified'] is False
