import copy
import os
from pathlib import Path
import sys

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from mobile_region_replay import NativeProbe
from trajectory_feedback_continuity_probe import continuity_decision, continuity_read, historical_proofs, probe, witness_provenance
from trajectory_feedback_gate_probe import gated_read
from trajectory_feedback_ledger_probe import events, ledger_region, receipt, record
from trajectory_question_frame_probe import collect, persist
from trajectory_route_relation_probe import fixture


@pytest.fixture
def native_case(tmp_path):
    library=Path(os.environ.get('MEMORIA_NATIVE_LIBRARY','build/trajectory-native/libmemoria_mobile.so'))
    if not library.exists(): pytest.skip('native library required')
    native=NativeProbe(library,tmp_path)
    rows,region,queries=fixture('partial_overlap',20270105)
    persist(native,rows)
    query=next(q for q in queries if q['name']=='literal_cue')
    before=continuity_read(native,region,query['text'],enabled=True)
    target=next(c for c in before['raw_view']['candidates'] if any(o[1]=='added-map-target' for o in c['origins']))
    binding=receipt(native,region,query['text'],target['payload_id'])
    record(native,binding,'oppose','a','oppose')
    try: yield native,rows,region,query,target,binding
    finally: native.close()


def append(native, rows, region, text='Observação posterior.', kind='user_turn'):
    persist(native,[dict(hierarchy_id=region,source_id='later',sequence=max(r['sequence'] for r in rows)+1,
                        text=text,source_kind=kind)])


@pytest.mark.parametrize('kind',['user_turn','assistant_generated'])
def test_identical_evidence_carries_veto_across_append_and_cold_restart(native_case,kind):
    native,rows,region,query,target,binding=native_case
    append(native,rows,region,kind=kind)
    current=receipt(native,region,query['text'],target['payload_id'])
    assert current['snapshot_sha256']!=binding['snapshot_sha256']
    assert current['candidate']==binding['candidate']
    assert not gated_read(native,region,query['text'],enabled=True)['withheld_candidates']
    before_rows=collect(native,[region]); ledger=events(native,region)
    result=continuity_read(native,region,query['text'],enabled=True)
    assert result['withheld_candidates']==[target]
    item=next(d for d in result['decisions'] if d['payload_id']==target['payload_id'])
    assert item['carried_event_count']==1 and item['feedback'][0]['match_kind']=='IDENTICAL_CANDIDATE_EVIDENCE'
    assert collect(native,[region])==before_rows and events(native,region)==ledger
    native.reopen()
    assert continuity_read(native,region,query['text'],enabled=True)==result
    assert result['answer'] is None and not result['qualified'] and not result['selection_used']


def test_same_payload_with_new_occurrence_does_not_inherit_veto(native_case):
    native,rows,region,query,target,binding=native_case
    append(native,rows,region,text=target['text'])
    current=receipt(native,region,query['text'],target['payload_id'])
    assert current['candidate']['payload_id']==binding['candidate']['payload_id']
    assert len(current['candidate']['origins'])==len(binding['candidate']['origins'])+1
    result=continuity_read(native,region,query['text'],enabled=True)
    assert not result['withheld_candidates']
    assert all(d['status']=='NO_FEEDBACK' for d in result['decisions'])


def test_new_route_evidence_on_same_root_expires_veto(tmp_path):
    library=Path(os.environ.get('MEMORIA_NATIVE_LIBRARY','build/trajectory-native/libmemoria_mobile.so'))
    if not library.exists(): pytest.skip('native library required')
    native=NativeProbe(library,tmp_path)
    try:
        before,region,queries=fixture('composed',20270105)
        after,_,_=fixture('same_root_two_routes',20270105)
        assert after[:len(before)]==before
        persist(native,before)
        query=next(q['text'] for q in queries if q['name']=='literal_cue')
        initial=continuity_read(native,region,query,enabled=True)
        root=initial['raw_view']['candidates'][0]['payload_id']
        binding=receipt(native,region,query,root)
        record(native,binding,'oppose','a','oppose')
        persist(native,after[len(before):])
        current=receipt(native,region,query,root)
        assert current['candidate']['origins']==binding['candidate']['origins']
        assert current['candidate']['route_evidence']!=binding['candidate']['route_evidence']
        assert not continuity_read(native,region,query,enabled=True)['withheld_candidates']
    finally: native.close()


