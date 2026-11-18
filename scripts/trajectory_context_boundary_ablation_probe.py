#!/usr/bin/env python3
"""Ablate only the observed context/body boundary while preserving destination roots."""
import argparse
import json
from random import Random

from trajectory_boundary_candidates_probe import checked_boundary_packet
from trajectory_separator_ablation_probe import score, counts
from trajectory_response_quality_probe import TrajectoryGenerationExperiment


MODES = ('explicit', 'absent', 'ambiguous')


def fixture(seed, mode, renamed=False):
    if mode not in MODES:
        raise ValueError('unknown context/body boundary mode')
    symbols = iter(Random(seed).sample(range(1000, 100000), 120))
    block = lambda n: tuple(next(symbols) for _ in range(n))
    p, s, separator, internal, t, b, bridge, end = (block(1) for _ in range(8))
    contexts = [block(2) for _ in range(7)]
    bodies = [block(4) for _ in range(5)]
    # Keep the bodies identical across modes, but make the ambiguous separator
    # occur inside one reserved body so its token value cannot identify a cut.
    bodies[3] = bodies[3][:2] + internal + bodies[3][3:]
    values = [block(2) for _ in range(7)]
    delimiter = separator if mode == 'explicit' else internal if mode == 'ambiguous' else ()
    transform = lambda xs: tuple(1000000 - x for x in xs) if renamed else tuple(xs)

    source = lambda i, c: transform(p + contexts[c] + delimiter + bodies[i] + s)
    missing_context = lambda i: transform(p + bodies[i] + s)
    target = lambda i, c, v: transform(t + contexts[c] + b + bodies[i] + bridge + values[v] + end)

    training_pairs = tuple((source(i, i), target(i, i, i)) for i in range(3))
    crossed_pairs = (
        (source(1, 0), target(1, 0, 3)),
        (source(1, 0), target(1, 0, 4)),
        (source(0, 1), target(0, 1, 5)),
    )
    facts = (target(3, 3, 3), target(3, 4, 4), target(3, 6, 3))
    rival = target(3, 3, 6)
    queries = (
        ('first', source(3, 3)),
        ('swapped_context', source(3, 4)),
        ('other_observed_context', source(3, 6)),
        ('unknown_context', source(3, 5)),
        ('unknown_body', source(4, 3)),
        ('missing_context', missing_context(3)),
        ('joined_context_queries', source(3, 3) + source(3, 4)),
    )
    cross_queries = (
        ('context_changed', source(1, 0), (target(1, 0, 3), target(1, 0, 4))),
        ('body_changed', source(0, 1), (target(0, 1, 5),)),
        ('original_retained', source(0, 0), (target(0, 0, 0),)),
    )
    return dict(
        mode=mode,
        delimiter=transform(delimiter),
        explicit_separator=transform(separator),
        ambiguous_token=transform(internal),
        contexts=tuple(transform(x) for x in contexts),
        bodies=tuple(transform(x) for x in bodies),
        training_pairs=training_pairs,
        crossed_pairs=crossed_pairs,
        facts=facts,
        rival=rival,
        queries=queries,
        cross_queries=cross_queries,
    )


