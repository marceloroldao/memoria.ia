#!/usr/bin/env python3
"""Shadow extension for consistently repeated exact copies of a source slot."""
import argparse
from dataclasses import asdict, dataclass
from hashlib import blake2b
from itertools import combinations
import json

from trajectory_analogy_boundary_probe import extract, recall as prior_recall
from trajectory_analogy_frame_probe import prefix, suffix, occurrences
from trajectory_analogy_stress_probe import FAMILIES, fixture
from trajectory_response_quality_probe import TrajectoryGenerationExperiment


@dataclass(frozen=True)
class CopyFrame:
    source_prefix: tuple
    source_suffix: tuple
    target_parts: tuple
    target_bridge: tuple
    target_suffix: tuple
    internal_anchors: tuple
    witnesses: tuple

    @property
    def frame_id(self):
        return blake2b(repr(self).encode(), digest_size=16).hexdigest()

    def head(self, variable):
        return tuple(s for part in self.target_parts for s in part+variable)+self.target_bridge


def learn_copies(memory):
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
        count = len(positions[0])
        if count < 2 or any(len(p) != count for p in positions):
            continue
        if any(any(a+len(v)>z for a, z in zip(p, p[1:]))
               for v, p in zip(variables, positions)):
            continue
        parts = [tuple(t[(p[j-1]+len(v) if j else 0):p[j]] for j in range(count))
                 for t, v, p in zip(targets, variables, positions)]
        if len(set(parts)) != 1 or any(not p for p in parts[0]):
            continue
        tails = [t[p[-1]+len(v):] for t, v, p in zip(targets, variables, positions)]
        bridge, ending = prefix(tails), suffix(tails)
        if not bridge or not ending:
            continue
        values = [extract(t, bridge, ending) for t in tails]
        if any(v is None for v in values) or len(set(values)) != 3:
            continue
        shared = {values[0][i:j] for i in range(len(values[0]))
                  for j in range(i+1, len(values[0])+1)
                  if all(occurrences(values[0][i:j], v) for v in values[1:])}
        maximal = [p for p in shared if not any(len(q)>len(p) and occurrences(p, q) for q in shared)]
        anchors = tuple((p, tuple(occurrences(p, v) for v in values)) for p in sorted(maximal))
        frames.add(CopyFrame(left, right, parts[0], bridge, ending, anchors, group))
    return tuple(sorted(frames, key=lambda f: f.frame_id))


def recall(memory, query):
    query = tuple(query)
    prior = prior_recall(memory, query)
    frames = learn_copies(memory)
    roots = {r['payload_id'] for r in memory.snapshot()['observations']}
    routes = {c['payload_id']: dict(c) for c in prior['candidates']}
    for frame in frames:
        if frame.internal_anchors:
            continue
        starts = occurrences(frame.source_prefix, query) if frame.source_prefix else (0,)
        if len(starts) != 1:
            continue
        variable = extract(query[starts[0]:], frame.source_prefix, frame.source_suffix)
        if variable is None:
            continue
        for root in sorted(roots):
            target = memory.expand(root)
            if len(occurrences(variable, target)) != len(frame.target_parts):
                continue
            if extract(target, frame.head(variable), frame.target_suffix) is None:
                continue
            candidate = routes.setdefault(root, dict(payload_id=root, output=target,
                                                    frame_ids=(), witnesses=()))
            candidate['frame_ids'] = candidate['frame_ids']+(frame.frame_id,)
            candidate['witnesses'] = tuple(sorted(set(candidate['witnesses'])|set(frame.witnesses)))
    candidates = tuple(routes[root] for root in sorted(routes))
    return dict(prior_boundary=prior,
        copy_frames=tuple(asdict(f)|dict(frame_id=f.frame_id) for f in frames),
        candidates=candidates, hypothesis=candidates[0]['output'] if len(candidates)==1 else None,
        reason='UNIQUE_OBSERVED_FRAME_MATCH' if len(candidates)==1 else
               'COMPETING_FRAME_MATCHES' if candidates else 'NO_COPY_FRAME_MATCH')


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
        result = checked(memory, transform(query))
        targets = tuple(transform(t) for t in expected)
        correct = kind=='answer' and result['hypothesis'] in targets
        cases.append(dict(name=name, kind=kind, expected=targets, result=result,
            quality_pass=correct if kind=='answer' else not result['candidates'],
            correct_answer=correct, false_unique=result['hypothesis'] is not None
            and result['hypothesis'] not in targets))
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
    return dict(format='memoria.ia-frame-repeated-copy-shadow-v1', seed=seed,
        integrity_status='PASS', quality_status='PASS' if counts['passed']==len(cases) else 'FAIL',
        policy_status='EXPERIMENTAL_REPEATED_COPY', engine_changed=False,
        prior_selectors_changed=False, native_executed=False, counts=counts, families=families)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seed', type=int, default=20261024)
    parser.add_argument('--strict-quality', action='store_true')
    args = parser.parse_args()
    report = probe(args.seed)
    print(json.dumps(report, separators=(',', ':')))
    raise SystemExit(1 if args.strict_quality and report['quality_status']!='PASS' else 0)
