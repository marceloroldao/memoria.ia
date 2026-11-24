import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import trajectory_rule_selection_probe as selection


def trial(a,b):
    cost={'match':0,'abstention':1,'mismatch':2}
    return dict(kinds=dict(whole_history=a,recent_suffix=b),losses=dict(whole_history=cost[a],recent_suffix=cost[b]))


@pytest.mark.parametrize('trials,proposals,status,leader',[
    ([],{'whole_history':{'value':1},'recent_suffix':{'value':1}},'CONSENSUS_WITHOUT_LEADER',None),
    ([],{'whole_history':None,'recent_suffix':{'value':1}},'ABSTAIN_NO_SUPPORTED_LEADER',None),
    ([trial('mismatch','match')],{'whole_history':{'value':1},'recent_suffix':{'value':2}},'ABSTAIN_NO_SUPPORTED_LEADER',None),
    ([trial('mismatch','match')]*2,{'whole_history':{'value':1},'recent_suffix':{'value':2}},'PAST_LOSS_LEADER','recent_suffix'),
    ([trial('match','mismatch')]*2,{'whole_history':None,'recent_suffix':{'value':2}},'ABSTAIN_LEADER_HAS_NO_PROPOSAL','whole_history'),
    ([trial('abstention','abstention')]*2,{'whole_history':{'value':1},'recent_suffix':{'value':2}},'ABSTAIN_NO_SUPPORTED_LEADER',None),
])
def test_explicit_past_loss_policy_preserves_ties_minimum_support_and_leader_abstention(trials,proposals,status,leader):
    result=selection.choose(proposals,trials)
    assert result['status']==status and result['selected_rule']==leader
    if status.startswith('ABSTAIN'): assert result['proposal'] is None


@pytest.fixture
def library():
    path=Path(os.environ.get('MEMORIA_NATIVE_LIBRARY','build/trajectory-native/libmemoria_mobile.so'))
    if not path.exists():
        if 'MEMORIA_NATIVE_LIBRARY' in os.environ:
            pytest.fail('Explicit native BDR library is missing')
        pytest.skip('Native integration runs in pinned-BDR CI')
    return path


def candidates(native,tick):
    ids=dict(whole_history=f'all-{tick}',recent_suffix=f'recent-{tick}')
    selection.base.freeze(native,'r','ab',tick,ids['whole_history'],'whole')
    selection.recent.freeze(native,'r','ab',tick,ids['recent_suffix'],'recent')
    return ids


@pytest.fixture
def case(library,tmp_path):
    native=selection.base.NativeProbe(library,tmp_path)
    rows=[dict(hierarchy_id='r',source_id=f'p{i}',sequence=i+1,text=f'M[ab;{i}]={10+i}.',source_kind='user_turn') for i in range(3)]
    selection.base.persist(native,rows)
    ids=candidates(native,3)
    try: yield native,ids
    finally: native.close()


def measurement(native,tick,value,source='later'):
    rows=selection.base.collect(native,['r'])
    row=dict(hierarchy_id='r',source_id=source,sequence=max(r['sequence'] for r in rows)+1,
             text=f'M[ab;{tick}]={value}.',source_kind='user_turn')
    selection.base.persist(native,[row]);return row


def link_pair(native,ids,row):
    address=selection.base.audit.address(row)
    selection.base.link_measurement(native,'r',ids['whole_history'],'o-'+ids['whole_history'],'observer',address)
    selection.recent.link_measurement(native,'r',ids['recent_suffix'],'o-'+ids['recent_suffix'],'observer',address)


def history(native,target):
    return selection.historical_trials(selection.base.audit.journal(native,'r'),selection.base.collect(native,['r']),'ab',target)


def snapshot(native):
    return selection.base.collect(native,['r']),selection.base.audit.journal(native,'r')


def test_same_prefix_same_measurement_counts_once_and_exact_retry_does_not_inflate_support(case):
    native,ids=case
    assert selection.base.freeze(native,'r','ab',3,ids['whole_history'],'whole')['status']=='EXACT_REPLAY'
    row=measurement(native,3,13);link_pair(native,ids,row)
    before=snapshot(native);trials,skipped=history(native,4)
    assert len(trials)==1 and skipped==[]
    assert trials[0]['losses']==dict(whole_history=0,recent_suffix=0)
    assert snapshot(native)==before


def test_distinct_forecast_ids_for_same_past_target_cannot_inflate_trials(case):
    native,ids=case
    selection.base.freeze(native,'r','ab',3,'duplicate','whole')
    row=measurement(native,3,13);link_pair(native,ids,row)
    trials,skipped=history(native,4)
    assert trials==[] and skipped[0]['reason']=='MISSING_OR_AMBIGUOUS_CANDIDATE_PAIR'


def test_equal_text_from_different_occurrences_is_not_a_paired_trial(case):
    native,ids=case
    first=measurement(native,3,13,'a');second=measurement(native,3,13,'b')
    selection.base.link_measurement(native,'r',ids['whole_history'],'o1','observer',selection.base.audit.address(first))
    selection.recent.link_measurement(native,'r',ids['recent_suffix'],'o2','observer',selection.base.audit.address(second))
    trials,skipped=history(native,4)
    assert trials==[] and skipped[0]['reason']=='DIFFERENT_MEASUREMENT_OCCURRENCES'


