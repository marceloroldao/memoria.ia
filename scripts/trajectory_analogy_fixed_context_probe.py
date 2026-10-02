#!/usr/bin/env python3
"""Shadow empty-bridge routes anchored by copied fixed source context."""
import argparse
from dataclasses import asdict
from itertools import combinations
from functools import partial
import json
from random import Random

from trajectory_analogy_alignment_probe import recall as prior_recall
from trajectory_analogy_boundary_probe import extract
from trajectory_analogy_frame_probe import Frame, prefix, suffix, occurrences
from trajectory_analogy_repeated_cue_probe import evaluate
from trajectory_analogy_two_slot_probe import common_parts
from trajectory_response_quality_probe import TrajectoryGenerationExperiment


def learn(memory):
    previous, pairs, frames = {}, set(), {}
    for row in memory.snapshot()['observations']:
        scope = row['hierarchy_id'], row['stream_id']
        if scope in previous and previous[scope] != row['payload_id']:
            pairs.add((previous[scope], row['payload_id'], row['stream_id']))
        previous[scope] = row['payload_id']
    for group in combinations(sorted(pairs), 3):
        sources = [memory.expand(a) for a, _, _ in group]
        targets = [memory.expand(z) for _, z, _ in group]
        left, right = prefix(sources), suffix(sources)
        if not left or not right:
            continue
        variables = [extract(s, left, right) for s in sources]
        if any(v is None for v in variables) or len(set(variables)) != 3:
            continue
        points = [occurrences(v, t) for v, t in zip(variables, targets)]
        if any(len(p) != 1 for p in points):
            continue
        heads = [t[:p[0]] for t, p in zip(targets, points)]
        if not heads[0] or len(set(heads)) != 1:
            continue
        contexts = tuple(dict(source_boundary=side, symbols=part,
            source_positions=occurrences(part, boundary), target_positions=occurrences(part, heads[0]))
            for side, boundary in (('prefix', left), ('suffix', right))
            for part in common_parts((boundary, heads[0])))
        if not contexts:
            continue
        tails = [t[p[0]+len(v):] for t, p, v in zip(targets, points, variables)]
        bridge, ending = prefix(tails), suffix(tails)
        if bridge or not ending:
            continue
        values = [extract(t, (), ending) for t in tails]
        if any(v is None for v in values) or len(set(values)) != 3:
            continue
        frame = Frame(left, right, heads[0], (), ending, group)
        frames[frame.frame_id] = dict(frame=frame, copied_contexts=contexts,
                                      internal_anchors=common_parts(values))
    return tuple(frames[k] for k in sorted(frames))


def recall(memory, query, *, authorize_new_unique=False):
    query = tuple(query)
    prior = prior_recall(memory, query)
    frames = learn(memory)
    routes = {c['payload_id']: dict(c) for c in prior['candidates']}
    roots = {r['payload_id'] for r in memory.snapshot()['observations']}
    matches = []
    for row in frames:
        frame = row['frame']
        if row['internal_anchors']:
            continue
        starts = occurrences(frame.source_prefix, query)
        if len(starts) != 1:
            continue
        variable = extract(query[starts[0]:], frame.source_prefix, frame.source_suffix)
        if variable is None:
            continue
        for root in sorted(roots):
            target = memory.expand(root)
            if len(occurrences(variable, target)) != 1:
                continue
            if extract(target, frame.target_prefix+variable, frame.target_suffix) is None:
                continue
            candidate = routes.setdefault(root, dict(payload_id=root, output=target,
                frame_ids=(), witnesses=(), alignment_matches=()))
            if frame.frame_id not in candidate['frame_ids']:
                candidate['frame_ids'] += (frame.frame_id,)
            candidate['witnesses'] = tuple(sorted(set(candidate['witnesses'])|set(frame.witnesses)))
            matches.append(dict(frame_id=frame.frame_id, payload_id=root, variable=variable,
                                copied_contexts=row['copied_contexts']))
    candidates = tuple(routes[root] for root in sorted(routes))
    unique = len(candidates)==1 and not prior['partial_alignment_support']
    hypothesis = candidates[0]['output'] if unique and (
        authorize_new_unique or prior['hypothesis']==candidates[0]['output']) else None
    return dict(prior_alignment=prior, fixed_context_frames=tuple(asdict(r['frame'])|
        dict(frame_id=r['frame'].frame_id, copied_contexts=r['copied_contexts'],
             internal_anchors=r['internal_anchors']) for r in frames),
        fixed_context_matches=tuple(matches), candidates=candidates, hypothesis=hypothesis,
        reason='COMPETING_FIXED_CONTEXT_ROOTS' if len(candidates)>1 else
               'PRIOR_PARTIAL_ALIGNMENT_SUPPORT' if candidates and prior['partial_alignment_support'] else
               'UNIQUE_OBSERVED_COPIED_CONTEXT_MATCH' if hypothesis is not None and matches else
               'COPIED_CONTEXT_CANDIDATE_ONLY' if candidates and hypothesis is None and matches else prior['reason'])


