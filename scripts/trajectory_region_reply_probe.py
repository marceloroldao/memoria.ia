#!/usr/bin/env python3
"""Observed region versus exact reply address, using unchanged native BDR."""
import argparse
import hashlib
import json
from pathlib import Path
import random
import tempfile

from mobile_personal_proof_gate import region_rows
from mobile_region_replay import NativeProbe


def fixtures(seed):
    rng = random.Random(seed)
    names = [f'x{rng.getrandbits(64):016x}' for _ in range(7)]
    a, b, c = ['conversation:' + x for x in names[:3]]
    query, first, rival, unknown = names[3:]
    query += '?'

    def row(scope, source, sequence, text):
        return dict(hierarchy_id=scope, source_id=source, sequence=sequence,
                    text=text, source_kind='user_turn')

    rows = [row(a, 'q', 1, query), row(a, 'a', 2, first),
            row(a, 'noise', 3, unknown), row(a, 'q', 4, query),
            row(a, 'b', 5, rival), row(b, 'q', 1, query),
            row(b, 'a', 2, rival), row(c, 'q', 1, query),
            row(c, 'a', 2, first)]
    links = [(a, 'a', 2, 'q', 1), (a, 'b', 5, 'q', 4),
             (b, 'a', 2, 'q', 1)]
    return (a, b, c), (query, first, rival, unknown), rows, links, row


def observe(probe, row):
    status, result = probe.call('observe_structural_text', row)
    if status != 0 or result['duplicate']:
        raise RuntimeError('observation failed')


def link(probe, address):
    scope, source, sequence, target, target_sequence = address
    status, result = probe.call('link_structural_reply', dict(
        hierarchy_id=scope, source_id=source, sequence=sequence,
        reply_to_source_id=target, reply_to_sequence=target_sequence))
    if status != 0 or result['qualified'] is not False:
        raise RuntimeError('explicit reply link failed')
    return result


def read(probe, query, scope, sequence=None):
    request = dict(hierarchy_id=scope, query=query,
                   mode='linked_reply_evidence', top_k=16)
    if sequence is not None:
        request.update(target_source_id='q', target_sequence=sequence)
    status, result = probe.call('resolve_structural_text', request)
    if (status != 2 or result['qualified'] is not False
            or result['answer'] is not None or result['selection_used'] is not False
            or result['groups_truncated']
            or any(g['sources_truncated'] for g in result['groups'])):
        raise RuntimeError('unqualified complete evidence contract violated')
    return result


def regional_groups(packet, scope):
    """Caller-selected provenance filter, never a native selection policy."""
    return [dict(trail_address=g['trail_address'],
                 representative_text=g['representative_text'], sources=sources)
            for g in packet['groups']
            if (sources := [s for s in g['sources'] if s['hierarchy_id'] == scope])]


def texts(packet):
    return {g['representative_text'] for g in packet['groups']}


def fingerprint(value):
    raw = json.dumps(value, sort_keys=True, separators=(',', ':')).encode()
    return hashlib.sha256(raw).hexdigest()


