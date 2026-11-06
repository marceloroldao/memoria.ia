#!/usr/bin/env python3
"""Caller-selected observed regions route roots without supplying hidden reply intent."""
import argparse
from dataclasses import asdict
from hashlib import sha256
import json

from trajectory_boundary_length_probe import fixture
from trajectory_cut_compatibility_probe import checked as checked_compatibility
from trajectory_response_quality_probe import TrajectoryGenerationExperiment
from trajectory_separator_ablation_probe import counts, score


def region_view(memory, region):
    if region is not None and (not isinstance(region, str) or not region.strip()):
        raise ValueError('region must be a nonempty observed ID or None')
    selected = [r for r in memory.snapshot()['observations'] if region is None or r['hierarchy_id'] == region]
    view = TrajectoryGenerationExperiment(memory.config)
    for row in selected:
        receipt = view.observe(memory.expand(row['payload_id']), observation_id=row['observation_id'],
                               hierarchy_id=row['hierarchy_id'], stream_id=row['stream_id'])
        assert receipt.payload_id == row['payload_id']
    assert view.snapshot()['observations'] == selected
    return view


def checked(memory, query, region=None):
    before = memory.snapshot(), memory.learning_state(), asdict(memory.generate(query))
    view = region_view(memory, region)
    packet, diagnostic = checked_compatibility(view, query)
    result = dict(format='memoria.ia-region-evidence-view-v1', requested_region=region,
                  selected_observations=view.snapshot()['observations'], packet=packet, diagnostic=diagnostic,
                  answer=None, qualified=False,
                  limitation='Region is explicit observed provenance selected by the caller; not learned reply intent or truth.')
    cold = TrajectoryGenerationExperiment.restore(memory.snapshot())
    cold_view = region_view(cold, region)
    cold_packet, cold_diagnostic = checked_compatibility(cold_view, query)
    assert packet == cold_packet and diagnostic == cold_diagnostic
    roots = {row['payload_id'] for row in view.snapshot()['observations']}
    assert {c['payload_id'] for c in packet['candidates']} <= roots
    assert all(region is None or row['hierarchy_id'] == region for row in result['selected_observations'])
    assert before == (memory.snapshot(), memory.learning_state(), asdict(memory.generate(query)))
    return result


def fingerprint(value):
    return sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def evaluate(seed, renamed=False):
    data = fixture(seed, True, True, renamed)
    regions = {name: f'capture:{seed * 7 + i if not renamed else 900000 - seed * 7 - i}'
               for i, name in enumerate(('left', 'right', 'isolated', 'unknown'))}
    memory = TrajectoryGenerationExperiment()

    def observe(payload, address, stream, region):
        memory.observe(payload, observation_id=address, stream_id=stream, hierarchy_id=region)

    def pair(i, address, region):
        source, target = data['training_pairs'][i]
        observe(source, address + ':source', address, region)
        observe(target, address + ':target', address, region)

    for name in ('left', 'right'):
        for i in range(3):
            pair(i, f'{name}:train:{i}', regions[name])
    observe(data['fact'], 'left:fact', 'isolated-fact', regions['left'])
    observe(data['rival'], 'right:fact', 'isolated-fact', regions['right'])
    observe(data['fact'], 'isolated:fact', 'isolated-fact', regions['isolated'])
    query = data['queries'][0][1]
    stages = []

    def capture(name, late=False):
        requests = (
            ('global', None, query, (data['fact'], data['rival'])),
            ('left', regions['left'], query, (data['fact'], data['rival']) if late else (data['fact'],)),
            ('right', regions['right'], query, (data['rival'],)),
            ('isolated_root_without_frames', regions['isolated'], query, ()),
            ('unknown_region', regions['unknown'], query, ()),
            ('unknown_body', regions['left'], data['queries'][2][1], ()),
        )
        cases = []
        for label, region, q, expected in requests:
            result = checked(memory, q, region)
            kind = 'conflict' if len(expected) > 1 else 'answer' if expected else 'absence'
            assert not result['packet']['observed_continuations']
            cases.append(dict(name=label, region=region, query=q, expected=expected, kind=kind,
                              result=result, **score(result['packet'], kind, expected)))
        rows = memory.snapshot()['observations']
        stages.append(dict(name=name, provenance=rows, unique_payloads=len({r['payload_id'] for r in rows}), cases=cases))

    capture('regions_with_competing_roots')
    # Independent engines get exactly equal observations and the same region.
    # Different desired roles exist only in the evaluator after both reads.
    twins = [TrajectoryGenerationExperiment.restore(memory.snapshot()) for _ in range(2)]
    results = [checked(m, query, regions['left']) for m in twins]
    assert twins[0].snapshot() == twins[1].snapshot() and results[0] == results[1]
    contracts = (('intended_reply', data['fact']), ('adjacent_unrelated_event', None))
    twin_cases = [dict(evaluator_role=role, expected=expected, actual=result['answer'],
                       quality_pass=result['answer'] == expected,
                       structural_proposal=result['packet']['prior_structural_hypothesis'],
                       proposal_pass=result['packet']['prior_structural_hypothesis'] == expected,
                       proposal_false=result['packet']['prior_structural_hypothesis'] is not None
                                      and result['packet']['prior_structural_hypothesis'] != expected)
                  for (role, expected), result in zip(contracts, results)]
    twin = dict(snapshot_fingerprints=tuple(fingerprint(m.snapshot()) for m in twins),
                result_fingerprints=tuple(map(fingerprint, results)), identical=True,
                query=query, region=regions['left'], result=results[0], cases=twin_cases)
    pair(0, 'right:repeat', regions['right'])
    observe(data['rival'], 'right:repeat-fact', 'repeat-fact', regions['right'])
    capture('repeated_foreign_evidence')
    # Reuse the globally existing root at a new local occurrence address.
    observe(data['rival'], 'left:late-rival', 'late-rival', regions['left'])
    capture('late_same_region_rival', late=True)
    return dict(renamed=renamed, fixture=data, regions=regions, stages=stages, hidden_role_twins=twin)


