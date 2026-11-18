#!/usr/bin/env python3
"""Read-only support coverage across competing source cuts; never answer authority."""
import argparse
import json
import random
from trajectory_boundary_candidates_probe import checked_boundary_packet
from trajectory_response_quality_probe import TrajectoryGenerationExperiment


def summarize(packet):
    groups={}
    for cut in packet['boundary_support']:
        groups.setdefault(cut['frame_id'],[]).append(cut)
    summaries=[]
    for frame_id,cuts in sorted(groups.items()):
        supports=[set(c['candidate_roots']) for c in cuts]
        union=set().union(*supports)
        common=set.intersection(*supports)
        covered=sum(bool(s) for s in supports)
        unanimous=len(common)==1 and all(s==common for s in supports)
        summaries.append(dict(frame_id=frame_id,total_cuts=len(cuts),covered_cuts=covered,
            coverage='EMPTY' if covered==0 else 'COMPLETE' if covered==len(cuts) else 'PARTIAL',
            root_relation='EMPTY' if not union else 'SINGLE_ROOT' if len(union)==1 else 'MULTIPLE_ROOTS',
            candidate_roots=tuple(sorted(union)),common_roots=tuple(sorted(common)),
            unanimous_single_root=unanimous))
    return dict(frames=tuple(summaries),answer=None,qualified=False,
                authorization_status='OBSERVATIONAL_SUPPORT_ONLY')


def fixture(seed,joined=False,renamed=False):
    symbols=random.Random(seed).sample(range(100,10000),23)
    left,right,head,between,end=symbols[:5]
    query_body=tuple(symbols[5:9])
    pairs=[]
    for i in range(3):
        body=tuple(symbols[9+4*i:13+4*i])
        target=(head,)+body[:2]+(() if joined else (between,))+body[2:]+(10001+i,end)
        pairs.append(((left,)+body+(right,),target))
    targets=tuple((head,)+query_body[:cut]+(() if joined else (between,))+query_body[cut:]+(symbols[22],end)
                  for cut in range(1,len(query_body)))
    rival=targets[0][:-2]+(10010,end)
    query=(left,)+query_body+(right,)
    if renamed:
        rename=lambda xs: tuple(1000000-x for x in xs)
        pairs=[(rename(a),rename(b)) for a,b in pairs]
        query,targets,rival=rename(query),tuple(map(rename,targets)),rename(rival)
    return pairs,query,targets,rival


def evaluate(seed,joined,renamed):
    pairs,query,targets,rival=fixture(seed,joined,renamed)
    memory=TrajectoryGenerationExperiment()
    for i,(source,target) in enumerate(pairs):
        memory.observe(source,observation_id=f'demo:{i}:source',stream_id=f'demo:{i}')
        memory.observe(target,observation_id=f'demo:{i}:target',stream_id=f'demo:{i}')
    stages=[]
    def capture(name,coverage,relation,expected_outputs):
        packet=checked_boundary_packet(memory,query)
        support=summarize(packet)
        outputs={memory.expand(root) for frame in support['frames'] for root in frame['candidate_roots']}
        passed=bool(support['frames']) and outputs==set(expected_outputs) and all(
            f['coverage']==coverage and f['root_relation']==relation for f in support['frames'])
        passed=passed and all(f['total_cuts']==3 for f in support['frames'])
        passed=passed and packet['answer'] is None and not packet['qualified']
        rows=memory.snapshot()['observations']
        roots={root for f in support['frames'] for root in f['candidate_roots']}
        stages.append(dict(name=name,expected_coverage=coverage,expected_root_relation=relation,
            expected_outputs=tuple(sorted(set(expected_outputs))),diagnostic_pass=passed,
            support=support,packet=packet,provenance=rows,
            candidate_occurrences=tuple(row for row in rows if row['payload_id'] in roots)))
    def observe(target,name):
        memory.observe(target,observation_id=name,stream_id=name)
    capture('empty','EMPTY','EMPTY',())
    observe(targets[0],'first')
    capture('first_root','COMPLETE' if joined else 'PARTIAL','SINGLE_ROOT',(targets[0],))
    observe(targets[0],'repeat:1'); observe(targets[0],'repeat:2')
    capture('repeated_root','COMPLETE' if joined else 'PARTIAL','SINGLE_ROOT',(targets[0],))
    observe(rival,'rival')
    capture('rival_same_cut','COMPLETE' if joined else 'PARTIAL','MULTIPLE_ROOTS',(targets[0],rival))
    if not joined:
        observe(targets[1],'second_cut')
        capture('second_cut','PARTIAL','MULTIPLE_ROOTS',(targets[0],targets[1],rival))
        observe(targets[2],'third_cut')
        capture('all_cuts','COMPLETE','MULTIPLE_ROOTS',(*targets,rival))
    return dict(joined_target_copies=joined,renamed=renamed,query=query,stages=stages)


def probe(seed):
    evaluations=[evaluate(seed,joined,renamed) for joined in (False,True) for renamed in (False,True)]
    cases=[stage for ev in evaluations for stage in ev['stages']]
    return dict(format='memoria.ia-boundary-support-probe-v1',seed=seed,evaluations=evaluations,
        diagnostic_cases=len(cases),diagnostic_passed=sum(c['diagnostic_pass'] for c in cases),
        integrity_status='PASS' if all(c['diagnostic_pass'] for c in cases) else 'FAIL',
        semantic_quality_status='UNQUALIFIED',engine_changed=False,prior_selectors_changed=False,
        previous_structural_quality=dict(passed=98,cases=126,status='FAIL',recomputed=False))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seed',type=int,default=20261115)
    args=parser.parse_args()
    result=probe(args.seed)
    print(json.dumps(result,separators=(',',':')))
    raise SystemExit(result['integrity_status']!='PASS')
