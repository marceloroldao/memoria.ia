#!/usr/bin/env python3
"""Sequential evidence interventions for the unchanged internal-anchor shadow."""
import argparse
import json
from random import Random

from trajectory_analogy_anchor_probe import checked_shadow
from trajectory_response_quality_probe import TrajectoryGenerationExperiment


def evaluate(seed, renamed=False):
    rng = Random(seed)
    symbols = iter(rng.sample(range(1000, 100000), 120))
    block = lambda: (next(symbols), next(symbols))
    p, s, t, b, c, e = (block() for _ in range(6))
    tags = [block() for _ in range(5)]
    identities = [block() for _ in range(11)]
    values = [block() for _ in range(11)]
    source = lambda i: p + identities[i] + s
    target = lambda i, tag: t + identities[i] + b + tag + c + values[i] + e
    transform = lambda xs: tuple(1000000-x for x in xs) if renamed else tuple(xs)
    memory = TrajectoryGenerationExperiment()
    origins = {}
    def observe(payload, address, stream):
        receipt = memory.observe(transform(payload), observation_id=address, stream_id=stream)
        origins.setdefault(receipt.payload_id, []).append(address)
    def pair(i, tag, stream):
        observe(source(i), stream+':s', stream)
        observe(target(i, tag), stream+':t', stream)
    for i in range(3):
        pair(i, tags[i], f'mixed:{i}')
    facts = target(9, tags[3]), target(9, tags[4])
    for i, fact in enumerate(facts):
        observe(fact, f'isolated:{i}', f'isolated:{i}')
    known = source(9)
    extra_prefix = block()
    stages = []
    def capture(name, expected):
        kind = 'conflict' if len(expected) == 2 else 'answer' if expected else 'absence'
        queries = [('known', known, kind, expected),
                   ('new_prefix', extra_prefix+known, kind, expected),
                   ('unknown', source(10), 'absence', ()),
                   ('two_cues', known+source(10), 'absence', ())]
        cases = []
        frame_catalogue, blocked_frames = None, None
        for label, query, required, outputs in queries:
            result = checked_shadow(memory, transform(query))
            frames = result['baseline'].pop('frames')
            blocked = result.pop('blocked_frames')
            if frame_catalogue is None:
                frame_catalogue, blocked_frames = frames, blocked
            assert frames == frame_catalogue and blocked == blocked_frames
            targets = tuple(transform(x) for x in outputs)
            selected = tuple(candidate['output'] for candidate in result['candidates'])
            passed = result['hypothesis'] in targets if required == 'answer' else (
                set(selected) == set(targets) and result['hypothesis'] is None
                if required == 'conflict' else not selected)
            witness_ids = {x for candidate in result['candidates']
                           for a, z, _ in candidate['witnesses'] for x in (a, z)}
            witness_ids.update(candidate['payload_id'] for candidate in result['candidates'])
            assert witness_ids <= set(origins)
            cases.append(dict(name=label, kind=required, expected=targets,
                quality_pass=passed, false_unique=result['hypothesis'] is not None
                and result['hypothesis'] not in targets, result=result))
        stages.append(dict(stage=name, observations=len(memory.snapshot()['observations']),
            distinct_roots=len(origins), cases=cases,
            frame_catalogue=frame_catalogue, blocked_frames=blocked_frames,
            root_provenance=tuple(dict(payload_id=root, observation_addresses=tuple(addresses))
                                  for root, addresses in sorted(origins.items()))))
    capture('mixed_only', ())
    pair(3, tags[3], 'support-a:0')
    pair(4, tags[3], 'support-a:1')
    capture('two_distinct_supports', ())
    for repetition in range(3):
        pair(3, tags[3], f'repeated:{repetition}')
    capture('repeated_payloads', ())
    pair(5, tags[3], 'support-a:2')
    capture('three_distinct_supports', (facts[0],))
    for i in range(6, 9):
        pair(i, tags[4], f'support-b:{i}')
    capture('both_relations_supported', facts)
    return dict(renamed=renamed, stages=stages)


def probe(seed):
    evaluations = [evaluate(seed, renamed) for renamed in (False, True)]
    cases = [c for evaluation in evaluations for stage in evaluation['stages'] for c in stage['cases']]
    counts = dict(cases=len(cases), passed=sum(c['quality_pass'] for c in cases),
        false_unique=sum(c['false_unique'] for c in cases),
        correct_answers=sum(c['kind'] == 'answer' and c['quality_pass'] for c in cases),
        conflicts_preserved=sum(c['kind'] == 'conflict' and c['quality_pass'] for c in cases),
        absence_empty=sum(c['kind'] == 'absence' and c['quality_pass'] for c in cases))
    return dict(format='memoria.ia-frame-evidence-intervention-v1', seed=seed,
        integrity_status='PASS', quality_status='PASS' if counts['passed'] == len(cases) else 'FAIL',
        engine_changed=False, shadow_selector_changed=False, native_executed=False,
        policy_status='EXPERIMENTAL_INTERVENTION', counts=counts, evaluations=evaluations)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seed', type=int, default=20261020)
    parser.add_argument('--strict-quality', action='store_true')
    args = parser.parse_args()
    report = probe(args.seed)
    print(json.dumps(report, separators=(',', ':')))
    raise SystemExit(1 if args.strict_quality and report['quality_status'] != 'PASS' else 0)
