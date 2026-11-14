#!/usr/bin/env python3
"""Adversarial field-role contracts without a shared internal delimiter."""
import argparse
import json
from random import Random

from trajectory_analogy_value_probe import checked
from trajectory_response_quality_probe import TrajectoryGenerationExperiment

FAMILIES = ('whole_value_two', 'relation_two_no_anchor', 'relation_three_no_anchor',
            'relation_two_with_anchor', 'fixed_tail_matching', 'fixed_tail_changed')


def fixture(seed, family):
    symbols = iter(Random(seed).sample(range(1000, 100000), 100))
    block = lambda: (next(symbols), next(symbols))
    p, s, t, b, e, c = (block() for _ in range(6))
    identities = [block() for _ in range(5)]
    tags = [block() for _ in range(4)]
    values = [block() for _ in range(4)]
    def source(i):
        return p+identities[i]+s
    def target(i):
        index = (0 if i<2 else 1 if i==2 else 3)
        if family == 'relation_three_no_anchor':
            index = i
        if family.startswith('fixed_tail_'):
            index = 0 if i<3 or family=='fixed_tail_matching' else 3
        anchor = c if family=='relation_two_with_anchor' else ()
        return t+identities[i]+b+tags[index]+anchor+values[index]+e
    pairs = tuple((source(i), target(i)) for i in range(3))
    fact = target(3)
    positive = family in ('whole_value_two', 'fixed_tail_matching')
    expected = (fact,) if positive else ()
    kind = 'answer' if positive else 'absence'
    queries = [('known', source(3), kind, expected),
               ('new_prefix', block()+source(3), kind, expected),
               ('unknown', source(4), 'absence', ()),
               ('changed_prefix', block()+identities[3]+s, 'absence', ()),
               ('changed_suffix', p+identities[3]+block(), 'absence', ()),
               ('unrelated', block()+block(), 'absence', ()),
               ('two_cues', source(3)+source(4), 'absence', ())]
    return pairs, fact, queries


def evaluate(seed, family, renamed=False):
    pairs, fact, queries = fixture(seed, family)
    transform = lambda xs: tuple(1000000-x for x in xs) if renamed else tuple(xs)
    memory = TrajectoryGenerationExperiment()
    origins = {}
    def observe(payload, address, stream):
        receipt = memory.observe(transform(payload), observation_id=address, stream_id=stream)
        origins.setdefault(receipt.payload_id, []).append(address)
    for i, (source, target) in enumerate(pairs):
        observe(source, f'{i}:s', f'train:{i}')
        observe(target, f'{i}:t', f'train:{i}')
    observe(fact, 'isolated:fact', 'isolated:fact')
    cases = []
    for name, query, kind, expected in queries:
        result = checked(memory, transform(query))
        targets = tuple(transform(t) for t in expected)
        ids = {x for candidate in result['candidates'] for a, z, _ in candidate['witnesses']
               for x in (a, z)}
        ids.update(candidate['payload_id'] for candidate in result['candidates'])
        assert ids <= set(origins)
        correct = kind=='answer' and result['hypothesis'] in targets
        prior_correct = kind=='answer' and result['prior_copy']['hypothesis'] in targets
        cases.append(dict(name=name, query=transform(query), kind=kind, expected=targets,
            quality_pass=correct if kind=='answer' else not result['candidates'],
            correct_answer=correct, false_unique=result['hypothesis'] is not None
            and result['hypothesis'] not in targets,
            prior_correct_answer=prior_correct,
            prior_quality_pass=prior_correct if kind=='answer' else not result['prior_copy']['candidates'],
            prior_false_unique=result['prior_copy']['hypothesis'] is not None
            and result['prior_copy']['hypothesis'] not in targets, result=result))
    return dict(family=family, renamed=renamed,
        training_pairs=tuple((transform(s), transform(t)) for s, t in pairs),
        isolated_fact=transform(fact), cases=cases,
        root_provenance=tuple(dict(payload_id=root, observation_addresses=tuple(addresses))
                              for root, addresses in sorted(origins.items())))


def probe(seed):
    families = [evaluate(seed, family, renamed) for family in FAMILIES for renamed in (False, True)]
    cases = [c for family in families for c in family['cases']]
    counts = dict(cases=len(cases), passed=sum(c['quality_pass'] for c in cases),
        correct_answers=sum(c['correct_answer'] for c in cases),
        answer_cases=sum(c['kind']=='answer' for c in cases),
        false_unique=sum(c['false_unique'] for c in cases),
        prior_false_unique=sum(c['prior_false_unique'] for c in cases),
        prior_passed=sum(c['prior_quality_pass'] for c in cases),
        prior_correct_answers=sum(c['prior_correct_answer'] for c in cases),
        absence_empty=sum(c['kind']=='absence' and not c['result']['candidates'] for c in cases),
        absence_cases=sum(c['kind']=='absence' for c in cases))
    return dict(format='memoria.ia-frame-unmarked-field-stress-v1', seed=seed,
        integrity_status='PASS', quality_status='PASS' if counts['passed']==len(cases) else 'FAIL',
        policy_status='UNMARKED_FIELD_ROLES_UNRESOLVED', engine_changed=False,
        selectors_changed=False, native_executed=False, counts=counts, families=families)


if __name__=='__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seed', type=int, default=20261028)
    parser.add_argument('--strict-quality', action='store_true')
    args = parser.parse_args()
    report = probe(args.seed)
    print(json.dumps(report, separators=(',', ':')))
    raise SystemExit(1 if args.strict_quality and report['quality_status']!='PASS' else 0)
