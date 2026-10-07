#!/usr/bin/env python3
"""Addressable paginated reply witnesses, including echoes, without answer selection."""
import argparse
import json
from pathlib import Path
import tempfile

from mobile_personal_proof_gate import region_rows
from mobile_region_replay import NativeProbe
from trajectory_native_bridge_probe import address
from trajectory_native_evidence_join_probe import adapt_regions
from trajectory_occurrence_relation_probe import fixtures, read
from trajectory_region_evidence_probe import checked, fingerprint
from trajectory_region_reply_probe import observe, link
from trajectory_region_target_probe import enumerate_targets
from trajectory_response_quality_probe import encode

HEADERS = ('explicit_reply_occurrences', 'distinct_reply_trails',
           'embedded_question_links', 'repeat_question_links')


def collect_pages(native, query, limit):
    if type(limit) is not int or not 1 <= limit <= 64:
        raise ValueError('page size must be an integer from 1 to 64')
    offset, summary, witnesses, identities, pages = 0, None, [], set(), 0
    while True:
        status, packet = native.call('probe_structural_linked_replies',
                                     dict(query=query, offset=offset, limit=limit))
        if (status != 2 or packet.get('qualified') is not False
                or packet.get('answer') is not None
                or packet.get('selection_used') is not False or packet.get('relation') != 'reply_to'):
            raise ValueError('unqualified reply-witness contract violated')
        header = {k: packet[k] for k in HEADERS}
        if any(type(v) is not int or v < 0 for v in header.values()):
            raise ValueError('invalid witness totals')
        if summary is None:
            summary = header
        elif header != summary:
            raise ValueError('witness totals changed during pagination')
        page = packet['page']
        returned = len(packet['witnesses'])
        if (type(page['offset']) is not int or type(page['returned']) is not int
                or page['offset'] != offset or page['returned'] != returned or returned > limit):
            raise ValueError('page offset or count mismatch')
        for witness in packet['witnesses']:
            q, r = witness['question'], witness['reply']
            if (not isinstance(witness['hierarchy_id'], str) or not witness['hierarchy_id']
                    or any(not isinstance(v['source_id'], str) or not v['source_id']
                           or type(v['sequence']) is not int or v['sequence'] < 0 for v in (q, r))
                    or type(r['repeats_query']) is not bool):
                raise ValueError('invalid witness address or echo flag')
            identity = (witness['hierarchy_id'], r['source_id'], r['sequence'])
            if identity in identities:
                raise ValueError('duplicate reply occurrence across pages')
            identities.add(identity)
            witnesses.append(witness)
        pages += 1
        next_offset = page['next_offset']
        if next_offset is None:
            break
        if type(next_offset) is not int or next_offset != offset + returned or next_offset <= offset:
            raise ValueError('nonprogressing or skipped witness page')
        if next_offset >= summary['explicit_reply_occurrences']:
            raise ValueError('continuation beyond declared total')
        offset = next_offset
    if len(witnesses) != summary['explicit_reply_occurrences']:
        raise ValueError('incomplete witness pagination')
    if sum(w['reply']['repeats_query'] is True for w in witnesses) != summary['repeat_question_links']:
        raise ValueError('echo count mismatch')
    return dict(summary=summary, witnesses=witnesses, page_count=pages,
                transport_scope='global_query_witness_pages')


def join_pages(rows, region, query, structural, collection):
    targets = enumerate_targets(rows, region, query)
    _, origins = adapt_regions(rows)
    root_by_origin = {origin: root for root, sources in origins.items() for origin in sources}
    indexed = {address(r): r for r in rows}
    selected, excluded = [], 0
    for witness in collection['witnesses']:
        q, r = witness['question'], witness['reply']
        target = (witness['hierarchy_id'], q['source_id'], q['sequence'])
        if target not in targets:
            excluded += 1
            continue
        origin = (witness['hierarchy_id'], r['source_id'], r['sequence'])
        source = indexed.get(origin)
        if (origin not in root_by_origin or source['text'] != r['text']
                or q['match'] != 'EXACT'
                or source['source_kind'] != r['source_kind']
                or indexed[target]['source_kind'] != q['source_kind']
                or source.get('reply_to') != dict(source_id=target[1], sequence=target[2])):
            raise ValueError('witness does not match observed address/text/relation')
        selected.append(dict(origin=origin, target=target, payload_id=root_by_origin[origin],
                             native_query_echo=r['repeats_query'],
                             native_trail_address=r['trail_address']))
    expected = {address(row) for row in rows
                if row['source_kind'] in ('user_turn', 'user_assertion') and row.get('reply_to')
                and (row['hierarchy_id'], row['reply_to']['source_id'], row['reply_to']['sequence']) in targets}
    if {r['origin'] for r in selected} != expected:
        raise ValueError('selected-target relation coverage incomplete')
    candidate_roots = {c['payload_id'] for c in structural['packet']['candidates']}
    if not candidate_roots <= origins.keys():
        raise ValueError('candidate lacks observed raw provenance')
    if structural['requested_region'] != region or tuple(structural['packet']['query']) != encode(query, 'unicode'):
        raise ValueError('structural scope/query mismatch')
    episodes = []
    for target in targets:
        relations = [r for r in selected if r['target'] == target]
        marked = {r['origin'] for r in relations}
        episodes.append(dict(target=target, relations=relations,
            candidates=[dict(payload_id=root, occurrences=[dict(origin=origin,
                explicit_reply_to_selected_target=origin in marked) for origin in origins[root]])
                for root in sorted(candidate_roots)],
            linked_roots_outside_structural_candidates=sorted({r['payload_id'] for r in relations} - candidate_roots)))
    return dict(region=region, structural=structural, episodes=episodes,
                excluded_other_target_witnesses=excluded,
                evidence_scope='exact_observed_target_addresses', selected_target=None,
                answer=None, qualified=False, selection_used=False,
                factual_quality_status='NOT_EVALUATED')


