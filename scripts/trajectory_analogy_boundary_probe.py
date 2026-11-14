#!/usr/bin/env python3
"""Shadow analogy with one optional source boundary and exact unanchored starts."""
import argparse
from dataclasses import asdict
from itertools import combinations
import json

from trajectory_analogy_anchor_probe import shadow_recall
from trajectory_analogy_frame_probe import Frame, prefix, suffix, occurrences
from trajectory_analogy_stress_probe import FAMILIES, fixture
from trajectory_response_quality_probe import TrajectoryGenerationExperiment


def extract(value, left, right):
    if left and value[:len(left)] != left:
        return None
    if right and value[-len(right):] != right:
        return None
    stop = len(value)-len(right)
    return value[len(left):stop] if stop > len(left) else None


def learn(memory):
    previous, pairs = {}, set()
    for row in memory.snapshot()['observations']:
        scope = row['hierarchy_id'], row['stream_id']
        if scope in previous and previous[scope] != row['payload_id']:
            pairs.add((previous[scope], row['payload_id'], row['stream_id']))
        previous[scope] = row['payload_id']
    frames = set()
    for group in combinations(sorted(pairs), 3):
        sources = [memory.expand(a) for a, _, _ in group]
        targets = [memory.expand(z) for _, z, _ in group]
        left, right = prefix(sources), suffix(sources)
        if not left and not right:
            continue
        variables = [extract(s, left, right) for s in sources]
        if any(v is None for v in variables) or len(set(variables)) != 3:
            continue
        positions = [occurrences(v, t) for v, t in zip(variables, targets)]
        if any(len(p) != 1 for p in positions):
            continue
        heads = [t[:p[0]] for t, p in zip(targets, positions)]
        if not heads[0] or len(set(heads)) != 1:
            continue
        tails = [t[p[0]+len(v):] for t, p, v in zip(targets, positions, variables)]
        bridge, ending = prefix(tails), suffix(tails)
        if not bridge or not ending:
            continue
        values = [extract(t, bridge, ending) for t in tails]
        if any(v is None for v in values) or len(set(values)) != 3:
            continue
        frames.add(Frame(left, right, heads[0], bridge, ending, group))
    return tuple(sorted(frames, key=lambda f: f.frame_id))


def anchors(memory, frame):
    values = []
    for source, target, _ in frame.witnesses:
        variable = extract(memory.expand(source), frame.source_prefix, frame.source_suffix)
        values.append(extract(memory.expand(target),
            frame.target_prefix+variable+frame.target_bridge, frame.target_suffix))
    shared = {values[0][i:j] for i in range(len(values[0]))
              for j in range(i+1, len(values[0])+1)
              if all(occurrences(values[0][i:j], v) for v in values[1:])}
    maximal = [p for p in shared if not any(len(q)>len(p) and occurrences(p, q) for q in shared)]
    return tuple(dict(symbols=p, positions=tuple(occurrences(p, v) for v in values))
                 for p in sorted(maximal))


def recall(memory, query):
    query = tuple(query)
    frames = learn(memory)
    blocked = {f.frame_id: anchors(memory, f) for f in frames}
    roots = {r['payload_id'] for r in memory.snapshot()['observations']}
    candidates = {}
    for frame in frames:
        if blocked[frame.frame_id]:
            continue
        # A missing prefix supplies no evidence for where added context ends.
        starts = occurrences(frame.source_prefix, query) if frame.source_prefix else (0,)
        if len(starts) != 1:
            continue
        variable = extract(query[starts[0]:], frame.source_prefix, frame.source_suffix)
        if variable is None:
            continue
        head = frame.target_prefix+variable+frame.target_bridge
        for root in sorted(roots):
            if extract(memory.expand(root), head, frame.target_suffix) is not None:
                candidates.setdefault(root, []).append(frame)
    outputs = tuple(dict(payload_id=root, output=memory.expand(root),
        frame_ids=tuple(f.frame_id for f in routes),
        witnesses=tuple(sorted({w for f in routes for w in f.witnesses})))
        for root, routes in sorted(candidates.items()))
    return dict(frames=tuple(asdict(f)|dict(frame_id=f.frame_id,
        internal_anchors=blocked[f.frame_id]) for f in frames), candidates=outputs,
        hypothesis=outputs[0]['output'] if len(outputs)==1 else None,
        reason='UNIQUE_BOUNDARY_FRAME_MATCH' if len(outputs)==1 else
               'COMPETING_FRAME_MATCHES' if outputs else 'NO_BOUNDARY_FRAME_MATCH')


def checked(memory, query):
    state = memory.snapshot(), memory.learning_state()
    generation = asdict(memory.generate(query))
    result = recall(memory, query)
    assert result == recall(TrajectoryGenerationExperiment.restore(memory.snapshot()), query)
    assert generation == asdict(memory.generate(query))
    assert state == (memory.snapshot(), memory.learning_state())
    return result


def evaluate(seed, family, renamed=False):
    pairs, facts, queries = fixture(seed, family)
    transform = lambda xs: tuple(1000000-x for x in xs) if renamed else tuple(xs)
    memory = TrajectoryGenerationExperiment()
    for i, (s, t) in enumerate(pairs):
        memory.observe(transform(s), observation_id=f'{i}:s', stream_id=f'train:{i}')
        memory.observe(transform(t), observation_id=f'{i}:t', stream_id=f'train:{i}')
    for i, fact in enumerate(facts):
        memory.observe(transform(fact), observation_id=f'isolated:{i}', stream_id=f'isolated:{i}')
    cases = []
    for name, query, kind, expected in queries:
        query, targets = transform(query), tuple(transform(t) for t in expected)
        result = checked(memory, query)
        old = shadow_recall(memory, query)
        correct = kind=='answer' and result['hypothesis'] in targets
        cases.append(dict(name=name, kind=kind, expected=targets,
            quality_pass=correct if kind=='answer' else not result['candidates'],
            correct_answer=correct,
            false_unique=result['hypothesis'] is not None and result['hypothesis'] not in targets,
            result=result, prior_shadow=old))
    return dict(family=family, renamed=renamed, cases=cases)


def probe(seed):
    families = [evaluate(seed, family, renamed) for family in FAMILIES for renamed in (False, True)]
    cases = [c for f in families for c in f['cases']]
    counts = dict(cases=len(cases), passed=sum(c['quality_pass'] for c in cases),
        correct_answers=sum(c['correct_answer'] for c in cases),
        answer_cases=sum(c['kind']=='answer' for c in cases),
        false_unique=sum(c['false_unique'] for c in cases),
        absence_empty=sum(c['kind']=='absence' and not c['result']['candidates'] for c in cases),
        absence_cases=sum(c['kind']=='absence' for c in cases))
    return dict(format='memoria.ia-frame-optional-boundary-shadow-v1', seed=seed,
        integrity_status='PASS', quality_status='PASS' if counts['passed']==len(cases) else 'FAIL',
        policy_status='EXPERIMENTAL_BOUNDARY_EXTENSION', engine_changed=False,
        prior_selectors_changed=False, native_executed=False, counts=counts, families=families)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seed', type=int, default=20261022)
    parser.add_argument('--strict-quality', action='store_true')
    args = parser.parse_args()
    report = probe(args.seed)
    print(json.dumps(report, separators=(',', ':')))
    raise SystemExit(1 if args.strict_quality and report['quality_status']!='PASS' else 0)