def test_current_support_cannot_outvote_historical_opposition(native_case):
    native,rows,region,query,target,_=native_case
    append(native,rows,region)
    current=receipt(native,region,query['text'],target['payload_id'])
    for i in range(3): record(native,current,f'support-{i}','b','support')
    result=continuity_read(native,region,query['text'],enabled=True)
    item=next(d for d in result['decisions'] if d['payload_id']==target['payload_id'])
    assert item['status']=='DISPUTED' and item['carried_event_count']==1
    assert len(item['feedback'])==4 and item['withheld']
    assert [e['match_kind'] for e in item['feedback']].count('EXACT_RECEIPT')==3
    assert not gated_read(native,region,query['text'],enabled=True)['withheld_candidates']


def test_new_witness_occurrence_expires_veto_even_if_candidate_packet_is_identical(native_case):
    native,rows,region,query,target,binding=native_case
    before=continuity_read(native,region,query['text'],enabled=True)
    witness_root=target['witnesses'][0][0]
    witness_text=before['raw_view']['root_provenance'][witness_root]['text']
    append(native,rows,region,text=witness_text)
    current=receipt(native,region,query['text'],target['payload_id'])
    assert current['candidate']==binding['candidate']
    after=continuity_read(native,region,query['text'],enabled=True)
    assert len(after['raw_view']['root_provenance'][witness_root]['origins'])==len(before['raw_view']['root_provenance'][witness_root]['origins'])+1
    assert not after['withheld_candidates']


def test_scope_query_and_all_evidence_fields_are_required(native_case):
    native,_,region,query,_,binding=native_case
    ledger=events(native,region); saved=copy.deepcopy(ledger)
    assert continuity_decision(binding,ledger)['withheld']
    for key in ('region','query'):
        current=copy.deepcopy(binding);current[key]+='different'
        assert not continuity_decision(current,ledger)['withheld']
    for key in ('origins','frame_ids','witnesses','route_evidence'):
        current=copy.deepcopy(binding);current['candidate'][key]=[]
        assert not continuity_decision(current,ledger)['withheld']
    assert ledger==saved
    variant=continuity_read(native,region,'Contexto: '+query['text'],enabled=True)
    assert variant['raw_view']['candidates'] and not variant['withheld_candidates']
    for enabled in (False,True):
        with pytest.raises(ValueError,match='learning region'):
            continuity_read(native,ledger_region(region),query['text'],enabled=enabled)


def test_default_disabled_preserves_all_candidates(native_case):
    native,_,region,query,_,_=native_case
    result=continuity_read(native,region,query['text'])
    assert not result['enabled'] and not result['candidate_filter_used']
    assert result['available_candidates']==result['raw_view']['candidates']


def test_missing_historical_prefix_or_changed_witness_provenance_prevents_carry(native_case):
    native,rows,region,query,target,binding=native_case
    append(native,rows,region)
    stored=collect(native,[region]);ledger=events(native,region)
    result=continuity_read(native,region,query['text'],enabled=True)
    current=receipt(native,region,query['text'],target['payload_id'])
    provenance=witness_provenance(result['raw_view'],target)
    assert not continuity_decision(current,ledger,current_provenance=provenance)['withheld']
    proofs=historical_proofs(stored,ledger)
    assert continuity_decision(current,ledger,current_provenance=provenance,proofs=proofs)['withheld']
    assert historical_proofs(stored[1:],ledger)=={}
    changed=copy.deepcopy(provenance)
    changed[target['payload_id']]['origins']=[]
    assert not continuity_decision(current,ledger,current_provenance=changed,proofs=proofs)['withheld']


def test_probe_exposes_wrong_feedback_and_hidden_context_failures():
    library=Path(os.environ.get('MEMORIA_NATIVE_LIBRARY','build/trajectory-native/libmemoria_mobile.so'))
    if not library.exists(): pytest.skip('native library required')
    result=probe(library,20270105)
    assert result['integrity_status']=='PASS'
    assert all(result['checks'].values())
    effects=result['effects']
    assert effects['unrelated_user']['strict_after_score']['false_positive']==1
    assert effects['unrelated_user']['continuity_after_score']['exact_set']
    assert effects['generated_barrier']['continuity_after_score']['exact_set']
    assert effects['repeated_target']['continuity_after_score']['false_positive']==1
    assert effects['new_candidate']['continuity_after_score']['false_positive']==1
    assert effects['wrong_veto']['continuity_after_score']['false_negative']==1
    assert effects['hidden_context_twin']['continuity_after_score']['false_negative']==1
    assert result['semantic_context_status']=='FAIL_INDISTINGUISHABLE_INPUTS'
    assert result['general_learning_status']=='NOT_ESTABLISHED'
