import copy
import os
from pathlib import Path
import sys
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from trajectory_composed_frame_probe import fixture,read,ROUTES,report_summary
from trajectory_question_frame_probe import trial
from trajectory_analogy_frame_probe import recall as copy_recall
from trajectory_symbol_transform_probe import recall as transform_recall
from trajectory_native_evidence_join_probe import adapt_regions


def view(case='composed',name='covered',seed=20261227,renamed=False):
    rows,region,queries=fixture(case,seed,renamed)
    query=next(q for q in queries if q['name']==name)
    return rows,region,query,read(rows,region,query['text'])


def texts(v): return {c['text'] for c in v['candidates']}


def test_composition_covers_both_cues_and_is_exact_union_of_unchanged_learners():
    for seed in (20261227,20261228):
        for name in ('covered','new_prefix','literal_cue','observed_paraphrase'):
            rows,region,q,v=view(seed=seed,name=name)
            assert texts(v)==set(q['expected'])
            assert q['text'] not in {r['text'] for r in rows}
            memory,_=adapt_regions(rows)
            symbols=tuple(map(ord,q['text']))
            copy_roots={c['payload_id'] for c in copy_recall(memory,symbols)['candidates']}
            map_roots={c['payload_id'] for c in transform_recall(memory,symbols)['candidates']}
            assert {c['payload_id'] for c in v['candidates']}==copy_roots|map_roots
            assert {c['payload_id'] for c in v['candidates'] if any(e['route']=='literal_copy' for e in c['route_evidence'])}==copy_roots
            assert {c['payload_id'] for c in v['candidates'] if any(e['route']=='symbol_transform' for e in c['route_evidence'])}==map_roots
            assert v['answer'] is None and not v['qualified'] and not v['selection_used']


def test_same_root_two_routes_does_not_duplicate_content_or_origins_or_qualify():
    _,_,q,v=view('same_root_two_routes','literal_cue')
    assert texts(v)==set(q['expected']) and len(v['candidates'])==1
    candidate=v['candidates'][0]
    assert {e['route'] for e in candidate['route_evidence']}==set(ROUTES)
    assert len(candidate['origins'])==1
    assert {w for e in candidate['route_evidence'] for w in e['witnesses']}==set(candidate['witnesses'])
    assert not v['qualified'] and v['answer'] is None and v['selected_target'] is None
    assert all(f['frame_id'].startswith(f['route']+':') for f in v['frames'])


def test_disagreeing_routes_keep_false_extra_without_prioritization():
    _,_,q,v=view('competing_routes','literal_cue')
    assert set(q['expected'])=={'A cor do drone é verde.'}
    assert texts(v)=={'A cor do drone é verde.','A cor do brole é verde.'}
    assert {c['text'] for c in v['candidates'] if any(e['route']=='literal_copy' for e in c['route_evidence'])}==set(q['expected'])
    assert v['proposal_payload_id'] is None and not v['selection_used']
    _,_,_,wrong=view('wrong_transform','covered')
    assert texts(wrong)=={'A cor do brole é verde.'}


def test_duplicate_conflict_is_preserved_in_both_supported_query_forms():
    for name in ('covered','literal_cue','observed_paraphrase'):
        _,_,q,v=view('repeated_conflict',name)
        assert texts(v)==set(q['expected'])
        assert sorted(len(c['origins']) for c in v['candidates'])==[1,20]
        assert v['proposal_payload_id'] is None


def test_missing_excluded_and_untrained_routes_and_absence_controls():
    assert not texts(view('no_examples')[3])
    assert not texts(view('copy_only','covered')[3])
    assert not texts(view('transform_only','literal_cue')[3])
    for case in ('generated_copy','foreign_copy'):
        assert not texts(view(case,'literal_cue')[3])
        assert not texts(view(case,'observed_paraphrase')[3])
        assert texts(view(case,'covered')[3])
    for name in ('unknown_symbols','absent_entity','untrained_relation','absent_attribute','unseen_paraphrase','two_cues','two_literal_cues'):
        assert not texts(view(name=name)[3])


def test_hidden_reference_twin_and_metadata_masks_preserve_full_reader_views():
    rows,region,q,v=view()
    before=copy.deepcopy(rows)
    twin=view('unrelated_twin')
    assert rows==twin[0] and v==twin[3] and not twin[2]['expected']
    extra=[dict(r,expected='hidden',route='imposed',reply_to={'source_id':'wrong'}) for r in rows]
    assert read(extra,region,q['text'])==v and rows==before
    allowed={(r['hierarchy_id'],r['source_id'],r['sequence']) for r in rows if r['source_kind']=='user_turn'}
    assert all(tuple(o) in allowed for p in v['root_provenance'].values() for o in p['origins'])


@pytest.mark.skipif(not os.environ.get('MEMORIA_NATIVE_LIBRARY'),reason='requires native BDR library')
def test_native_reopen_opaque_union_and_report_retains_all_route_proofs():
    for renamed in (False,True):
        result=trial(Path(os.environ['MEMORIA_NATIVE_LIBRARY']),'same_root_two_routes',20261227,renamed,fixture,read)
        assert all(result['checks'].values())
        q=next(q for q in result['queries'] if q['name']=='literal_cue')
        assert q['frame_score']['exact_set']
        assert len(q['frame_view']['candidates'])==1
        assert len(q['frame_view']['candidates'][0]['route_evidence'])==2
        report=dict(cases=[result]);before=copy.deepcopy(report)
        compact=report_summary(report)
        assert compact['cases'][0]['composed_frames']==result['frames']
        compact['cases'][0]['composed_frames'][0]['route']='mutated-copy'
        assert report==before
