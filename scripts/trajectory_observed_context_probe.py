#!/usr/bin/env python3
"""Observed copied context separates roots; context is never a hardcoded reply role."""
import argparse
import json
from random import Random
from trajectory_boundary_candidates_probe import checked_boundary_packet
from trajectory_separator_ablation_probe import score,counts
from trajectory_response_quality_probe import TrajectoryGenerationExperiment


def fixture(seed,renamed=False):
    symbols=iter(Random(seed).sample(range(1000,100000),100))
    block=lambda n:tuple(next(symbols) for _ in range(n))
    p,s,sep,t,b,bridge,end=(block(1) for _ in range(7))
    contexts=[block(2) for _ in range(7)]
    bodies=[block(4) for _ in range(5)]
    values=[block(2) for _ in range(7)]
    transform=lambda xs:tuple(1000000-x for x in xs) if renamed else tuple(xs)
    source=lambda i,c:transform(p+contexts[c]+sep+bodies[i]+s)
    hidden=lambda i:transform(p+bodies[i]+s)
    target=lambda i,c,v:transform(t+contexts[c]+b+bodies[i]+bridge+values[v]+end)
    stripped=transform(t+b+bodies[3]+bridge+values[3]+end)
    initial=tuple((hidden(i),target(i,i,i)) for i in range(3))
    transported=tuple((source(i,i),target(i,i,i)) for i in range(3))
    crossed=((source(1,0),target(1,0,3)),(source(1,0),target(1,0,4)),
             (source(0,1),target(0,1,5)))
    facts=(target(3,3,3),target(3,4,4),target(3,6,3),stripped)
    rival=target(3,3,6)
    queries=(('first',source(3,3)),('swapped_context',source(3,4)),
        ('other_observed_context',source(3,6)),('unknown_context',source(3,5)),
        ('unknown_body',source(4,3)),('missing_context',hidden(3)),
        ('joined_context_queries',source(3,3)+source(3,4)))
    cross_queries=(('context_changed',source(1,0),(target(1,0,3),target(1,0,4))),
                   ('body_changed',source(0,1),(target(0,1,5),)),
                   ('original_retained',source(0,0),(target(0,0,0),)))
    return dict(initial_pairs=initial,transported_pairs=transported,crossed_pairs=crossed,
                facts=facts,rival=rival,queries=queries,cross_queries=cross_queries)


def evaluate(seed,renamed=False):
    data=fixture(seed,renamed)
    memory=TrajectoryGenerationExperiment()
    def pair(source,target,address):
        memory.observe(source,observation_id=address+':source',stream_id=address)
        memory.observe(target,observation_id=address+':target',stream_id=address)
    for i,(source,target) in enumerate(data['initial_pairs']):
        pair(source,target,f'hidden:{i}')
    for i,fact in enumerate(data['facts']):
        memory.observe(fact,observation_id=f'fact:{i}',stream_id=f'fact:{i}')
    stages=[]
    def capture(name,enriched=False,conflict=False):
        cases=[]
        for query_name,query in data['queries']:
            expected=(data['facts'][0],data['rival']) if query_name=='first' and conflict else (
                (data['facts'][0],) if query_name=='first' else
                (data['facts'][1],) if query_name=='swapped_context' else
                (data['facts'][2],) if query_name=='other_observed_context' else ())
            kind='conflict' if len(expected)>1 else 'answer' if expected else 'absence'
            result=checked_boundary_packet(memory,query)
            assert not result['observed_continuations']
            cases.append(dict(name=query_name,query=query,kind=kind,expected=expected,
                              packet=result,**score(result,kind,expected)))
        rows=memory.snapshot()['observations']
        stages.append(dict(name=name,enriched=enriched,cases=cases,provenance=rows,
            unique_payloads=len({r['payload_id'] for r in rows})))
    capture('context_missing_in_demonstration_source')
    for i,(source,target) in enumerate(data['transported_pairs']):
        pair(source,target,f'transported:{i}')
    capture('context_copied_from_source',enriched=True)
    for i,(source,target) in enumerate(data['crossed_pairs']):
        pair(source,target,f'cross:{i}')
    capture('crossed_context_body_value',enriched=True)
    for i in range(2):
        pair(*data['crossed_pairs'][0],f'repeat:{i}')
    capture('repeated_crossed_pair',enriched=True)
    memory.observe(data['rival'],observation_id='rival',stream_id='rival')
    capture('same_context_competing_value',enriched=True,conflict=True)
    controls=[]
    for name,query,expected in data['cross_queries']:
        result=checked_boundary_packet(memory,query)
        kind='conflict' if len(expected)>1 else 'answer'
        controls.append(dict(name=name,query=query,expected=expected,kind=kind,
                             packet=result,**score(result,kind,expected)))
    return dict(renamed=renamed,fixture=data,stages=stages,cross_controls=controls)


def probe(seed):
    evaluations=[evaluate(seed,renamed) for renamed in (False,True)]
    cases=[c for ev in evaluations for stage in ev['stages'] for c in stage['cases']]
    enriched=[c for ev in evaluations for stage in ev['stages'] if stage['enriched'] for c in stage['cases']]
    cross=[c for ev in evaluations for c in ev['cross_controls']]
    all_counts,enriched_counts,cross_counts=counts(cases),counts(enriched),counts(cross)
    return dict(format='memoria.ia-observed-context-transport-probe-v1',seed=seed,evaluations=evaluations,
        integrity_status='PASS',structural_quality_status='PASS' if all_counts['passed']==all_counts['cases']
            and cross_counts['passed']==cross_counts['cases'] else 'FAIL',
        enriched_structural_quality_status='PASS' if enriched_counts['passed']==enriched_counts['cases']
            and cross_counts['passed']==cross_counts['cases'] else 'FAIL',
        semantic_quality_status='UNQUALIFIED',counts=all_counts,enriched_counts=enriched_counts,
        cross_control_counts=cross_counts,
        stage_counts={stage['name']:counts([c for ev in evaluations for s in ev['stages']
            if s['name']==stage['name'] for c in s['cases']]) for stage in evaluations[0]['stages']},
        previous_structural_quality=dict(passed=98,cases=126,status='FAIL',recomputed=False),
        previous_role_twins_quality=dict(passed=12,cases=24,status='FAIL',recomputed=False),
        engine_changed=False,prior_selectors_changed=False,native_executed=False,
        limitation='Copied opaque context routes observed roots; its meaning and reply intent remain unqualified.')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seed',type=int,default=20261119)
    parser.add_argument('--strict-quality',action='store_true')
    args=parser.parse_args()
    report=probe(args.seed)
    print(json.dumps(report,separators=(',',':')))
    raise SystemExit(args.strict_quality and report['structural_quality_status']!='PASS')
