#!/usr/bin/env python3
"""Sequential copied-cue interventions; field names exist only in the evaluator."""
import argparse
import json
from random import Random

from trajectory_evidence_packet_probe import checked_packet
from trajectory_response_quality_probe import TrajectoryGenerationExperiment


def evaluate(seed, renamed=False):
    symbols = iter(Random(seed).sample(range(1000, 100000), 40))
    p,s,sep,t,b,bridge,e = (next(symbols) for _ in range(7))
    identities,relations,values = ([next(symbols) for _ in range(6)] for _ in range(3))
    transform = lambda xs: tuple(1000000-x for x in xs) if renamed else tuple(xs)
    source = lambda i,r: transform((p,identities[i],sep,relations[r],s))
    hidden = lambda i: transform((p,identities[i],s))
    target = lambda i,r,v: transform((t,identities[i],b,relations[r],bridge,values[v],e))
    memory = TrajectoryGenerationExperiment()
    stages = []
    def pair(query,answer,address):
        memory.observe(query,observation_id=address+':q',stream_id=address)
        memory.observe(answer,observation_id=address+':a',stream_id=address)
    facts = (target(3,3,3),target(3,4,4))
    for i,fact in enumerate(facts):
        memory.observe(fact,observation_id=f'fact:{i}',stream_id=f'fact:{i}')
    def capture(stage, *, enriched=False, conflict=False):
        descriptors = [('first',source(3,3), (facts[0],)+( (target(3,3,5),) if conflict else ())),
            ('second',source(3,4),(facts[1],)),
            ('missing_relation',hidden(3),()),
            ('unknown_relation',source(3,5),()),
            ('unknown_identity',source(4,3),())]
        cases = []
        for name,query,expected in descriptors:
            result = checked_packet(memory,query)
            outputs = {c['output'] for c in result['candidates']}
            hypothesis = result['prior_structural_hypothesis']
            kind = 'conflict' if len(expected)>1 else 'answer' if expected else 'absence'
            passed = (hypothesis==expected[0] and outputs==set(expected)) if kind=='answer' else (
                outputs==set(expected) and hypothesis is None) if kind=='conflict' else not outputs and hypothesis is None
            cases.append(dict(name=name,kind=kind,expected=expected,query=query,packet=result,
                quality_pass=passed,false_unique=hypothesis is not None and hypothesis not in expected))
        stages.append(dict(stage=stage,enriched=enriched,cases=cases,
            provenance=memory.snapshot()['observations'],
            unique_payloads=len({r['payload_id'] for r in memory.snapshot()['observations']})))
    for i in range(3):
        pair(hidden(i),target(i,i,i),f'hidden:{i}')
    capture('hidden_relation')
    for i in range(3):
        pair(hidden(i),target(i,i,i),f'hidden-repeat:{i}')
    capture('repeated_hidden_relation')
    for i in range(3):
        pair(source(i,i),target(i,i,i),f'cue:{i}')
    capture('copied_relation_cue',enriched=True)
    # Change the second cue while retaining identity; then change value alone.
    pair(source(0,1),target(0,1,3),'cross:relation')
    pair(source(0,1),target(0,1,4),'cross:value')
    pair(source(1,0),target(1,0,5),'cross:identity')
    capture('crossed_relation_value',enriched=True)
    for i in range(2):
        pair(source(0,1),target(0,1,3),f'cross-repeat:{i}')
    capture('repeated_crossed_pair',enriched=True)
    memory.observe(target(3,3,5),observation_id='rival',stream_id='rival')
    capture('same_cues_competing_value',enriched=True,conflict=True)
    cross_controls=[]
    for name,query,expected in (
        ('relation_changed_values_compete',source(0,1),(target(0,1,3),target(0,1,4))),
        ('original_relation_retained',source(0,0),(target(0,0,0),)),
        ('identity_changed',source(1,0),(target(1,0,5),))):
        result=checked_packet(memory,query)
        outputs={c['output'] for c in result['candidates']}
        hypothesis=result['prior_structural_hypothesis']
        passed=outputs==set(expected) and (hypothesis==expected[0] if len(expected)==1 else hypothesis is None)
        cross_controls.append(dict(name=name,query=query,expected=expected,packet=result,quality_pass=passed))
    return dict(renamed=renamed,stages=stages,cross_controls=cross_controls)


def probe(seed):
    evaluations = [evaluate(seed,renamed) for renamed in (False,True)]
    cases = [c for ev in evaluations for stage in ev['stages'] if stage['enriched'] for c in stage['cases']]
    counts = dict(cases=len(cases),passed=sum(c['quality_pass'] for c in cases),
        answer_cases=sum(c['kind']=='answer' for c in cases),
        correct_answers=sum(c['kind']=='answer' and c['quality_pass'] for c in cases),
        conflict_cases=sum(c['kind']=='conflict' for c in cases),
        conflicts_preserved=sum(c['kind']=='conflict' and c['quality_pass'] for c in cases),
        absence_cases=sum(c['kind']=='absence' for c in cases),
        absence_empty=sum(c['kind']=='absence' and c['quality_pass'] for c in cases),
        false_unique=sum(c['false_unique'] for c in cases))
    stages={name: [c for ev in evaluations for s in ev['stages'] if s['stage']==name for c in s['cases']]
            for name in (s['stage'] for s in evaluations[0]['stages'])}
    cross=[c for ev in evaluations for c in ev['cross_controls']]
    all_cases=[c for rows in stages.values() for c in rows]
    return dict(format='memoria.ia-copied-relation-contrast-v1',seed=seed,
        integrity_status='PASS',enriched_quality_status='PASS' if counts['passed']==counts['cases']
            and all(c['quality_pass'] for c in cross) else 'FAIL',
        structural_quality_status='PASS' if all(c['quality_pass'] for c in all_cases+cross) else 'FAIL',
        all_stage_counts=dict(cases=len(all_cases),passed=sum(c['quality_pass'] for c in all_cases)),
        semantic_quality_status='UNQUALIFIED',counts=counts,evaluations=evaluations,
        stage_counts={name:dict(cases=len(rows),passed=sum(c['quality_pass'] for c in rows))
                      for name,rows in stages.items()},
        cross_control_counts=dict(cases=len(cross),passed=sum(c['quality_pass'] for c in cross)),
        engine_changed=False,native_executed=False,
        limitation='Observed copied cues discriminate these roots; no semantic role labels enter the learner.')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seed',type=int,default=20261109)
    parser.add_argument('--strict-quality',action='store_true')
    args=parser.parse_args()
    report=probe(args.seed)
    print(json.dumps(report,separators=(',',':')))
    raise SystemExit(1 if args.strict_quality and report['structural_quality_status']!='PASS' else 0)
