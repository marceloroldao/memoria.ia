#!/usr/bin/env python3
"""Join native reply provenance to unchanged structural packets, without selection."""
import argparse
from dataclasses import asdict
import json
from pathlib import Path
from random import Random
from string import ascii_lowercase, digits
import tempfile

from mobile_personal_proof_gate import region_rows
from mobile_region_replay import NativeProbe
from trajectory_boundary_length_probe import fixture
from trajectory_native_bridge_probe import adapt, address
from trajectory_region_evidence_probe import checked, fingerprint
from trajectory_region_reply_probe import observe, link
from trajectory_response_quality_probe import TrajectoryGenerationExperiment, encode


def adapt_regions(rows):
    """Reuse raw adapter validation/barriers; preserve native hierarchy IDs too."""
    original, origins = adapt(rows, 'unicode')
    memory = TrajectoryGenerationExperiment(original.config)
    for observation in original.snapshot()['observations']:
        index = int(observation['observation_id'].split(':')[1])
        source = rows[index]
        receipt = memory.observe(original.expand(observation['payload_id']),
                                 observation_id=observation['observation_id'],
                                 hierarchy_id=source['hierarchy_id'],
                                 stream_id=observation['stream_id'])
        if receipt.payload_id != observation['payload_id']:
            raise RuntimeError('raw payload address changed')
    return memory, origins


def join_evidence(structural, origins, rows, linked, target):
    """Attach explicit relations to occurrences; retain unmatched evidence too."""
    indexed = {address(r): r for r in rows}
    if len(indexed) != len(rows):
        raise ValueError('duplicate native address')
    _, validated_origins = adapt_regions(rows)
    if origins != validated_origins:
        raise ValueError('raw payload provenance mismatch')
    if (target not in indexed or tuple(structural['packet']['query']) !=
            encode(indexed[target]['text'], 'unicode')):
        raise ValueError('requires exact raw target query')
    payload_by_origin = {origin: root for root, sources in origins.items() for origin in sources}
    if len(payload_by_origin) != sum(map(len, origins.values())):
        raise ValueError('origin assigned to multiple payloads')
    for root, sources in origins.items():
        for origin in sources:
            if origin not in indexed or indexed[origin]['source_kind'] not in ('user_turn', 'user_assertion'):
                raise ValueError('unobserved or excluded origin')
    if (linked.get('answer') is not None or linked.get('qualified') is not False
            or linked.get('selection_used') is not False
            or linked.get('evidence_scope') != 'exact_target'
            or linked.get('groups_truncated') or linked.get('repeat_question_links')):
        raise ValueError('requires complete unqualified exact-target evidence')
    relations = []
    for group in linked['groups']:
        if group['sources_truncated']:
            raise ValueError('truncated origins')
        for source in group['sources']:
            origin = (source['hierarchy_id'], source['source_id'], source['sequence'])
            observed_target = (source['hierarchy_id'], source['question_source_id'],
                               source['question_sequence'])
            row = indexed.get(origin)
            if (origin not in payload_by_origin or observed_target != target
                    or target not in indexed or row['text'] != source['text']
                    or source['text'] != group['representative_text']
                    or row.get('reply_to') != dict(source_id=target[1], sequence=target[2])):
                raise ValueError('reply provenance mismatch')
            relations.append(dict(payload_id=payload_by_origin[origin], origin=origin,
                                  target=target, native_trail_address=group['trail_address']))
    linked_origins = {r['origin'] for r in relations}
    candidates = [dict(payload_id=c['payload_id'], occurrences=[
        dict(origin=origin, explicit_reply_to_selected_target=origin in linked_origins)
        for origin in origins.get(c['payload_id'], ())])
        for c in structural['packet']['candidates']]
    roots = {c['payload_id'] for c in candidates}
    if not roots <= origins.keys():
        raise ValueError('structural candidate without observed provenance')
    return dict(structural=structural, candidates_with_provenance=candidates,
                explicit_reply_relations=relations,
                linked_roots_outside_structural_candidates=sorted({r['payload_id'] for r in relations} - roots),
                requested_target=target, answer=None, qualified=False, selection_used=False)


def synthetic(seed):
    data = fixture(seed, True, True)
    payloads = [xs for pair in data['training_pairs'][:3] for xs in pair]
    query = data['queries'][0][1]
    payloads += [query, data['fact'], data['rival']]
    symbols = sorted({x for xs in payloads for x in xs})
    # Native tokenizer admits ASCII and Latin-1; use one raw character per symbol.
    alphabet = list(ascii_lowercase + digits + ''.join(map(chr, range(0xE0, 0x100))))
    Random(seed).shuffle(alphabet)
    if len(symbols) > len(alphabet):
        raise ValueError('fixture exceeds injective alphabet')
    mapping = dict(zip(symbols, alphabet))
    text = lambda xs: ''.join(mapping[x] for x in xs)
    scope = f'conversation:opaque-{seed}'
    rows = [dict(hierarchy_id=scope, source_id=f'row-{i}', sequence=i+1,
                 text=text(xs), source_kind='user_turn') for i, xs in enumerate(payloads)]
    rows += [dict(hierarchy_id=scope, source_id='outside', sequence=10,
                  text='unrelated-opaque-value', source_kind='user_turn'),
             dict(hierarchy_id=scope, source_id='generated', sequence=11,
                  text=text(data['fact']), source_kind='assistant_generated')]
    return rows, text(query), (text(data['fact']), text(data['rival']))


