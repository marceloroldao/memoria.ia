#!/usr/bin/env python3
"""Fixed-arm synthetic transfer evaluation; references never enter session commands."""
import argparse
from collections import Counter
import json
from pathlib import Path
from random import Random
import tempfile

from trajectory_feedback_portuguese_probe import score
from trajectory_feedback_session import FeedbackSession
from trajectory_region_evidence_probe import fingerprint


SEEDS = (20261101, 20261102)
DOMAINS = {'humidity': ('umidade', '%'), 'vibration': ('vibração', 'mm/s')}
ARMS = ('baseline', 'irrelevant', 'contrast', 'intervention')


def fixture(domain, seed, arm):
    if domain not in DOMAINS or arm not in ARMS:
        raise ValueError('unknown domain or arm')
    rng = Random(seed)
    a,b,c,d,e,f = rng.sample('ABCDEFGHJKLMNPQRSTUVXYZ', 6)
    values = rng.sample('abcdefghjklmnpqrstuvxyz', 6)
    mapping = dict(zip((a,b,c,d,e,f), values))
    attribute, unit = DOMAINS[domain]
    question = lambda entity: f'Qual é a {attribute} do {entity}?'
    statement = lambda entity, value: f'A {attribute} do {entity} é {value}.'
    convert = lambda entity: ''.join(mapping[s] for s in entity)
    rows = []
    def add(text, kind='user_turn'):
        rows.append(dict(event_id=f'row-{len(rows)}', text=text, source_kind=kind))
    def barrier(): add('Intervalo observado.', 'assistant_generated')
    def pair(entity, value, target=None):
        add(question(entity)); add(statement(convert(entity) if target is None else target, value)); barrier()
    for i, entity in enumerate((a+b+c,b+c+a,c+a+b)):
        pair(entity, f'{(i+1)*10} {unit}')
    targets = (d+a+b,b+d+a)
    expected = [statement(convert(entity), f'{40+i*10} {unit}') for i, entity in enumerate(targets)]
    for text in expected: add(text); barrier()
    add(statement(convert(a+d+b), f'60 {unit}'), 'assistant_generated'); barrier()
    prefix_length = len(rows)
    teaching = d+c+a
    if arm in ('intervention','contrast'):
        target = convert(teaching)
        if arm == 'contrast':
            wrong = next(s for s in 'abcdefghjklmnpqrstuvxyz' if s not in mapping.values())
            target = wrong + target[1:]
        pair(teaching, f'70 {unit}', target)
    elif arm == 'irrelevant':
        add('Observação isolada sem demonstração.'); barrier()
    queries = [dict(name=f'novel_combination_{i+1}',text=question(entity),expected=[text],family='transfer',required=True)
               for i,(entity,text) in enumerate(zip(targets,expected))]
    queries += [dict(name='uppercase',text=question(targets[0]).upper(),expected=[expected[0]],family='surface',required=False),
                dict(name='paraphrase',text=f'Que {attribute} tem o {targets[0]}?',expected=[expected[0]],family='surface',required=False)]
    for name, text in (('absent_attribute', f'Qual é a idade do {targets[0]}?'),
                       ('absent_entity',question(d+d+a)), ('unknown_symbol',question(e+a+b)),
                       ('generated_only',question(a+d+b)),('foreign_only',question(a+b+d))):
        queries.append(dict(name=name,text=text,expected=[],family='absence',required=True))
    assert all(q['text'] not in {r['text'] for r in rows} for q in queries)
    assert question(teaching) not in {q['text'] for q in queries}
    return dict(domain=domain,seed=seed,arm=arm,scope=f'{domain}_{seed}',rows=rows,
                intervention_start=prefix_length,queries=queries,
                foreign=statement(convert(a+b+d),f'80 {unit}'))


