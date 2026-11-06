import copy
import os
from pathlib import Path
import sys

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from mobile_region_replay import NativeProbe
from trajectory_feedback_continuity_probe import continuity_read
from trajectory_feedback_ledger_probe import events,ledger_region,receipt,record
from trajectory_feedback_withdrawal_probe import feedback_projection,probe,withdraw,withdrawal_read,withdrawal_region,withdrawals
from trajectory_question_frame_probe import collect,persist
from trajectory_route_relation_probe import fixture


@pytest.fixture
def native_case(tmp_path):
    library=Path(os.environ.get('MEMORIA_NATIVE_LIBRARY','build/trajectory-native/libmemoria_mobile.so'))
    if not library.exists(): pytest.skip('native library required')
    native=NativeProbe(library,tmp_path)
    rows,region,queries=fixture('same_root_two_routes',20270107)
    persist(native,rows)
    query=next(q['text'] for q in queries if q['name']=='literal_cue')
    root=withdrawal_read(native,region,query)['raw_view']['candidates'][0]['payload_id']
    binding=receipt(native,region,query,root)
    record(native,binding,'oppose-a','a','oppose')
    try: yield native,rows,region,query,binding,events(native,region)[0]
    finally: native.close()


def test_withdraw_wrong_veto_restores_candidate_preserving_both_histories(native_case):
    native,_,region,query,_,target=native_case
    ledger=events(native,region);rows=collect(native,[region])
    assert withdrawal_read(native,region,query,enabled=True)['withheld_candidates']
    withdraw(native,region,'withdraw','a',target)
    after=withdrawal_read(native,region,query,enabled=True)
    assert after['available_candidates']==after['raw_view']['candidates']
    assert not after['withheld_candidates']
    assert not after['feedback_projection'][0]['active']
    assert after['feedback_projection'][0]['withdrawal']['event']['target_event_id']=='oppose-a'
    assert events(native,region)==ledger and collect(native,[region])==rows
    # Existing opt-in policies retain their old semantics; only the new reader applies withdrawals.
    assert continuity_read(native,region,query,enabled=True)['withheld_candidates']
    native.reopen()
    assert withdrawal_read(native,region,query,enabled=True)==after
    assert after['answer'] is None and not after['qualified'] and not after['selection_used']


def test_old_feedback_retry_does_not_reactivate_but_new_event_can(native_case):
    native,_,region,query,binding,target=native_case
    withdraw(native,region,'withdraw','a',target)
    assert withdraw(native,region,'withdraw','a',target)['status']=='EXACT_REPLAY'
    assert record(native,binding,'oppose-a','a','oppose')['status']=='EXACT_REPLAY'
    assert not withdrawal_read(native,region,query,enabled=True)['withheld_candidates']
    record(native,binding,'new-opposition','a','oppose')
    after=withdrawal_read(native,region,query,enabled=True)
    assert after['withheld_candidates']
    assert [p['active'] for p in after['feedback_projection']]==[False,True]
    assert len(withdrawals(native,region))==1


@pytest.mark.parametrize('change',['actor','address','content','region'])
def test_invalid_withdrawals_never_write(native_case,change):
    native,_,region,_,_,target=native_case
    altered=copy.deepcopy(target);actor='a';scope=region
    if change=='actor':actor='b'
    if change=='address':altered['address']['sequence']+=1
    if change=='content':altered['event']['stance']='support'
    if change=='region':scope='conversation:foreign'
    with pytest.raises(ValueError):withdraw(native,scope,'withdraw',actor,altered)
    assert withdrawals(native,region)==[] and withdrawals(native,'conversation:foreign')==[]
    assert len(events(native,region))==1


def test_reused_request_or_second_withdrawal_rejects(native_case):
    native,_,region,_,binding,target=native_case
    record(native,binding,'oppose-b','b','oppose')
    second=events(native,region)[1]
    withdraw(native,region,'request','a',target)
    saved=withdrawals(native,region)
    with pytest.raises(ValueError,match='identity reused'):withdraw(native,region,'request','b',second)
    with pytest.raises(ValueError,match='already withdrawn'):withdraw(native,region,'another','a',target)
    assert withdrawals(native,region)==saved


