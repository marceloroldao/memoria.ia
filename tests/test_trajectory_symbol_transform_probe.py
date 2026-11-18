import copy
import os
from pathlib import Path
import sys
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from trajectory_symbol_transform_probe import fixture,read,checked_read,learn_frames,report_summary
from trajectory_question_frame_probe import trial, read as copy_read
from trajectory_native_evidence_join_probe import adapt_regions
from trajectory_response_quality_probe import TrajectoryGenerationExperiment


def view(case='observed_map',name='covered',seed=20261225,renamed=False):
    rows,region,queries=fixture(case,seed,renamed)
    query=next(q for q in queries if q['name']==name)
    return rows,region,query,read(rows,region,query['text'])


def texts(v): return {c['text'] for c in v['candidates']}


def test_observed_symbol_map_recovers_held_out_combination_without_imposed_case_rule():
    for seed in (20261225,20261226):
        rows,region,q,v=view(seed=seed)
        assert texts(v)==set(q['expected'])
        assert not texts(copy_read(rows,region,q['text']))
        assert q['text'] not in {r['text'] for r in rows}
        assert len(v['frames'])==1
        frame=v['frames'][0]
        mapping=dict(frame['symbol_map'])
        assert mapping and any(a!=b for a,b in mapping.items())
        assert len(set(mapping.values()))==len(mapping)
        assert len(frame['witnesses'])==3
        assert v['answer'] is None and not v['qualified'] and not v['selection_used']
        assert texts(view(name='new_prefix',seed=seed)[3])==set(q['expected'])


def test_missing_evidence_absence_unknown_symbols_and_untrained_cues_remain_unresolved():
    for case in ('no_examples','two_examples','repeated_one_example','generated_examples','foreign_examples'):
        assert not texts(view(case)[3])
    for name in ('unknown_symbols','absent_entity','untrained_relation','absent_attribute','untrained_lowercase','unseen_paraphrase','two_cues'):
        assert not texts(view(name=name)[3])


def test_wrong_and_competing_maps_and_repeated_content_do_not_authorize_truth():
    _,_,q,v=view('wrong_map')
    assert texts(v)=={'A cor do brole é verde.'} and texts(v)!=set(q['expected'])
    _,_,q,v=view('competing_maps')
    assert texts(v)==set(q['expected'])=={'A cor do drone é verde.','A cor do brole é verde.'}
    assert v['proposal_payload_id'] is None and not v['selection_used']
    _,_,q,v=view('repeated_conflict')
    assert texts(v)==set(q['expected'])
    assert sorted(len(c['origins']) for c in v['candidates'])==[1,20]
    assert v['proposal_payload_id'] is None


def test_generated_roots_and_metadata_are_excluded_from_map_witnesses():
    rows,region,q,v=view()
    allowed={(r['hierarchy_id'],r['source_id'],r['sequence']) for r in rows if r['source_kind']=='user_turn'}
    assert all(tuple(o) in allowed for p in v['root_provenance'].values() for o in p['origins'])
    changed=[dict(r,expected='hidden',reply_to={'source_id':'wrong'},symbol_map='imposed') for r in rows]
    assert read(changed,region,q['text'])==v
    before=copy.deepcopy(rows)
    read(rows,region,q['text'])
    assert rows==before


def test_conflicting_symbol_correspondences_within_witnesses_are_rejected():
    rows,region,q,_=view()
    # Two occurrences of the same input symbol get different output symbols.
    rows=[dict(r,text='A cor do xardo é azul.') if r['source_id']=='train-0-0-a' else r for r in rows]
    memory,_=adapt_regions(rows)
    assert not learn_frames(memory)
    assert not texts(read(rows,region,q['text']))


def test_integer_symbol_renaming_conjugates_map_without_language_dependency():
    rows,region,q,_=view()
    memory,_=adapt_regions([r for r in rows if r['hierarchy_id']==region])
    before=checked_read(memory,tuple(map(ord,q['text'])))
    renamed=TrajectoryGenerationExperiment(memory.config)
    convert=lambda xs: tuple(10000-x for x in xs)
    for r in memory.snapshot()['observations']:
        renamed.observe(convert(memory.expand(r['payload_id'])),observation_id=r['observation_id'],
                        hierarchy_id=r['hierarchy_id'],stream_id=r['stream_id'])
    after=checked_read(renamed,convert(tuple(map(ord,q['text']))))
    assert {c['output'] for c in after['candidates']}=={convert(c['output']) for c in before['candidates']}
    assert {tuple(sorted((10000-a,10000-b) for a,b in f['symbol_map'])) for f in before['frames']}=={f['symbol_map'] for f in after['frames']}


def test_hidden_relevance_twin_has_identical_inputs_and_views():
    positive=view(); twin=view('unrelated_twin')
    assert positive[0]==twin[0] and positive[3]==twin[3]
    assert positive[2]['expected'] and not twin[2]['expected']


@pytest.mark.skipif(not os.environ.get('MEMORIA_NATIVE_LIBRARY'),reason='requires native BDR library')
def test_native_cold_full_views_raw_projection_and_opaque_control():
    for renamed in (False,True):
        result=trial(Path(os.environ['MEMORIA_NATIVE_LIBRARY']),'repeated_conflict',20261225,renamed,fixture,read)
        assert all(result['checks'].values())
        assert result['queries'][0]['frame_score']['exact_set']
        report = dict(cases=[result])
        before = copy.deepcopy(report)
        compact = report_summary(report)
        assert report == before
        assert compact['cases'][0]['transform_frames'] == result['frames']
        assert compact['cases'][0]['frames_count'] == len(result['frames'])
        compact['cases'][0]['transform_frames'][0]['symbol_map'] = ()
        assert report == before
