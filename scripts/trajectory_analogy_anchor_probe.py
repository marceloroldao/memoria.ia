#!/usr/bin/env python3
"""Shadow veto for internal shared anchors hidden inside a frame's free slot."""
import argparse
from dataclasses import asdict
import json

from trajectory_analogy_frame_probe import learn_frames, middle, occurrences, recall
from trajectory_analogy_stress_probe import FAMILIES, fixture
from trajectory_response_quality_probe import TrajectoryGenerationExperiment


def internal_anchors(memory, frame):
    values = []
    for source, target, _ in frame.witnesses:
        variable = middle(memory.expand(source), frame.source_prefix, frame.source_suffix)
        head = frame.target_prefix + variable + frame.target_bridge
        values.append(middle(memory.expand(target), head, frame.target_suffix))
    shared = set()
    for start in range(len(values[0])):
        for stop in range(start + 1, len(values[0]) + 1):
            part = values[0][start:stop]
            if all(occurrences(part, value) for value in values[1:]):
                shared.add(part)
    # Keep maximal contiguous anchors; record every location, not a chosen split.
    maximal = [p for p in shared if not any(len(q) > len(p) and occurrences(p, q)
                                          for q in shared)]
    return tuple(dict(symbols=p, positions=tuple(occurrences(p, v) for v in values))
                 for p in sorted(maximal))


def shadow_recall(memory, query):
    baseline = recall(memory, query)
    frames = learn_frames(memory)
    blocked = {f.frame_id: dict(frame_id=f.frame_id, witnesses=f.witnesses,
                               anchors=internal_anchors(memory, f)) for f in frames}
    blocked = {k: v for k, v in blocked.items() if v['anchors']}
    candidates = []
    for candidate in baseline['candidates']:
        routes = [f for f in frames if f.frame_id in candidate['frame_ids']
                  and f.frame_id not in blocked]
        if routes:
            candidates.append(dict(candidate, frame_ids=tuple(f.frame_id for f in routes),
                witnesses=tuple(sorted({w for f in routes for w in f.witnesses}))))
    return dict(baseline=baseline, blocked_frames=tuple(blocked[k] for k in sorted(blocked)),
                candidates=tuple(candidates),
                hypothesis=candidates[0]['output'] if len(candidates) == 1 else None,
                reason='UNIQUE_UNBLOCKED_FRAME_MATCH' if len(candidates) == 1 else
                       'COMPETING_FRAME_MATCHES' if candidates else 'NO_UNBLOCKED_FRAME_MATCH')


def checked_shadow(memory, query):
    state = memory.snapshot(), memory.learning_state()
    generation = asdict(memory.generate(query))
    result = shadow_recall(memory, query)
    assert result == shadow_recall(TrajectoryGenerationExperiment.restore(memory.snapshot()), query)
    assert generation == asdict(memory.generate(query))
    assert state == (memory.snapshot(), memory.learning_state())
    return result


def evaluate(seed, family, renamed=False):
    pairs, facts, queries = fixture(seed, family)
    transform = lambda xs: tuple(1000000-x for x in xs) if renamed else tuple(xs)
    memory = TrajectoryGenerationExperiment()
    for i, (source, target) in enumerate(pairs):
        memory.observe(transform(source), observation_id=f'{i}:s', stream_id=f'train:{i}')
        memory.observe(transform(target), observation_id=f'{i}:t', stream_id=f'train:{i}')
    for i, fact in enumerate(facts):
        memory.observe(transform(fact), observation_id=f'isolated:{i}', stream_id=f'isolated:{i}')
    cases = []
    for name, query, kind, expected in queries:
        result = checked_shadow(memory, transform(query))
        targets = tuple(transform(t) for t in expected)
        correct = kind == 'answer' and result['hypothesis'] in targets
        cases.append(dict(name=name, kind=kind, expected=targets, result=result,
            quality_pass=correct if kind == 'answer' else not result['candidates'],
            correct_answer=correct,
            false_unique=result['hypothesis'] is not None and result['hypothesis'] not in targets))
    return dict(family=family, renamed=renamed, cases=cases)


def probe(seed):
    families = [evaluate(seed, family, renamed) for family in FAMILIES for renamed in (False, True)]
    cases = [c for f in families for c in f['cases']]
    counts = dict(cases=len(cases), passed=sum(c['quality_pass'] for c in cases),
        correct_answers=sum(c['correct_answer'] for c in cases),
        answer_cases=sum(c['kind'] == 'answer' for c in cases),
        false_unique=sum(c['false_unique'] for c in cases),
        absence_empty=sum(c['kind'] == 'absence' and not c['result']['candidates'] for c in cases),
        absence_cases=sum(c['kind'] == 'absence' for c in cases))
    return dict(format='memoria.ia-frame-internal-anchor-shadow-v1', seed=seed,
        integrity_status='PASS', quality_status='PASS' if counts['passed'] == len(cases) else 'FAIL',
        policy_status='EXPERIMENTAL_CONSERVATIVE_VETO', engine_changed=False,
        baseline_selector_changed=False, native_executed=False, counts=counts, families=families)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seed', type=int, default=20261018)
    parser.add_argument('--strict-quality', action='store_true')
    args = parser.parse_args()
    report = probe(args.seed)
    print(json.dumps(report, separators=(',', ':')))
    raise SystemExit(1 if args.strict_quality and report['quality_status'] != 'PASS' else 0)
