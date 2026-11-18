#!/usr/bin/env python3
"""Read-only two-slot copying learned from shared source separators."""
import argparse
from dataclasses import asdict, dataclass
from hashlib import blake2b
from itertools import combinations
import json
from random import Random

from trajectory_analogy_boundary_probe import extract
from trajectory_analogy_frame_probe import prefix, suffix, occurrences
from trajectory_analogy_value_probe import recall as prior_recall
from trajectory_response_quality_probe import TrajectoryGenerationExperiment


def common_parts(values):
    shared = {values[0][i:j] for i in range(len(values[0]))
              for j in range(i+1, len(values[0])+1)
              if all(occurrences(values[0][i:j], v) for v in values[1:])}
    return tuple(sorted(p for p in shared if not any(
        len(q)>len(p) and occurrences(p, q) for q in shared)))


@dataclass(frozen=True)
class TwoSlotFrame:
    source_prefix: tuple
    source_separator: tuple
    source_suffix: tuple
    target_prefix: tuple
    target_between: tuple
    target_order: tuple
    target_bridge: tuple
    target_suffix: tuple
    internal_anchors: tuple
    witnesses: tuple

    @property
    def frame_id(self):
        return blake2b(repr(self).encode(), digest_size=16).hexdigest()

    def head(self, slots):
        a, b = self.target_order
        return self.target_prefix+slots[a]+self.target_between+slots[b]+self.target_bridge


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
        if not left or not right:
            continue
        middles = [extract(s, left, right) for s in sources]
        if any(m is None for m in middles):
            continue
        for separator in common_parts(middles):
            points = [occurrences(separator, m) for m in middles]
            if any(len(p)!=1 for p in points):
                continue
            slots = [(m[:p[0]], m[p[0]+len(separator):]) for m, p in zip(middles, points)]
            if any(not a or not b for a, b in slots) or any(
                len({s[j] for s in slots})!=3 for j in (0, 1)):
                continue
            locations = [tuple(occurrences(v, target) for v in pair)
                         for pair, target in zip(slots, targets)]
            if any(any(len(p)!=1 for p in pair) for pair in locations):
                continue
            orders = [(0, 1) if p[0][0]<p[1][0] else (1, 0) for p in locations]
            if len(set(orders))!=1:
                continue
            a, b = orders[0]
            if any(pos[a][0]+len(pair[a])>pos[b][0] for pair, pos in zip(slots, locations)):
                continue
            heads = [t[:pos[a][0]] for t, pos in zip(targets, locations)]
            between = [t[pos[a][0]+len(pair[a]):pos[b][0]]
                       for t, pair, pos in zip(targets, slots, locations)]
            if not heads[0] or len(set(heads))!=1 or len(set(between))!=1:
                continue
            tails = [t[pos[b][0]+len(pair[b]):] for t, pair, pos in zip(targets, slots, locations)]
            bridge, ending = prefix(tails), suffix(tails)
            if not ending:
                continue
            values = [extract(t, bridge, ending) for t in tails]
            if any(v is None for v in values) or len(set(values))!=3:
                continue
            frames.add(TwoSlotFrame(left, separator, right, heads[0], between[0],
                orders[0], bridge, ending, common_parts(values), group))
    return tuple(sorted(frames, key=lambda f:f.frame_id))


def recall(memory, query):
    query = tuple(query)
    prior = prior_recall(memory, query)
    frames = learn(memory)
    roots = {r['payload_id'] for r in memory.snapshot()['observations']}
    routes = {c['payload_id']:dict(c) for c in prior['candidates']}
    alignments = []
    for frame in frames:
        starts = occurrences(frame.source_prefix, query)
        if len(starts)!=1:
            continue
        body = extract(query[starts[0]:], frame.source_prefix, frame.source_suffix)
        if body is None:
            continue
        points = occurrences(frame.source_separator, body)
        choices = tuple((body[:i], body[i+len(frame.source_separator):]) for i in points)
        alignments.append(dict(frame_id=frame.frame_id, separator_positions=points,
                               slot_choices=choices, authorized=not frame.internal_anchors
                               and len(choices)==1 and all(choices[0])))
        if frame.internal_anchors or len(choices)!=1 or not all(choices[0]):
            continue
        slots = choices[0]
        for root in sorted(roots):
            target = memory.expand(root)
            if any(len(occurrences(v, target))!=1 for v in slots):
                continue
            if extract(target, frame.head(slots), frame.target_suffix) is None:
                continue
            candidate = routes.setdefault(root, dict(payload_id=root, output=target,
                                                    frame_ids=(), witnesses=()))
            candidate['frame_ids'] += (frame.frame_id,)
            candidate['witnesses'] = tuple(sorted(set(candidate['witnesses'])|set(frame.witnesses)))
    candidates = tuple(routes[root] for root in sorted(routes))
    return dict(prior_value=prior, two_slot_frames=tuple(asdict(f)|dict(frame_id=f.frame_id) for f in frames),
        query_alignments=tuple(alignments), candidates=candidates,
        hypothesis=candidates[0]['output'] if len(candidates)==1 else None,
        reason='UNIQUE_OBSERVED_FRAME_MATCH' if len(candidates)==1 else
               'COMPETING_FRAME_MATCHES' if candidates else 'NO_TWO_SLOT_FRAME_MATCH')