def probe(library, seed):
    scopes, values, rows, links, row = fixtures(seed)
    a, b, c = scopes
    query, first, rival, unknown = values
    gates, stages = {}, []
    with tempfile.TemporaryDirectory(prefix='memoria-region-reply-') as directory:
        native = NativeProbe(library, Path(directory))
        try:
            for observation in rows:
                observe(native, observation)
            unlinked = read(native, query, a, 1)
            gates['adjacency_does_not_create_link'] = not unlinked['groups']
            temporal_status, temporal = native.call('probe_structural_continuations',
                                                    dict(query=query, limit=64))
            gates['unlinked_region_has_temporal_evidence'] = (
                temporal_status == 2 and temporal['qualified'] is False
                and temporal['page']['next_offset'] is None
                and any(w['hierarchy_id'] == c and w['next']['text'] == first
                        for w in temporal['witnesses']))
            for address in links:
                link(native, address)
            gates['link_idempotent'] = link(native, links[0])['duplicate'] is True
            gates['links_do_not_change_temporal_evidence'] = (
                (temporal_status, temporal) == native.call('probe_structural_continuations',
                                                         dict(query=query, limit=64)))
            initial_trail = None

            for stage in ('initial', 'repeat', 'local_rival'):
                if stage != 'initial':
                    sequence = 6 if stage == 'repeat' else 7
                    observe(native, row(a, stage, sequence,
                                        first if stage == 'repeat' else rival))
                    link(native, (a, stage, sequence, 'q', 1))
                before = {scope: region_rows(native, scope) for scope in scopes}
                packets = dict(global_view=read(native, query, a),
                               first_target=read(native, query, a, 1),
                               same_text_later=read(native, query, a, 4),
                               other_region=read(native, query, b, 1),
                               unlinked_region=read(native, query, c, 1),
                               wrong_sequence=read(native, query, a, 2),
                               unknown_query=read(native, unknown + '?', a, 1))
                regional = regional_groups(packets['global_view'], a)
                first_trail = next(g['trail_address'] for g in
                                   packets['first_target']['groups']
                                   if g['representative_text'] == first)
                if initial_trail is None:
                    initial_trail = first_trail
                gates[stage + '_same_payload_address_retained'] = first_trail == initial_trail
                expected = {first, rival} if stage == 'local_rival' else {first}
                gates[stage + '_exact_targets'] = (
                    texts(packets['global_view']) == {first, rival}
                    and texts(packets['first_target']) == expected
                    and texts(packets['same_text_later']) == {rival}
                    and texts(packets['other_region']) == {rival}
                    and all(not packets[key]['groups'] for key in
                            ('unlinked_region', 'wrong_sequence', 'unknown_query')))
                gates[stage + '_region_retains_same_text_episodes'] = (
                    {g['representative_text'] for g in regional} == {first, rival})
                gates[stage + '_occurrences_are_not_votes'] = (
                    packets['first_target']['explicit_reply_occurrences'] ==
                    {'initial': 1, 'repeat': 2, 'local_rival': 3}[stage]
                    and packets['first_target']['distinct_reply_trails'] == len(expected)
                    and packets['first_target']['status'] ==
                    ('CONFLICT' if stage == 'local_rival' else 'CANDIDATES'))
                # A hierarchy alone is NOT a native region restriction here.
                other_header = read(native, query, c)
                gates[stage + '_hierarchy_only_is_global'] = (
                    other_header['groups'] == packets['global_view']['groups']
                    and other_header['evidence_scope'] == 'matching_targets')
                source_rows = {(scope, r['source_id'], r['sequence']): r
                               for scope, stored in before.items() for r in stored}
                gates[stage + '_source_links_addressable'] = all(
                    source_rows[(s['hierarchy_id'], s['source_id'], s['sequence'])]['reply_to']
                    == dict(source_id=s['question_source_id'], sequence=s['question_sequence'])
                    and (s['hierarchy_id'], s['question_source_id'], s['question_sequence'])
                    in source_rows
                    for packet in packets.values() for group in packet['groups']
                    for s in group['sources'])
                gates[stage + '_read_only'] = before == {
                    scope: region_rows(native, scope) for scope in scopes}
                native.reopen()
                cold = dict(global_view=read(native, query, a),
                            first_target=read(native, query, a, 1),
                            same_text_later=read(native, query, a, 4),
                            other_region=read(native, query, b, 1),
                            unlinked_region=read(native, query, c, 1),
                            wrong_sequence=read(native, query, a, 2),
                            unknown_query=read(native, unknown + '?', a, 1))
                gates[stage + '_cold_parity'] = cold == packets and before == {
                    scope: region_rows(native, scope) for scope in scopes}
                stages.append(dict(stage=stage, packets=packets,
                                   regional_groups=regional, packet_sha256=fingerprint(packets)))
        finally:
            native.close()
    if not all(gates.values()):
        raise RuntimeError('failed gates: ' + ', '.join(k for k, v in gates.items() if not v))
    return dict(seed=seed, integrity_status='PASS', integrity_passed=sum(gates.values()),
                integrity_total=len(gates), gates=gates, stages=stages,
                initial_temporal_evidence=temporal,
                answer=None, qualified=False, factual_quality_status='NOT_EVALUATED',
                evidence_boundary='observed_reply_relation_not_factual_truth')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--library', type=Path, required=True)
    parser.add_argument('--seed', type=int, default=20261129)
    args = parser.parse_args()
    print(json.dumps(probe(args.library, args.seed), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
