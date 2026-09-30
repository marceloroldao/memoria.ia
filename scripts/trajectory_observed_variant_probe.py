#!/usr/bin/env python3
"""Measure observed symbol variants without normalizing or teaching labels."""
import argparse
from collections import Counter
from dataclasses import asdict
import json
from random import Random

from trajectory_contextual_hypothesis_probe import read
from trajectory_response_quality_probe import TrajectoryGenerationExperiment, encode

STAGES = ('unseen', 'source_only', 'paired', 'repeated', 'conflict')


def score(result, expected, kind):
    contains = lambda part, whole: any(whole[i:i + len(part)] == part
                                     for i in range(len(whole) - len(part) + 1))
    retained = [any(contains(target, c.output) for c in result.generation.candidates)
                for target in expected]
    correct = (kind == 'answer' and result.hypothesis is not None
               and len(expected) == 1 and contains(expected[0], result.hypothesis))
    passed = correct if kind == 'answer' else (
        result.hypothesis is None if kind == 'absence' else
        result.hypothesis is None and all(retained))
    return dict(correct_answer=bool(correct), targets_retained=retained,
                false_unique=bool(result.hypothesis is not None and not correct
                                  and kind != 'conflict'), quality_pass=bool(passed))


def run_fixture(cue, variant, target, rival, prefix, unknown, unrelated):
    rows = []
    receipts = []
    for stage in STAGES:
        memory = TrajectoryGenerationExperiment()
        pairs = [(cue, target)]
        if stage == 'source_only':
            pairs.append((variant,))
        if stage in ('paired', 'repeated', 'conflict'):
            pairs.append((variant, target))
        if stage == 'repeated':
            pairs.extend([(variant, target)] * 2)
        if stage == 'conflict':
            pairs.append((variant, rival))
        observations = []
        for i, pair in enumerate(pairs):
            for j, payload in enumerate(pair):
                receipt = memory.observe(payload, observation_id=f'{i}:{j}', stream_id=str(i))
                observations.append(dict(symbols=payload, stream=str(i), receipt=asdict(receipt)))
        # All symbols are provided observations. Query/answer labels remain here.
        state = memory.snapshot()
        payload_ids = {row['payload_id'] for row in state['observations']}
        assert len(payload_ids) == len({p for pair in pairs for p in pair})
        if stage == 'repeated':
            assert all(not row['receipt']['learned']
                       and row['receipt']['new_relations'] == 0 for row in observations[4:])
        receipts.append(dict(stage=stage, observations=observations,
                             unique_payloads=len(payload_ids)))
        variant_kind = ('absence' if stage in ('unseen', 'source_only') else
                        'conflict' if stage == 'conflict' else 'answer')
        expected = () if variant_kind == 'absence' else (
            (target, rival) if variant_kind == 'conflict' else (target,))
        descriptors = [
            ('original', cue, 'answer', (target,)),
            ('variant', variant, variant_kind, expected),
            ('new_prefix', prefix + variant, variant_kind, expected),
            ('unknown_variant_subject', unknown, 'absence', ()),
            ('unrelated', unrelated, 'absence', ()),
        ]
        for name, query, kind, answers in descriptors:
            result = read(memory, query)
            rows.append(dict(stage=stage, name=name, kind=kind, query=query,
                             expected=answers, result=asdict(result),
                             **score(result, answers, kind)))
    return rows, receipts


def probe(seed, trials=2):
    rng = Random(seed)
    rows, observations = [], []
    for trial in range(trials):
        name, absent = rng.sample(('Luma', 'Neri', 'Vero', 'Daro', 'Kivo', 'Zuri'), 2)
        code, other = rng.sample(range(100, 999), 2)
        for adapter in ('unicode', 'utf8'):
            texts = (f'Código de {name}?', f'código de {name.lower()}?',
                     f'{name}: {code}.', f'{name}: {other}.', 'Lembre: ',
                     f'código de {absent}?', 'Temperatura de Marte?')
            fixture = tuple(encode(text, adapter) for text in texts)
            cases, records = run_fixture(*fixture)
            rows.extend(dict(trial=trial, adapter=adapter, **r) for r in cases)
            observations.append(dict(trial=trial, adapter=adapter, surface_inputs=texts,
                                     stages=records))
    # Numeric renaming is bijective, not a case conversion or symbol merge.
    opaque = ((1, 2, 3, 4), (11, 2, 3, 14), (7, 8, 9), (17, 18, 19),
              (100, 101), (11, 2, 3, 24), (30, 31, 32))
    for renamed in (False, True):
        transform = lambda xs: tuple(10000 - x if renamed else x for x in xs)
        cases, records = run_fixture(*(transform(xs) for xs in opaque))
        rows.extend(dict(trial=0, adapter='opaque', renamed=renamed, **r) for r in cases)
        observations.append(dict(adapter='opaque', renamed=renamed, stages=records))
    counts = Counter(cases=len(rows), passed=sum(r['quality_pass'] for r in rows),
                     correct_answers=sum(r['correct_answer'] for r in rows),
                     answer_cases=sum(r['kind'] == 'answer' for r in rows),
                     false_unique=sum(r['false_unique'] for r in rows))
    by_stage = {}
    for stage in STAGES:
        group = [r for r in rows if r['stage'] == stage]
        by_stage[stage] = dict(cases=len(group), passed=sum(r['quality_pass'] for r in group),
            answer_cases=sum(r['kind'] == 'answer' for r in group),
            correct_answers=sum(r['correct_answer'] for r in group),
            targets_retained=sum(all(r['targets_retained']) for r in group if r['expected']),
            expected_target_cases=sum(bool(r['expected']) for r in group),
            absence_cases=sum(r['kind'] == 'absence' for r in group),
            absence_abstentions=sum(r['kind'] == 'absence' and r['result']['hypothesis'] is None
                                    for r in group), false_unique=sum(r['false_unique'] for r in group))
    return dict(format='memoria.ia-observed-variant-v1', seed=seed, trials=trials,
                integrity_status='PASS', quality_status='PASS' if all(r['quality_pass'] for r in rows) else 'FAIL',
                engine_changed=False, default_selection_changed=False, counts=dict(counts),
                by_stage=by_stage, observations=observations, cases=rows)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--seed', type=int, default=20260930)
    parser.add_argument('--trials', type=int, default=2)
    parser.add_argument('--strict-quality', action='store_true')
    args = parser.parse_args()
    if args.trials < 1:
        parser.error('--trials must be positive')
    report = probe(args.seed, args.trials)
    print(json.dumps(report, ensure_ascii=False, separators=(',', ':')))
    raise SystemExit(1 if args.strict_quality and report['quality_status'] != 'PASS' else 0)