def resolve_paged_region(native, rows, region, query, limit=64):
    """Explicit witness transport; no native request when local targets are absent."""
    targets = enumerate_targets(rows, region, query)
    if type(limit) is not int or not 1 <= limit <= 64:
        raise ValueError('page size must be an integer from 1 to 64')
    memory, _ = adapt_regions(rows)
    structural = checked(memory, encode(query, 'unicode'), region)
    collection = collect_pages(native, query, limit) if targets else dict(
        witnesses=[], page_count=0, summary={k: 0 for k in HEADERS},
        transport_scope='not_requested_no_local_raw_targets')
    return dict(view=join_pages(rows, region, query, structural, collection),
                transport=dict(scope=collection['transport_scope'], page_count=collection['page_count'],
                               page_size=limit, summary=collection['summary']))


def probe(library, seed):
    rows, query, values, targets, links, _ = fixtures(seed)
    scope = targets[0][0]
    for i in range(20):
        source, sequence = f'copy-{i}', 17 + i
        rows.append(dict(hierarchy_id=scope, source_id=source, sequence=sequence,
                         text=values[0], source_kind='user_turn'))
        links.append((scope, source, sequence, targets[0][1], targets[0][2]))
    # Grouped native evidence omits the echo source; witness API retains it.
    links.append((scope, 'again-q', 12, targets[0][1], targets[0][2]))
    scopes = list(dict.fromkeys(r['hierarchy_id'] for r in rows))
    # Keep each scope ordered after adding copies to an earlier scope.
    rows = [r for s in scopes for r in rows if r['hierarchy_id'] == s]
    gates, evaluations = {}, []
    with tempfile.TemporaryDirectory(prefix='memoria-paged-relations-') as directory:
        native = NativeProbe(library, Path(directory))
        try:
            for row in rows:
                observe(native, row)
            for relation in links:
                link(native, relation)
            def collect():
                return [dict(r, hierarchy_id=s) for s in scopes for r in region_rows(native, s)]
            stored = collect()
            memory, _ = adapt_regions(stored)
            structural = {s: checked(memory, encode(query, 'unicode'), s) for s in scopes}
            grouped = read(native, query, targets[0])
            gates['original_grouped_packet_has_omitted_echo_and_truncated_sources'] = (
                grouped['repeat_question_links'] == 1 and any(g['sources_truncated'] for g in grouped['groups']))
            reference = None
            for limit in (1, 7, 64):
                collection = collect_pages(native, query, limit)
                views = [join_pages(stored, s, query, structural[s], collection) for s in scopes]
                if reference is None:
                    reference = views
                gates[f'{limit}_page_size_does_not_change_scoped_results'] = views == reference
                gates[f'{limit}_all_global_witnesses_collected'] = len(collection['witnesses']) == 25
                gates[f'{limit}_local_counts_include_echo_and_every_copy'] = [
                    len(e['relations']) for e in views[0]['episodes']] == [23, 1, 0]
                gates[f'{limit}_echo_source_is_addressed'] = [
                    r['origin'] for e in views[0]['episodes'] for r in e['relations'] if r['native_query_echo']
                ] == [(scope, 'again-q', 12)]
                gates[f'{limit}_foreign_witness_excluded_from_local_evidence'] = (
                    views[0]['excluded_other_target_witnesses'] == 1
                    and len(views[1]['episodes'][0]['relations']) == 1)
                gates[f'{limit}_unlinked_episode_retained'] = not views[0]['episodes'][2]['relations']
                gates[f'{limit}_native_reads_do_not_change_rows'] = stored == collect()
                native.reopen()
                cold_rows = collect()
                cold_memory, _ = adapt_regions(cold_rows)
                cold_structural = {s: checked(cold_memory, encode(query, 'unicode'), s) for s in scopes}
                cold_collection = collect_pages(native, query, limit)
                cold_views = [join_pages(cold_rows, s, query, cold_structural[s], cold_collection) for s in scopes]
                gates[f'{limit}_full_cold_parity'] = (
                    cold_rows == stored and cold_collection == collection and cold_views == views)
                evaluations.append(dict(page_size=limit, collection=collection, views=views,
                                        scoped_results_sha256=fingerprint(views)))
        finally:
            native.close()
    if not all(gates.values()):
        raise RuntimeError('failed gates: ' + ', '.join(k for k, v in gates.items() if not v))
    return dict(seed=seed, integrity_status='PASS', integrity_passed=sum(gates.values()),
                integrity_total=len(gates), gates=gates, evaluations=evaluations,
                native_executed=True, answer=None, qualified=False, factual_quality_status='NOT_EVALUATED')


def compact(report):
    return {k: v for k, v in report.items() if k != 'evaluations'} | dict(
        full_report_sha256=fingerprint(report), evaluations=[dict(
            page_size=e['page_size'], page_count=e['collection']['page_count'],
            summary=e['collection']['summary'], scoped_results_sha256=e['scoped_results_sha256'],
            scopes=[dict(region=v['region'], excluded=v['excluded_other_target_witnesses'],
                         episodes=[dict(target=x['target'], relations=x['relations'],
                                        outside_roots=x['linked_roots_outside_structural_candidates'])
                                   for x in v['episodes']]) for v in e['views']]) for e in report['evaluations']])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--library', type=Path, required=True)
    parser.add_argument('--seed', type=int, default=20261207)
    parser.add_argument('--summary', action='store_true')
    args = parser.parse_args()
    report = probe(args.library, args.seed)
    print(json.dumps(compact(report) if args.summary else report, ensure_ascii=False, indent=2))
