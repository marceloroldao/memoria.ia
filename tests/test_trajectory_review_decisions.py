import copy
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from trajectory_feedback_session import FeedbackSession
from trajectory_demonstration_review_probe import fixture_and_offers,populate
from trajectory_review_decisions import field
from trajectory_window_consistency_probe import window_snapshot


@pytest.fixture
def session(tmp_path):
    library=Path(os.environ.get('MEMORIA_NATIVE_LIBRARY','build/trajectory-native/libmemoria_mobile.so'))
    if not library.exists():pytest.skip('native library required')
    with FeedbackSession(library,tmp_path) as active:yield active,library,tmp_path


def start(active):
    fixture,offers=fixture_and_offers('pressure','unseen_identity')
    populate(active,fixture)
    request=dict(scope=fixture['scope'],text=fixture['queries'][0]['text'],offers=offers)
    opened=active.execute(dict(op='open_review',**request))
    return request,opened,dict(op='record_review_decision',scope=fixture['scope'],
        receipt_id=opened['result']['event']['receipt_id'],decision_id='choice-1',actor_id='operator',
        choice='select',offer_id='offer-b',reason='Conferi a origem declarada; decisão explícita do operador.')


def test_operator_choice_is_durable_without_learning_or_example_incorporation(session):
    active,library,directory=session
    request,opened,decision=start(active)
    review=active.execute(dict(op='review_examples',**request))
    learning=active.execute(dict(op='history',scope=request['scope']))
    saved=active.execute(decision)
    assert saved['result']['status']=='APPENDED' and saved['result']['persisted']
    assert active.execute(decision)['result']['status']=='EXACT_REPLAY'
    assert active.execute(dict(op='open_review',**request))['result']['status']=='EXACT_REPLAY'
    history=active.execute(dict(op='review_decisions',scope=request['scope']))
    assert len(history['result']['receipts'])==len(history['result']['decisions'])==1
    assert history['result']['decisions'][0]['event']['offer_id']=='offer-b'
    assert not history['result']['offers_incorporated']
    assert active.execute(dict(op='history',scope=request['scope']))==learning
    assert active.execute(dict(op='review_examples',**request))==review
    assert opened['result']['event']['reviewed_result']==review['result']
    active.close()
    with FeedbackSession(library,directory) as cold:
        assert cold.execute(dict(op='review_decisions',scope=request['scope']))==history
        assert cold.execute(dict(op='review_examples',**request))==review
        assert cold.execute(decision)['result']['status']=='EXACT_REPLAY'


@pytest.mark.parametrize('choice', ['defer','reject_all'])
def test_uncertainty_and_rejection_are_explicit_choices_without_offer(session,choice):
    active,_,_=session
    request,_,decision=start(active)
    decision.update(choice=choice,offer_id=None,reason='Ainda preciso conferir a evidência.')
    active.execute(decision)
    event=active.execute(dict(op='review_decisions',scope=request['scope']))['result']['decisions'][0]['event']
    assert event['choice']==choice and event['offer_id'] is None


@pytest.mark.parametrize('change', ['scope','offer','choice','reason','identity_conflict'])
def test_invalid_decisions_do_not_append(session,change):
    active,_,_=session
    request,_,decision=start(active)
    active.execute(decision)
    before=active.execute(dict(op='review_decisions',scope=request['scope']))
    invalid=dict(decision,decision_id='choice-2')
    if change=='scope':invalid['scope']='foreign'
    if change=='offer':invalid['offer_id']='not-offered'
    if change=='choice':invalid.update(choice='defer',offer_id='offer-a')
    if change=='reason':invalid['reason']=' '
    if change=='identity_conflict':invalid.update(decision_id='choice-1',offer_id='offer-a')
    with pytest.raises(ValueError):active.execute(invalid)
    assert active.execute(dict(op='review_decisions',scope=request['scope']))==before


def test_new_decision_rejects_stale_snapshot_but_exact_replay_survives(session):
    active,_,_=session
    request,_,decision=start(active)
    active.execute(decision)
    active.execute(dict(op='observe',scope=request['scope'],event_id='later',text='Observação posterior isolada.'))
    assert active.execute(decision)['result']['status']=='EXACT_REPLAY'
    with pytest.raises(ValueError,match='stale'):
        active.execute(dict(decision,decision_id='choice-2'))
    fresh=active.execute(dict(op='open_review',**request))
    assert fresh['result']['event']['receipt_id']!=decision['receipt_id']
    active.execute(dict(decision,decision_id='choice-2',receipt_id=fresh['result']['event']['receipt_id']))


