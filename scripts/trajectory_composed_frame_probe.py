#!/usr/bin/env python3
"""Opt-in union of observed copy and transform routes, without ranking/voting."""
import argparse
import copy
from dataclasses import asdict
import json
from pathlib import Path
from random import Random
from string import ascii_lowercase, digits

from trajectory_analogy_frame_probe import recall as copy_recall
from trajectory_symbol_transform_probe import recall as transform_recall, fixture as transform_fixture
from trajectory_question_frame_probe import read as raw_read, trial, score, summary
from trajectory_response_quality_probe import TrajectoryGenerationExperiment

ROUTES = ('literal_copy','symbol_transform')


def recall(memory, query):
    views = {'literal_copy':copy_recall(memory,query), 'symbol_transform':transform_recall(memory,query)}
    frames, candidates = {}, {}
    for route in ROUTES:
        view = views[route]
        def qualified_id(value): return route + ':' + value
        for frame in view['frames']:
            key=qualified_id(frame['frame_id'])
            frames[key]=dict(frame,frame_id=key,source_frame_id=frame['frame_id'],route=route)
        for candidate in view['candidates']:
            root=candidate['payload_id']
            item=candidates.setdefault(root,dict(payload_id=root,output=candidate['output'],frame_ids=set(),witnesses=set()))
            if item['output']!=candidate['output']:
                raise RuntimeError('same root with inconsistent payload')
            item['frame_ids'].update(qualified_id(x) for x in candidate['frame_ids'])
            item['witnesses'].update(candidate['witnesses'])
    combined=tuple(dict(payload_id=root,output=c['output'],frame_ids=tuple(sorted(c['frame_ids'])),
                        witnesses=tuple(sorted(c['witnesses']))) for root,c in sorted(candidates.items()))
    return dict(frames=tuple(frames[k] for k in sorted(frames)),candidates=combined,
        hypothesis=combined[0]['output'] if len(combined)==1 else None,
        reason='UNIQUE_OBSERVED_COMPOSED_ROOT' if len(combined)==1 else
               'COMPETING_OBSERVED_COMPOSED_ROOTS' if combined else 'NO_OBSERVED_COMPOSED_ROOT')


def checked_read(memory, query):
    before=memory.snapshot(),memory.learning_state(),asdict(memory.generate(query))
    view=recall(memory,query)
    if view!=recall(TrajectoryGenerationExperiment.restore(memory.snapshot()),query):
        raise RuntimeError('composed cold parity failed')
    if before!=(memory.snapshot(),memory.learning_state(),asdict(memory.generate(query))):
        raise RuntimeError('composed read mutated memory')
    return view


def read(rows, region, query):
    view=raw_read(rows,region,query,reader=checked_read)
    frames={f['frame_id']:f for f in view['frames']}
    for candidate in view['candidates']:
        evidence=[]
        for route in ROUTES:
            admitted=[frames[k] for k in candidate['frame_ids'] if frames[k]['route']==route]
            if admitted:
                evidence.append(dict(route=route,frame_ids=tuple(f['frame_id'] for f in admitted),
                    witnesses=tuple(sorted({w for f in admitted for w in f['witnesses']}))))
        candidate['route_evidence']=tuple(evidence)
    view['format']='memoria.ia-composed-frame-view-v1'
    return view


CASES=('no_examples','copy_only','transform_only','composed','same_root_two_routes',
       'wrong_transform','competing_routes','repeated_conflict','generated_copy',
       'foreign_copy','unrelated_twin')


def fixture(case, seed, renamed=False):
    if case not in CASES: raise ValueError('unknown case')
    base=('no_examples' if case in ('no_examples','copy_only') else
          'wrong_map' if case in ('wrong_transform','competing_routes') else
          'repeated_conflict' if case=='repeated_conflict' else 'observed_map')
    rows,region,queries=transform_fixture(base,seed)
    subjects=('dardo','nervo','odre') if seed%2 else ('nardo','vereda','ordem')
    values=('azul','preto','cinza') if seed%2 else ('rosa','âmbar','prata')
    entity='drone' if seed%2 else 'morena'
    color='verde' if seed%2 else 'laranja'
    foreign=f'conversation:copy-outside-{seed}'
    def add(text,source,scope=region,kind='user_turn'):
        rows.append(dict(hierarchy_id=scope,source_id=source,
            sequence=1+sum(r['hierarchy_id']==scope for r in rows),text=text,source_kind=kind))
    if case not in ('no_examples','transform_only'):
        for family in range(2):
            for i,(subject,value) in enumerate(zip(subjects,values)):
                question=(f'Qual é a cor do {subject}?' if family==0 else f'Que cor tem o {subject}?')
                scope=foreign if case=='foreign_copy' else region
                kind='assistant_generated' if case=='generated_copy' else 'user_turn'
                add(question,f'copy-{family}-{i}-q',scope,kind)
                add(f'A cor do {subject} é {value}.',f'copy-{family}-{i}-a',scope,kind)
                add('Intervalo observado.',f'copy-{family}-{i}-barrier',scope,'assistant_generated')
    if case in ('same_root_two_routes','competing_routes'):
        convert=(lambda text:text.replace('v','w')) if case=='same_root_two_routes' else (lambda text:text.replace('d','b').replace('n','l'))
        for i,(subject,value) in enumerate(zip(subjects,values)):
            add(f'Qual é a cor do {subject}?',f'other-route-{i}-q')
            add(f'A cor do {convert(subject)} é {value}.',f'other-route-{i}-a')
            add('Intervalo observado.',f'other-route-{i}-barrier',kind='assistant_generated')
    expected=[f'A cor do {entity} é {color}.']
    if case=='repeated_conflict': expected.append(f'A cor do {entity} é branca.')
    # References express desired content, not route voting or factual claims.
    for q in queries:
        if q['name']=='untrained_lowercase': q['name']='literal_cue'
    queries += [dict(name='observed_paraphrase',text=f'Que cor tem o {entity}?',expected=list(expected)),
                dict(name='two_literal_cues',text=f'Qual é a cor do {entity}? Qual é a cor do NORDE?',expected=[])]
    if case=='unrelated_twin':
        for q in queries: q['expected']=[]
    if renamed:
        symbols=sorted({c for r in rows for c in r['text']} | {c for q in queries for c in q['text']})
        alphabet=list(ascii_lowercase+digits+''.join(chr(i) for i in range(0xe0,0x100) if i!=0xf7))
        if len(symbols)>len(alphabet): raise ValueError('alphabet exhausted')
        Random(seed).shuffle(alphabet);mapping=dict(zip(symbols,alphabet))
        convert=lambda text:''.join(mapping[c] for c in text)
        rows=[dict(r,text=convert(r['text'])) for r in rows]
        queries=[dict(q,text=convert(q['text']),expected=[convert(t) for t in q['expected']]) for q in queries]
    return rows,region,queries