def test_one_withdrawal_cannot_cancel_other_opposition(native_case):
    native,_,region,query,binding,target=native_case
    record(native,binding,'oppose-b','b','oppose')
    withdraw(native,region,'withdraw-a','a',target)
    assert withdrawal_read(native,region,query,enabled=True)['withheld_candidates']
    second=events(native,region)[1]
    withdraw(native,region,'withdraw-b','b',second)
    assert not withdrawal_read(native,region,query,enabled=True)['withheld_candidates']


def test_withdraw_support_does_not_cancel_opposition(native_case):
    native,_,region,query,binding,_=native_case
    record(native,binding,'support-b','b','support')
    support=events(native,region)[1]
    before=withdrawal_read(native,region,query,enabled=True)
    assert before['decisions'][0]['status']=='DISPUTED'
    withdraw(native,region,'withdraw-support','b',support)
    after=withdrawal_read(native,region,query,enabled=True)
    assert after['decisions'][0]['status']=='OPPOSED' and after['withheld_candidates']


def test_historical_withdrawal_survives_append_and_does_not_mutate_old_receipt(native_case):
    native,rows,region,query,binding,target=native_case
    persist(native,[dict(hierarchy_id=region,source_id='later',sequence=max(r['sequence'] for r in rows)+1,
                         text='Observação posterior.',source_kind='user_turn')])
    assert receipt(native,region,query,binding['candidate']['payload_id'])!=binding
    assert withdrawal_read(native,region,query,enabled=True)['withheld_candidates']
    withdraw(native,region,'withdraw','a',target)
    after=withdrawal_read(native,region,query,enabled=True)
    assert not after['withheld_candidates']
    assert events(native,region)[0]['event']['receipt']==binding
    native.reopen()
    assert withdrawal_read(native,region,query,enabled=True)==after


def test_projection_rejects_corrupted_control_and_reader_rejects_control_scopes(native_case):
    native,_,region,query,_,target=native_case
    withdraw(native,region,'withdraw','a',target)
    controls=withdrawals(native,region);ledger=events(native,region)
    altered=copy.deepcopy(controls);altered[0]['event']['target_sha256']='missing'
    with pytest.raises(ValueError):feedback_projection(ledger,altered)
    with pytest.raises(ValueError):feedback_projection(ledger,controls+controls)
    for scope in (ledger_region(region),withdrawal_region(region)):
        for enabled in (False,True):
            with pytest.raises(ValueError,match='learning region'):withdrawal_read(native,scope,query,enabled=enabled)
    assert not withdrawal_read(native,region,query)['candidate_filter_used']


def test_withdrawal_codec_preserves_literal_request_id(native_case):
    native,_,region,_,_,target=native_case
    request='retirada "é"\n\\literal'
    withdraw(native,region,request,'a',target)
    native.reopen()
    assert withdrawals(native,region)[0]['event']['request_id']==request
    assert withdraw(native,region,request,'a',target)['status']=='EXACT_REPLAY'


def test_probe_preserves_negative_effect_of_withdrawing_valid_veto():
    library=Path(os.environ.get('MEMORIA_NATIVE_LIBRARY','build/trajectory-native/libmemoria_mobile.so'))
    if not library.exists():pytest.skip('native library required')
    report=probe(library,20270107)
    assert report['integrity_status']=='PASS'
    assert report['integrity_passed']==report['integrity_total']==145
    effects=report['effects']
    assert effects['wrong_veto_withdrawn']['before']['false_negative']==1
    assert effects['wrong_veto_withdrawn']['after']['exact_set']
    assert effects['correct_veto_withdrawn']['before']['exact_set']
    assert effects['correct_veto_withdrawn']['after']['false_positive']==1
    assert effects['other_opposition_remains']['after']['false_negative']==1
    assert effects['support_withdrawn']['after']['false_negative']==1