def test_receipt_digest_includes_context_even_when_review_output_is_unchanged(session):
    active,_,_=session
    offers=[dict(offer_id='one',examples=[dict(source_text='q',target_text='a')])]
    request=dict(text='Pergunta sem exemplos.',offers=offers)
    old=active.execute(dict(op='open_review',**request))['result']['event']
    active.execute(dict(op='observe',event_id='later',text='Entrada isolada.'))
    new=active.execute(dict(op='open_review',**request))['result']['event']
    assert old['reviewed_result']==new['reviewed_result']
    assert old['learning_sha256']!=new['learning_sha256'] and old['receipt_id']!=new['receipt_id']


def test_different_reviewed_order_or_provenance_gets_a_different_receipt(session):
    active,_,_=session
    request,old,_=start(active)
    changed=copy.deepcopy(request);changed['offers'].reverse()
    new=active.execute(dict(op='open_review',**changed))
    assert new['result']['event']['receipt_id']!=old['result']['event']['receipt_id']
    changed=copy.deepcopy(request);changed['offers'][0]['provenance']='Outra origem declarada.'
    assert active.execute(dict(op='open_review',**changed))['result']['event']['receipt_id']!=old['result']['event']['receipt_id']


def test_feedback_changes_invalidate_an_unrecorded_decision(session):
    active,_,_=session
    request,_,decision=start(active)
    # The candidate-free baseline still cannot receive feedback; add known examples then review.
    for i,example in enumerate(request['offers'][1]['examples']):
        for suffix,text in (('q',example['source_text']),('a',example['target_text'])):
            active.execute(dict(op='observe',scope=request['scope'],event_id=f'learn-{i}-{suffix}',text=text))
    opened=active.execute(dict(op='open_review',**request))['result']['event']
    query=active.execute(dict(op='query',scope=request['scope'],text=request['text']))['result']
    active.execute(dict(op='feedback',scope=request['scope'],receipt=query['receipts'][0],event_id='oppose',actor_id='operator',stance='oppose'))
    with pytest.raises(ValueError,match='stale'):
        active.execute(dict(decision,receipt_id=opened['receipt_id']))


def test_terminal_decision_protocol_with_unicode_and_newlines(session,tmp_path):
    _,library,_=session
    script=Path(__file__).resolve().parents[1]/'scripts'/'trajectory_feedback_session.py'
    commands=[dict(op='open_review',text='Pergunta?',offers=[dict(offer_id='one',examples=[dict(source_text='q',target_text='a')])])]
    process=subprocess.Popen([sys.executable,str(script),'--library',str(library.resolve()),'--data-dir',str(tmp_path/'terminal')],
                             stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    try:
        process.stdin.write(json.dumps(commands[0])+'\n');process.stdin.flush()
        opened=json.loads(process.stdout.readline())
        command=dict(op='record_review_decision',receipt_id=opened['result']['event']['receipt_id'],decision_id='decisão "1"',
                     actor_id='operador',choice='defer',offer_id=None,reason='Conferir "origem".\nAinda há dúvida.\\literal')
        process.stdin.write(json.dumps(command)+'\n');process.stdin.flush()
        saved=json.loads(process.stdout.readline())
        assert saved['result']['event']['reason']==command['reason']
        process.stdin.close();assert process.wait(timeout=20)==0
    finally:
        if process.poll() is None:process.kill();process.wait()


def test_corrupt_control_history_is_rejected_without_new_decision(session):
    active,_,_=session
    request,_,decision=start(active)
    region='conversation:feedback-session:'+request['scope']
    control=field(region,'decisions')
    status,_=active.native.call('observe_structural_text',dict(hierarchy_id=control,source_id='invalid-control',sequence=1,
                                                              text='invalid-codec',source_kind='user_turn'))
    assert status==0
    before=window_snapshot(active.native,control)
    with pytest.raises(ValueError,match='codec'):active.execute(decision)
    with pytest.raises(ValueError,match='codec'):active.execute(dict(op='open_review',**request))
    with pytest.raises(ValueError,match='codec'):active.execute(dict(op='review_decisions',scope=request['scope']))
    assert window_snapshot(active.native,control)==before
