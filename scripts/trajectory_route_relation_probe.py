#!/usr/bin/env python3
"""Read-only relations between composed candidate sets, never factual labels."""
import argparse
from itertools import combinations
import json
from pathlib import Path
from random import Random
from string import ascii_lowercase, digits
import tempfile

from mobile_region_replay import NativeProbe

from trajectory_composed_frame_probe import read as composed_read, fixture as composed_fixture, ROUTES, report_summary
from trajectory_question_frame_probe import trial, persist, collect


def route_relation(view):
    roots={route:set() for route in ROUTES}
    witness_roots={route:set() for route in ROUTES}
    witness_pairs={route:set() for route in ROUTES}
    for candidate in view['candidates']:
        for evidence in candidate['route_evidence']:
            route=evidence['route']
            roots[route].add(candidate['payload_id'])
            for witness in evidence['witnesses']:
                witness_pairs[route].add(tuple(witness))
                witness_roots[route].update(witness[:2])
    active=tuple(route for route in ROUTES if roots[route])
    status=('NO_ROUTE_OUTPUT' if not active else 'ONE_ROUTE_OUTPUT' if len(active)==1 else
            'SAME_ROOT_SET' if len({frozenset(roots[r]) for r in active})==1 else 'DIFFERENT_ROOT_SETS')
    shared=set.intersection(*(roots[r] for r in active)) if len(active)>1 else set()
    comparisons=[]
    for left,right in combinations(active,2):
        comparisons.append(dict(routes=(left,right),same_root_set=roots[left]==roots[right],
            shared_roots=tuple(sorted(roots[left]&roots[right])),
            left_only_roots=tuple(sorted(roots[left]-roots[right])),
            right_only_roots=tuple(sorted(roots[right]-roots[left])),
            shared_witness_payload_roots=tuple(sorted(witness_roots[left]&witness_roots[right])),
            shared_witness_pairs=tuple(sorted(witness_pairs[left]&witness_pairs[right]))))
    return dict(status=status,active_routes=active,
        route_roots={r:tuple(sorted(roots[r])) for r in ROUTES},
        shared_candidate_roots=tuple(sorted(shared)),
        multiple_candidate_roots=len(view['candidates'])>1,
        within_route_multiple_roots=tuple(r for r in ROUTES if len(roots[r])>1),
        comparisons=tuple(comparisons),
        factual_contradiction_status='NOT_EVALUATED', evidence_independence_status='NOT_ESTABLISHED',
        factual_quality_status='NOT_EVALUATED', selection_used=False)


def read(rows, region, query):
    view=composed_read(rows,region,query)
    view['route_relation']=route_relation(view)
    view['format']='memoria.ia-route-relation-view-v1'
    return view


CASES=('no_examples','copy_only','transform_only','composed','same_root_two_routes',
       'competing_routes','wrong_transform','repeated_conflict','shared_conflict',
       'partial_overlap','generated_copy','foreign_copy','unrelated_twin','same_root_unrelated_twin')


def fixture(case, seed, renamed=False):
    if case not in CASES: raise ValueError('unknown case')
    base='same_root_two_routes' if case in ('shared_conflict','partial_overlap','same_root_unrelated_twin') else case
    rows,region,queries=composed_fixture(base,seed)
    entity='drone' if seed%2 else 'morena'
    color='verde' if seed%2 else 'laranja'
    fact=f'A cor do {entity} é {color}.'
    def add(text,source,kind='user_turn'):
        rows.append(dict(hierarchy_id=region,source_id=source,
            sequence=1+sum(r['hierarchy_id']==region for r in rows),text=text,source_kind=kind))
    if case=='shared_conflict':
        for i in range(20):
            add(fact if i else f'A cor do {entity} é branca.',f'added-conflict-{i}')
            add('Intervalo observado.',f'added-conflict-{i}-barrier','assistant_generated')
        for q in queries:
            if q['expected']==[fact]: q['expected'].append(f'A cor do {entity} é branca.')
    if case=='partial_overlap':
        subjects=('dardo','nervo','odre') if seed%2 else ('nardo','vereda','ordem')
        values=('azul','preto','cinza') if seed%2 else ('rosa','âmbar','prata')
        convert=lambda text:text.replace('d','b').replace('n','l')
        for i,(subject,value) in enumerate(zip(subjects,values)):
            add(f'Qual é a cor do {subject}?',f'added-map-{i}-q')
            add(f'A cor do {convert(subject)} é {value}.',f'added-map-{i}-a')
            add('Intervalo observado.',f'added-map-{i}-barrier','assistant_generated')
        add(f'A cor do {convert(entity)} é {color}.','added-map-target')
        add('Intervalo observado.','added-map-target-barrier','assistant_generated')
    if case=='same_root_unrelated_twin':
        for q in queries: q['expected']=[]
    queries=[q for q in queries if q['name'] in ('covered','literal_cue','observed_paraphrase','absent_entity')]
    if renamed:
        symbols=sorted({c for r in rows for c in r['text']} | {c for q in queries for c in q['text']})
        alphabet=list(ascii_lowercase+digits+''.join(chr(i) for i in range(0xe0,0x100) if i!=0xf7))
        if len(symbols)>len(alphabet): raise ValueError('alphabet exhausted')
        Random(seed).shuffle(alphabet);mapping=dict(zip(symbols,alphabet))
        convert=lambda text:''.join(mapping[c] for c in text)
        rows=[dict(r,text=convert(r['text'])) for r in rows]
        queries=[dict(q,text=convert(q['text']),expected=[convert(t) for t in q['expected']]) for q in queries]
    return rows,region,queries



