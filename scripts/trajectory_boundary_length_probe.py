#!/usr/bin/env python3
"""Test length variation without a source delimiter using the unchanged reader."""
import argparse
from hashlib import sha256
import json
from random import Random

from trajectory_boundary_candidates_probe import checked_boundary_packet
from trajectory_boundary_support_probe import summarize
from trajectory_response_quality_probe import TrajectoryGenerationExperiment
from trajectory_separator_ablation_probe import counts, score


def fixture(seed, varied, joined, renamed=False):
    symbols = iter(Random(seed).sample(range(1000, 100000), 150))
    block = lambda n: tuple(next(symbols) for _ in range(n))
    p, s, t, between, bridge, end = (block(1) for _ in range(6))
    # Cross the lengths, while keeping each copied span's content distinct.
    lengths = ((1, 2), (1, 4), (3, 2), (3, 4)) if varied else ((2, 3),) * 4
    spans = [(block(a), block(b)) for a, b in lengths]
    reserved = (block(2), block(3))
    unknown = (block(2), block(3))
    values = [block(2) for _ in range(6)]
    rename = lambda xs: tuple(1000000 - x for x in xs) if renamed else tuple(xs)
    source = lambda a, b: rename(p + a + b + s)
    target = lambda a, b, v: rename(t + a + (() if joined else between) + b + bridge + v + end)
    pairs = tuple((source(a, b), target(a, b, values[i])) for i, (a, b) in enumerate(spans))
    a, b = reserved
    fact = target(a, b, values[4])
    # Rival uses a different source cut. With adjacent copies this is physically
    # indistinguishable from the original cut; with separated copies it is not.
    rival = target(a + b[:1], b[1:], values[5])
    queries = (
        ('reserved', source(a, b)),
        ('unknown_context', source(unknown[0], b)),
        ('unknown_body', source(a, unknown[1])),
        ('missing_body', rename(p + a + s)),
        ('joined_queries', source(a, b) + source(a, b)),
    )
    return dict(lengths=lengths, training_pairs=pairs, fact=fact, rival=rival,
                queries=queries, reserved_cut=1 + len(a), rival_cut=2 + len(a))


def layout(frame):
    """Observed frame structure, excluding occurrence multiplicity and IDs."""
    return tuple((key, repr(value)) for key, value in sorted(frame.items())
                 if key not in ('frame_id', 'witnesses', 'demonstration_alignments'))


def evaluate(seed, varied, joined, renamed=False):
    data = fixture(seed, varied, joined, renamed)
    memory = TrajectoryGenerationExperiment()

    def pair(index, address):
        a, b = data['training_pairs'][index]
        memory.observe(a, observation_id=address + ':source', stream_id=address)
        memory.observe(b, observation_id=address + ':target', stream_id=address)

    for i in range(3):
        pair(i, f'train:{i}')
    memory.observe(data['fact'], observation_id='fact', stream_id='fact')
    stages = []

    def capture(name, conflict=False):
        cases = []
        for name_query, query in data['queries']:
            expected = ((data['fact'], data['rival']) if conflict else (data['fact'],)) if name_query == 'reserved' else ()
            kind = 'conflict' if len(expected) > 1 else 'answer' if expected else 'absence'
            packet = checked_boundary_packet(memory, query)
            assert not packet['observed_continuations']
            cases.append(dict(name=name_query, query=query, expected=expected, kind=kind,
                              packet=packet, support=summarize(packet), **score(packet, kind, expected)))
        rows = memory.snapshot()['observations']
        stages.append(dict(name=name, cases=cases, provenance=rows,
                           unique_payloads=len({r['payload_id'] for r in rows}),
                           distinct_layouts=tuple(sorted({layout(f) for f in cases[0]['packet']['boundary_frames']}))))

    capture('three_distinct_pairs')
    pair(0, 'repeat:0')
    pair(1, 'repeat:1')
    capture('repeated_pairs')
    pair(3, 'train:3')
    capture('fourth_length_combination')
    memory.observe(data['rival'], observation_id='rival', stream_id='rival')
    capture('rival_other_cut', conflict=True)
    return dict(varied_lengths=varied, joined_target_copies=joined, renamed=renamed,
                fixture=data, stages=stages)


def probe(seed):
    evaluations = [evaluate(seed, varied, joined, renamed)
                   for varied in (False, True) for joined in (False, True) for renamed in (False, True)]
    complete = counts([c for ev in evaluations for stage in ev['stages'] for c in stage['cases']])
    by_shape = {
        f'{"varied" if varied else "fixed"}_{"adjacent" if joined else "separated"}':
        counts([c for ev in evaluations if ev['varied_lengths'] == varied and ev['joined_target_copies'] == joined
                for stage in ev['stages'] for c in stage['cases']])
        for varied in (False, True) for joined in (False, True)
    }
    return dict(format='memoria.ia-boundary-length-probe-v1', seed=seed,
                integrity_status='PASS', structural_quality_status='PASS' if complete['passed'] == complete['cases'] else 'FAIL',
                semantic_quality_status='UNQUALIFIED', counts=complete, by_shape=by_shape,
                evaluations=evaluations, engine_changed=False, prior_selectors_changed=False, native_executed=False,
                limitation='Finite opaque crossed-length fixtures. Adjacent target copies admit equivalent cuts. '
                           'Unique demonstrated layouts do not eliminate unsupported query cuts or establish reply intent.')


def compact_report(report):
    result = {key: value for key, value in report.items() if key != 'evaluations'}
    raw = json.dumps(report, separators=(',', ':')) + '\n'
    result['full_report_sha256'] = sha256(raw.encode()).hexdigest()
    result['stages'] = []
    for ev in report['evaluations']:
        stages = []
        for stage in ev['stages']:
            packet = stage['cases'][0]['packet']
            cuts = packet['boundary_support']
            stages.append(dict(name=stage['name'], unique_payloads=stage['unique_payloads'],
                               distinct_layouts=len(stage['distinct_layouts']),
                               frame_witnesses=len(packet['boundary_frames']),
                               reserved_candidate_count=len(packet['candidates']),
                               supported_cuts=sorted({c['source_position'] for c in cuts if c['candidate_roots']}),
                               enumerated_cuts=sorted({c['source_position'] for c in cuts}),
                               quality={c['name']: c['quality_pass'] for c in stage['cases']}))
        result['stages'].append(dict(varied_lengths=ev['varied_lengths'],
                                     joined_target_copies=ev['joined_target_copies'],
                                     renamed=ev['renamed'], stages=stages))
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seed', type=int, default=20261123)
    parser.add_argument('--strict-quality', action='store_true')
    parser.add_argument('--summary', action='store_true', help='Compact stage counts plus full-report SHA256')
    args = parser.parse_args()
    report = probe(args.seed)
    print(json.dumps(compact_report(report) if args.summary else report, separators=(',', ':')))
    raise SystemExit(1 if args.strict_quality and report['structural_quality_status'] != 'PASS' else 0)
