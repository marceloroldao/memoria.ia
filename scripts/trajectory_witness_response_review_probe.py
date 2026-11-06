#!/usr/bin/env python3
"""Durable response review and explicit decision matrix; never apply the offered pair."""
import argparse
import json
from pathlib import Path
import tempfile

from trajectory_borrowed_map_probe import fixture
from trajectory_feedback_session import FeedbackSession
from trajectory_region_evidence_probe import fingerprint
from trajectory_review_wizard import ReviewWizard
from trajectory_transfer_evaluation import SEEDS
from trajectory_witness_requests_probe import scripted_response
from trajectory_witness_response_review import current_requests,open_response,response_origin


RESPONSES=('observed','incorrect_observation','generated')
CHOICES=('select','defer','reject_all')


def trial(library,seed,surface,world,response_kind,choice):
    descriptor=fixture('humidity',seed,surface,'two_anchors',world)
    scope=descriptor['scope'];query=descriptor['queries'][0]['text'];kind='assistant_generated' if response_kind=='generated' else 'user_turn'
    with tempfile.TemporaryDirectory(prefix='memoria-witness-response-review-') as directory:
        with FeedbackSession(library,directory) as session:
            for row in descriptor['rows']:session.execute(dict(op='observe',scope=scope,**row))
            session.execute(dict(op='observe',scope='foreign',event_id='foreign',text=descriptor['foreign']))
            history=session.execute(dict(op='history',scope=scope));foreign=session.execute(dict(op='history',scope='foreign'))
            pending=current_requests(session,scope,query);request=pending['requests'][0]
            response=scripted_response(descriptor,request,response_kind)[1]['text']
            queries=descriptor['queries'][:2]
            before=[session.execute(dict(op='query',scope=scope,text=q['text'])) for q in queries]
            opened=open_response(session,scope,query,request['request_id'],response,kind)
            receipt=opened['review_receipt']['event'];offer=receipt['reviewed_result']['example_review']['offers'][0]['offer']
            binding=response_origin(offer)
            decision=session.execute(dict(op='record_review_decision',scope=scope,receipt_id=receipt['receipt_id'],
                decision_id='response-decision',actor_id='scripted-operator',choice=choice,
                offer_id=offer['offer_id'] if choice=='select' else None,reason='Scripted review; no human verification.'))['result']['event']
            outcome=session.execute(dict(op='record_review_outcome',scope=scope,decision_id=decision['decision_id'],
                after_receipt_id=receipt['receipt_id'],outcome_id='response-outcome',actor_id='scripted-operator',
                judgement='uncertain',reason='Response remains outside the learning region.'))['result']['event']
            checks=dict(request_binding=binding['request_id']==request['request_id'] and binding['request_sha256']==fingerprint(request),
                        response_content_preserved=offer['examples']==[dict(source_text=request['source_text'],target_text=response)],
                        origin_preserved=binding['source_kind']==kind,
                        learning_history_unchanged=session.execute(dict(op='history',scope=scope))==history,
                        foreign_history_unchanged=session.execute(dict(op='history',scope='foreign'))==foreign,
                        full_query_views_unchanged=all(session.execute(dict(op='query',scope=scope,text=q['text']))==v for q,v in zip(queries,before)),
                        request_still_pending=current_requests(session,scope,query)==pending,
                        no_fact_selection=all(v['answer'] is None and not v['qualified'] and not v['selection_used'] for v in before),
                        declared_decision_preserved=decision['choice']==choice,
                        uncertain_outcome_without_learning=outcome['judgement']=='uncertain' and not outcome['comparison']['learning_context_changed'])
            if kind=='assistant_generated' and choice=='select':
                wizard=ReviewWizard(session,scope,'scripted-operator')
                try:wizard.incorporation_plan(decision,receipt,'user_turn')
                except ValueError:checks['generated_application_veto']=True
                else:checks['generated_application_veto']=False
                checks['veto_before_observe']=session.execute(dict(op='history',scope=scope))==history
            replay=open_response(session,scope,query,request['request_id'],response,kind)
            checks['same_state_receipt_replay']=replay['review_receipt']['status']=='EXACT_REPLAY'
            audit=session.execute(dict(op='review_outcomes',scope=scope))
        with FeedbackSession(library,directory) as cold:
            checks['cold_learning_history']=cold.execute(dict(op='history',scope=scope))==history
            checks['cold_full_audit']=cold.execute(dict(op='review_outcomes',scope=scope))==audit
            checks['cold_pending_request']=current_requests(cold,scope,query)==pending
            checks['cold_query_views']=all(cold.execute(dict(op='query',scope=scope,text=q['text']))==v for q,v in zip(queries,before))
            again=open_response(cold,scope,query,request['request_id'],response,kind)
            checks['cold_replay_without_new_audit']=again['review_receipt']['status']=='EXACT_REPLAY' and cold.execute(dict(op='review_outcomes',scope=scope))==audit
    return dict(seed=seed,surface=surface,world=world,response_kind=response_kind,choice=choice,
                fixture=descriptor,request=request,response_text=response,origin=kind,audit=audit,
                query_views_sha256=[fingerprint(view) for view in before],checks=checks)


def probe(library):
    trials=[trial(library,seed,surface,world,response_kind,choice) for seed in SEEDS
            for surface in ('uppercase','paraphrase') for world in ('shared_map','switched_map')
            for response_kind in RESPONSES for choice in CHOICES]
    checks={f'{i}:{name}':passed for i,t in enumerate(trials) for name,passed in t['checks'].items()}
    return dict(format='memoria.ia-witness-response-review-probe-v1',trials=trials,checks=checks,
                integrity_status='PASS' if all(checks.values()) else 'FAIL',response_records=len(trials),
                offered_examples_applied=0,human_evaluation_status='NOT_PERFORMED',general_learning_status='NOT_ESTABLISHED',
                limitation='Scripted audit protocol on reused synthetic humidity fixtures. Selection is a recorded operator choice, never automatic incorporation. Generated origin is protected in the wizard; incorrect declared user observations remain a factual risk if explicitly incorporated later.')


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--library',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();report=probe(args.library);report['report_content_sha256']=fingerprint(report)
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(report,ensure_ascii=False,sort_keys=True,separators=(',',':'))+'\n')
    print(json.dumps(dict(integrity_status=report['integrity_status'],responses=report['response_records'],checks=len(report['checks']),passed=sum(report['checks'].values()),sha256=report['report_content_sha256'])))
    return 0 if report['integrity_status']=='PASS' else 1


if __name__=='__main__':raise SystemExit(main())
