import base64
import copy
import os
from pathlib import Path
import sys
import json
import subprocess

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from trajectory_feedback_session import FeedbackSession
from trajectory_demonstration_review_probe import fixture_and_offers,populate
from trajectory_feedback_ledger_probe import canonical
from trajectory_region_evidence_probe import fingerprint
from trajectory_review_decisions import CODEC,field
from trajectory_window_consistency_probe import window_snapshot


@pytest.fixture
def session(tmp_path):
    library=Path(os.environ.get('MEMORIA_NATIVE_LIBRARY','build/trajectory-native/libmemoria_mobile.so'))
    if not library.exists():pytest.skip('native library required')
    with FeedbackSession(library,tmp_path) as active:yield active,library,tmp_path


def start(active):
    fixture,offers=fixture_and_offers('pressure','value_boundary');populate(active,fixture)
    request=dict(scope=fixture['scope'],text=fixture['queries'][0]['text'],offers=offers)
    before=active.execute(dict(op='open_review',**request))['result']['event']['receipt_id']
    active.execute(dict(op='record_review_decision',scope=fixture['scope'],receipt_id=before,decision_id='choice',actor_id='operator',
                        choice='select',offer_id='offer-b',reason='Escolha declarada para o teste.'))
    command=dict(op='record_review_outcome',scope=fixture['scope'],decision_id='choice',after_receipt_id=before,
                 outcome_id='outcome',actor_id='operator',judgement='uncertain',reason='Avaliação declarada sem certificação factual.')
    return request,command


def incorporate(active,request):
    for i,example in enumerate(request['offers'][1]['examples']):
        for ending,text,kind in (('q',example['source_text'],'user_turn'),('a',example['target_text'],'user_turn'),
                                 ('barrier','Intervalo observado.','assistant_generated')):
            active.execute(dict(op='observe',scope=request['scope'],event_id=f'apply-{i}-{ending}',text=text,source_kind=kind))


def test_before_after_delta_is_persisted_without_further_learning(session):
    active,library,directory=session
    request,command=start(active)
    incorporate(active,request)
    after=active.execute(dict(op='open_review',**request))['result']['event']['receipt_id']
    command.update(after_receipt_id=after,judgement='helped')
    before_history=active.execute(dict(op='history',scope=request['scope']))
    review=active.execute(dict(op='review_examples',**request))
    saved=active.execute(command)
    comparison=saved['result']['event']['comparison']
    assert comparison['raw']['before_count']==1 and comparison['raw']['after_count']==2
    assert len(comparison['raw']['added_ids'])==1 and not comparison['raw']['removed_ids']
    assert comparison['causal_attribution']=='NOT_ESTABLISHED' and not comparison['offer_application_verified']
    assert active.execute(command)['result']['status']=='EXACT_REPLAY'
    audit=active.execute(dict(op='review_outcomes',scope=request['scope']))
    assert len(audit['result']['outcomes'])==1
    assert active.execute(dict(op='history',scope=request['scope']))==before_history
    assert active.execute(dict(op='review_examples',**request))==review
    active.close()
    with FeedbackSession(library,directory) as cold:
        assert cold.execute(dict(op='review_outcomes',scope=request['scope']))==audit
        assert cold.execute(command)['result']['status']=='EXACT_REPLAY'


@pytest.mark.parametrize('judgement',['helped','unchanged','worsened','uncertain'])
def test_subjective_judgement_is_not_inferred_from_candidate_counts(session,judgement):
    active,_,_=session
    _,command=start(active)
    saved=active.execute(dict(command,judgement=judgement))['result']['event']
    assert saved['judgement']==judgement
    assert not saved['comparison']['raw']['added_ids'] and not saved['comparison']['full_review_changed']
    assert not saved['comparison']['retrieval_change_means_quality_improvement']


@pytest.mark.parametrize('change',['actor','decision','scope','after','judgement','reason','id_conflict','query','offers'])
def test_invalid_outcome_does_not_append(session,change):
    active,_,_=session
    request,command=start(active);active.execute(command)
    before=active.execute(dict(op='review_outcomes',scope=request['scope']))
    invalid=dict(command,outcome_id='second')
    if change=='actor':invalid['actor_id']='someone-else'
    if change=='decision':invalid['decision_id']='missing'
    if change=='scope':invalid['scope']='foreign'
    if change=='after':invalid['after_receipt_id']='missing'
    if change=='judgement':invalid['judgement']='proven_true'
    if change=='reason':invalid['reason']=' '
    if change=='id_conflict':invalid.update(outcome_id='outcome',judgement='worsened')
    if change in ('query','offers'):
        altered=copy.deepcopy(request)
        if change=='query':altered['text']='Outra pergunta.'
        else:altered['offers'].reverse()
        invalid['after_receipt_id']=active.execute(dict(op='open_review',**altered))['result']['event']['receipt_id']
        before=active.execute(dict(op='review_outcomes',scope=request['scope']))
    with pytest.raises(ValueError):active.execute(invalid)
    assert active.execute(dict(op='review_outcomes',scope=request['scope']))==before


