import itertools
import os
from pathlib import Path
import subprocess
import sys

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from trajectory_demonstration_review_probe import fixture_and_offers,populate
from trajectory_feedback_session import FeedbackSession
from trajectory_review_wizard import ReviewWizard,literal


@pytest.fixture
def session(tmp_path):
    library=Path(os.environ.get('MEMORIA_NATIVE_LIBRARY','build/trajectory-native/libmemoria_mobile.so'))
    if not library.exists():pytest.skip('native library required')
    with FeedbackSession(library,tmp_path) as active:yield active,library,tmp_path


def run_script(active,scope,answers,actor='scripted-operator'):
    answers=iter(answers);output=[];ids=itertools.count(1)
    def read(prompt):
        try:return next(answers)
        except StopIteration:raise EOFError
    ReviewWizard(active,scope,actor,read=read,write=output.append,new_id=lambda:f'test-{next(ids)}').run()
    return output


def review_inputs(fixture,offers,choice):
    values=['2',fixture['queries'][0]['text'],str(len(offers))]
    for offer in offers:
        values += [offer['provenance'],str(len(offer['examples']))]
        for example in offer['examples']:values += [example['source_text'],example['target_text']]
    return values+[choice,'Decisão programada para testar o terminal.']


@pytest.mark.parametrize('origin,expected', [('u',1),('g',0),('p',0)])
def test_wizard_incorporation_requires_explicit_origin_and_preserves_audit(session,origin,expected):
    active,_,_=session
    fixture,offers=fixture_and_offers('pressure','unseen_identity');populate(active,fixture)
    offers=[offers[1]]
    run_script(active,fixture['scope'],review_inputs(fixture,offers,'1')+[origin,'d','Avaliação incerta de teste.','0'])
    audit=active.execute(dict(op='review_outcomes',scope=fixture['scope']))['result']
    assert len(audit['decisions'])==len(audit['outcomes'])==1
    event=audit['outcomes'][0]['event']
    assert event['judgement']=='uncertain' and event['comparison']['raw']['after_count']==expected
    assert event['comparison']['causal_attribution']=='NOT_ESTABLISHED'


@pytest.mark.parametrize('choice,label',[('d','defer'),('r','reject_all')])
def test_wizard_can_defer_or_reject_without_incorporating(session,choice,label):
    active,_,_=session
    fixture,offers=fixture_and_offers('pressure','unseen_identity');populate(active,fixture)
    before=active.execute(dict(op='history',scope=fixture['scope']))
    run_script(active,fixture['scope'],review_inputs(fixture,[offers[1]],choice)+['d','Ainda há dúvida.','0'])
    audit=active.execute(dict(op='review_outcomes',scope=fixture['scope']))['result']
    assert audit['decisions'][0]['event']['choice']==label
    assert audit['decisions'][0]['event']['offer_id'] is None
    assert active.execute(dict(op='history',scope=fixture['scope']))==before


def test_resume_after_restart_reuses_observation_ids_and_preserves_original_snapshot(session):
    active,library,directory=session
    fixture,offers=fixture_and_offers('pressure','unseen_identity');populate(active,fixture)
    run_script(active,fixture['scope'],review_inputs(fixture,[offers[1]],'1')+['u','s','0'])
    learning=active.execute(dict(op='history',scope=fixture['scope']))
    audit=active.execute(dict(op='review_decisions',scope=fixture['scope']))['result']
    decision=audit['decisions'][0]['event'];before_receipt=decision['receipt_id']
    active.close()
    with FeedbackSession(library,directory) as cold:
        run_script(cold,fixture['scope'],['4',decision['decision_id'],'u','d','Retomada programada; sem avaliação humana.','0'])
        after=cold.execute(dict(op='review_outcomes',scope=fixture['scope']))['result']
        assert after['outcomes'][0]['event']['before_receipt_id']==before_receipt
        assert cold.execute(dict(op='history',scope=fixture['scope']))==learning


def test_incorporation_preflight_rejects_whole_batch_without_partial_learning(session):
    active,_,_=session
    for i,text in enumerate(('A'*2000,'B'*2000)):
        active.execute(dict(op='observe',event_id=f'large-{i}',text=text))
    before=active.execute(dict(op='history'))
    fixture=dict(queries=[dict(text='Pergunta curta?')])
    offers=[dict(provenance='teste',examples=[dict(source_text='nova origem',target_text='x'*120)])]
    output=run_script(active,'principal',review_inputs(fixture,offers,'1')+['u','0'])
    assert any('conjunto inteiro excede' in line for line in output)
    assert active.execute(dict(op='history'))==before
    assert len(active.execute(dict(op='review_decisions'))['result']['decisions'])==1