def test_unlinked_or_ambiguous_labels_cannot_score_candidates(case):
    native,ids=case
    first=measurement(native,3,13,'a')
    selection.base.link_measurement(native,'r',ids['whole_history'],'o1','observer',selection.base.audit.address(first))
    assert history(native,4)[1][0]['reason']=='MISSING_OR_AMBIGUOUS_OUTCOME_PAIR'
    selection.recent.link_measurement(native,'r',ids['recent_suffix'],'o2','observer',selection.base.audit.address(first))
    second=measurement(native,3,99,'b')
    selection.base.link_measurement(native,'r',ids['whole_history'],'o3','observer',selection.base.audit.address(second))
    trials,skipped=history(native,4)
    assert trials==[] and skipped[0]['reason']=='MISSING_OR_AMBIGUOUS_OUTCOME_PAIR'


def test_forecasts_from_different_training_prefixes_are_not_compared(library,tmp_path):
    native=selection.base.NativeProbe(library,tmp_path)
    try:
        rows=[dict(hierarchy_id='r',source_id=f'p{i}',sequence=i+1,text=f'M[ab;{i}]={10+i}.',source_kind='user_turn') for i in range(3)]
        selection.base.persist(native,rows)
        selection.base.freeze(native,'r','ab',3,'all-3','whole')
        selection.base.persist(native,[dict(hierarchy_id='r',source_id='irrelevant',sequence=4,text='M[zz;0]=2.',source_kind='user_turn')])
        selection.recent.freeze(native,'r','ab',3,'recent-3','recent')
        row=measurement(native,3,13);link_pair(native,dict(whole_history='all-3',recent_suffix='recent-3'),row)
        trials,skipped=history(native,4)
        assert trials==[] and skipped[0]['reason']=='DIFFERENT_TRAINING_PREFIXES'
    finally: native.close()


def test_later_declared_tick_is_not_used_even_if_already_recorded(case):
    native,_=case
    ids=candidates(native,9)
    row=measurement(native,9,19);link_pair(native,ids,row)
    trials,skipped=history(native,5)
    assert all(t['tick']<5 for t in trials)
    assert not any(t['tick']==9 for t in trials+skipped)


@pytest.mark.parametrize('linked',[False,True])
def test_current_outcome_cannot_leak_into_freeze_decision(case,linked):
    native,ids=case;row=measurement(native,3,13)
    if linked: link_pair(native,ids,row)
    before=snapshot(native)
    with pytest.raises(ValueError,match='current prefix and remain unobserved'):
        selection.freeze(native,'r',ids,'s3','selector')
    assert snapshot(native)==before


def test_wrong_candidate_rule_or_target_is_rejected_before_writing(case):
    native,ids=case;before=snapshot(native)
    with pytest.raises(ValueError,match='model format'):
        selection.freeze(native,'r',dict(whole_history=ids['recent_suffix'],recent_suffix=ids['whole_history']),'bad','selector')
    assert snapshot(native)==before
    other=candidates(native,4);before=snapshot(native)
    with pytest.raises(ValueError,match='current prefix'):
        selection.freeze(native,'r',dict(whole_history=ids['whole_history'],recent_suffix=other['recent_suffix']),'bad','selector')
    assert snapshot(native)==before


def test_frozen_score_ignores_labels_added_after_cutoff_and_survives_reopen(case):
    native,ids=case
    first=selection.freeze(native,'r',ids,'s3','selector')
    initial=selection.compare(native,'r','s3')
    assert initial['model']['paired_trials']==[]
    row=measurement(native,3,13);link_pair(native,ids,row)
    selection.link_measurement(native,'r','s3','os3','observer',selection.base.audit.address(row))
    before=snapshot(native);result=selection.compare(native,'r','s3')
    assert result['model']==initial['model'] and result['status']=='MATCHES_SELECTED_PROPOSAL'
    assert len(history(native,4)[0])==1
    assert selection.freeze(native,'r',ids,'s3','selector')['event']==first['event']
    assert snapshot(native)==before
    native.reopen()
    assert selection.compare(native,'r','s3')==result and snapshot(native)==before


def test_current_decision_and_comparison_never_query_world(case,monkeypatch):
    native,ids=case
    def forbidden(*args): raise AssertionError('future world must not rank rules')
    monkeypatch.setattr(selection.base,'measure',forbidden)
    selection.freeze(native,'r',ids,'s3','selector');before=snapshot(native)
    result=selection.compare(native,'r','s3')
    assert result['model']['status']=='CONSENSUS_WITHOUT_LEADER'
    assert result['qualified'] is False and snapshot(native)==before


def test_injected_old_prefix_invalidates_selector_comparison(case):
    native,ids=case;selection.freeze(native,'r',ids,'s3','selector')
    selection.base.persist(native,[dict(hierarchy_id='r',source_id='injected',sequence=0,text='M[ab;0]=99.',source_kind='user_turn')])
    assert selection.compare(native,'r','s3')['status']=='UNVERIFIABLE_HISTORY'


