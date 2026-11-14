#!/usr/bin/env python3
"""Root-scoped copy incompatibility never excludes a globally unknown query cut."""
import argparse
from dataclasses import asdict
from hashlib import blake2b, sha256
import json

from trajectory_analogy_boundary_probe import extract
from trajectory_analogy_frame_probe import occurrences
from trajectory_boundary_candidates_probe import checked_boundary_packet
from trajectory_boundary_length_probe import fixture, layout
from trajectory_response_quality_probe import TrajectoryGenerationExperiment
from trajectory_separator_ablation_probe import counts, score


def compare(frame, slots, target):
    """Compare one observed root to one frame/cut; never judge reply or truth."""
    locations = tuple(occurrences(slot, target) for slot in slots)
    if any(not points for points in locations):
        return dict(status='INCOMPATIBLE_OBSERVED_ROOT', reason='MISSING_EXACT_COPY', locations=locations)
    if any(len(points) != 1 for points in locations):
        return dict(status='INCOMPATIBLE_OBSERVED_ROOT', reason='NONUNIQUE_EXACT_COPY', locations=locations)
    a, b = frame['target_order']
    if locations[a][0] + len(slots[a]) > locations[b][0]:
        return dict(status='INCOMPATIBLE_OBSERVED_ROOT', reason='COPY_ORDER_OR_OVERLAP', locations=locations)
    head = frame['target_prefix'] + slots[a] + frame['target_between'] + slots[b] + frame['target_bridge']
    if extract(target, head, frame['target_suffix']) is None:
        return dict(status='INCOMPATIBLE_OBSERVED_ROOT', reason='FIXED_LAYOUT_OR_VALUE_MISMATCH', locations=locations)
    return dict(status='SUPPORTED_OBSERVED_ROOT', reason='EXACT_COPIES_AND_LAYOUT', locations=locations)


def compatibility(memory, packet):
    """Observe compatibility for each cut while retaining every root and cut."""
    rows = memory.snapshot()['observations']
    root_rows = {}
    for row in rows:
        root_rows.setdefault(row['payload_id'], []).append(dict(row))
    frames = {frame['frame_id']: frame for frame in packet['boundary_frames']}
    grouped = {}
    for cut in packet['boundary_support']:
        frame = frames[cut['frame_id']]
        identity = layout(frame)
        layout_id = blake2b(repr(identity).encode(), digest_size=16).hexdigest()
        key = layout_id, cut['source_position'], cut['slots']
        if key in grouped:
            assert grouped[key]['supported_roots'] == cut['candidate_roots']
            grouped[key]['frame_ids'].append(frame['frame_id'])
            continue
        comparisons = []
        # Restrict root diagnostics to the observed destination envelope. A
        # mismatch is conditional on this root, frame and cut, not on all data.
        for root in sorted(root_rows):
            target = memory.expand(root)
            if not (target[:len(frame['target_prefix'])] == frame['target_prefix']
                    and target[-len(frame['target_suffix']):] == frame['target_suffix']):
                continue
            comparisons.append(dict(payload_id=root, output=target, occurrences=root_rows[root],
                                    **compare(frame, cut['slots'], target)))
        supported = tuple(c['payload_id'] for c in comparisons if c['status'] == 'SUPPORTED_OBSERVED_ROOT')
        assert supported == cut['candidate_roots']
        grouped[key] = dict(layout_id=layout_id, layout=identity, frame_ids=[frame['frame_id']],
                            source_position=cut['source_position'], slots=cut['slots'],
                            status='SUPPORTED' if supported else 'UNKNOWN', supported_roots=supported,
                            comparisons=comparisons, cut_excluded=False,
                            reason='OBSERVED_COPY_MATCH' if supported else 'NO_OBSERVED_MATCH_NOT_AN_EXCLUSION')
    return dict(format='memoria.ia-cut-root-compatibility-v1', cuts=tuple(grouped[k] for k in sorted(grouped)),
                candidate_roots=tuple(c['payload_id'] for c in packet['candidates']),
                excluded_cuts=(), answer=None, qualified=False,
                limitation='Incompatibility concerns one observed root under one frame/cut. '
                           'It cannot exclude unseen roots, establish reply intent or factual truth.')


