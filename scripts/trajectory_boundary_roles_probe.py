#!/usr/bin/env python3
"""Identical observations under different evaluator roles, including complete cut agreement."""
import argparse
from hashlib import sha256
import json
from trajectory_boundary_support_probe import fixture,summarize
from trajectory_boundary_candidates_probe import checked_boundary_packet
from trajectory_response_quality_probe import TrajectoryGenerationExperiment


def fingerprint(value):
    return sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def evaluate(seed,renamed=False):
    pairs,query,targets,rival=fixture(seed,joined=True,renamed=renamed)
    fact=targets[0]
    # Independent engines receive identical events; roles never enter observation or reader APIs.
    memories=[TrajectoryGenerationExperiment(),TrajectoryGenerationExperiment()]
    contracts=(dict(role='INTENDED_REPLY',expected_answer=fact),
               dict(role='ADJACENT_UNRELATED_EVENT',expected_answer=None))
    def observe(payload,observation_id,stream_id):
        for memory in memories:
            memory.observe(payload,observation_id=observation_id,stream_id=stream_id)
    for i,(source,target) in enumerate(pairs):
        observe(source,f'demo:{i}:source',f'demo:{i}')
        observe(target,f'demo:{i}:target',f'demo:{i}')
    observe(fact,'fact','fact')
    stages=[]
    def capture(name,expected_continuation_roots,expected_occurrences,conflict=False):
        packets=[checked_boundary_packet(memory,query) for memory in memories]
        snapshots=[memory.snapshot() for memory in memories]
        supports=[summarize(packet) for packet in packets]
        same=snapshots[0]==snapshots[1] and packets[0]==packets[1] and supports[0]==supports[1]
        packet,support=packets[0],supports[0]
        boundary_roots={root for f in support['frames'] for root in f['candidate_roots']}
        outputs={memories[0].expand(root) for root in boundary_roots}
        direct=packet['observed_continuations']
        occurrences=sum(len(c['witnesses']) for c in direct)
        unanimous=bool(support['frames']) and all(f['unanimous_single_root'] for f in support['frames'])
        # Deliberately unsafe evaluator-only comparator. Never feeds back to the packet or memory.
        proposed=next(iter(outputs)) if unanimous and len(outputs)==1 else None
        outcomes=[]
        for contract in contracts:
            expected=contract['expected_answer']
            outcomes.append(dict(evaluator_contract=contract,answer=packet['answer'],
                quality_pass=packet['answer']==expected,forced_consensus_proposal=proposed,
                forced_consensus_pass=proposed==expected,
                forced_consensus_false_answer=proposed is not None and proposed!=expected))
        passed=same and bool(support['frames']) and all(f['coverage']=='COMPLETE' for f in support['frames'])
        passed=passed and all(f['total_cuts']==3 for f in support['frames'])
        passed=passed and outputs==({fact,rival} if conflict else {fact}) and unanimous==(not conflict)
        passed=passed and len(direct)==expected_continuation_roots and occurrences==expected_occurrences
        passed=passed and packet['answer'] is None and not packet['qualified']
        stages.append(dict(name=name,diagnostic_pass=passed,
            observations_identical=snapshots[0]==snapshots[1],packets_identical=packets[0]==packets[1],
            twin_snapshot_fingerprints=tuple(map(fingerprint,snapshots)),
            twin_packet_fingerprints=tuple(map(fingerprint,packets)),
            expected_continuation_roots=expected_continuation_roots,
            expected_continuation_occurrences=expected_occurrences,continuation_occurrences=occurrences,
            support_frame_count=len(support['frames']),unique_boundary_roots=len(boundary_roots),
            support=support,packet=packet,provenance=snapshots[0]['observations'],outcomes=outcomes))
    capture('complete_cut_agreement',0,0)
    observe(fact,'repeat:1','repeat:1'); observe(fact,'repeat:2','repeat:2')
    capture('repeated_root',0,0)
    observe(query,'query-only','query-only')
    capture('query_without_continuation',0,0)
    observe(query,'direct:source','direct'); observe(fact,'direct:target','direct')
    capture('exact_continuation',1,1)
    observe(query,'direct-repeat:source','direct-repeat'); observe(fact,'direct-repeat:target','direct-repeat')
    capture('repeated_exact_continuation',1,2)
    observe(query,'rival:source','rival'); observe(rival,'rival:target','rival')
    capture('competing_exact_continuation',2,3,conflict=True)
    return dict(renamed=renamed,query=query,contracts=contracts,stages=stages)


def probe(seed):
    evaluations=[evaluate(seed,renamed) for renamed in (False,True)]
    stages=[s for ev in evaluations for s in ev['stages']]
    outcomes=[o for stage in stages for o in stage['outcomes']]
    positives=[o for o in outcomes if o['evaluator_contract']['expected_answer'] is not None]
    negatives=[o for o in outcomes if o['evaluator_contract']['expected_answer'] is None]
    actual=dict(cases=len(outcomes),passed=sum(o['quality_pass'] for o in outcomes),
        positive_cases=len(positives),correct_answers=sum(o['quality_pass'] for o in positives),
        negative_cases=len(negatives),correct_abstentions=sum(o['quality_pass'] for o in negatives),
        false_answers=sum(o['answer'] is not None and not o['quality_pass'] for o in outcomes))
    comparator=dict(cases=len(outcomes),passed=sum(o['forced_consensus_pass'] for o in outcomes),
        correct_answers=sum(o['forced_consensus_pass'] for o in positives),
        correct_abstentions=sum(o['forced_consensus_pass'] for o in negatives),
        false_answers=sum(o['forced_consensus_false_answer'] for o in outcomes))
    return dict(format='memoria.ia-boundary-role-twins-probe-v1',seed=seed,evaluations=evaluations,
        diagnostic_cases=len(stages),diagnostic_passed=sum(s['diagnostic_pass'] for s in stages),
        integrity_status='PASS' if all(s['diagnostic_pass'] for s in stages) else 'FAIL',
        semantic_quality_status='PASS' if actual['passed']==actual['cases'] else 'FAIL',
        actual_reader_counts=actual,unsafe_evaluator_comparator_counts=comparator,
        previous_structural_quality=dict(passed=98,cases=126,status='FAIL',recomputed=False),
        engine_changed=False,prior_selectors_changed=False,native_executed=False,
        limitation='Identical encoded observations cannot expose evaluator-only reply intent; complete cut agreement and exact sequence do not supply that missing observation.')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seed',type=int,default=20261117)
    parser.add_argument('--strict-quality',action='store_true')
    args=parser.parse_args()
    result=probe(args.seed)
    print(json.dumps(result,separators=(',',':')))
    raise SystemExit(result['integrity_status']!='PASS' or
                     (args.strict_quality and result['semantic_quality_status']!='PASS'))
