#!/usr/bin/env python3
"""Read-only separation of frame candidates and exact observed continuations."""
import argparse
from dataclasses import asdict
import json

from trajectory_analogy_fixed_context_probe import checked, control_fixture
from trajectory_response_quality_probe import TrajectoryGenerationExperiment


def packet(memory, query):
    query = tuple(query)
    prior = checked(memory, query)
    previous, direct = {}, {}
    for row in memory.snapshot()['observations']:
        scope = row['hierarchy_id'], row['stream_id']
        source = previous.get(scope)
        if source is not None and memory.expand(source['payload_id']) == query:
            target = direct.setdefault(row['payload_id'], dict(
                payload_id=row['payload_id'], output=memory.expand(row['payload_id']), witnesses=[]))
            target['witnesses'].append(dict(source_observation_id=source['observation_id'],
                target_observation_id=row['observation_id'], source_payload_id=source['payload_id'],
                target_payload_id=row['payload_id'], hierarchy_id=scope[0], stream_id=scope[1]))
        previous[scope] = row
    direct = tuple(direct[k] for k in sorted(direct))
    roots = {c['payload_id']: dict(c, evidence_kinds=['FRAME_MATCH']) for c in prior['candidates']}
    for target in direct:
        if target['payload_id'] not in roots:
            roots[target['payload_id']] = dict(payload_id=target['payload_id'], output=target['output'],
                evidence_kinds=[], frame_ids=(), witnesses=(), alignment_matches=())
        roots[target['payload_id']]['evidence_kinds'].append('EXACT_OBSERVED_CONTINUATION')
    candidates = tuple(roots[k] for k in sorted(roots))
    return dict(format='memoria.ia-structural-evidence-packet-v1', query=query,
        frame_read=prior, candidates=candidates, observed_continuations=direct,
        distinct_continuation_roots=len(direct),
        continuation_occurrences=sum(len(c['witnesses']) for c in direct),
        structural_status='CONFLICT' if len(candidates)>1 else 'CANDIDATE' if candidates else 'EMPTY',
        prior_structural_hypothesis=prior['hypothesis'], answer=None, qualified=False,
        authorization_status='UNQUALIFIED_STRUCTURAL_EVIDENCE',
        limitation='Adjacent observations establish sequence, not reply intent or factual truth.')


def checked_packet(memory, query):
    before = memory.snapshot(), memory.learning_state(), asdict(memory.generate(query))
    result = packet(memory, query)
    assert result == packet(TrajectoryGenerationExperiment.restore(memory.snapshot()), query)
    assert before == (memory.snapshot(), memory.learning_state(), asdict(memory.generate(query)))
    observations = {r['observation_id']: r for r in memory.snapshot()['observations']}
    for target in result['observed_continuations']:
        for witness in target['witnesses']:
            source = observations[witness['source_observation_id']]
            destination = observations[witness['target_observation_id']]
            assert source['payload_id'] == witness['source_payload_id']
            assert destination['payload_id'] == witness['target_payload_id'] == target['payload_id']
            assert memory.expand(source['payload_id']) == tuple(query)
    return result


def intervention(seed, renamed=False):
    memory, query, fact, pairs = control_fixture(seed, 'whole_tail', renamed)
    stages = []
    def capture(name):
        stages.append(dict(stage=name, unique_payloads=len({r['payload_id'] for r in memory.snapshot()['observations']}),
            observation_count=len(memory.snapshot()['observations']), packet=checked_packet(memory, query)))
    capture('initial_candidate')
    for i in range(3):
        memory.observe(pairs[0][0], observation_id=f'repeat:{i}:q', stream_id=f'repeat:{i}')
        memory.observe(pairs[0][1], observation_id=f'repeat:{i}:a', stream_id=f'repeat:{i}')
    capture('repeated_demonstration')
    memory.observe(query, observation_id='source-only', stream_id='source-only')
    capture('query_without_continuation')
    memory.observe(query, observation_id='direct:q', stream_id='direct')
    memory.observe(fact, observation_id='direct:a', stream_id='direct')
    capture('observed_exact_continuation')
    memory.observe(query, observation_id='direct-repeat:q', stream_id='direct-repeat')
    memory.observe(fact, observation_id='direct-repeat:a', stream_id='direct-repeat')
    capture('repeated_exact_continuation')
    rival = pairs[0][1]
    memory.observe(query, observation_id='rival:q', stream_id='rival')
    memory.observe(rival, observation_id='rival:a', stream_id='rival')
    capture('competing_exact_continuation')
    counts = [s['packet']['distinct_continuation_roots'] for s in stages]
    assert counts == [0, 0, 0, 1, 1, 2]
    assert stages[0]['unique_payloads'] == stages[1]['unique_payloads']
    assert stages[2]['unique_payloads'] == stages[-1]['unique_payloads']
    assert stages[-1]['packet']['structural_status'] == 'CONFLICT'
    assert all(s['packet']['answer'] is None and not s['packet']['qualified'] for s in stages)
    return dict(renamed=renamed, stages=stages)


def probe(seed):
    evaluations = [intervention(seed, renamed) for renamed in (False, True)]
    twins = []
    for family in ('whole_tail', 'latent_relation'):
        memory, query, fact, _ = control_fixture(seed, family)
        memory.observe(query, observation_id='direct:q', stream_id='direct')
        memory.observe(fact, observation_id='direct:a', stream_id='direct')
        twins.append(dict(evaluator_contract=family, packet=checked_packet(memory, query)))
    assert twins[0]['packet'] == twins[1]['packet']
    return dict(format='memoria.ia-evidence-intervention-probe-v1', seed=seed,
        integrity_status='PASS', semantic_quality_status='UNRESOLVED',
        engine_changed=False, native_executed=False, evaluations=evaluations,
        observationally_equivalent_contracts=twins,
        limitation='Exact continuation adds addressable sequence evidence; hidden field roles remain indistinguishable.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seed', type=int, default=20261107)
    args = parser.parse_args()
    print(json.dumps(probe(args.seed), separators=(',', ':')))
