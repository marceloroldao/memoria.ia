#!/usr/bin/env python3
"""Identical payloads retain occurrence-local reply provenance across episodes."""
import argparse
import json
from pathlib import Path
import tempfile

from mobile_personal_proof_gate import region_rows
from mobile_region_replay import NativeProbe
from trajectory_native_bridge_probe import address
from trajectory_native_evidence_join_probe import adapt_regions, join_evidence, synthetic
from trajectory_region_evidence_probe import checked, fingerprint
from trajectory_region_reply_probe import observe, link
from trajectory_response_quality_probe import TrajectoryGenerationExperiment, encode


def fixtures(seed):
    rows, query, values = synthetic(seed)
    a = rows[0]['hierarchy_id']
    b = a + '-other'
    def row(scope, source, sequence, text):
        return dict(hierarchy_id=scope, source_id=source, sequence=sequence,
                    text=text, source_kind='user_turn')
    rows += [row(a, 'again-q', 12, query), row(a, 'again-a', 13, values[0]),
             row(a, 'unlinked-copy', 14, values[0]),
             row(a, 'unlinked-q', 15, query), row(a, 'unlinked-a', 16, values[0])]
    # Same source IDs/sequences/content in a different observed region.
    rows += [dict(r, hierarchy_id=b) for r in rows[:9]]
    targets = [(a, 'row-6', 7), (a, 'again-q', 12), (a, 'unlinked-q', 15), (b, 'row-6', 7)]
    links = [(a, 'row-7', 8, 'row-6', 7), (a, 'row-8', 9, 'row-6', 7),
             (a, 'again-a', 13, 'again-q', 12), (b, 'row-7', 8, 'row-6', 7)]
    late = (a, 'unlinked-copy', 14, 'row-6', 7)
    return rows, query, values, targets, links, late


def read(native, query, target):
    status, packet = native.call('resolve_structural_text', dict(
        hierarchy_id=target[0], query=query, mode='linked_reply_evidence', top_k=16,
        target_source_id=target[1], target_sequence=target[2]))
    if status != 2:
        raise RuntimeError('native exact-target read failed')
    return packet


def relation_flags(joined):
    return {tuple(s['origin']): s['explicit_reply_to_selected_target']
            for c in joined['candidates_with_provenance'] for s in c['occurrences']}


