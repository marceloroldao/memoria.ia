#!/usr/bin/env python3
"""Expose repeated-cue coverage and competing specific/broad routes without changing readers."""
import argparse
import json
from random import Random

from trajectory_analogy_alignment_probe import checked
from trajectory_response_quality_probe import TrajectoryGenerationExperiment


def evaluate(seed, fixed_slot, renamed=False, *, reader=checked):
    symbols = iter(Random(seed).sample(range(1000, 100000), 40))
    p, s, sep, t, u, between, end = (next(symbols) for _ in range(7))
    ids, tags, values = ([next(symbols) for _ in range(8)] for _ in range(3))
    transform = lambda xs: tuple(1000000-x for x in xs) if renamed else tuple(xs)
    source = lambda a, b: (p, a, sep, b, s)
    target = lambda head, a, b, value: (head, a, between, b, value, end)
    slots = lambda i: (ids[0], tags[i]) if fixed_slot == 0 else (ids[i], tags[0])
    memory, origins, stages = TrajectoryGenerationExperiment(), {}, []

    def observe(payload, address, stream):
        receipt = memory.observe(transform(payload), observation_id=address, stream_id=stream)
        origins.setdefault(receipt.payload_id, []).append(address)

    def pair(q, a, name):
        observe(q, name+':s', name)
        observe(a, name+':t', name)

    initial = tuple((source(*slots(i)), target(t, *slots(i), values[i])) for i in range(3))
    for i, (q, a) in enumerate(initial):
        pair(q, a, f'specific:{i}')
    a, b = slots(3)
    own, rival = target(t, a, b, values[3]), target(u, a, b, values[4])
    observe(own, 'own', 'own')
    observe(rival, 'rival', 'rival')
    query = source(a, b)
    changed = source(ids[7], b) if fixed_slot == 0 else source(a, tags[7])

    for stage in ('specific_only', 'repeat_specific', 'add_broad_route', 'repeat_specific_after_conflict'):
        if stage == 'repeat_specific':
            pair(*initial[0], 'repeat:before')
        elif stage == 'add_broad_route':
            for i in range(4, 7):
                pair(source(ids[i], tags[i]), target(u, ids[i], tags[i], values[i]), f'broad:{i}')
        elif stage == 'repeat_specific_after_conflict':
            pair(*initial[0], 'repeat:after')
        competing = stage in ('add_broad_route', 'repeat_specific_after_conflict')
        required = (own, rival) if competing else (own,)
        cases = []
        for name, q, kind, expected in (
            ('held_out', query, 'conflict' if competing else 'answer', required),
            ('new_prefix', (ids[7],)+query, 'conflict' if competing else 'answer', required),
            ('changed_fixed_cue', changed, 'absence', ())):
            result = reader(memory, transform(q))
            targets = tuple(transform(x) for x in expected)
            outputs = {c['output'] for c in result['candidates']}
            addressed = {root for c in result['candidates'] for a, z, _ in c['witnesses'] for root in (a, z)}
            addressed.update(c['payload_id'] for c in result['candidates'])
            assert addressed <= set(origins)
            passed = (result['hypothesis'] in targets and outputs == set(targets)) if kind == 'answer' else (
                not outputs and result['hypothesis'] is None if kind == 'absence' else
                outputs == set(targets) and result['hypothesis'] is None)
            cases.append(dict(name=name, query=transform(q), kind=kind, expected=targets,
                quality_pass=passed, false_unique=result['hypothesis'] is not None and (
                    kind != 'answer' or result['hypothesis'] not in targets), result=result))
        stages.append(dict(stage=stage, cases=cases, observation_count=len(memory.snapshot()['observations']),
            unique_root_count=len(origins), root_provenance=tuple(dict(payload_id=root,
                observation_addresses=tuple(addresses)) for root, addresses in sorted(origins.items()))))
    return dict(fixed_slot=fixed_slot, renamed=renamed,
        specific_training_pairs=tuple((transform(q), transform(a)) for q, a in initial), stages=stages)


def probe(seed):
    evaluations = [evaluate(seed, fixed, renamed) for fixed in (0, 1) for renamed in (False, True)]
    cases = [c for e in evaluations for stage in e['stages'] for c in stage['cases']]
    counts = dict(cases=len(cases), passed=sum(c['quality_pass'] for c in cases),
        answer_cases=sum(c['kind']=='answer' for c in cases),
        correct_answers=sum(c['kind']=='answer' and c['quality_pass'] for c in cases),
        conflict_cases=sum(c['kind']=='conflict' for c in cases),
        conflicts_preserved=sum(c['kind']=='conflict' and c['quality_pass'] for c in cases),
        absence_cases=sum(c['kind']=='absence' for c in cases),
        absence_empty=sum(c['kind']=='absence' and c['quality_pass'] for c in cases),
        false_unique=sum(c['false_unique'] for c in cases))
    return dict(format='memoria.ia-repeated-cue-shadow-v1', seed=seed, integrity_status='PASS',
        quality_status='PASS' if counts['passed']==counts['cases'] else 'FAIL',
        engine_changed=False, selectors_changed=False, native_executed=False,
        counts=counts, evaluations=evaluations)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seed', type=int, default=20261103)
    parser.add_argument('--strict-quality', action='store_true')
    args = parser.parse_args()
    report = probe(args.seed)
    print(json.dumps(report, separators=(',', ':')))
    raise SystemExit(1 if args.strict_quality and report['quality_status']!='PASS' else 0)