def trial(library, descriptor, operation='query'):
    if operation not in ('query','diagnose'):
        raise ValueError('read-only evaluation operation required')
    scope = descriptor['scope']; queries = descriptor['queries']; cases = []; checks = {}
    with tempfile.TemporaryDirectory(prefix='memoria-transfer-') as directory:
        with FeedbackSession(library,directory) as session:
            for row in descriptor['rows']:
                session.execute(dict(op='observe',scope=scope,**row))
            session.execute(dict(op='observe',scope='foreign',event_id='foreign',text=descriptor['foreign']))
            for row in descriptor.get('foreign_rows',[]):
                session.execute(dict(op='observe',scope='foreign',**row))
            before = session.execute(dict(op='history',scope=scope))
            foreign = session.execute(dict(op='history',scope='foreign'))
            views = [session.execute(dict(op=operation,scope=scope,text=q['text'])) for q in queries]
            checks['read_only'] = session.execute(dict(op='history',scope=scope)) == before
            checks['foreign_unchanged'] = session.execute(dict(op='history',scope='foreign')) == foreign
            checks['repeat_full_views'] = all(session.execute(dict(op=operation,scope=scope,text=q['text'])) == v
                                               for q,v in zip(queries,views))
            accepted = {r['text'] for r in descriptor['rows'] if r['source_kind']=='user_turn'}
            checks['observed_candidates_only'] = all(c['text'] in accepted for v in views for c in v['result']['available_candidates'])
            checks['unqualified'] = all(v['answer'] is None and not v['qualified'] and not v['selection_used'] for v in views)
        with FeedbackSession(library,directory) as cold:
            checks['cold_history'] = cold.execute(dict(op='history',scope=scope)) == before
            checks['cold_full_views'] = all(cold.execute(dict(op=operation,scope=scope,text=q['text'])) == v for q,v in zip(queries,views))
    for query, view in zip(queries,views):
        cases.append(dict(query=query,score=score(view,query['expected']),
                          available_candidates=view['result']['available_candidates'],
                          answer=view['answer'],qualified=view['qualified'],selection_used=view['selection_used'],
                          full_view_sha256=fingerprint(view)))
        if operation=='diagnose':
            diagnosis = view['result']['diagnosis']
            cases[-1]['diagnosis'] = dict(findings=[f['code'] for f in diagnosis['findings']],
                frame_status_counts=dict(sorted(Counter(f['status'] for f in diagnosis['frames']).items())),
                transform_candidate_set_equal=diagnosis['transform_trace']['candidate_set_equal'])
    return dict(fixture=descriptor,cases=cases,checks=checks)


def probe(library):
    # All conditions are fixed before execution; no score selects examples or later queries.
    trials = [trial(library,fixture(domain,seed,arm)) for seed in SEEDS for domain in DOMAINS for arm in ARMS]
    checks = {f'{i}:{name}':ok for i,t in enumerate(trials) for name,ok in t['checks'].items()}
    summary = {}
    for arm in ARMS:
        cases = [c for t in trials if t['fixture']['arm']==arm for c in t['cases']]
        summary[arm] = {family:dict(exact=sum(c['score']['exact'] for c in cases if c['query']['family']==family),
                                   total=sum(c['query']['family']==family for c in cases))
                        for family in ('transfer','surface','absence')}
    required = [c for t in trials if t['fixture']['arm']=='intervention' for c in t['cases'] if c['query']['required']]
    intervention = [c for t in trials if t['fixture']['arm']=='intervention' for c in t['cases']]
    return dict(format='memoria.ia-synthetic-transfer-evaluation-v1',seeds=list(SEEDS),arms=list(ARMS),trials=trials,
                summary=summary,checks=checks,integrity_status='PASS' if all(checks.values()) else 'FAIL',
                retrieval_status='PASS_CURATED_SET' if all(c['score']['exact'] for c in intervention) else 'EXTRA_OR_MISSING_CONTENT',
                required_retrieval_status='PASS_CURATED_REQUIRED_SET' if all(c['score']['exact'] for c in required) else 'EXTRA_OR_MISSING_CONTENT',
                required_exact=sum(c['score']['exact'] for c in required),required_total=len(required),
                selected_answer_count=sum(c['answer'] is not None for t in trials for c in t['cases']),
                labels_used_by_session=False,human_evaluation_status='NOT_PERFORMED',general_learning_status='NOT_ESTABLISHED',
                limitation='Curated finite injective symbol maps and correlated templates, not a blind independent benchmark. Target facts are observed; only queries and entity combinations are withheld from paired demonstrations. Native persistence plus Python experimental frame reader; candidate recovery is not factual answer selection. No engine changes or LLM.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--library',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--strict-retrieval',action='store_true')
    args = parser.parse_args(); report = probe(args.library)
    report['report_content_sha256'] = fingerprint(report)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,ensure_ascii=False,sort_keys=True,separators=(',',':'))+'\n')
    print(json.dumps({k:report[k] for k in ('integrity_status','retrieval_status','required_retrieval_status','summary','required_exact','required_total','selected_answer_count','report_content_sha256')}))
    return 1 if report['integrity_status']!='PASS' or (args.strict_retrieval and report['retrieval_status']!='PASS_CURATED_SET') else 0


if __name__=='__main__':
    raise SystemExit(main())
