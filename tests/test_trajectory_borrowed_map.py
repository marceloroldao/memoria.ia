import copy
import os
from pathlib import Path
import sys

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from trajectory_borrowed_map import read
from trajectory_borrowed_map_probe import ARMS,fixture,trial
from trajectory_transfer_evaluation import DOMAINS,SEEDS
from trajectory_surface_evaluation import surface_text


@pytest.mark.parametrize('domain',DOMAINS)
@pytest.mark.parametrize('seed',SEEDS)
def test_hidden_worlds_have_identical_evidence_without_target_leakage(domain,seed):
    for surface in ('uppercase','paraphrase'):
        for arm in ARMS:
            a=fixture(domain,seed,surface,arm,'shared_map')
            b=fixture(domain,seed,surface,arm,'switched_map')
            assert a['rows']==b['rows'] and a['foreign_rows']==b['foreign_rows'] and a['foreign']==b['foreign']
            assert [q['text'] for q in a['queries']]==[q['text'] for q in b['queries']]
            targets={text for f in (a,b) for q in f['queries'] for text in q['expected']}
            assert a['queries'][0]['expected']!=b['queries'][0]['expected']
            assert a['queries'][1]['expected']!=b['queries'][1]['expected']
            assert targets <= {row['text'] for row in a['rows']}
            added=[row for row in a['rows'] if row['event_id'].startswith('surface-')]+a['foreign_rows']
            assert targets.isdisjoint(row['text'] for row in added)
            assert {q['text'] for q in a['queries']}.isdisjoint(row['text'] for row in a['rows']+a['foreign_rows'])
            assert all(set(row)=={'event_id','text','source_kind'} for row in a['rows']+a['foreign_rows'])


@pytest.mark.parametrize('surface',['uppercase','paraphrase'])
def test_native_borrowing_cannot_distinguish_hidden_world_and_never_selects(surface):
    library=Path(os.environ.get('MEMORIA_NATIVE_LIBRARY','build/trajectory-native/libmemoria_mobile.so'))
    if not library.exists(): pytest.skip('native library required')
    a,b=[trial(library,fixture('humidity',SEEDS[0],surface,'two_anchors',world)) for world in ('shared_map','switched_map')]
    assert a['observations_sha256']==b['observations_sha256']
    assert all(a['checks'].values()) and all(b['checks'].values())
    for first,second in zip(a['cases'],b['cases']):
        assert first['borrowed']==second['borrowed']
        assert first['borrowed']['answer'] is None and not first['borrowed']['qualified']
        if first['query']['family']=='surface':
            assert first['score']['exact'] and not second['score']['exact']
            assert second['score']['extra']==second['score']['missing']==1
            for hypothesis in first['borrowed']['hypotheses']:
                for route in hypothesis['routes']:
                    assert len(route['new_form_witnesses'])==2 and len(route['donor_witnesses'])==3
                    assert route['borrowed_pairs'] and route['epistemic_status']=='UNWITNESSED_IN_NEW_SOURCE_FORM'


def materialize(descriptor):
    region='conversation:feedback-session:'+descriptor['scope']
    rows=[dict(row,hierarchy_id=region,source_id=f'origin-{i}',sequence=i+1) for i,row in enumerate(descriptor['rows'])]
    rows += [dict(row,hierarchy_id='conversation:feedback-session:foreign',source_id=f'foreign-{i}',sequence=i+1)
             for i,row in enumerate(descriptor['foreign_rows'])]
    return region,rows


@pytest.mark.parametrize('arm',['baseline','one_anchor','wrong_anchor','generated','foreign'])
def test_missing_or_ineligible_anchors_do_not_authorize_borrowing(arm):
    f=fixture('humidity',SEEDS[0],'uppercase',arm,'shared_map');region,rows=materialize(f)
    assert all(not read(rows,region,q['text'])['hypotheses'] for q in f['queries'])


def test_repeated_anchor_and_repeated_cue_are_not_two_distinct_witnesses():
    f=fixture('humidity',SEEDS[0],'uppercase','one_anchor','shared_map')
    f['rows'] += copy.deepcopy(f['rows'][-3:])
    region,rows=materialize(f)
    assert not read(rows,region,f['queries'][0]['text'])['hypotheses']
    f=fixture('humidity',SEEDS[0],'uppercase','two_anchors','shared_map');region,rows=materialize(f)
    assert not read(rows,region,f['queries'][0]['text']+' '+f['queries'][1]['text'])['hypotheses']


def test_generated_target_payload_is_not_admitted_by_borrowed_route():
    f=fixture('humidity',SEEDS[0],'uppercase','two_anchors','shared_map')
    targets={text for q in f['queries'] for text in q['expected']}
    for row in f['rows']:
        if row['text'] in targets: row['source_kind']='assistant_generated'
    region,rows=materialize(f)
    assert all(not read(rows,region,q['text'])['hypotheses'] for q in f['queries'])


def test_explicit_new_form_counterwitness_vetoes_an_otherwise_matching_donor():
    f=fixture('humidity',SEEDS[0],'uppercase','two_anchors','switched_map')
    start=f['intervention_start']-3
    original=f['rows'][start:start+2]
    expected=f['queries'][0]['expected'][0].split(' do ')[1].split(' é ')[0][0]
    content=original[1]['text'];head,rest=content.split(' do ')
    f['rows'] += [dict(event_id='counter-q',text=surface_text(original[0]['text'],'uppercase'),source_kind='user_turn'),
                  dict(event_id='counter-a',text=head+' do '+expected+rest[1:],source_kind='user_turn'),
                  dict(event_id='counter-barrier',text='Intervalo observado.',source_kind='assistant_generated')]
    region,rows=materialize(f)
    assert all(not read(rows,region,q['text'])['hypotheses'] for q in f['queries'])