def probe(library, seed):
    trials=[trial(library,c,seed,r,fixture,read) for r in (False,True) for c in CASES]
    checks={f'{i}:{k}':v for i,t in enumerate(trials) for k,v in t['checks'].items()}
    for i,t in enumerate(trials):
        for q in t['queries']:
            candidates=q['frame_view']['candidates']
            for route in ROUTES:
                texts=[c['text'] for c in candidates if any(e['route']==route for e in c['route_evidence'])]
                q[route+'_texts']=texts
                q[route+'_score']=score(texts,q['expected'])
        checks[f'route_union:{i}']=all(set(q['literal_copy_texts'])|set(q['symbol_transform_texts'])=={c['text'] for c in q['frame_view']['candidates']} for q in t['queries'])
        checks[f'roots_once:{i}']=all(len({c['payload_id'] for c in q['frame_view']['candidates']})==len(q['frame_view']['candidates']) for q in t['queries'])
        checks[f'route_witnesses_cover:{i}']=all({tuple(w) for e in c['route_evidence'] for w in e['witnesses']}=={tuple(w) for w in c['witnesses']} for q in t['queries'] for c in q['frame_view']['candidates'])
    for i,c in enumerate(CASES):
        plain,opaque=trials[i],trials[i+len(CASES)]
        checks['rename:'+c]=all([q[key+'_score'] for q in plain['queries']]==[q[key+'_score'] for q in opaque['queries']] for key in ('frame',)+ROUTES)
    for offset in (0,len(CASES)):
        positive,twin=trials[offset+CASES.index('composed')],trials[offset+CASES.index('unrelated_twin')]
        checks[f'twin_rows:{offset}']=positive['rows']==twin['rows']
        checks[f'twin_views:{offset}']=[q['frame_view'] for q in positive['queries']]==[q['frame_view'] for q in twin['queries']]
    totals={}
    for route in ('frame','native')+ROUTES:
        scores=[q[route+'_score'] for t in trials for q in t['queries']]
        totals[route]=dict(queries=len(scores),exact_sets=sum(s['exact_set'] for s in scores),
            **{k:sum(s[k] for s in scores) for k in ('true_positive','false_positive','false_negative')})
    return dict(format='memoria.ia-composed-frame-probe-v1',seed=seed,cases=trials,
        checks=checks,integrity_status='PASS' if all(checks.values()) else 'FAIL',
        integrity_passed=sum(checks.values()),integrity_total=len(checks),totals=totals,
        retrieval_quality_status='PASS_CURATED_ONLY' if totals['frame']['exact_sets']==totals['frame']['queries'] else 'FAIL_EXTRA_OR_MISSING_CONTENT',
        hidden_relevance_status='FAIL_INDISTINGUISHABLE_INPUTS',factual_quality_status='NOT_EVALUATED',
        limitation='Union of independently learned literal and finite transformed frames; no prioritization, votes or factual selection. Correlated fixture and symbol-renaming controls, no general semantic guarantee.')


def report_summary(report):
    compact=summary(report)
    for source,target in zip(report['cases'],compact['cases']):
        target['composed_frames']=copy.deepcopy(source['frames'])
    return compact


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--library',type=Path,required=True)
    parser.add_argument('--seed',type=int,default=20261227)
    parser.add_argument('--output',type=Path)
    parser.add_argument('--summary',action='store_true')
    args=parser.parse_args();report=probe(args.library,args.seed)
    body=json.dumps(report_summary(report) if args.summary else report,ensure_ascii=False,indent=2)+'\n'
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(body,encoding='utf-8')
    print(body,end='');raise SystemExit(0 if report['integrity_status']=='PASS' else 1)


if __name__=='__main__': main()