def checked(memory, query, *, authorize_new_unique=False):
    state = memory.snapshot(), memory.learning_state()
    generation = asdict(memory.generate(query))
    result = recall(memory, query, authorize_new_unique=authorize_new_unique)
    assert result == recall(TrajectoryGenerationExperiment.restore(memory.snapshot()), query,
                            authorize_new_unique=authorize_new_unique)
    assert generation == asdict(memory.generate(query))
    assert state == (memory.snapshot(), memory.learning_state())
    roots = {r['payload_id'] for r in memory.snapshot()['observations']}
    addressed = {x for c in result['candidates'] for a, z, _ in c['witnesses'] for x in (a, z)}
    addressed.update(c['payload_id'] for c in result['candidates'])
    assert addressed <= roots
    return result


def counts(evaluations):
    cases = [c for e in evaluations for stage in e['stages'] for c in stage['cases']]
    return dict(cases=len(cases), passed=sum(c['quality_pass'] for c in cases),
        answer_cases=sum(c['kind']=='answer' for c in cases),
        correct_answers=sum(c['kind']=='answer' and c['quality_pass'] for c in cases),
        conflict_cases=sum(c['kind']=='conflict' for c in cases),
        conflicts_preserved=sum(c['kind']=='conflict' and c['quality_pass'] for c in cases),
        absence_cases=sum(c['kind']=='absence' for c in cases),
        absence_empty=sum(c['kind']=='absence' and c['quality_pass'] for c in cases),
        false_unique=sum(c['false_unique'] for c in cases))


def control_fixture(seed, family, renamed=False):
    symbols = iter(Random(seed).sample(range(1000,100000), 30))
    p, fixed, sep, s, t, b, end, anchor = (next(symbols) for _ in range(8))
    ids, tags, values = ([next(symbols) for _ in range(5)] for _ in range(3))
    transform = lambda xs:tuple(1000000-x for x in xs) if renamed else tuple(xs)
    source = lambda i:(p,fixed,sep,ids[i],s)
    target = lambda i:(t,)+(() if family=='no_copied_context' else (fixed,))+(b,ids[i],tags[i])+(
        (anchor,) if family=='internal_anchor' else ())+(values[i],end)
    memory = TrajectoryGenerationExperiment()
    pairs = tuple((transform(source(i)),transform(target(i))) for i in range(3))
    for i,(q,a) in enumerate(pairs):
        memory.observe(q, observation_id=f'{i}:s', stream_id=str(i))
        memory.observe(a, observation_id=f'{i}:t', stream_id=str(i))
    fact, query = transform(target(3)), transform(source(3))
    memory.observe(fact, observation_id='fact', stream_id='fact')
    return memory, query, fact, pairs


def controls(seed, *, authorize_new_unique=False):
    cases = []
    for family in ('whole_tail','latent_relation','no_copied_context','internal_anchor'):
        for renamed in (False,True):
            memory, query, fact, pairs = control_fixture(seed,family,renamed)
            result = checked(memory,query,authorize_new_unique=authorize_new_unique)
            answer = family=='whole_tail'
            passed = result['hypothesis']==fact if answer else not result['candidates']
            cases.append(dict(family=family,renamed=renamed,training_pairs=pairs,query=query,fact=fact,
                kind='answer' if answer else 'absence',quality_pass=passed,
                false_unique=result['hypothesis'] is not None and not answer,result=result))
    return cases


def probe(seed):
    evaluations = [evaluate(seed, fixed, renamed, reader=checked) for fixed in (0,1) for renamed in (False,True)]
    prior = [evaluate(seed, fixed, renamed) for fixed in (0,1) for renamed in (False,True)]
    score = counts(evaluations)
    extra = controls(seed)
    authorized = [evaluate(seed,fixed,renamed,reader=partial(checked,authorize_new_unique=True))
                  for fixed in (0,1) for renamed in (False,True)]
    authorized_controls = controls(seed,authorize_new_unique=True)
    main_pass = score['passed']==score['cases']
    control_pass = all(c['quality_pass'] for c in extra)
    return dict(format='memoria.ia-copied-fixed-context-shadow-v1', seed=seed, integrity_status='PASS',
        quality_status='PASS' if main_pass and control_pass else 'FAIL',
        main_quality_status='PASS' if main_pass else 'FAIL',
        control_quality_status='PASS' if control_pass else 'FAIL',
        engine_changed=False, prior_selectors_changed=False, native_executed=False,
        counts=score, prior_counts=counts(prior), evaluations=evaluations, controls=extra,
        control_counts=dict(cases=len(extra),passed=sum(c['quality_pass'] for c in extra),
                            false_unique=sum(c['false_unique'] for c in extra)),
        authorization_ablation=dict(policy_status='REJECTED_UNIQUE_AUTHORIZATION',counts=counts(authorized),
            control_counts=dict(cases=len(authorized_controls),
                passed=sum(c['quality_pass'] for c in authorized_controls),
                false_unique=sum(c['false_unique'] for c in authorized_controls)),
            controls=tuple(dict(family=c['family'],renamed=c['renamed'],kind=c['kind'],
                hypothesis=c['result']['hypothesis'],quality_pass=c['quality_pass'],
                false_unique=c['false_unique']) for c in authorized_controls)))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seed', type=int, default=20261105)
    parser.add_argument('--strict-quality', action='store_true')
    args = parser.parse_args()
    report = probe(args.seed)
    print(json.dumps(report, separators=(',', ':')))
    raise SystemExit(1 if args.strict_quality and report['quality_status']!='PASS' else 0)