def test_generic_audit_wrong_target_label_is_not_used_for_scoring(case):
    native,ids=case
    row=measurement(native,4,14)
    for i,r in enumerate(selection.RULES):
        selection.base.audit.observe_outcome(native,'r',ids[r],f'o{i}','caller',selection.base.audit.address(row))
    trials,skipped=history(native,5)
    assert trials==[] and skipped[0]['reason']=='INVALID_TARGET_MEASUREMENT'


def test_complete_selection_history_survives_two_processes(library,tmp_path):
    code='''
import json,sys
from pathlib import Path
sys.path.insert(0,'scripts')
import trajectory_rule_selection_probe as s
n=s.base.NativeProbe(Path(sys.argv[2]),Path(sys.argv[3]))
try:
    if sys.argv[1]=='write':
        rows=[dict(hierarchy_id='r',source_id=f'p{i}',sequence=i+1,text=f'M[ab;{i}]={10+i}.',source_kind='user_turn') for i in range(3)]
        s.base.persist(n,rows)
        for t,value in ((3,17),(4,18),(5,19),(6,20),(7,21)):
            ids=dict(whole_history=f'all-{t}',recent_suffix=f'recent-{t}')
            s.base.freeze(n,'r','ab',t,ids['whole_history'],'whole')
            s.recent.freeze(n,'r','ab',t,ids['recent_suffix'],'recent')
            s.freeze(n,'r',ids,f'select-{t}','selector')
            row=dict(hierarchy_id='r',source_id=f'p{t}',sequence=t+1,text=f'M[ab;{t}]={value}.',source_kind='user_turn')
            s.base.persist(n,[row]);a=s.base.audit.address(row)
            s.base.link_measurement(n,'r',ids['whole_history'],f'oa{t}','observer',a)
            s.recent.link_measurement(n,'r',ids['recent_suffix'],f'or{t}','observer',a)
            s.link_measurement(n,'r',f'select-{t}',f'os{t}','observer',a)
    print(json.dumps(dict(rows=s.base.collect(n,['r']),journal=s.base.audit.journal(n,'r'),results=[s.compare(n,'r',f'select-{t}') for t in range(3,8)]),sort_keys=True))
finally: n.close()
'''
    output=[]
    for mode in ('write','read'):
        p=subprocess.run([sys.executable,'-c',code,mode,str(library.resolve()),str(tmp_path)],
                         cwd=Path(__file__).resolve().parents[1],capture_output=True,text=True,check=True)
        output.append(json.loads(p.stdout))
    assert output[0]==output[1]
    assert output[1]['results'][-1]['model']['selected_rule']=='recent_suffix'


def test_reports_keep_past_selection_distinct_from_true_source_quality(library):
    for seed in (20270131,20270132):
        result=selection.probe(library,seed)
        assert result['integrity_status']=='PASS' and result['integrity_total']==230
        cases={c['scenario']:c for c in result['cases']}
        for case in result['cases']:
            ids={e['event']['forecast_id'] for e in case['final_journal'] if e['event']['op']=='FORECAST'}
            assert len(ids)==15
            assert len(case['final_rows'])==8
            for step in case['steps']:
                assert set(step['result']['model']['candidate_ids'].values())<=ids
        recovered=cases['hidden_break']['steps']
        assert recovered[-2]['result']['model']['proposal'] is None
        assert recovered[-1]['result']['model']['selected_rule']=='recent_suffix'
        assert recovered[-1]['evaluator']['proposal_matches_world'] is True
        poisoned=cases['poisoned_labels']['steps'][-1]
        assert poisoned['result']['model']['selected_rule']=='recent_suffix'
        assert poisoned['result']['status']=='MATCHES_SELECTED_PROPOSAL'
        assert poisoned['evaluator']['proposal_matches_world'] is False
        copied=cases['self_copy_labels']['steps']
        assert all(s['result']['status']=='MATCHES_SELECTED_PROPOSAL' for s in copied)
        assert all(s['evaluator']['proposal_matches_world'] is False for s in copied)


def test_late_prior_label_conflict_cannot_rewrite_an_already_frozen_score(case):
    native,ids=case
    observed=measurement(native,3,13,'initial-label');link_pair(native,ids,observed)
    next_ids=candidates(native,4)
    selection.freeze(native,'r',next_ids,'s4','selector')
    frozen=selection.compare(native,'r','s4')
    assert len(frozen['model']['paired_trials'])==1
    contradictory=measurement(native,3,99,'late-label')
    address=selection.base.audit.address(contradictory)
    selection.base.link_measurement(native,'r',ids['whole_history'],'late-a','observer',address)
    selection.recent.link_measurement(native,'r',ids['recent_suffix'],'late-r','observer',address)
    assert any(t['tick']==3 and t['reason']=='MISSING_OR_AMBIGUOUS_OUTCOME_PAIR' for t in history(native,5)[1])
    before=snapshot(native)
    assert selection.compare(native,'r','s4')==frozen
    assert snapshot(native)==before
