import copy
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import trajectory_recent_regime_probe as recent


def rows(points,region='r',kind='user_turn'):
    return [dict(hierarchy_id=region,source_id=f'p{i}',sequence=i+1,source_kind=kind,text=f'M[ab;{tick}]={value}.')
            for i,(tick,value) in enumerate(points)]


def test_break_suspends_until_three_distinct_recent_points_and_keeps_full_history():
    points=[(0,10),(1,11),(2,12),(3,17)]
    first=recent.fit(rows(points),'r','ab',4)
    assert first['status']=='SUSPENDED_PENDING_STABLE_SUFFIX' and first['proposal'] is None
    assert first['active_from_tick']==2 and first['active_tick_count']==2
    points.append((4,18))
    second=recent.fit(rows(points),'r','ab',5)
    assert second['status']=='SUSPENDED_PENDING_STABLE_SUFFIX' and second['active_from_tick']==3
    points.append((5,19));data=rows(points);before=copy.deepcopy(data)
    recovered=recent.fit(data,'r','ab',6)
    assert recovered['proposal']['value']==20 and recovered['active_tick_count']==3
    assert recovered['excluded_earlier_point_count']==3 and len(recovered['history_points'])==6
    assert recent.base.fit(data,'r','ab',6)['proposal'] is None
    assert data==before


@pytest.mark.parametrize('tail,expected',[
    ([(3,20),(4,22),(5,24)],26),
    ([(3,20),(4,18),(5,16)],14),
    ([(3,20),(4,20),(5,20)],20),
    ([(4,20),(6,21),(8,22)],23),
])
def test_new_rate_is_derived_from_recent_values_including_fractional_gaps(tail,expected):
    data=rows([(0,10),(1,11),(2,12)]+tail)
    target=10 if tail[-1][0]==8 else 6
    result=recent.fit(data,'r','ab',target)
    assert result['proposal']['value']==expected
    assert result['qualified'] is False and result['learning_applied'] is False


def test_latest_unstable_suffix_does_not_fall_back_to_old_good_segment():
    result=recent.fit(rows([(0,10),(1,11),(2,12),(3,17),(4,18),(5,20)]),'r','ab',6)
    assert result['status']=='SUSPENDED_PENDING_STABLE_SUFFIX'
    assert result['active_from_tick']==4 and result['proposal'] is None


@pytest.mark.parametrize('points,status',[
    ([(0,1),(1,2)],'INSUFFICIENT_DISTINCT_TICKS'),
    ([(0,1),(1,2),(1,3),(2,4),(3,5)],'CONFLICTING_VALUES_AT_TICK'),
    ([(0,1),(2,3),(1,2),(3,4),(4,5)],'NONMONOTONIC_DECLARED_TICKS'),
    ([(0,1),(1,2),(2,3)],'TARGET_NOT_AFTER_HISTORY'),
])
def test_adaptation_does_not_hide_invalid_or_insufficient_history(points,status):
    result=recent.fit(rows(points),'r','ab',2 if status=='TARGET_NOT_AFTER_HISTORY' else 6)
    assert result['status']==status and result['proposal'] is None


def test_repeated_measurement_does_not_complete_stable_suffix():
    result=recent.fit(rows([(0,10),(1,11),(2,12),(3,17),(4,18),(4,18)]),'r','ab',5)
    assert result['status']=='SUSPENDED_PENDING_STABLE_SUFFIX' and result['active_tick_count']==2
    assert len(result['history_points'][-1]['addresses'])==2


@pytest.mark.parametrize('region,kind',[('foreign','user_turn'),('r','assistant_generated')])
def test_foreign_or_generated_tail_does_not_recover_after_break(region,kind):
    data=rows([(0,10),(1,11),(2,12),(3,17)])
    extra=rows([(4,18),(5,19)],region,kind)
    for i,row in enumerate(extra): row.update(source_id=f'extra-{i}',sequence=5+i)
    result=recent.fit(data+extra,'r','ab',6)
    assert result['status']=='SUSPENDED_PENDING_STABLE_SUFFIX' and len(result['history_points'])==4


def test_novelty_is_checked_against_full_history_not_only_active_suffix():
    result=recent.fit(rows([(0,5),(1,6),(2,7),(3,3),(4,4),(5,5)]),'r','ab',6)
    assert result['proposal']['value']==6 and result['predicted_value_not_observed_for_entity'] is False


def test_active_suffix_still_obeys_representation_bounds():
    result=recent.fit(rows([(0,1),(1,2),(2,3),(3,9996),(4,9998),(5,10000)]),'r','ab',6)
    assert result['status']=='TARGET_OUT_OF_RANGE' and result['proposal'] is None


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
    native=recent.base.NativeProbe(library,tmp_path)
    recent.base.persist(native,rows([(0,10),(1,11),(2,12)]))
    recent.freeze(native,'r','ab',3,'f3','forecaster')
    try:
        yield native
    finally:
        native.close()


def observe(native,tick,value,forecast_id=None):
    row=dict(hierarchy_id='r',source_id=f'later-{tick}',sequence=tick+1,
             text=f'M[ab;{tick}]={value}.',source_kind='user_turn')
    recent.base.persist(native,[row])
    if forecast_id is not None:
        recent.link_measurement(native,'r',forecast_id,'o-'+forecast_id,'observer',recent.base.audit.address(row))


def snapshot(native):
    return recent.base.collect(native,['r']),recent.base.audit.journal(native,'r')