def probe(seed):
    evaluations = [evaluate(seed, renamed) for renamed in (False, True)]
    totals = counts([c for ev in evaluations for stage in ev['stages'] for c in stage['cases']])
    twins = [c for ev in evaluations for c in ev['hidden_role_twins']['cases']]
    reply = dict(cases=len(twins), passed=sum(c['quality_pass'] for c in twins),
                 false_answers=sum(c['actual'] is not None and not c['quality_pass'] for c in twins))
    comparator = dict(cases=len(twins), passed=sum(c['proposal_pass'] for c in twins),
                      false_answers=sum(c['proposal_false'] for c in twins))
    return dict(format='memoria.ia-region-evidence-probe-v1', seed=seed, integrity_status='PASS',
                structural_quality_status='PASS' if totals['passed'] == totals['cases'] else 'FAIL',
                semantic_quality_status='FAIL' if reply['passed'] != reply['cases'] else 'PASS',
                counts=totals, reply_role_counts=reply, unsafe_evaluator_comparator=comparator,
                evaluations=evaluations, engine_changed=False, prior_selectors_changed=False, native_executed=False,
                limitation='Explicit caller-selected hierarchy metadata and exact copied frames; '
                           'not autonomous situation discovery, negative evidence or semantic answer selection.')


def compact_report(report):
    result = {k: v for k, v in report.items() if k != 'evaluations'}
    result['full_report_sha256'] = sha256((json.dumps(report, separators=(',', ':')) + '\n').encode()).hexdigest()
    result['evaluations'] = []
    for ev in report['evaluations']:
        stages = []
        for stage in ev['stages']:
            cases = []
            for c in stage['cases']:
                result_view = c['result']
                packet = result_view['packet']
                cases.append(dict(name=c['name'], region=c['region'], quality_pass=c['quality_pass'],
                                  candidate_roots=[x['payload_id'] for x in packet['candidates']],
                                  structural_hypothesis=packet['prior_structural_hypothesis'],
                                  selected_observation_ids=[r['observation_id'] for r in result_view['selected_observations']],
                                  selected_regions=sorted({r['hierarchy_id'] for r in result_view['selected_observations']}),
                                  result_sha256=fingerprint(result_view)))
            stages.append(dict(name=stage['name'], unique_payloads=stage['unique_payloads'], cases=cases))
        twins = ev['hidden_role_twins']
        result['evaluations'].append(dict(renamed=ev['renamed'], regions=ev['regions'], stages=stages,
                                          hidden_role_twins={k: v for k, v in twins.items() if k != 'result'}))
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seed', type=int, default=20261127)
    parser.add_argument('--summary', action='store_true')
    parser.add_argument('--strict-quality', action='store_true')
    args = parser.parse_args()
    report = probe(args.seed)
    print(json.dumps(compact_report(report) if args.summary else report, separators=(',', ':')))
    raise SystemExit(1 if args.strict_quality and (report['structural_quality_status'] != 'PASS'
                                                 or report['semantic_quality_status'] != 'PASS') else 0)