def evaluate(seed, mode, renamed=False):
    data = fixture(seed, mode, renamed)
    memory = TrajectoryGenerationExperiment()

    def pair(source, target, address):
        memory.observe(source, observation_id=address + ':source', stream_id=address)
        memory.observe(target, observation_id=address + ':target', stream_id=address)

    for i, (source, target) in enumerate(data['training_pairs']):
        pair(source, target, f'train:{i}')
    for i, fact in enumerate(data['facts']):
        memory.observe(fact, observation_id=f'fact:{i}', stream_id=f'fact:{i}')

    stages = []

    def capture(name, conflict=False):
        cases = []
        for query_name, query in data['queries']:
            expected = (
                (data['facts'][0], data['rival'])
                if query_name == 'first' and conflict
                else (data['facts'][0],)
                if query_name == 'first'
                else (data['facts'][1],)
                if query_name == 'swapped_context'
                else (data['facts'][2],)
                if query_name == 'other_observed_context'
                else ()
            )
            kind = 'conflict' if len(expected) > 1 else 'answer' if expected else 'absence'
            result = checked_boundary_packet(memory, query)
            assert not result['observed_continuations']
            cases.append(
                dict(
                    name=query_name,
                    query=query,
                    kind=kind,
                    expected=expected,
                    packet=result,
                    **score(result, kind, expected),
                )
            )
        rows = memory.snapshot()['observations']
        stages.append(
            dict(
                name=name,
                cases=cases,
                provenance=rows,
                unique_payloads=len({row['payload_id'] for row in rows}),
            )
        )

    capture('observed_context_body_routes')
    for i, (source, target) in enumerate(data['crossed_pairs']):
        pair(source, target, f'cross:{i}')
    capture('crossed_context_body_value')
    for i in range(2):
        pair(*data['crossed_pairs'][0], f'repeat:{i}')
    capture('repeated_crossed_pair')
    memory.observe(data['rival'], observation_id='rival', stream_id='rival')
    capture('same_context_competing_value', conflict=True)

    controls = []
    for name, query, expected in data['cross_queries']:
        result = checked_boundary_packet(memory, query)
        kind = 'conflict' if len(expected) > 1 else 'answer'
        controls.append(
            dict(
                name=name,
                query=query,
                expected=expected,
                kind=kind,
                packet=result,
                **score(result, kind, expected),
            )
        )
    return dict(mode=mode, renamed=renamed, fixture=data, stages=stages, cross_controls=controls)


def probe(seed):
    evaluations = [evaluate(seed, mode, renamed) for mode in MODES for renamed in (False, True)]

    # The intervention is source-side only: all destination roots must remain byte-identical.
    for renamed in (False, True):
        variants = [ev['fixture'] for ev in evaluations if ev['renamed'] == renamed]
        destination_views = [
            (
                tuple(target for _, target in f['training_pairs']),
                tuple(target for _, target in f['crossed_pairs']),
                f['facts'],
                f['rival'],
            )
            for f in variants
        ]
        assert len({repr(view) for view in destination_views}) == 1
        assert len({repr(f['contexts']) for f in variants}) == 1
        assert len({repr(f['bodies']) for f in variants}) == 1

    by_mode = {}
    cross_by_mode = {}
    for mode in MODES:
        cases = [
            case
            for ev in evaluations
            if ev['mode'] == mode
            for stage in ev['stages']
            for case in stage['cases']
        ]
        cross = [case for ev in evaluations if ev['mode'] == mode for case in ev['cross_controls']]
        by_mode[mode] = counts(cases)
        cross_by_mode[mode] = counts(cross)

    complete = counts(
        [case for ev in evaluations for stage in ev['stages'] for case in stage['cases']]
    )
    return dict(
        format='memoria.ia-context-body-boundary-ablation-v1',
        seed=seed,
        integrity_status='PASS',
        structural_quality_status='PASS' if complete['passed'] == complete['cases'] else 'FAIL',
        semantic_quality_status='UNQUALIFIED',
        counts=complete,
        by_mode=by_mode,
        cross_control_by_mode=cross_by_mode,
        evaluations=evaluations,
        engine_changed=False,
        prior_selectors_changed=False,
        native_executed=False,
        limitation=(
            'Only the source context/body delimiter changes. Destination roots, contexts, bodies, '
            'values and evaluator contracts are fixed; structural routing remains unqualified.'
        ),
    )


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seed', type=int, default=20261121)
    parser.add_argument('--strict-quality', action='store_true')
    args = parser.parse_args()
    report = probe(args.seed)
    print(json.dumps(report, separators=(',', ':')))
    raise SystemExit(
        1 if args.strict_quality and report['structural_quality_status'] != 'PASS' else 0
    )