def test_original_error_stays_frozen_after_new_regime_recovers(case):
    native=case
    observe(native,3,17,'f3');failure=recent.compare(native,'r','f3')
    assert failure['status']=='DIFFERS_FROM_PROPOSED_TRANSITION'
    recent.freeze(native,'r','ab',4,'f4','forecaster')
    assert recent.compare(native,'r','f4')['model']['proposal'] is None
    observe(native,4,18,'f4')
    recent.freeze(native,'r','ab',5,'f5','forecaster');observe(native,5,19,'f5')
    recent.freeze(native,'r','ab',6,'f6','forecaster')
    assert recent.compare(native,'r','f6')['model']['proposal']['value']==20
    observe(native,6,20,'f6');recovered=recent.compare(native,'r','f6')
    assert recovered['status']=='MATCHES_PROPOSED_TRANSITION'
    before=snapshot(native)
    assert recent.compare(native,'r','f3')==failure
    assert recent.freeze(native,'r','ab',3,'f3','forecaster')['status']=='EXACT_REPLAY'
    assert snapshot(native)==before
    native.reopen()
    assert recent.compare(native,'r','f3')==failure and recent.compare(native,'r','f6')==recovered


def test_fit_and_comparison_never_query_future_world(case,monkeypatch):
    native=case
    def forbidden(*args):
        raise AssertionError('future world must not select the active suffix')
    monkeypatch.setattr(recent.base,'measure',forbidden)
    before=snapshot(native)
    assert recent.compare(native,'r','f3')['model']['proposal']['value']==13
    assert snapshot(native)==before


def test_adaptation_uses_observations_without_requiring_evaluator_error_labels(case):
    native=case
    observe(native,3,17);observe(native,4,18);observe(native,5,19)
    assert recent.compare(native,'r','f3')['status']=='PENDING'
    recent.freeze(native,'r','ab',6,'f6','forecaster')
    assert recent.compare(native,'r','f6')['model']['proposal']['value']==20


def test_old_prefix_injection_invalidates_comparison(case):
    native=case
    recent.base.persist(native,[dict(hierarchy_id='r',source_id='injected',sequence=0,
                                    text='M[ab;0]=99.',source_kind='user_turn')])
    assert recent.compare(native,'r','f3')['status']=='UNVERIFIABLE_HISTORY'


def test_forecast_identity_cannot_change_target_after_error(case):
    native=case;observe(native,3,17,'f3');before=snapshot(native)
    with pytest.raises(ValueError,match='identity reused'):
        recent.freeze(native,'r','ab',4,'f3','forecaster')
    assert snapshot(native)==before


def test_wrong_target_cannot_be_linked(case):
    native=case
    row=dict(hierarchy_id='r',source_id='wrong-target',sequence=4,text='M[ab;4]=14.',source_kind='user_turn')
    recent.base.persist(native,[row]);before=snapshot(native)
    with pytest.raises(ValueError,match='target entity and tick'):
        recent.link_measurement(native,'r','f3','o1','observer',recent.base.audit.address(row))
    assert snapshot(native)==before


def test_complete_error_and_recovery_history_survives_two_processes(library,tmp_path):
    code='''
import json,sys
from pathlib import Path
sys.path.insert(0,'scripts')
import trajectory_recent_regime_probe as r
n=r.base.NativeProbe(Path(sys.argv[2]),Path(sys.argv[3]))
try:
    if sys.argv[1]=='write':
        rows=[dict(hierarchy_id='r',source_id=f'p{i}',sequence=i+1,text=f'M[ab;{i}]={10+i}.',source_kind='user_turn') for i in range(3)]
        r.base.persist(n,rows)
        for tick,value in ((3,17),(4,18),(5,19),(6,20)):
            fid=f'f{tick}'
            r.freeze(n,'r','ab',tick,fid,'forecaster')
            row=dict(hierarchy_id='r',source_id=f'p{tick}',sequence=tick+1,text=f'M[ab;{tick}]={value}.',source_kind='user_turn')
            r.base.persist(n,[row]);r.link_measurement(n,'r',fid,f'o{tick}','observer',r.base.audit.address(row))
    print(json.dumps(dict(rows=r.base.collect(n,['r']),journal=r.base.audit.journal(n,'r'),results=[r.compare(n,'r',f'f{t}') for t in range(3,7)]),sort_keys=True))
finally:
    n.close()
'''
    output=[]
    for mode in ('write','read'):
        p=subprocess.run([sys.executable,'-c',code,mode,str(library.resolve()),str(tmp_path)],
                         cwd=Path(__file__).resolve().parents[1],capture_output=True,text=True,check=True)
        output.append(json.loads(p.stdout))
    assert output[0]==output[1]
    assert output[1]['results'][0]['status']=='DIFFERS_FROM_PROPOSED_TRANSITION'
    assert output[1]['results'][-1]['status']=='MATCHES_PROPOSED_TRANSITION'


def test_reports_preserve_break_recovery_poisoning_and_self_copy(library):
    for seed in (20270129,20270130):
        result=recent.probe(library,seed)
        assert result['integrity_status']=='PASS' and result['integrity_total']==204
        assert result['hidden_break_comparison']==dict(whole_history=dict(matches=0,misses=1,abstentions=3),
                                                       recent_suffix=dict(matches=1,misses=1,abstentions=2))
        cases={c['scenario']:c for c in result['cases']}
        assert cases['hidden_break']['steps'][-1]['recent_result']['model']['active_from_tick']==3
        assert cases['poisoned_tail']['steps'][-1]['evaluator']['recent_matches_world'] is False
        assert cases['generated_tail']['steps'][-1]['recent_result']['model']['proposal'] is None
        copied=cases['self_copy_feedback']['steps']
        assert all(s['recent_result']['status']=='MATCHES_PROPOSED_TRANSITION' for s in copied)
        assert all(s['evaluator']['recent_matches_world'] is False for s in copied)
