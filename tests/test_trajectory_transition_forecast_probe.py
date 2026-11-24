import copy
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import trajectory_transition_forecast_probe as transition


def rows(points,kind='user_turn',region='r',entity='ab'):
    return [dict(hierarchy_id=region,source_id=f'p{i}',sequence=i+1,source_kind=kind,
                 text=f'M[{entity};{tick}]={value}.') for i,(tick,value) in enumerate(points)]


@pytest.mark.parametrize('extra',['forecast','candidates','memory_path'])
def test_measurement_worker_rejects_model_and_memory_inputs(extra):
    request=dict(seed=20270127,entity='ab',tick=3,law='linear_up')
    request[extra]='forbidden'
    result=subprocess.run([sys.executable,str(transition.WORKER)],input=json.dumps(request)+'\n',
                          capture_output=True,text=True,check=True)
    assert json.loads(result.stdout)['ok'] is False


@pytest.mark.parametrize('points,target,expected',[
    ([(0,9),(1,12),(2,15)],3,18),
    ([(0,20),(1,17),(2,14)],3,11),
    ([(0,7),(1,7),(2,7)],3,7),
    ([(0,10),(2,11),(4,12)],6,13),
])
def test_exact_rate_is_fitted_from_values_including_fractional_training_gaps(points,target,expected):
    input_rows=rows(points);before=copy.deepcopy(input_rows)
    result=transition.fit(input_rows,'r','ab',target)
    assert result['proposal']['value']==expected and result['qualified'] is False
    assert input_rows==before
    if expected==7:
        assert result['predicted_value_not_observed_for_entity'] is False
    else:
        assert result['predicted_value_not_observed_for_entity'] is True


@pytest.mark.parametrize('points,target,status',[
    ([(0,1),(1,2)],3,'INSUFFICIENT_DISTINCT_TICKS'),
    ([(0,1),(0,1),(0,1)],3,'INSUFFICIENT_DISTINCT_TICKS'),
    ([(0,1),(1,2),(1,3)],3,'CONFLICTING_VALUES_AT_TICK'),
    ([(0,1),(2,3),(1,2)],3,'NONMONOTONIC_DECLARED_TICKS'),
    ([(0,1),(1,2),(2,5)],3,'INCONSISTENT_OBSERVED_RATES'),
    ([(0,1),(1,2),(2,3)],2,'TARGET_NOT_AFTER_HISTORY'),
    ([(0,10),(2,11),(4,12)],5,'NONINTEGER_TARGET'),
    ([(0,9998),(1,9999),(2,10000)],3,'TARGET_OUT_OF_RANGE'),
])
def test_insufficient_conflicting_and_unrepresentable_predictions_abstain(points,target,status):
    result=transition.fit(rows(points),'r','ab',target)
    assert result['status']==status and result['proposal'] is None


@pytest.mark.parametrize('kind,region',[('assistant_generated','r'),('user_turn','foreign')])
def test_generated_and_foreign_values_cannot_support_fitted_rate(kind,region):
    result=transition.fit(rows([(0,1),(1,2),(2,3)],kind,region),'r','ab',3)
    assert result['status']=='INSUFFICIENT_DISTINCT_TICKS' and result['points']==[]


def test_repeated_point_keeps_addresses_without_extra_training_support():
    result=transition.fit(rows([(0,1),(1,2),(1,2),(2,3)]),'r','ab',3)
    assert len(result['points'])==3 and len(result['points'][1]['addresses'])==2
    assert result['proposal']['value']==4


def test_malformed_target_measurement_does_not_disappear_from_evidence():
    data=rows([(0,1),(1,2),(2,3)])
    data.append(dict(hierarchy_id='r',source_id='bad',sequence=4,source_kind='user_turn',text='M[ab;3]=unknown.'))
    assert transition.fit(data,'r','ab',4)['status']=='MALFORMED_TARGET_MEASUREMENT'


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
    native=transition.NativeProbe(library,tmp_path)
    transition.persist(native,rows([(0,10),(1,12),(2,14)]))
    first=transition.freeze(native,'r','ab',3,'f1','forecaster')
    try:
        yield native,first
    finally:
        native.close()


def snapshot(native):
    return transition.collect(native,['r']),transition.audit.journal(native,'r')


def test_freeze_does_not_learn_proposal_and_comparison_does_not_call_world(case,monkeypatch):
    native,first=case
    before=snapshot(native)
    def forbidden(*args):
        raise AssertionError('future observer must never be queried by fit or compare')
    monkeypatch.setattr(transition,'measure',forbidden)
    result=transition.compare(native,'r','f1')
    assert result['model']['proposal']['text']=='M[ab;3]=16.'
    assert all(r['text']!='M[ab;3]=16.' for r in before[0])
    assert result['status']=='PENDING' and snapshot(native)==before


def test_new_value_match_preserves_native_occurrence_and_frozen_model_after_reopen(case):
    native,first=case
    row=dict(hierarchy_id='r',source_id='later',sequence=4,text='M[ab;3]=16.',source_kind='user_turn')
    transition.persist(native,[row])
    transition.link_measurement(native,'r','f1','o1','observer',transition.audit.address(row))
    result=transition.compare(native,'r','f1')
    assert result['status']=='MATCHES_PROPOSED_TRANSITION' and result['qualified'] is False
    before=snapshot(native)
    retry=transition.freeze(native,'r','ab',3,'f1','forecaster')
    assert retry['status']=='EXACT_REPLAY' and retry['event']==first['event']
    assert snapshot(native)==before
    native.reopen()
    assert transition.compare(native,'r','f1')==result and snapshot(native)==before


