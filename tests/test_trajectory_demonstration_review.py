import copy
import os
from pathlib import Path
import sys
import json
import subprocess

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from trajectory_demonstration_review import validate_offers
from trajectory_demonstration_review_probe import fixture_and_offers, populate
from trajectory_feedback_session import FeedbackSession


@pytest.fixture
def session(tmp_path):
    library=Path(os.environ.get('MEMORIA_NATIVE_LIBRARY','build/trajectory-native/libmemoria_mobile.so'))
    if not library.exists():pytest.skip('native library required')
    with FeedbackSession(library,tmp_path) as active:yield active,library,tmp_path


@pytest.mark.parametrize('experiment,related',[
    ('unseen_symbol',{'offer-a','offer-b'}),
    ('unseen_identity',{'offer-a','offer-b'}),
    ('value_boundary',{'offer-b'}),
    ('conflicting_map',set()),
])
def test_native_review_reports_structural_relation_without_choosing_truth(session,experiment,related):
    active,library,directory=session
    fixture,offers=fixture_and_offers('pressure',experiment);populate(active,fixture)
    request=dict(scope=fixture['scope'],text=fixture['queries'][0]['text'])
    history=active.execute(dict(op='history',scope=fixture['scope']))
    before=active.execute(dict(op='diagnose',**request))
    saved=copy.deepcopy(offers)
    result=active.execute(dict(op='review_examples',offers=offers,**request))
    review=result['result']['example_review']
    assert set(review['structurally_related_offer_ids'])==related
    assert review['selected_offer_id'] is None and not review['selection_used']
    assert not review['offers_recorded'] and not review['learning_performed']
    projection=dict(result['result']);projection.pop('example_review')
    assert projection==before['result'] and offers==saved
    reversed_review=active.execute(dict(op='review_examples',offers=list(reversed(offers)),**request))['result']['example_review']
    assert set(reversed_review['structurally_related_offer_ids'])==related
    assert reversed_review['selected_offer_id'] is None and not reversed_review['ranked']
    assert [r['offer']['offer_id'] for r in reversed_review['offers']]==[o['offer_id'] for o in reversed(offers)]
    assert active.execute(dict(op='history',scope=fixture['scope']))==history
    active.close()
    with FeedbackSession(library,directory) as cold:
        assert cold.execute(dict(op='review_examples',offers=offers,**request))==result


@pytest.mark.parametrize('offers',[
    [],{},[{}],
    [dict(offer_id='x',examples=[])],
    [dict(offer_id='x',examples=[dict(source_text='q',target_text='a',expected='answer')])],
    [dict(offer_id='x',examples=[dict(source_text='q',target_text='a')])]*2,
    [dict(offer_id='x',examples=[dict(source_text=' ',target_text='a')])],
    [dict(offer_id='x',examples=[dict(source_text='q'*2001,target_text='a')])],
])
def test_invalid_offers_are_rejected_without_writing(session,offers):
    active,_,_=session
    before=active.execute(dict(op='history'))
    with pytest.raises(ValueError):active.execute(dict(op='review_examples',text='q',offers=offers))
    assert active.execute(dict(op='history'))==before


def test_total_offer_budget_and_identity_limits():
    examples=[dict(source_text='q'*2000,target_text='a'*2000)]*3
    with pytest.raises(ValueError,match='16000'):
        validate_offers([dict(offer_id='x',examples=examples),dict(offer_id='y',examples=examples)])
    with pytest.raises(ValueError):validate_offers([dict(offer_id='x'*129,examples=examples[:1])])


def test_feedback_context_is_not_treated_as_permission_to_learn(session):
    active,_,_=session
    fixture,offers=fixture_and_offers('pressure','unseen_identity');populate(active,fixture)
    for i,example in enumerate(offers[1]['examples']):
        for suffix,text in (('q',example['source_text']),('a',example['target_text'])):
            active.execute(dict(op='observe',scope=fixture['scope'],event_id=f'test-{i}-{suffix}',text=text))
    request=dict(scope=fixture['scope'],text=fixture['queries'][0]['text'])
    query=active.execute(dict(op='query',**request))
    active.execute(dict(op='feedback',scope=fixture['scope'],receipt=query['result']['receipts'][0],event_id='feedback',actor_id='operator',stance='oppose'))
    review=active.execute(dict(op='review_examples',offers=offers,**request))['result']['example_review']
    assert review['existing_feedback_requires_review']
    assert not review['learning_performed'] and review['selected_offer_id'] is None


def test_review_terminal_protocol_never_records_offered_examples(session,tmp_path):
    _,library,_=session
    fixture,offers=fixture_and_offers('pressure','unseen_symbol')
    offers[0]['provenance']='Origem literal é\nsegunda linha'
    commands=[dict(op='history'),dict(op='review_examples',text=fixture['queries'][0]['text'],offers=offers),dict(op='history')]
    script=Path(__file__).resolve().parents[1]/'scripts'/'trajectory_feedback_session.py'
    run=subprocess.run([sys.executable,str(script),'--library',str(library.resolve()),'--data-dir',str(tmp_path/'cli')],
                       input=''.join(json.dumps(c)+'\n' for c in commands),text=True,capture_output=True,check=True)
    outputs=[json.loads(line) for line in run.stdout.splitlines()]
    assert len(outputs)==3 and outputs[0]==outputs[2]
    review=outputs[1]['result']['example_review']
    assert [r['offer'] for r in review['offers']]==offers
    assert not review['offers_recorded'] and review['selected_offer_id'] is None
