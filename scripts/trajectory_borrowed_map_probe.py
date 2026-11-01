#!/usr/bin/env python3
"""Evaluate borrowed-map gains and indistinguishable counterexamples separately."""
import argparse
import copy
import json
from pathlib import Path
import tempfile

from trajectory_borrowed_map import read
from trajectory_feedback_session import FeedbackSession
from trajectory_region_evidence_probe import fingerprint
from trajectory_surface_evaluation import fixture as surface_fixture
from trajectory_transfer_evaluation import DOMAINS,SEEDS


ARMS = ('baseline','one_anchor','two_anchors','wrong_anchor','generated','foreign')
WORLDS = ('shared_map','switched_map')


def fixture(domain,seed,surface,arm,world):
    if arm not in ARMS or world not in WORLDS: raise ValueError('unknown condition')
    result = surface_fixture(domain,seed,surface,'known_symbols_only')
    start = result['intervention_start']; additions = copy.deepcopy(result['rows'][start:start+6])
    result['rows'] = result['rows'][:start];result['foreign_rows']=[]
    # Both possible worlds have exactly the same observable evidence. They differ
    # only in the unobserved map of the fourth symbol in the new query form.
    queries = [q for q in result['queries'] if q['family']=='surface']
    alternatives = []
    # The existing original-form teaching pair covers the fourth symbol.
    fourth = result['rows'][-2]['text'].split(' do ')[1].split(' é ')[0][0]
    occupied = {c for row in result['rows'] for c in row['text']}
    other = next(c for c in 'abcdefghjklmnpqrstuvxyz' if c not in occupied)
    for i,q in enumerate(queries):
        expected = q['expected'][0]; head,rest = expected.split(' do ')
        variable,value = rest.split(' é ')
        alternative = head+' do '+variable.replace(fourth,other)+' é '+value
        alternatives.append(alternative)
        result['rows'] += [dict(event_id=f'alternative-{i}',text=alternative,source_kind='user_turn'),
                           dict(event_id=f'alternative-{i}-barrier',text='Intervalo observado.',source_kind='assistant_generated')]
    # References are not part of observations or query commands.
    if world=='switched_map':
        for q,alternative in zip(queries,alternatives): q['expected']=[alternative]
    result['queries']=queries+[q for q in result['queries'] if q['family']=='absence']
    count = 0 if arm=='baseline' else 3 if arm=='one_anchor' else 6
    additions = additions[:count]
    if arm=='wrong_anchor':
        additions[1]['text']='Conteúdo sem vínculo com o mapa.'
    if arm=='generated':
        for row in additions: row['source_kind']='assistant_generated'
    result['foreign_rows' if arm=='foreign' else 'rows'].extend(additions)
    result.update(arm=arm,world=world,intervention_start=start)
    return result


def trial(library,descriptor):
    scope=descriptor['scope']; region='conversation:feedback-session:'+scope
    with tempfile.TemporaryDirectory(prefix='memoria-borrowed-map-') as directory:
        with FeedbackSession(library,directory) as session:
            for row in descriptor['rows']: session.execute(dict(op='observe',scope=scope,**row))
            session.execute(dict(op='observe',scope='foreign',event_id='foreign',text=descriptor['foreign']))
            for row in descriptor['foreign_rows']: session.execute(dict(op='observe',scope='foreign',**row))
            history=session.execute(dict(op='history',scope=scope)); foreign=session.execute(dict(op='history',scope='foreign'))
            rows=history['result']['entries']+foreign['result']['entries']
            cases=[]
            for query in descriptor['queries']:
                standard=session.execute(dict(op='query',scope=scope,text=query['text']))
                borrowed=read(rows,region,query['text'])
                observed={h['text'] for h in borrowed['hypotheses']}; expected=set(query['expected'])
                cases.append(dict(query=query,standard_candidate_texts=[c['text'] for c in standard['result']['available_candidates']],
                                  borrowed=borrowed,score=dict(exact=observed==expected,recovered=len(observed&expected),
                                                              extra=len(observed-expected),missing=len(expected-observed))))
            checks=dict(history_unchanged=session.execute(dict(op='history',scope=scope))==history,
                        foreign_unchanged=session.execute(dict(op='history',scope='foreign'))==foreign,
                        queries_not_observed=all(q['text'] not in {row['text'] for row in descriptor['rows']} for q in descriptor['queries']),
                        no_selection=all(c['borrowed']['answer'] is None and not c['borrowed']['qualified'] and not c['borrowed']['selection_used'] for c in cases))
        with FeedbackSession(library,directory) as cold:
            cold_history=cold.execute(dict(op='history',scope=scope));cold_foreign=cold.execute(dict(op='history',scope='foreign'))
            checks['cold_history']=cold_history==history and cold_foreign==foreign
            cold_rows=cold_history['result']['entries']+cold_foreign['result']['entries']
            checks['cold_borrowed']=all(read(cold_rows,region,c['query']['text'])==c['borrowed'] for c in cases)
            checks['standard_reader_unchanged']=all([x['text'] for x in cold.execute(dict(op='query',scope=scope,text=c['query']['text']))['result']['available_candidates']]==c['standard_candidate_texts'] for c in cases)
    return dict(fixture=descriptor,cases=cases,checks=checks,
                observations_sha256=fingerprint(dict(rows=descriptor['rows'],foreign_rows=descriptor['foreign_rows'],foreign=descriptor['foreign'])))


def probe(library):
    trials=[trial(library,fixture(domain,seed,surface,arm,world)) for seed in SEEDS for domain in DOMAINS
            for surface in ('uppercase','paraphrase') for arm in ARMS for world in WORLDS]
    checks={f'{i}:{k}':v for i,t in enumerate(trials) for k,v in t['checks'].items()}
    summary={world:{arm:{family:dict(exact=sum(c['score']['exact'] for t in trials if t['fixture']['world']==world and t['fixture']['arm']==arm for c in t['cases'] if c['query']['family']==family),
                                   total=sum(1 for t in trials if t['fixture']['world']==world and t['fixture']['arm']==arm for c in t['cases'] if c['query']['family']==family))
                             for family in ('surface','absence')} for arm in ARMS} for world in WORLDS}
    for i in range(0,len(trials),2):
        a,b=trials[i:i+2]
        checks[f'{i}:indistinguishable_observations']=a['observations_sha256']==b['observations_sha256']
        checks[f'{i}:same_hypotheses_despite_hidden_world']=all(x['borrowed']==y['borrowed'] for x,y in zip(a['cases'],b['cases']))
    return dict(format='memoria.ia-borrowed-map-probe-v1',trials=trials,summary=summary,checks=checks,
                integrity_status='PASS' if all(checks.values()) else 'FAIL',
                promotion_status='NOT_APPROVED_FOR_SELECTION',human_evaluation_status='NOT_PERFORMED',
                general_learning_status='NOT_ESTABLISHED',default_reader_changed=False,
                limitation='Synthetic map borrowing assumes an unwitnessed pair is shared across source forms. Identical evidence supports worlds with different hidden mappings, so successful transfer does not justify factual selection. Hypotheses are opt-in, read-only and outside the standard session.')


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--library',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();report=probe(args.library);report['report_content_sha256']=fingerprint(report)
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(report,ensure_ascii=False,sort_keys=True,separators=(',',':'))+'\n')
    print(json.dumps(dict(integrity_status=report['integrity_status'],summary=report['summary'],promotion_status=report['promotion_status'],sha256=report['report_content_sha256'])))
    return 0 if report['integrity_status']=='PASS' else 1


if __name__=='__main__': raise SystemExit(main())
