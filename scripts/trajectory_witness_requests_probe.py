#!/usr/bin/env python3
"""Scripted responses to witness requests; preserve misleading observation controls."""
import argparse
import copy
import json
from pathlib import Path
import tempfile

from trajectory_borrowed_map_probe import fixture as borrowed_fixture
from trajectory_feedback_session import FeedbackSession
from trajectory_region_evidence_probe import fingerprint
from trajectory_transfer_evaluation import DOMAINS,SEEDS
from trajectory_witness_requests import propose


ARMS=('no_response','observed','generated','irrelevant','incorrect_observation')


def scripted_response(descriptor,request,arm):
    """Evaluation oracle only: never called by the request proposer."""
    if arm=='no_response':return []
    if arm=='irrelevant':texts=('Relato sem vínculo.','Outro relato sem relação.')
    else:
        start=descriptor['intervention_start']-3
        content=descriptor['rows'][start+1]['text']
        expected=descriptor['queries'][0]['expected'][0].split(' do ')[1].split(' é ')[0][0]
        if arm=='incorrect_observation':
            alternatives=[row['text'] for row in descriptor['rows'] if row['event_id']=='alternative-0']
            original=descriptor['rows'][start+1]['text'].split(' do ')[1].split(' é ')[0][0]
            alternative=alternatives[0].split(' do ')[1].split(' é ')[0][0]
            expected=alternative if expected==original else original
        head,rest=content.split(' do ');content=head+' do '+expected+rest[1:]
        texts=(request['source_text'],content)
    kind='assistant_generated' if arm=='generated' else 'user_turn'
    return [dict(event_id='response-q',text=texts[0],source_kind=kind),
            dict(event_id='response-a',text=texts[1],source_kind=kind),
            dict(event_id='response-barrier',text='Intervalo observado.',source_kind='assistant_generated')]


def trial(library,domain,seed,surface,world,arm):
    fixture=borrowed_fixture(domain,seed,surface,'two_anchors',world)
    fixture=copy.deepcopy(fixture);scope=fixture['scope'];region='conversation:feedback-session:'+scope
    with tempfile.TemporaryDirectory(prefix='memoria-witness-request-') as directory:
        with FeedbackSession(library,directory) as session:
            for row in fixture['rows']:session.execute(dict(op='observe',scope=scope,**row))
            session.execute(dict(op='observe',scope='foreign',event_id='foreign',text=fixture['foreign']))
            history=session.execute(dict(op='history',scope=scope));foreign=session.execute(dict(op='history',scope='foreign'))
            rows=history['result']['entries']+foreign['result']['entries']
            request=propose(rows,region,fixture['queries'][0]['text'])
            checks=dict(request_read_only=session.execute(dict(op='history',scope=scope))==history,
                        deterministic_request=propose(rows,region,fixture['queries'][0]['text'])==request,
                        one_request=len(request['requests'])==1,
                        no_dispatch=not request['request_dispatched'] and not request['observations_recorded'])
            if not checks['one_request']:raise RuntimeError('curated fixture did not yield one request')
            response=scripted_response(fixture,request['requests'][0],arm)
            targets={text for q in fixture['queries'] for text in q['expected']}
            checks['held_out_targets_excluded']=all(row['text'] not in targets for row in response)
            checks['held_out_queries_excluded']=all(row['text'] not in {q['text'] for q in fixture['queries']} for row in response)
            before=[session.execute(dict(op='query',scope=scope,text=q['text'])) for q in fixture['queries']]
            for row in response:session.execute(dict(op='observe',scope=scope,**row))
            after=[session.execute(dict(op='query',scope=scope,text=q['text'])) for q in fixture['queries']]
            final=session.execute(dict(op='history',scope=scope))
            pending=propose(final['result']['entries']+foreign['result']['entries'],region,fixture['queries'][0]['text'])
            checks['scripted_pending_state']=(pending==request if arm in ('no_response','generated','irrelevant') else not pending['requests'])
            checks['queries_read_only']=session.execute(dict(op='history',scope=scope))==final
            checks['foreign_unchanged']=session.execute(dict(op='history',scope='foreign'))==foreign
            checks['no_qualification']=all(view['answer'] is None and not view['qualified'] and not view['selection_used'] for view in before+after)
        with FeedbackSession(library,directory) as cold:
            cold_history=cold.execute(dict(op='history',scope=scope))
            checks['cold_history']=cold_history==final
            checks['cold_full_views']=all(cold.execute(dict(op='query',scope=scope,text=q['text']))==view for q,view in zip(fixture['queries'],after))
            checks['cold_pending_request']=propose(cold_history['result']['entries']+foreign['result']['entries'],region,fixture['queries'][0]['text'])==pending
    cases=[]
    for query,old,new in zip(fixture['queries'],before,after):
        observed={c['text'] for c in new['result']['available_candidates']};expected=set(query['expected'])
        cases.append(dict(query=query,before_candidates=[c['text'] for c in old['result']['available_candidates']],
            after_candidates=new['result']['available_candidates'],full_view_sha256=fingerprint(new),
            score=dict(exact=observed==expected,recovered=len(observed&expected),extra=len(observed-expected),missing=len(expected-observed))))
    return dict(domain=domain,seed=seed,surface=surface,world=world,arm=arm,fixture=fixture,
                request=request,response=response,pending_request=pending,cases=cases,checks=checks)


def probe(library):
    trials=[trial(library,domain,seed,surface,world,arm) for seed in SEEDS for domain in DOMAINS
            for surface in ('uppercase','paraphrase') for arm in ARMS for world in ('shared_map','switched_map')]
    checks={f'{i}:{key}':value for i,t in enumerate(trials) for key,value in t['checks'].items()}
    for i in range(0,len(trials),2):checks[f'{i}:same_request_before_world_response']=trials[i]['request']==trials[i+1]['request']
    summary={arm:{family:dict(exact=sum(c['score']['exact'] for t in trials if t['arm']==arm for c in t['cases'] if c['query']['family']==family),
                             total=sum(1 for t in trials if t['arm']==arm for c in t['cases'] if c['query']['family']==family))
                   for family in ('surface','absence')} for arm in ARMS}
    return dict(format='memoria.ia-witness-requests-probe-v1',trials=trials,summary=summary,checks=checks,
                integrity_status='PASS' if all(checks.values()) else 'FAIL',
                human_evaluation_status='NOT_PERFORMED',general_learning_status='NOT_ESTABLISHED',
                limitation='Post-diagnosis synthetic scripted responses. A new truthful pair can distinguish these worlds, but a misleading declared observation can teach the wrong route. Proposals do not verify truth, dispatch requests or ingest responses; the evaluator explicitly observes scripted data.')


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--library',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();report=probe(args.library);report['report_content_sha256']=fingerprint(report)
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(report,ensure_ascii=False,sort_keys=True,separators=(',',':'))+'\n')
    print(json.dumps(dict(integrity_status=report['integrity_status'],summary=report['summary'],sha256=report['report_content_sha256'])))
    return 0 if report['integrity_status']=='PASS' else 1


if __name__=='__main__':raise SystemExit(main())