def append_intervention(library, before_rows, after_rows, region, query):
    if after_rows[:len(before_rows)] != before_rows:
        raise ValueError('intervention must append to the same raw history')
    with tempfile.TemporaryDirectory(prefix='memoria-route-intervention-') as directory:
        native=NativeProbe(library,Path(directory))
        try:
            persist(native,before_rows)
            before_stored=collect(native,[region])
            before=read(before_stored,region,query)
            before_unchanged=collect(native,[region])==before_stored
            persist(native,after_rows[len(before_rows):])
            after_stored=collect(native,[region])
            after=read(after_stored,region,query)
            after_unchanged=collect(native,[region])==after_stored
            native.reopen()
            cold=collect(native,[region])
            checks=dict(initial_raw_projection=before_stored==before_rows,
                before_query_read_only=before_unchanged,
                appended_raw_projection=after_stored==after_rows,
                historical_prefix_preserved=after_stored[:len(before_stored)]==before_stored,
                after_query_read_only=after_unchanged,
                cold_raw_projection=cold==after_stored,
                cold_full_view=read(cold,region,query)==after,
                queries_unobserved=all(query not in {r['text'] for r in xs} for xs in (before_stored,after_stored)),
                all_envelopes_unqualified=all(v['answer'] is None and not v['qualified'] and not v['selection_used'] for v in (before,after)))
            return dict(checks=checks,before_view=before,after_view=after)
        finally:
            native.close()