def probe(library, seed):
    rows, query, expected_texts = synthetic(seed)
    scope = rows[0]['hierarchy_id']
    target = address(rows[6])
    gates, stages = {}, []
    baseline = None
    with tempfile.TemporaryDirectory(prefix='memoria-evidence-join-') as directory:
        native = NativeProbe(library, Path(directory))
        try:
            for row in rows:
                observe(native, row)
            for stage, source_index in [('unlinked', None), ('one_link', 7),
                                        ('rival_link', 8), ('outside_structural', 9)]:
                if source_index is not None:
                    source = rows[source_index]
                    link(native, (scope, source['source_id'], source['sequence'], target[1], target[2]))
                stored = [dict(r, hierarchy_id=scope) for r in region_rows(native, scope)]
                memory, origins = adapt_regions(stored)
                before = memory.snapshot(), memory.learning_state(), asdict(memory.generate(encode(query, 'unicode')))
                structural = checked(memory, encode(query, 'unicode'), scope)
                status, linked = native.call('resolve_structural_text', dict(
                    hierarchy_id=scope, query=query, mode='linked_reply_evidence', top_k=16,
                    target_source_id=target[1], target_sequence=target[2]))
                if status != 2:
                    raise RuntimeError('native evidence read failed')
                joined = join_evidence(structural, origins, stored, linked, target)
                if baseline is None:
                    baseline = structural
                gates[stage + '_structural_packet_unchanged_by_links'] = structural == baseline
                gates[stage + '_competing_structural_roots_retained'] = {
                    tuple(c['output']) for c in structural['packet']['candidates']
                } == {encode(t, 'unicode') for t in expected_texts}
                count = {'unlinked': 0, 'one_link': 1, 'rival_link': 2, 'outside_structural': 3}[stage]
                gates[stage + '_explicit_relations_only'] = len(joined['explicit_reply_relations']) == count
                gates[stage + '_outside_relation_retained'] = len(
                    joined['linked_roots_outside_structural_candidates']) == (stage == 'outside_structural')
                gates[stage + '_generated_origin_excluded'] = address(rows[-1]) not in {
                    origin for sources in origins.values() for origin in sources}
                gates[stage + '_read_only'] = before == (
                    memory.snapshot(), memory.learning_state(), asdict(memory.generate(encode(query, 'unicode'))))
                gates[stage + '_native_rows_read_only'] = stored == [
                    dict(r, hierarchy_id=scope) for r in region_rows(native, scope)]
                native.reopen()
                cold_rows = [dict(r, hierarchy_id=scope) for r in region_rows(native, scope)]
                cold_memory, cold_origins = adapt_regions(cold_rows)
                cold_structural = checked(cold_memory, encode(query, 'unicode'), scope)
                cold_status, cold_linked = native.call('resolve_structural_text', dict(
                    hierarchy_id=scope, query=query, mode='linked_reply_evidence', top_k=16,
                    target_source_id=target[1], target_sequence=target[2]))
                gates[stage + '_cold_join_parity'] = cold_status == status and joined == join_evidence(
                    cold_structural, cold_origins, cold_rows, cold_linked, target)
                stages.append(dict(stage=stage, structural_sha256=fingerprint(structural),
                                   joined_sha256=fingerprint(joined), joined=joined))
        finally:
            native.close()
    if not all(gates.values()):
        raise RuntimeError('failed gates: ' + ', '.join(k for k, v in gates.items() if not v))
    return dict(seed=seed, integrity_status='PASS', gates=gates,
                integrity_passed=sum(gates.values()), integrity_total=len(gates), stages=stages,
                native_executed=True, answer=None, qualified=False, factual_quality_status='NOT_EVALUATED')


def compact(report):
    return {k: v for k, v in report.items() if k != 'stages'} | dict(
        full_report_sha256=fingerprint(report), stages=[dict(
            stage=s['stage'], structural_sha256=s['structural_sha256'], joined_sha256=s['joined_sha256'],
            candidates=s['joined']['candidates_with_provenance'],
            relations=s['joined']['explicit_reply_relations'],
            outside_roots=s['joined']['linked_roots_outside_structural_candidates']) for s in report['stages']])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--library', type=Path, required=True)
    parser.add_argument('--seed', type=int, default=20261201)
    parser.add_argument('--summary', action='store_true')
    args = parser.parse_args()
    report = probe(args.library, args.seed)
    print(json.dumps(compact(report) if args.summary else report, ensure_ascii=False, indent=2))
