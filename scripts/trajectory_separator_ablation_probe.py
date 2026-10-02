#!/usr/bin/env python3
"""Ablate only the source delimiter; preserve all observed destination roots."""
import argparse
import json
from random import Random

from trajectory_evidence_packet_probe import checked_packet
from trajectory_response_quality_probe import TrajectoryGenerationExperiment


def fixture(seed, mode, renamed=False):
    if mode not in ('explicit','absent','ambiguous'):
        raise ValueError('unknown separator mode')
    symbols=iter(Random(seed).sample(range(1000,100000),100))
    block=lambda n:tuple(next(symbols) for _ in range(n))
    p,s,separator,internal,t,b,bridge,e=(block(1) for _ in range(8))
    identities=[block(3) for _ in range(6)]
    identities[3]=identities[3][:1]+internal+identities[3][2:]
    relations=[block(2) for _ in range(6)]
    values=[block(2) for _ in range(6)]
    delimiter=separator if mode=='explicit' else internal if mode=='ambiguous' else ()
    transform=lambda xs:tuple(1000000-x for x in xs) if renamed else tuple(xs)
    source=lambda i,r:transform(p+identities[i]+delimiter+relations[r]+s)
    target=lambda i,r,v:transform(t+identities[i]+b+relations[r]+bridge+values[v]+e)
    pairs=tuple((source(i,i),target(i,i,i)) for i in range(3)) + (
        (source(0,1),target(0,1,3)),(source(0,1),target(0,1,4)),(source(1,0),target(1,0,5)))
    facts=(target(3,3,3),target(3,4,4))
    rival=target(3,3,5)
    queries=(('first',source(3,3)),('new_prefix',transform((999999,))+source(3,3)),
        ('second',source(3,4)),('unknown_relation',source(3,5)),
        ('unknown_identity',source(4,3)),('missing_relation',transform(p+identities[3]+s)),
        ('joined_queries',source(3,3)+source(3,4)))
    return pairs,facts,rival,queries


def score(result,kind,expected):
    outputs={c['output'] for c in result['candidates']}
    hypothesis=result['prior_structural_hypothesis']
    passed=(outputs==set(expected) and hypothesis==expected[0]) if kind=='answer' else (
        outputs==set(expected) and hypothesis is None) if kind=='conflict' else not outputs and hypothesis is None
    return dict(quality_pass=passed,targets_retained=all(x in outputs for x in expected) if expected else None,
        false_unique=hypothesis is not None and (hypothesis not in expected or kind=='conflict'))


def evaluate(seed,mode,renamed=False,*,reader=checked_packet):
    pairs,facts,rival,queries=fixture(seed,mode,renamed)
    memory=TrajectoryGenerationExperiment()
    def pair(q,a,address):
        memory.observe(q,observation_id=address+':q',stream_id=address)
        memory.observe(a,observation_id=address+':a',stream_id=address)
    for i,(q,a) in enumerate(pairs):
        pair(q,a,f'train:{i}')
    for i,fact in enumerate(facts):
        memory.observe(fact,observation_id=f'fact:{i}',stream_id=f'fact:{i}')
    stages=[]
    def capture(name,conflict=False):
        cases=[]
        for query_name,query in queries:
            expected=(facts[0],rival) if conflict and query_name in ('first','new_prefix') else (
                (facts[0],) if query_name in ('first','new_prefix') else (facts[1],) if query_name=='second' else ())
            kind='conflict' if len(expected)>1 else 'answer' if expected else 'absence'
            result=reader(memory,query)
            assert not result['observed_continuations']
            cases.append(dict(name=query_name,query=query,kind=kind,expected=expected,
                packet=result,**score(result,kind,expected)))
        stages.append(dict(stage=name,cases=cases,provenance=memory.snapshot()['observations'],
            unique_payloads=len({r['payload_id'] for r in memory.snapshot()['observations']})))
    capture('crossed_support')
    for i in range(2):
        pair(*pairs[3],f'repeat:{i}')
    capture('repeated_pair')
    memory.observe(rival,observation_id='rival',stream_id='rival')
    capture('competing_value',conflict=True)
    return dict(mode=mode,renamed=renamed,training_pairs=pairs,isolated_facts=facts,
                rival=rival,stages=stages)


def counts(cases):
    return dict(cases=len(cases),passed=sum(c['quality_pass'] for c in cases),
        answer_cases=sum(c['kind']=='answer' for c in cases),
        correct_answers=sum(c['kind']=='answer' and c['quality_pass'] for c in cases),
        conflict_cases=sum(c['kind']=='conflict' for c in cases),
        conflicts_preserved=sum(c['kind']=='conflict' and c['quality_pass'] for c in cases),
        absence_cases=sum(c['kind']=='absence' for c in cases),
        absence_empty=sum(c['kind']=='absence' and c['quality_pass'] for c in cases),
        target_cases=sum(c['kind']!='absence' for c in cases),
        all_targets_retained=sum(c['kind']!='absence' and c['targets_retained'] for c in cases),
        false_unique=sum(c['false_unique'] for c in cases))


def probe(seed):
    evaluations=[evaluate(seed,mode,renamed) for mode in ('explicit','absent','ambiguous') for renamed in (False,True)]
    for renamed in (False,True):
        matches=[ev for ev in evaluations if ev['renamed']==renamed]
        assert len({repr((tuple(a for _,a in ev['training_pairs']),ev['isolated_facts'],ev['rival']))
                    for ev in matches})==1
    by_mode={mode:counts([c for ev in evaluations if ev['mode']==mode for stage in ev['stages'] for c in stage['cases']])
             for mode in ('explicit','absent','ambiguous')}
    complete=counts([c for ev in evaluations for stage in ev['stages'] for c in stage['cases']])
    return dict(format='memoria.ia-source-separator-ablation-v1',seed=seed,integrity_status='PASS',
        structural_quality_status='PASS' if complete['passed']==complete['cases'] else 'FAIL',
        semantic_quality_status='UNQUALIFIED',counts=complete,by_mode=by_mode,evaluations=evaluations,
        engine_changed=False,prior_selectors_changed=False,native_executed=False,
        limitation='Fixed destinations do not determine source field boundaries; only source separators are changed.')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seed',type=int,default=20261111)
    parser.add_argument('--strict-quality',action='store_true')
    args=parser.parse_args()
    report=probe(args.seed)
    print(json.dumps(report,separators=(',',':')))
    raise SystemExit(1 if args.strict_quality and report['structural_quality_status']!='PASS' else 0)
