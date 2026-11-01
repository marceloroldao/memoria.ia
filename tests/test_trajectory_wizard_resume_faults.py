from pathlib import Path
import itertools
import os
import sys

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from trajectory_demonstration_review_probe import fixture_and_offers,populate
from trajectory_feedback_session import FeedbackSession
from trajectory_review_wizard import ReviewWizard


@pytest.fixture
def case(tmp_path):
    library=Path(os.environ.get('MEMORIA_NATIVE_LIBRARY','build/trajectory-native/libmemoria_mobile.so'))
    if not library.exists():pytest.skip('native library required')
    with FeedbackSession(library,tmp_path) as active:
        fixture,offers=fixture_and_offers('pressure','unseen_identity');populate(active,fixture)
        request=dict(scope=fixture['scope'],text=fixture['queries'][0]['text'],offers=offers)
        binding=active.execute(dict(op='open_review',**request))['result']['event']
        decision=active.execute(dict(op='record_review_decision',scope=fixture['scope'],receipt_id=binding['receipt_id'],
                    decision_id='partial-decision',actor_id='scripted-operator',choice='select',offer_id='offer-b',reason='Falha programada para testar retomada.'))['result']['event']
        yield active,library,tmp_path,request,binding,decision


def wizard(active,scope,answers):
    inputs=iter(answers);output=[];ids=itertools.count(1)
    def read(prompt):
        try:return next(inputs)
        except StopIteration:raise EOFError
    return ReviewWizard(active,scope,'scripted-operator',read=read,write=output.append,new_id=lambda:f'resumed-{next(ids)}'),output


def observe_planned(active,scope,entry):
    return active.execute(dict(op='observe',scope=scope,**entry))


@pytest.mark.parametrize('stage',['before','after_flush'])
@pytest.mark.parametrize('cut',[1,2,3])
def test_partial_batch_and_lost_ack_resume_after_reopen_without_duplicate_rows(case,monkeypatch,stage,cut):
    active,library,directory,request,binding,decision=case
    scope=request['scope'];ui,_=wizard(active,scope,['u','d','Primeira tentativa.'])
    planned=ui.incorporation_plan(decision,binding,'user_turn')
    before=active.execute(dict(op='history',scope=scope))['result']['entries']
    original=active.execute;count=0
    def interrupted(command):
        nonlocal count
        targeted=command.get('op')=='observe' and command.get('event_id','').startswith('wizard-apply:')
        if targeted:count+=1
        if targeted and count==cut and stage=='before':raise RuntimeError('scripted failure before observe')
        result=original(command)
        if targeted and count==cut and stage=='after_flush':raise RuntimeError('scripted lost acknowledgement after confirmed flush')
        return result
    monkeypatch.setattr(active,'execute',interrupted)
    with pytest.raises(RuntimeError,match='scripted'):ui.finish(decision,binding)
    monkeypatch.setattr(active,'execute',original)
    partial=active.execute(dict(op='history',scope=scope))['result']['entries']
    assert len(partial)==len(before)+(cut-1 if stage=='before' else cut)
    active.close()
    with FeedbackSession(library,directory) as cold:
        resumed,_=wizard(cold,scope,['4',decision['decision_id'],'u','d','Retomada após falha.','0'])
        resumed.run()
        after=cold.execute(dict(op='history',scope=scope))['result']['entries']
        assert len(after)==len(before)+len(planned) and after[:len(before)]==before
        assert [r['text'] for r in after[len(before):]]==[r['text'] for r in planned]
        audit=cold.execute(dict(op='review_outcomes',scope=scope))['result']
        assert len(audit['decisions'])==len(audit['outcomes'])==1
        assert audit['outcomes'][0]['event']['comparison']['raw']['after_count']==1


@pytest.mark.parametrize('pattern',['interleaved_tail','interleaved_middle','nonprefix'])
def test_ambiguous_partial_history_is_rejected_without_further_writes(case,pattern):
    active,_,_,request,binding,decision=case
    scope=request['scope'];ui,output=wizard(active,scope,['4',decision['decision_id'],'u','0'])
    planned=ui.incorporation_plan(decision,binding,'user_turn')
    if pattern=='nonprefix':observe_planned(active,scope,planned[1])
    else:
        observe_planned(active,scope,planned[0])
        active.execute(dict(op='observe',scope=scope,event_id='intervening',text='Observação inserida durante a interrupção.'))
        if pattern=='interleaved_middle':observe_planned(active,scope,planned[1])
    before=active.execute(dict(op='history',scope=scope))
    audit=active.execute(dict(op='review_outcomes',scope=scope))
    ui.run()
    assert any('Operação recusada:' in line for line in output)
    assert active.execute(dict(op='history',scope=scope))==before
    assert active.execute(dict(op='review_outcomes',scope=scope))==audit


def test_complete_batch_can_be_replayed_after_later_context_without_new_observations(case):
    active,_,_,request,binding,decision=case
    scope=request['scope'];ui,_=wizard(active,scope,['4',decision['decision_id'],'u','d','Conferência posterior.','0'])
    for entry in ui.incorporation_plan(decision,binding,'user_turn'):observe_planned(active,scope,entry)
    active.execute(dict(op='observe',scope=scope,event_id='later',text='Contexto posterior ao lote completo.'))
    before=active.execute(dict(op='history',scope=scope))
    ui.run()
    assert active.execute(dict(op='history',scope=scope))==before
    assert len(active.execute(dict(op='review_outcomes',scope=scope))['result']['outcomes'])==1