def test_feedback_suspension_changes_available_candidates_without_removing_raw_memory(session):
    active,_,_=session
    request,command=start(active)
    query=active.execute(dict(op='query',scope=request['scope'],text=request['text']))['result']
    active.execute(dict(op='feedback',scope=request['scope'],receipt=query['receipts'][0],event_id='oppose',actor_id='operator',stance='oppose'))
    command['after_receipt_id']=active.execute(dict(op='open_review',**request))['result']['event']['receipt_id']
    delta=active.execute(command)['result']['event']['comparison']
    assert not delta['raw']['removed_ids'] and len(delta['available']['removed_ids'])==1
    assert len(delta['withheld']['added_ids'])==1 and not delta['learning_context_changed']


def test_outcome_can_reference_historical_snapshots_after_further_observations(session):
    active,_,_=session
    request,command=start(active)
    active.execute(dict(op='observe',scope=request['scope'],event_id='later',text='Observação posterior.'))
    # This is explicitly a historical comparison, not an implicit capture of the current state.
    saved=active.execute(command)
    assert not saved['result']['event']['comparison']['learning_context_changed']
    assert active.execute(command)['result']['status']=='EXACT_REPLAY'


def test_comparison_corruption_is_rejected_instead_of_partial_history(session):
    active,_,_=session
    request,command=start(active);saved=active.execute(command)['result']['event']
    changed=copy.deepcopy(saved);changed['outcome_id']='corrupt';changed['comparison']['raw']['after_count']=999
    region=field('conversation:feedback-session:'+request['scope'],'outcomes')
    active.native.call('observe_structural_text',dict(hierarchy_id=region,source_id='operator-review-outcome:'+fingerprint('corrupt'),sequence=2,
                       text=CODEC+base64.b64encode(canonical(changed).encode()).decode(),source_kind='user_turn'))
    before=window_snapshot(active.native,region)
    with pytest.raises(ValueError,match='comparison'):active.execute(dict(op='review_outcomes',scope=request['scope']))
    with pytest.raises(ValueError,match='comparison'):active.execute(dict(command,outcome_id='third'))
    assert window_snapshot(active.native,region)==before


def test_after_receipt_cannot_precede_the_selected_decision_snapshot(session):
    active,_,_=session
    request,command=start(active);older=command['after_receipt_id']
    active.execute(dict(op='observe',scope=request['scope'],event_id='new-context',text='Contexto adicional.'))
    newer=active.execute(dict(op='open_review',**request))['result']['event']['receipt_id']
    active.execute(dict(op='record_review_decision',scope=request['scope'],receipt_id=newer,decision_id='new-choice',actor_id='operator',
                        choice='defer',offer_id=None,reason='Revisão mais recente.'))
    with pytest.raises(ValueError,match='precedes'):
        active.execute(dict(command,decision_id='new-choice',after_receipt_id=older))


def test_outcome_terminal_protocol_preserves_declared_uncertainty(session,tmp_path):
    _,library,_=session
    script=Path(__file__).resolve().parents[1]/'scripts'/'trajectory_feedback_session.py'
    process=subprocess.Popen([sys.executable,str(script),'--library',str(library.resolve()),'--data-dir',str(tmp_path/'terminal')],
                             stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    def call(command):
        process.stdin.write(json.dumps(command)+'\n');process.stdin.flush()
        return json.loads(process.stdout.readline())
    try:
        opened=call(dict(op='open_review',text='Pergunta?',offers=[dict(offer_id='one',examples=[dict(source_text='q',target_text='a')])]))
        receipt_id=opened['result']['event']['receipt_id']
        call(dict(op='record_review_decision',receipt_id=receipt_id,decision_id='choice',actor_id='operador',choice='defer',offer_id=None,reason='Conferir origem.'))
        reason='Ainda há dúvida.\nNão concluí que houve melhora.'
        saved=call(dict(op='record_review_outcome',decision_id='choice',after_receipt_id=receipt_id,outcome_id='resultado',
                        actor_id='operador',judgement='uncertain',reason=reason))
        assert saved['result']['event']['reason']==reason
        assert saved['result']['event']['judgement']=='uncertain'
        assert call(dict(op='history'))['result']['entries']==[]
        process.stdin.close();assert process.wait(timeout=20)==0
    finally:
        if process.poll() is None:process.kill();process.wait()
