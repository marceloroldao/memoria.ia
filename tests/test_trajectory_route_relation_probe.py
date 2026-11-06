import copy
import os
from pathlib import Path
import sys
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from trajectory_route_relation_probe import fixture,read,route_relation,append_intervention
from trajectory_composed_frame_probe import read as composed_read
from trajectory_question_frame_probe import trial


def view(case='composed',name='literal_cue',seed=20261229,renamed=False):
    rows,region,queries=fixture(case,seed,renamed)
    query=next(q for q in queries if q['name']==name)
    return rows,region,query,read(rows,region,query['text'])


def test_set_relation_states_do_not_change_outputs_or_recover_missing_content():
    for case,name,status in (('no_examples','literal_cue','NO_ROUTE_OUTPUT'),
                            ('composed','literal_cue','ONE_ROUTE_OUTPUT'),
                            ('same_root_two_routes','literal_cue','SAME_ROOT_SET'),
                            ('competing_routes','literal_cue','DIFFERENT_ROOT_SETS')):
        rows,region,q,v=view(case,name)
        assert v['route_relation']['status']==status
        original=composed_read(rows,region,q['text'])
        del v['route_relation'];v['format']=original['format']
        assert v==original
    absent=view('composed','absent_entity')
    uncovered=view('no_examples')
    assert absent[3]['route_relation']['status']==uncovered[3]['route_relation']['status']=='NO_ROUTE_OUTPUT'
    assert not absent[2]['expected'] and uncovered[2]['expected']


def test_full_and_partial_overlap_have_exact_shared_and_exclusive_root_sets():
    for seed in (20261229,20261230):
        _,_,_,v=view('partial_overlap',seed=seed)
        d=v['route_relation'];comparison=d['comparisons'][0]
        assert d['status']=='DIFFERENT_ROOT_SETS'
        assert len(d['shared_candidate_roots'])==1
        assert len(comparison['right_only_roots'])==1 and not comparison['left_only_roots']
        assert comparison['shared_witness_payload_roots']
        assert comparison['shared_witness_pairs']
        assert d['evidence_independence_status']=='NOT_ESTABLISHED'
        disjoint=view('competing_routes',seed=seed)[3]['route_relation']
        assert disjoint['status']=='DIFFERENT_ROOT_SETS' and not disjoint['shared_candidate_roots']
        assert len(disjoint['comparisons'][0]['left_only_roots'])==len(disjoint['comparisons'][0]['right_only_roots'])==1


def test_same_output_sets_can_contain_conflicting_contents_and_many_occurrences():
    _,_,_,v=view('shared_conflict')
    d=v['route_relation']
    assert d['status']=='SAME_ROOT_SET' and d['multiple_candidate_roots']
    assert len(d['shared_candidate_roots'])==2
    assert set(d['within_route_multiple_roots'])=={'literal_copy','symbol_transform'}
    assert sorted(len(c['origins']) for c in v['candidates'])==[1,20]
    assert d['factual_contradiction_status']=='NOT_EVALUATED'
    assert v['proposal_payload_id'] is None and v['answer'] is None and not v['qualified']


def test_single_route_error_and_agreement_hidden_twin_are_not_identified_as_truth():
    _,_,q,v=view('wrong_transform','covered')
    assert v['route_relation']['status']=='ONE_ROUTE_OUTPUT'
    assert {c['text'] for c in v['candidates']}!=set(q['expected'])
    positive=view('same_root_two_routes');twin=view('same_root_unrelated_twin')
    assert positive[0]==twin[0] and positive[3]==twin[3]
    assert positive[3]['route_relation']['status']=='SAME_ROOT_SET'
    assert positive[2]['expected'] and not twin[2]['expected']
    assert positive[3]['route_relation']['factual_quality_status']=='NOT_EVALUATED'


def test_append_only_interventions_change_relations_without_selecting_routes():
    original=view('composed');overlap=view('same_root_two_routes')
    assert overlap[0][:len(original[0])]==original[0]
    assert original[3]['route_relation']['status']=='ONE_ROUTE_OUTPUT'
    assert overlap[3]['route_relation']['status']=='SAME_ROOT_SET'
    assert original[3]['candidates'][0]['payload_id']==overlap[3]['candidates'][0]['payload_id']
    for case in ('partial_overlap','shared_conflict'):
        modified=view(case)
        assert modified[0][:len(overlap[0])]==overlap[0]
        assert modified[3]['selected_target'] is None and not modified[3]['selection_used']
        assert not modified[3]['route_relation']['selection_used']


def test_diagnostic_is_pure_and_evaluator_metadata_cannot_change_relations():
    rows,region,q,v=view('partial_overlap')
    before=copy.deepcopy(v)
    assert route_relation(v)==v['route_relation'] and v==before
    masked=[dict(r,expected='hidden',contradiction=True,independent=True,route='imposed') for r in rows]
    assert read(masked,region,q['text'])==v


@pytest.mark.skipif(not os.environ.get('MEMORIA_NATIVE_LIBRARY'),reason='requires native BDR library')
def test_native_cold_full_diagnostic_and_opaque_preservation():
    results=[]
    for renamed in (False,True):
        r=trial(Path(os.environ['MEMORIA_NATIVE_LIBRARY']),'partial_overlap',20261229,renamed,fixture,read)
        assert all(r['checks'].values())
        results.append([(q['frame_view']['route_relation']['status'],q['frame_score']) for q in r['queries']])
    assert results[0]==results[1]


@pytest.mark.skipif(not os.environ.get('MEMORIA_NATIVE_LIBRARY'),reason='requires native BDR library')
def test_intervention_appends_in_one_native_store_and_retains_candidate_address():
    before,region,queries=fixture('same_root_two_routes',20261229)
    after,_,_=fixture('partial_overlap',20261229)
    query=next(q['text'] for q in queries if q['name']=='literal_cue')
    result=append_intervention(Path(os.environ['MEMORIA_NATIVE_LIBRARY']),before,after,region,query)
    assert all(result['checks'].values())
    b,a=result['before_view'],result['after_view']
    assert b['route_relation']['status']=='SAME_ROOT_SET'
    assert a['route_relation']['status']=='DIFFERENT_ROOT_SETS'
    old=b['candidates'][0]
    kept=next(c for c in a['candidates'] if c['payload_id']==old['payload_id'])
    assert kept['text']==old['text'] and kept['origins']==old['origins']