def test_later_conflict_is_preserved_without_refitting_or_weight_updates(case):
    native,_=case
    for sequence,value in ((4,16),(5,20)):
        row=dict(hierarchy_id='r',source_id=f'later-{sequence}',sequence=sequence,
                 text=f'M[ab;3]={value}.',source_kind='user_turn')
        transition.persist(native,[row])
        transition.link_measurement(native,'r','f1',f'o{sequence}','observer',transition.audit.address(row))
    before=snapshot(native)
    result=transition.compare(native,'r','f1')
    assert result['status']=='DIVERGENT_LATER_MEASUREMENTS'
    assert result['model']['proposal']['value']==16 and result['learning_applied'] is False
    assert snapshot(native)==before


@pytest.mark.parametrize('text',['M[zz;3]=16.','M[ab;4]=16.','not a measurement'])
def test_wrong_entity_tick_or_payload_cannot_be_linked(case,text):
    native,_=case
    row=dict(hierarchy_id='r',source_id='wrong-task',sequence=4,text=text,source_kind='user_turn')
    transition.persist(native,[row]);before=snapshot(native)
    with pytest.raises(ValueError,match='target entity and tick'):
        transition.link_measurement(native,'r','f1','o1','observer',transition.audit.address(row))
    assert snapshot(native)==before


def test_generic_audit_wrong_target_bypass_cannot_count_as_transition_evidence(case):
    native,_=case
    row=dict(hierarchy_id='r',source_id='bypass',sequence=4,text='M[zz;3]=16.',source_kind='user_turn')
    transition.persist(native,[row])
    transition.audit.observe_outcome(native,'r','f1','o1','caller',transition.audit.address(row))
    before=snapshot(native)
    assert transition.compare(native,'r','f1')['status']=='UNVERIFIABLE_HISTORY'
    assert snapshot(native)==before


def test_changed_native_prefix_is_not_hidden_by_frozen_model(case):
    native,_=case
    transition.persist(native,[dict(hierarchy_id='r',source_id='old-injection',sequence=0,
                                   text='M[ab;0]=99.',source_kind='user_turn')])
    assert transition.compare(native,'r','f1')['status']=='UNVERIFIABLE_HISTORY'


def test_frozen_model_cannot_be_reused_for_another_target(case):
    native,_=case;before=snapshot(native)
    with pytest.raises(ValueError,match='identity reused'):
        transition.freeze(native,'r','ab',4,'f1','forecaster')
    assert snapshot(native)==before


def test_full_forecast_and_later_comparison_survive_two_processes(library,tmp_path):
    code='''
import json,sys
from pathlib import Path
sys.path.insert(0,'scripts')
import trajectory_transition_forecast_probe as t
n=t.NativeProbe(Path(sys.argv[2]),Path(sys.argv[3]))
try:
    if sys.argv[1]=='write':
        rows=[dict(hierarchy_id='r',source_id=f'p{i}',sequence=i+1,text=f'M[ab;{i}]={10+2*i}.',source_kind='user_turn') for i in range(3)]
        t.persist(n,rows)
        t.freeze(n,'r','ab',3,'f1','forecaster')
        row=dict(hierarchy_id='r',source_id='later',sequence=4,text='M[ab;3]=16.',source_kind='user_turn')
        t.persist(n,[row]);t.link_measurement(n,'r','f1','o1','observer',t.audit.address(row))
    print(json.dumps(dict(rows=t.collect(n,['r']),journal=t.audit.journal(n,'r'),comparison=t.compare(n,'r','f1')),sort_keys=True))
finally:
    n.close()
'''
    outputs=[]
    for mode in ('write','read'):
        p=subprocess.run([sys.executable,'-c',code,mode,str(library.resolve()),str(tmp_path)],
                         cwd=Path(__file__).resolve().parents[1],capture_output=True,text=True,check=True)
        outputs.append(json.loads(p.stdout))
    assert outputs[0]==outputs[1]


def test_reports_preserve_identical_past_different_futures_and_self_copy_failure(library):
    for seed in (20270127,20270128):
        result=transition.probe(library,seed)
        assert result['integrity_status']=='PASS' and result['integrity_total']==110
        cases={c['scenario']:c for c in result['cases']}
        assert result['controlled_four_law_score']==dict(proposed=4,matches=3,misses=1)
        assert cases['linear_up']['rows']==cases['hidden_break']['rows']
        assert cases['linear_up']['initial']['model']==cases['hidden_break']['initial']['model']
        assert cases['hidden_break']['result']['status']=='DIFFERS_FROM_PROPOSED_TRANSITION'
        copy_case=cases['self_copy_as_observation']
        assert copy_case['result']['status']=='MATCHES_PROPOSED_TRANSITION'
        assert copy_case['evaluator']['supplied_measurement_matches_world'] is False
        assert copy_case['result']['qualified'] is False
        assert cases['unlinked_later']['result']['status']=='PENDING'
