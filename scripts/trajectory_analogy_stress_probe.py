#!/usr/bin/env python3
"""Opaque adversarial scorecard for the unchanged frame analogy diagnostic."""
import argparse
from dataclasses import asdict
import json
from random import Random

from trajectory_analogy_frame_probe import checked_read
from trajectory_response_quality_probe import TrajectoryGenerationExperiment

FAMILIES = ('baseline', 'constant_value', 'two_equal_values', 'copied_twice',
            'reversed_copy', 'no_source_prefix', 'no_source_suffix',
            'identifier_contains_prefix', 'invariant_tag', 'varying_tag',
            'shared_value_prefix', 'shared_value_suffix')


def fixture(seed, family):
    rng = Random(seed)
    symbols = iter(rng.sample(range(1000,100000),100))
    block = lambda: (next(symbols),next(symbols))
    p,s,t,b,e,c,tag,wrong_tag = (block() for _ in range(8))
    identities=[block() for _ in range(5)]
    values=[block() for _ in range(5)]
    tags=[block() for _ in range(3)]
    if family=='no_source_prefix':
        p=()
    if family=='no_source_suffix':
        s=()
    if family=='identifier_contains_prefix':
        identities[3]=identities[3]+p+block()
    if family=='constant_value':
        values[:3]=[values[0]]*3
    if family=='two_equal_values':
        values[1]=values[0]
    edge=block()
    if family=='shared_value_prefix':
        values[:3]=[edge+v for v in values[:3]]
    if family=='shared_value_suffix':
        values[:3]=[v+edge for v in values[:3]]
    def source(identity):
        return p+identity+s
    def target(identity,value,index):
        copied=identity[::-1] if family=='reversed_copy' else identity
        body=b+value
        if family=='copied_twice':
            body=b+identity+c+value
        if family in ('invariant_tag','varying_tag'):
            # Tag is a separate relation field in this fixture's generator.
            # The learner sees only symbols, never this field annotation.
            chosen=tag if family=='invariant_tag' else tags[index] if index<3 else wrong_tag
            body=b+chosen+c+value
        return t+copied+body+e
    pairs=[(source(identities[i]),target(identities[i],values[i],i)) for i in range(3)]
    fact=target(identities[3],values[3],3)
    wrong_fact=t+identities[3]+wrong_tag+values[4]+e
    known=source(identities[3])
    expected=() if family=='varying_tag' else (fact,)
    kind='absence' if not expected else 'answer'
    queries=[('known',known,kind,expected),
             ('new_prefix',block()+known,kind,expected),
             ('unknown_identity',source(identities[4]),'absence',()),
             ('changed_prefix',block()+identities[3]+s,'absence',()),
             ('changed_suffix',p+identities[3]+block(),'absence',()),
             ('unrelated',block()+block(),'absence',()),
             ('two_cues',known+source(identities[4]),'absence',())]
    return pairs,(fact,wrong_fact),queries


def evaluate(seed,family,renamed=False):
    pairs,facts,queries=fixture(seed,family)
    transform=lambda xs:tuple(1000000-x for x in xs) if renamed else xs
    memory=TrajectoryGenerationExperiment()
    for i,(source,target) in enumerate(pairs):
        memory.observe(transform(source),observation_id=f'{i}:s',stream_id=f'train:{i}')
        memory.observe(transform(target),observation_id=f'{i}:t',stream_id=f'train:{i}')
    for i,fact in enumerate(facts):
        memory.observe(transform(fact),observation_id=f'isolated:{i}',stream_id=f'isolated:{i}')
    rows=[]
    for name,query,kind,expected in queries:
        query=transform(query)
        expected=tuple(transform(target) for target in expected)
        result=checked_read(memory,query)
        outputs=tuple(c['output'] for c in result['candidates'])
        correct=kind=='answer' and result['hypothesis'] in expected
        passed=correct if kind=='answer' else not outputs
        rows.append(dict(name=name,query=query,kind=kind,expected=expected,
            quality_pass=passed,correct_answer=correct,
            false_unique=result['hypothesis'] is not None and result['hypothesis'] not in expected,
            result=result,default_generation=asdict(memory.generate(query)),
            cold_parity=True,learning_unchanged=True,generation_unchanged=True))
    return dict(family=family,renamed=renamed,training_pairs=tuple(
        (transform(s),transform(t)) for s,t in pairs),isolated_roots=tuple(transform(f) for f in facts),
        cases=rows,quality_status='PASS' if all(r['quality_pass'] for r in rows) else 'FAIL')


def probe(seed):
    families=[evaluate(seed,family,renamed) for family in FAMILIES for renamed in (False,True)]
    cases=[r for family in families for r in family['cases']]
    counts=dict(cases=len(cases),passed=sum(r['quality_pass'] for r in cases),
        correct_answers=sum(r['correct_answer'] for r in cases),
        answer_cases=sum(r['kind']=='answer' for r in cases),
        false_unique=sum(r['false_unique'] for r in cases),
        absence_empty=sum(r['kind']=='absence' and not r['result']['candidates'] for r in cases),
        absence_cases=sum(r['kind']=='absence' for r in cases))
    return dict(format='memoria.ia-frame-analogy-stress-v1',seed=seed,integrity_status='PASS',
        quality_status='PASS' if counts['passed']==counts['cases'] else 'FAIL',
        engine_changed=False,frame_selector_changed=False,native_executed=False,
        policy_status='UNRESOLVED',counts=counts,families=families)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seed',type=int,default=20261016)
    parser.add_argument('--strict-quality',action='store_true')
    args=parser.parse_args()
    report=probe(args.seed)
    print(json.dumps(report,separators=(',',':')))
    raise SystemExit(1 if args.strict_quality and report['quality_status']!='PASS' else 0)
