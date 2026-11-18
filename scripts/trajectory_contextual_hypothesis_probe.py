#!/usr/bin/env python3
"""Score an opt-in contextual hypothesis separately from default selection."""
from dataclasses import asdict
import argparse
import json
from random import Random

from trajectory_response_quality_probe import (
    TrajectoryGenerationExperiment, encode, decode, evaluate_case, fixture_groups,
)


def read(memory, query):
    before = memory.snapshot(), memory.learning_state()
    baseline = asdict(memory.generate(query))
    result = memory.contextual_route_hypothesis(query)
    cold = TrajectoryGenerationExperiment.restore(memory.snapshot())
    assert asdict(result) == asdict(cold.contextual_route_hypothesis(query))
    assert asdict(result.generation) == baseline
    assert asdict(memory.generate(query)) == baseline
    assert (memory.snapshot(), memory.learning_state()) == before
    return result


def positive_controls():
    rows = []
    for kind, present in [('introduced', (False, False)), ('carried', (True, True)),
                          ('mixed', (True, False))]:
        for renamed in (False, True):
            for padding in (1, 4, 8, 16):
                transform = lambda xs: tuple(x * 101 + 17 if renamed else x for x in xs)
                memory = TrajectoryGenerationExperiment()
                for i, carried in enumerate(present):
                    source = (90 + 2*i,) + ((7, 8, 9) if carried else ()) + (1, 2, 3, 91 + 2*i)
                    target = (94 + 2*i, 7, 8, 9, 95 + 2*i)
                    memory.observe(transform(source), observation_id=f'{i}:s', stream_id=str(i))
                    memory.observe(transform(target), observation_id=f'{i}:t', stream_id=str(i))
                result = read(memory, transform((100,) * padding + (1, 2, 3) + (101,) * padding))
                assert result.hypothesis == transform((7, 8, 9))
                rows.append(dict(kind=kind, renamed=renamed, padding=padding, preserved=True))
    return rows


def probe(seed):
    rng = Random(seed)
    rows = []
    for trial in range(2):
        groups = fixture_groups(rng)
        for adapter in ('unicode', 'utf8'):
            for group, records, descriptors in groups:
                memory = TrajectoryGenerationExperiment()
                for i, (text, stream) in enumerate(records):
                    memory.observe(encode(text, adapter), observation_id=str(i), stream_id=stream)
                cold = TrajectoryGenerationExperiment.restore(memory.snapshot())
                for descriptor in descriptors:
                    row = evaluate_case(memory, cold, descriptor, adapter)
                    result = read(memory, encode(descriptor['query'], adapter))
                    output = None if result.hypothesis is None else decode(result.hypothesis, adapter)
                    correct = bool(output and output[1] and len(descriptor['expected']) == 1
                                   and descriptor['expected'][0] in output[0])
                    quality = correct if descriptor['kind'] == 'answer' else (
                        output is None if descriptor['kind'] == 'absence' else
                        output is None and all(row['targets_retained']))
                    row.update(trial=trial, group=group,
                               hypothesis=None if output is None else output[0],
                               hypothesis_reason=result.reason,
                               hypothesis_correct=correct,
                               hypothesis_false_unique=bool(output and not correct and descriptor['kind'] != 'conflict'),
                               hypothesis_quality_pass=quality,
                               contextual_fragments=[decode(s, adapter)[0] for s in result.contextual_fragments],
                               shared_source_contexts=[decode(s, adapter)[0] for s in result.shared_source_contexts])
                    rows.append(row)
    positive = positive_controls()
    required = [r for r in rows if r['required']]
    return dict(format='memoria.ia-contextual-route-hypothesis-v1', seed=seed,
                integrity_status='PASS', default_selection_changed=False,
                hypothesis_quality_status='PASS' if all(r['hypothesis_quality_pass'] for r in required) else 'FAIL',
                counts=dict(baseline_correct_answers=sum(r['selected_correct'] for r in rows),
                            hypothesis_correct_answers=sum(r['hypothesis_correct'] for r in rows),
                            baseline_false_unique=sum(r['false_unique'] for r in rows),
                            hypothesis_false_unique=sum(r['hypothesis_false_unique'] for r in rows),
                            hypothesis_absence_abstentions=sum(r['kind']=='absence' and r['hypothesis'] is None for r in rows),
                            conflicts_preserved=sum(r['kind']=='conflict' and r['hypothesis_quality_pass'] for r in rows),
                            required_passes=sum(r['hypothesis_quality_pass'] for r in required),
                            required_cases=len(required), positive_controls_preserved=len(positive)),
                positive_controls=positive, cases=rows)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--seed', type=int, default=20260930)
    parser.add_argument('--strict-quality', action='store_true')
    args = parser.parse_args()
    report = probe(args.seed)
    print(json.dumps(report, ensure_ascii=False, separators=(',', ':')))
    if args.strict_quality and report['hypothesis_quality_status'] != 'PASS':
        raise SystemExit(1)