def probe(library, seed):
    trials=[trial(library,c,seed,r,fixture,read) for r in (False,True) for c in CASES]
    checks={f'{i}:{k}':v for i,t in enumerate(trials) for k,v in t['checks'].items()}
    for i,t in enumerate(trials):
        preserved=[]
        for q in t['queries']:
            plain=composed_read(t['rows'],q['frame_view']['region'],q['text'])
            expected={k:v for k,v in plain.items() if k not in ('frames','root_provenance','format')}
            actual={k:v for k,v in q['frame_view'].items() if k not in ('format','route_relation')}
            preserved.append(expected==actual)
        checks[f'outputs_preserved:{i}']=all(preserved)
        checks[f'diagnostics_unqualified:{i}']=all(q['frame_view']['route_relation']['factual_contradiction_status']=='NOT_EVALUATED' and
            q['frame_view']['route_relation']['evidence_independence_status']=='NOT_ESTABLISHED' and
            not q['frame_view']['route_relation']['selection_used'] for q in t['queries'])
    for i,c in enumerate(CASES):
        plain,opaque=trials[i],trials[i+len(CASES)]
        checks['rename_scores:'+c]=[q['frame_score'] for q in plain['queries']]==[q['frame_score'] for q in opaque['queries']]
        checks['rename_relations:'+c]=[(q['frame_view']['route_relation']['status'],q['frame_view']['route_relation']['multiple_candidate_roots'],len(q['frame_view']['route_relation']['shared_candidate_roots'])) for q in plain['queries']]==[(q['frame_view']['route_relation']['status'],q['frame_view']['route_relation']['multiple_candidate_roots'],len(q['frame_view']['route_relation']['shared_candidate_roots'])) for q in opaque['queries']]
    for offset in (0,len(CASES)):
        for base_case,twin_case in (('composed','unrelated_twin'),('same_root_two_routes','same_root_unrelated_twin')):
            positive,twin=trials[offset+CASES.index(base_case)],trials[offset+CASES.index(twin_case)]
            checks[f'twin_rows:{offset}:{base_case}']=positive['rows']==twin['rows']
            checks[f'twin_views:{offset}:{base_case}']=[q['frame_view'] for q in positive['queries']]==[q['frame_view'] for q in twin['queries']]
    interventions=[]
    for before_case,after_case in (('composed','same_root_two_routes'),('same_root_two_routes','shared_conflict'),('same_root_two_routes','partial_overlap')):
        before=trials[CASES.index(before_case)];after=trials[CASES.index(after_case)]
        prefix_equal=after['rows'][:len(before['rows'])]==before['rows']
        checks[f'append_only:{after_case}']=prefix_equal
        bq=next(q for q in before['queries'] if q['name']=='literal_cue');aq=next(q for q in after['queries'] if q['name']=='literal_cue')
        direct=append_intervention(library,before['rows'],after['rows'],bq['frame_view']['region'],bq['text'])
        for key,value in direct['checks'].items():
            checks[f'native_append:{after_case}:{key}']=value
        projected=lambda v:{k:value for k,value in v.items() if k not in ('frames','root_provenance')}
        checks[f'native_append:{after_case}:matches_trials']=projected(direct['before_view'])==bq['frame_view'] and projected(direct['after_view'])==aq['frame_view']
        interventions.append(dict(before_case=before_case,after_case=after_case,append_only=prefix_equal,
            native_append_checks=direct['checks'],
            added_rows=len(after['rows'])-len(before['rows']),query=bq['text'],
            before_relation=bq['frame_view']['route_relation'],after_relation=aq['frame_view']['route_relation'],
            before_roots=tuple(c['payload_id'] for c in bq['frame_view']['candidates']),
            after_roots=tuple(c['payload_id'] for c in aq['frame_view']['candidates'])))
    totals={}
    for route in ('frame','native'):
        scores=[q[route+'_score'] for t in trials for q in t['queries']]
        totals[route]=dict(queries=len(scores),exact_sets=sum(s['exact_set'] for s in scores),
            **{k:sum(s[k] for s in scores) for k in ('true_positive','false_positive','false_negative')})
    relation_counts={}
    relation_quality={}
    for t in trials:
        for q in t['queries']:
            status=q['frame_view']['route_relation']['status']
            relation_counts[status]=relation_counts.get(status,0)+1
            bucket=relation_quality.setdefault(status,dict(queries=0,exact_sets=0,true_positive=0,false_positive=0,false_negative=0))
            bucket['queries']+=1
            bucket['exact_sets']+=q['frame_score']['exact_set']
            for key in ('true_positive','false_positive','false_negative'):
                bucket[key]+=q['frame_score'][key]
    return dict(format='memoria.ia-route-relation-probe-v1',seed=seed,cases=trials,interventions=interventions,
        checks=checks,integrity_status='PASS' if all(checks.values()) else 'FAIL',
        integrity_passed=sum(checks.values()),integrity_total=len(checks),totals=totals,relation_counts=relation_counts,relation_quality_by_status=relation_quality,
        retrieval_quality_status='PASS_CURATED_ONLY' if totals['frame']['exact_sets']==totals['frame']['queries'] else 'FAIL_EXTRA_OR_MISSING_CONTENT',
        hidden_relevance_status='FAIL_INDISTINGUISHABLE_INPUTS',factual_quality_status='NOT_EVALUATED',
        limitation='Set relations and payload/witness overlap are diagnostics only: neither disagreement nor agreement identifies truth, falsehood or independent evidence; no selection or learned error penalty.')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--library',type=Path,required=True)
    parser.add_argument('--seed',type=int,default=20261229)
    parser.add_argument('--output',type=Path)
    parser.add_argument('--summary',action='store_true')
    args=parser.parse_args();report=probe(args.library,args.seed)
    body=json.dumps(report_summary(report) if args.summary else report,ensure_ascii=False,indent=1)+'\n'
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(body,encoding='utf-8')
    print(body,end='');raise SystemExit(0 if report['integrity_status']=='PASS' else 1)


if __name__=='__main__': main()