def test_eof_after_decision_keeps_a_resumable_decision(session):
    active,_,_=session
    fixture,offers=fixture_and_offers('pressure','unseen_identity');populate(active,fixture)
    run_script(active,fixture['scope'],review_inputs(fixture,[offers[1]],'1'))
    audit=active.execute(dict(op='review_outcomes',scope=fixture['scope']))['result']
    assert len(audit['decisions'])==1 and audit['outcomes']==[]


def test_wrong_declared_actor_cannot_resume_a_decision(session):
    active,_,_=session
    fixture,offers=fixture_and_offers('pressure','unseen_identity');populate(active,fixture)
    run_script(active,fixture['scope'],review_inputs(fixture,[offers[1]],'d')+['s','0'])
    audit=active.execute(dict(op='review_outcomes',scope=fixture['scope']))
    identity=audit['result']['decisions'][0]['event']['decision_id']
    output=run_script(active,fixture['scope'],['4',identity,'0'],actor='another-caller')
    assert any('mesma identidade' in line for line in output)
    assert active.execute(dict(op='review_outcomes',scope=fixture['scope']))==audit


def test_real_terminal_entry_registration_and_literal_output(session,tmp_path):
    _,library,_=session
    script=Path(__file__).resolve().parents[1]/'scripts'/'trajectory_review_wizard.py'
    text='<b>Entrada literal é.</b>'
    run=subprocess.run([sys.executable,str(script),'--library',str(library.resolve()),'--data-dir',str(tmp_path/'cli'),'--actor','scripted-operator'],
                       input='1\n'+text+'\nu\n5\n0\n',text=True,capture_output=True,check=True)
    assert literal(text) in run.stdout
    with FeedbackSession(library,tmp_path/'cli') as cold:
        rows=cold.execute(dict(op='history'))['result']['entries']
        assert len(rows)==1 and rows[0]['text']==text and rows[0]['source_kind']=='user_turn'
    assert '\\u001b' in literal('\x1b[31m')


def test_real_terminal_review_cycle_needs_no_json_or_manual_receipt_ids(session,tmp_path):
    _,library,_=session
    fixture,offers=fixture_and_offers('pressure','unseen_identity')
    directory=tmp_path/'review-cli'
    with FeedbackSession(library,directory) as setup:populate(setup,fixture)
    script=Path(__file__).resolve().parents[1]/'scripts'/'trajectory_review_wizard.py'
    answers=review_inputs(fixture,[offers[1]],'1')+['p','d','Ainda preciso conferir a origem.','0']
    run=subprocess.run([sys.executable,str(script),'--library',str(library.resolve()),'--data-dir',str(directory),
                        '--scope',fixture['scope'],'--actor','scripted-operator'],
                       input='\n'.join(answers)+'\n',text=True,capture_output=True,check=True)
    assert 'Decisão registrada:' in run.stdout and 'Resultado registrado:' in run.stdout
    with FeedbackSession(library,directory) as cold:
        audit=cold.execute(dict(op='review_outcomes',scope=fixture['scope']))['result']
        assert len(audit['decisions'])==len(audit['outcomes'])==1
        assert audit['outcomes'][0]['event']['judgement']=='uncertain'
        assert not audit['outcomes'][0]['event']['comparison']['learning_context_changed']


def test_resume_cannot_relabel_generated_examples_as_user_observations(session):
    active,_,_=session
    fixture,offers=fixture_and_offers('pressure','unseen_identity');populate(active,fixture)
    run_script(active,fixture['scope'],review_inputs(fixture,[offers[1]],'1')+['g','s','0'])
    before=active.execute(dict(op='history',scope=fixture['scope']))
    audit=active.execute(dict(op='review_outcomes',scope=fixture['scope']))['result']
    identity=audit['decisions'][0]['event']['decision_id']
    output=run_script(active,fixture['scope'],['4',identity,'u','0'])
    assert any('mesma origem' in line for line in output)
    assert active.execute(dict(op='history',scope=fixture['scope']))==before
    assert active.execute(dict(op='review_outcomes',scope=fixture['scope']))['result']['outcomes']==[]