def checked(memory, query):
    before = memory.snapshot(), memory.learning_state(), asdict(memory.generate(query))
    packet = checked_boundary_packet(memory, query)
    result = compatibility(memory, packet)
    restored = TrajectoryGenerationExperiment.restore(memory.snapshot())
    assert result == compatibility(restored, checked_boundary_packet(restored, query))
    assert before == (memory.snapshot(), memory.learning_state(), asdict(memory.generate(query)))
    return packet, result


def evaluate(seed, joined, renamed=False):
    data = fixture(seed, True, joined, renamed)
    memory = TrajectoryGenerationExperiment()

    def pair(index, address):
        a, b = data['training_pairs'][index]
        memory.observe(a, observation_id=address + ':source', stream_id=address)
        memory.observe(b, observation_id=address + ':target', stream_id=address)

    for i in range(3):
        pair(i, f'train:{i}')
    memory.observe(data['fact'], observation_id='fact', stream_id='fact')
    stages = []

    def capture(name, conflict=False):
        cases = []
        for query_name, query in (data['queries'][0], data['queries'][2]):
            expected = ((data['fact'], data['rival']) if conflict else (data['fact'],)) if query_name == 'reserved' else ()
            kind = 'conflict' if len(expected) > 1 else 'answer' if expected else 'absence'
            packet, diagnostic = checked(memory, query)
            assert not packet['observed_continuations']
            cases.append(dict(name=query_name, query=query, kind=kind, expected=expected,
                              packet=packet, diagnostic=diagnostic, **score(packet, kind, expected)))
        stages.append(dict(name=name, cases=cases, provenance=memory.snapshot()['observations']))

    capture('first_root')
    pair(0, 'repeat:pair')
    capture('repeated_demonstration')
    memory.observe(data['rival'], observation_id='late:rival', stream_id='late:rival')
    capture('late_root_other_cut', conflict=True)
    memory.observe(data['rival'], observation_id='repeat:rival', stream_id='repeat:rival')
    capture('repeated_rival', conflict=True)
    return dict(joined_target_copies=joined, renamed=renamed, fixture=data, stages=stages)


def probe(seed):
    evaluations = [evaluate(seed, joined, renamed) for joined in (False, True) for renamed in (False, True)]
    totals = counts([c for ev in evaluations for stage in ev['stages'] for c in stage['cases']])
    return dict(format='memoria.ia-cut-compatibility-probe-v1', seed=seed,
                integrity_status='PASS', structural_quality_status='PASS' if totals['passed'] == totals['cases'] else 'FAIL',
                semantic_quality_status='UNQUALIFIED', counts=totals, evaluations=evaluations,
                engine_changed=False, prior_selectors_changed=False, native_executed=False,
                limitation='Separate opaque sequential diagnostic; adds no negative-observation API, '
                           'cut-exclusion rule or answer policy. Historical failures remain unresolved.')


def compact_report(report):
    result = {k: v for k, v in report.items() if k != 'evaluations'}
    result['full_report_sha256'] = sha256((json.dumps(report, separators=(',', ':')) + '\n').encode()).hexdigest()
    result['evaluations'] = []
    for ev in report['evaluations']:
        stages = []
        for stage in ev['stages']:
            cases = []
            for c in stage['cases']:
                d = c['diagnostic']
                cases.append(dict(name=c['name'], quality_pass=c['quality_pass'],
                                  candidate_roots=d['candidate_roots'], excluded_cuts=d['excluded_cuts'],
                                  cuts=[dict(layout_id=cut['layout_id'], source_position=cut['source_position'],
                                             status=cut['status'], supported_roots=cut['supported_roots'],
                                             root_comparisons=[dict(payload_id=x['payload_id'], status=x['status'],
                                                                    reason=x['reason'], observation_ids=[r['observation_id'] for r in x['occurrences']])
                                                               for x in cut['comparisons']]) for cut in d['cuts']]))
            stages.append(dict(name=stage['name'], cases=cases))
        result['evaluations'].append(dict(joined_target_copies=ev['joined_target_copies'], renamed=ev['renamed'], stages=stages))
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seed', type=int, default=20261125)
    parser.add_argument('--summary', action='store_true')
    parser.add_argument('--strict-quality', action='store_true')
    args = parser.parse_args()
    report = probe(args.seed)
    print(json.dumps(compact_report(report) if args.summary else report, separators=(',', ':')))
    raise SystemExit(1 if args.strict_quality and report['structural_quality_status'] != 'PASS' else 0)