def probe(library, seed):
    requested, query, values, targets, links, late = fixtures(seed)
    scopes = list(dict.fromkeys(r['hierarchy_id'] for r in requested))
    gates, stages = {}, []
    with tempfile.TemporaryDirectory(prefix='memoria-occurrence-relations-') as directory:
        native = NativeProbe(library, Path(directory))
        try:
            for row in requested:
                observe(native, row)
            def collect():
                return [dict(r, hierarchy_id=scope) for scope in scopes
                        for r in region_rows(native, scope)]
            stored = collect()
            memory, origins = adapt_regions(stored)
            baseline_snapshot = memory.snapshot()
            root_texts = {memory.expand(root): root for root in origins}
            first = root_texts[encode(values[0], 'unicode')]
            rival = root_texts[encode(values[1], 'unicode')]
            structural = {scope: checked(memory, encode(query, 'unicode'), scope) for scope in scopes}
            cold_memory = TrajectoryGenerationExperiment.restore(baseline_snapshot)
            gates['restored_regional_packets_equal'] = all(
                structural[scope] == checked(cold_memory, encode(query, 'unicode'), scope) for scope in scopes)
            gates['shared_payload_reuses_address'] = len(origins[first]) == 5 and len(origins[rival]) == 2
            gates['generated_copy_excluded'] = (scopes[0], 'generated', 11) not in origins[first]
            gates['regional_witnesses_stay_local'] = all(
                all(r['hierarchy_id'] == scope for r in packet['selected_observations'])
                and {c['payload_id'] for c in packet['packet']['candidates']} == {first, rival}
                for scope, packet in structural.items())
            expected_links = []
            for stage in ('unlinked', 'separate_episode_links', 'late_local_link'):
                additions = links if stage == 'separate_episode_links' else [late] if stage == 'late_local_link' else []
                for item in additions:
                    link(native, item)
                expected_links += additions
                before = collect()
                current, current_origins = adapt_regions(before)
                gates[stage + '_raw_memory_unchanged_by_links'] = (
                    current.snapshot() == baseline_snapshot and current_origins == origins)
                cases = []
                for target in targets:
                    linked = read(native, query, target)
                    joined = join_evidence(structural[target[0]], origins, before, linked, target)
                    expected = {(s, source, sequence) for s, source, sequence, q, qseq in expected_links
                                if (s, q, qseq) == target}
                    flags = relation_flags(joined)
                    actual = {origin for origin, marked in flags.items() if marked}
                    label = f'{stage}_{targets.index(target)}'
                    gates[label + '_exact_occurrence_flags'] = actual == expected
                    gates[label + '_all_origins_retained'] = set(flags) == set(origins[first] + origins[rival])
                    gates[label + '_same_payload_does_not_propagate_relation'] = all(
                        flags[origin] == (origin in expected) for origin in origins[first])
                    gates[label + '_unqualified_and_competition_retained'] = (
                        joined['answer'] is None and joined['qualified'] is False
                        and joined['selection_used'] is False
                        and len(joined['candidates_with_provenance']) == 2)
                    # Evaluator-only counterexample; never installed in the join.
                    linked_roots = {r['payload_id'] for r in joined['explicit_reply_relations']}
                    root_only_marks = {origin for root in linked_roots for origin in origins[root]}
                    cases.append(dict(target=target, expected_linked_origins=sorted(expected),
                                      native_status=linked['status'], joined=joined,
                                      unsafe_root_only_false_annotations=len(root_only_marks - expected),
                                      joined_sha256=fingerprint(joined)))
                gates[stage + '_native_reads_do_not_change_rows'] = before == collect()
                native.reopen()
                cold_rows = collect()
                restored, restored_origins = adapt_regions(cold_rows)
                gates[stage + '_cold_raw_snapshot_equal'] = (
                    before == cold_rows and restored.snapshot() == baseline_snapshot and restored_origins == origins)
                gates[stage + '_cold_complete_join_equal'] = all(
                    case['joined'] == join_evidence(structural[case['target'][0]], restored_origins,
                                                  cold_rows, read(native, query, case['target']), case['target'])
                    for case in cases)
                stages.append(dict(stage=stage, cases=cases))
        finally:
            native.close()
    if not all(gates.values()):
        raise RuntimeError('failed gates: ' + ', '.join(k for k, v in gates.items() if not v))
    return dict(seed=seed, integrity_status='PASS', integrity_passed=sum(gates.values()),
                integrity_total=len(gates), gates=gates, stages=stages,
                shared_payload_id=first, shared_payload_origins=origins[first],
                structural_packet_sha256={s: fingerprint(p) for s, p in structural.items()},
                unsafe_root_only_false_annotations=sum(c['unsafe_root_only_false_annotations']
                    for s in stages for c in s['cases']),
                answer=None, qualified=False, factual_quality_status='NOT_EVALUATED', native_executed=True)


def compact(report):
    return {k: v for k, v in report.items() if k != 'stages'} | dict(
        full_report_sha256=fingerprint(report), stages=[dict(stage=s['stage'], cases=[dict(
            target=c['target'], expected_linked_origins=c['expected_linked_origins'],
            native_status=c['native_status'], joined_sha256=c['joined_sha256'],
            unsafe_root_only_false_annotations=c['unsafe_root_only_false_annotations'],
            candidates=c['joined']['candidates_with_provenance'],
            relations=c['joined']['explicit_reply_relations']) for c in s['cases']]) for s in report['stages']])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--library', type=Path, required=True)
    parser.add_argument('--seed', type=int, default=20261203)
    parser.add_argument('--summary', action='store_true')
    args = parser.parse_args()
    report = probe(args.library, args.seed)
    print(json.dumps(compact(report) if args.summary else report, ensure_ascii=False, indent=2))
