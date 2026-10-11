#!/usr/bin/env python3
"""Retain roots for every valid two-slot query split and require alignment consensus."""
import argparse
from dataclasses import asdict
import json
from random import Random

from trajectory_analogy_boundary_probe import extract
from trajectory_analogy_frame_probe import occurrences
from trajectory_analogy_two_slot_probe import learn, recall as prior_recall
from trajectory_response_quality_probe import TrajectoryGenerationExperiment


def recall(memory, query):
    query = tuple(query)
    prior = prior_recall(memory, query)
    roots = {r['payload_id'] for r in memory.snapshot()['observations']}
    routes = {c['payload_id']:dict(c, alignment_matches=()) for c in prior['candidates']}
    alignments, partial = [], False
    for frame in learn(memory):
        if frame.internal_anchors:
            continue
        starts = occurrences(frame.source_prefix, query)
        if len(starts)!=1:
            continue
        body = extract(query[starts[0]:], frame.source_prefix, frame.source_suffix)
        if body is None:
            continue
        choices = [(i, (body[:i], body[i+len(frame.source_separator):]))
                   for i in occurrences(frame.source_separator, body)]
        valid = [(i, slots) for i, slots in choices if all(slots)]
        supports = []
        for position, slots in valid:
            matched = []
            for root in sorted(roots):
                target = memory.expand(root)
                if any(len(occurrences(v, target))!=1 for v in slots):
                    continue
                if extract(target, frame.head(slots), frame.target_suffix) is None:
                    continue
                matched.append(root)
                candidate = routes.setdefault(root, dict(payload_id=root, output=target,
                    frame_ids=(), witnesses=(), alignment_matches=()))
                if frame.frame_id not in candidate['frame_ids']:
                    candidate['frame_ids'] += (frame.frame_id,)
                candidate['witnesses'] = tuple(sorted(set(candidate['witnesses'])|set(frame.witnesses)))
                candidate['alignment_matches'] += (dict(frame_id=frame.frame_id,
                    separator_position=position, slots=slots),)
            supports.append(tuple(matched))
            alignments.append(dict(frame_id=frame.frame_id, separator_position=position,
                                   slots=slots, candidate_roots=tuple(matched)))
        if len(valid)>1 and any(not matches for matches in supports):
            partial = True
    candidates = tuple(routes[root] for root in sorted(routes))
    hypothesis = candidates[0]['output'] if len(candidates)==1 and not partial else None
    supported = any(row['candidate_roots'] for row in alignments)
    status = 'COMPETING_ALIGNMENT_ROOTS' if len(candidates)>1 else (
        'PARTIAL_ALIGNMENT_SUPPORT' if partial and candidates else
        'UNIQUE_ROOT_WITH_COMPLETE_ALIGNMENT_SUPPORT' if hypothesis is not None and supported else
        'PRIOR_SELECTOR_HYPOTHESIS_ONLY' if hypothesis is not None else 'NO_OBSERVED_ROOT')
    return dict(prior_two_slot=prior, query_alignment_support=tuple(alignments),
        partial_alignment_support=partial, candidates=candidates, hypothesis=hypothesis, reason=status)


def checked(memory, query):
    state = memory.snapshot(), memory.learning_state()
    generation = asdict(memory.generate(query))
    result = recall(memory, query)
    assert result == recall(TrajectoryGenerationExperiment.restore(memory.snapshot()), query)
    assert generation == asdict(memory.generate(query))
    assert state == (memory.snapshot(), memory.learning_state())
    roots = {r['payload_id'] for r in memory.snapshot()['observations']}
    addressed = {x for c in result['candidates'] for a, z, _ in c['witnesses'] for x in (a,z)}
    addressed.update(c['payload_id'] for c in result['candidates'])
    assert addressed <= roots
    return result


def alignment_controls(seed, renamed=False):
    symbols = iter(Random(seed).sample(range(1000,100000), 30))
    p, s, sep, t, b, e = (next(symbols) for _ in range(6))
    ids, tags, values = ([next(symbols) for _ in range(5)] for _ in range(3))
    transform = lambda xs:tuple(1000000-x for x in xs) if renamed else tuple(xs)
    cases = []
    for stage in ('partial', 'conflict', 'consensus', 'empty'):
        memory = TrajectoryGenerationExperiment()
        between = sep if stage=='consensus' else b
        for i in range(3):
            memory.observe(transform((p,ids[i],sep,tags[i],s)),
                           observation_id=f'{i}:s', stream_id=str(i))
            memory.observe(transform((t,ids[i],between,tags[i],values[i],e)),
                           observation_id=f'{i}:t', stream_id=str(i))
        body = (ids[3],sep,ids[4],sep,tags[3])
        a = (t,ids[3],between,ids[4],sep,tags[3],values[3],e)
        z = (t,ids[3],sep,ids[4],between,tags[3],values[3],e)
        facts = () if stage=='empty' else (a,z) if stage=='conflict' else (z,)
        for i, fact in enumerate(facts):
            memory.observe(transform(fact), observation_id=f'fact:{i}', stream_id=f'fact:{i}')
        result = checked(memory, transform((p,)+body+(s,)))
        expected = {transform(f) for f in facts}
        outputs = {c['output'] for c in result['candidates']}
        passed = outputs==expected and (result['hypothesis']==transform(z) if stage=='consensus'
                                       else result['hypothesis'] is None)
        cases.append(dict(stage=stage, renamed=renamed, quality_pass=passed,
                          expected=tuple(sorted(expected)), result=result))
    return cases


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
    controls = [c for renamed in (False, True) for c in alignment_controls(seed, renamed)]
    return dict(format='memoria.ia-frame-alignment-consensus-shadow-v1', seed=seed, integrity_status='PASS',
        quality_status='PASS' if counts['passed']==len(cases) else 'FAIL',
        policy_status='EXPERIMENTAL_ALIGNMENT_CONSENSUS', engine_changed=False,
        prior_selectors_changed=False, native_executed=False, counts=counts, evaluations=evaluations, alignment_controls=controls,
        alignment_control_status='PASS' if all(c['quality_pass'] for c in controls) else 'FAIL')


if __name__=='__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seed', type=int, default=20261101)
    parser.add_argument('--strict-quality', action='store_true')
    args = parser.parse_args()
    report = probe(args.seed)
    print(json.dumps(report, separators=(',', ':')))
    raise SystemExit(1 if args.strict_quality and report['quality_status']!='PASS' else 0)