def checked(memory, query):
    state = memory.snapshot(), memory.learning_state()
    generation = asdict(memory.generate(query))
    result = recall(memory, query)
    assert result == recall(TrajectoryGenerationExperiment.restore(memory.snapshot()), query)
    assert generation == asdict(memory.generate(query))
    assert state == (memory.snapshot(), memory.learning_state())
    return result


def evaluate(seed, stage, renamed=False):
    symbols = iter(Random(seed).sample(range(1000, 100000), 100))
    block = lambda:(next(symbols), next(symbols))
    p, s, separator, t, b, e = (block() for _ in range(6))
    ids, tags, values = ([block() for _ in range(6)] for _ in range(3))
    if stage=='ambiguous_separator':
        ids[3] += separator+block()
    source = lambda identity, tag:p+identity+separator+tag+s
    def target(identity, tag, value):
        return t+(tag+b+identity if stage=='reversed_order' else identity+b+tag)+value+e
    transform = lambda xs:tuple(1000000-x for x in xs) if renamed else tuple(xs)
    memory, origins = TrajectoryGenerationExperiment(), {}
    def observe(payload, address, stream):
        receipt = memory.observe(transform(payload), observation_id=address, stream_id=stream)
        origins.setdefault(receipt.payload_id, []).append(address)
    pairs = tuple((source(ids[i], tags[i]), target(ids[i], tags[i], values[i])) for i in range(3))
    for i, (q, a) in enumerate(pairs):
        observe(q, f'{i}:s', f'train:{i}')
        observe(a, f'{i}:t', f'train:{i}')
    facts = (target(ids[3], tags[3], values[3]), target(ids[3], tags[4], values[4]))
    for i, fact in enumerate(facts):
        observe(fact, f'fact:{i}', f'fact:{i}')
    first = (facts[0],)
    if stage=='conflict':
        rival = target(ids[3], tags[3], values[5])
        observe(rival, 'rival', 'rival')
        first += (rival,)
    kind = 'conflict' if len(first)>1 else 'answer'
    qa, qb = source(ids[3], tags[3]), source(ids[3], tags[4])
    queries = [('first', qa, kind, first), ('new_prefix', block()+qa, kind, first),
               ('second', qb, 'answer', (facts[1],)),
               ('unknown_second', source(ids[3], tags[5]), 'absence', ()),
               ('unknown_first', source(ids[4], tags[3]), 'absence', ()),
               ('missing_second', p+ids[3]+s, 'absence', ()),
               ('changed_separator', p+ids[3]+block()+tags[3]+s, 'absence', ()),
               ('two_cues', qa+qb, 'absence', ()), ('unrelated', block()+block(), 'absence', ())]
    cases = []
    for name, query, required, expected in queries:
        result = checked(memory, transform(query))
        targets = tuple(transform(x) for x in expected)
        outputs = {c['output'] for c in result['candidates']}
        correct = required=='answer' and result['hypothesis'] in targets
        passed = correct if required=='answer' else not outputs if required=='absence' else (
            outputs==set(targets) and result['hypothesis'] is None)
        addressed = {x for candidate in result['candidates'] for a, z, _ in candidate['witnesses'] for x in (a, z)}
        addressed.update(c['payload_id'] for c in result['candidates'])
        assert addressed <= set(origins)
        cases.append(dict(name=name, kind=required, expected=targets, result=result,
            quality_pass=passed, correct_answer=correct, false_unique=result['hypothesis'] is not None
            and result['hypothesis'] not in targets))
    return dict(stage=stage, renamed=renamed, training_pairs=tuple((transform(q), transform(a)) for q,a in pairs),
        cases=cases, root_provenance=tuple(dict(payload_id=root, observation_addresses=tuple(addresses))
                                         for root, addresses in sorted(origins.items())))


def probe(seed):
    evaluations = [evaluate(seed, stage, renamed)
                   for stage in ('ordered', 'reversed_order', 'conflict', 'ambiguous_separator')
                   for renamed in (False, True)]
    cases = [c for evaluation in evaluations for c in evaluation['cases']]
    counts = dict(cases=len(cases), passed=sum(c['quality_pass'] for c in cases),
        correct_answers=sum(c['correct_answer'] for c in cases), answer_cases=sum(c['kind']=='answer' for c in cases),
        false_unique=sum(c['false_unique'] for c in cases),
        conflicts_preserved=sum(c['kind']=='conflict' and c['quality_pass'] for c in cases),
        conflict_cases=sum(c['kind']=='conflict' for c in cases),
        absence_empty=sum(c['kind']=='absence' and not c['result']['candidates'] for c in cases),
        absence_cases=sum(c['kind']=='absence' for c in cases))
    return dict(format='memoria.ia-frame-two-slot-shadow-v1', seed=seed, integrity_status='PASS',
        quality_status='PASS' if counts['passed']==len(cases) else 'FAIL',
        policy_status='EXPERIMENTAL_TWO_COPIED_SLOTS', engine_changed=False,
        prior_selectors_changed=False, native_executed=False, counts=counts, evaluations=evaluations)


if __name__=='__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seed', type=int, default=20261030)
    parser.add_argument('--strict-quality', action='store_true')
    args = parser.parse_args()
    report = probe(args.seed)
    print(json.dumps(report, separators=(',', ':')))
    raise SystemExit(1 if args.strict_quality and report['quality_status']!='PASS' else 0)
