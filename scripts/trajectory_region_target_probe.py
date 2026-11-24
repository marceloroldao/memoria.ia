#!/usr/bin/env python3
"""Enumerate region-local raw target occurrences without silently using global links."""
import argparse
import json
from pathlib import Path
import tempfile

from mobile_personal_proof_gate import region_rows
from mobile_region_replay import NativeProbe
from trajectory_native_bridge_probe import address
from trajectory_native_evidence_join_probe import adapt_regions, join_evidence
from trajectory_occurrence_relation_probe import fixtures, read
from trajectory_region_evidence_probe import checked, fingerprint
from trajectory_region_reply_probe import observe, link
from trajectory_response_quality_probe import encode


def enumerate_targets(rows, region, query):
    if not isinstance(region, str) or not region.strip():
        raise ValueError('explicit nonempty region required')
    if not isinstance(query, str) or not query:
        raise ValueError('nonempty raw query required')
    adapt_regions(rows)  # Validate complete addresses, source kinds and order.
    return [address(r) for r in rows if r['hierarchy_id'] == region
            and r['source_kind'] in ('user_turn', 'user_assertion') and r['text'] == query]


def resolve_region(native, rows, region, query):
    targets = enumerate_targets(rows, region, query)
    memory, origins = adapt_regions(rows)
    structural = checked(memory, encode(query, 'unicode'), region)
    before = memory.snapshot(), memory.learning_state()
    episodes = []
    for target in targets:
        evidence = read(native, query, target)  # Always a complete target address.
        if (evidence.get('answer') is not None or evidence.get('qualified') is not False
                or evidence.get('selection_used') is not False
                or evidence.get('evidence_scope') != 'exact_target'):
            raise RuntimeError('native unqualified exact-target contract violated')
        if evidence.get('repeat_question_links'):
            entry = dict(target=target, join_status='UNSUPPORTED_QUERY_ECHO_LINKS',
                         native_evidence=evidence, joined=None)
        elif evidence.get('groups_truncated') or any(g['sources_truncated'] for g in evidence['groups']):
            entry = dict(target=target, join_status='INCOMPLETE_NATIVE_EVIDENCE',
                         native_evidence=evidence, joined=None)
        else:
            entry = dict(target=target, join_status='COMPLETE', native_evidence=evidence,
                         joined=join_evidence(structural, origins, rows, evidence, target))
        episodes.append(entry)
    if before != (memory.snapshot(), memory.learning_state()):
        raise RuntimeError('regional read modified structural memory')
    return dict(region=region, query=query, raw_target_count=len(targets),
                target_status='AMBIGUOUS_RAW_MATCHES' if len(targets) > 1 else
                              'SINGLE_RAW_MATCH' if targets else 'NO_RAW_MATCH',
                selected_target=None, target_match_kind='RAW_EXACT_TEXT_OCCURRENCE',
                structural=structural, episodes=episodes, answer=None, qualified=False,
                global_fallback_used=False, factual_quality_status='NOT_EVALUATED')


def probe(library, seed):
    requested, query, _, targets, links, _ = fixtures(seed)
    scopes = list(dict.fromkeys(r['hierarchy_id'] for r in requested))
    # Generated exact-query copies do not become target occurrences.
    requested.append(dict(hierarchy_id=scopes[0], source_id='generated-query', sequence=17,
                          text=query, source_kind='assistant_generated'))
    gates, stages = {}, []
    with tempfile.TemporaryDirectory(prefix='memoria-region-target-') as directory:
        native = NativeProbe(library, Path(directory))
        try:
            for row in requested:
                observe(native, row)
            def collect():
                return [dict(r, hierarchy_id=s) for s in scopes for r in region_rows(native, s)]
            for stage in ('unlinked', 'explicit_links', 'query_echo_link'):
                additions = links if stage == 'explicit_links' else [
                    (scopes[0], 'again-q', 12, 'row-6', 7)] if stage == 'query_echo_link' else []
                for item in additions:
                    link(native, item)
                stored = collect()
                requests = [('local', scopes[0], query), ('foreign', scopes[1], query),
                            ('missing_region', 'conversation:missing', query),
                            ('new_prefix', scopes[0], 'prefix ' + query)]
                cases = [dict(name=name, result=resolve_region(native, stored, region, q))
                         for name, region, q in requests]
                local, foreign, missing, prefix = [c['result'] for c in cases]
                gates[stage + '_all_local_addresses_retained'] = [e['target'] for e in local['episodes']] == targets[:3]
                gates[stage + '_foreign_address_only'] = [e['target'] for e in foreign['episodes']] == targets[3:]
                gates[stage + '_unknown_and_prefix_do_not_fall_back'] = (
                    not missing['episodes'] and not prefix['episodes']
                    and all(not r['global_fallback_used'] for r in (missing, prefix)))
                gates[stage + '_ambiguity_not_selected'] = (
                    local['target_status'] == 'AMBIGUOUS_RAW_MATCHES'
                    and foreign['target_status'] == 'SINGLE_RAW_MATCH'
                    and all(c['result']['selected_target'] is None and c['result']['answer'] is None
                            and c['result']['qualified'] is False for c in cases))
                gates[stage + '_generated_query_excluded'] = all(
                    e['target'][1] != 'generated-query' for e in local['episodes'])
                gates[stage + '_unlinked_episode_retained'] = (
                    local['episodes'][2]['native_evidence']['status'] == 'UNRESOLVED'
                    and local['episodes'][2]['join_status'] == 'COMPLETE'
                    and not local['episodes'][2]['joined']['explicit_reply_relations'])
                gates[stage + '_native_reads_do_not_change_rows'] = stored == collect()
                gates[stage + '_incomplete_echo_preserved'] = (
                    local['episodes'][0]['join_status'] ==
                    ('UNSUPPORTED_QUERY_ECHO_LINKS' if stage == 'query_echo_link' else 'COMPLETE')
                    and (local['episodes'][0]['joined'] is None) == (stage == 'query_echo_link'))
                native.reopen()
                cold_rows = collect()
                cold = [dict(name=name, result=resolve_region(native, cold_rows, region, q))
                        for name, region, q in requests]
                gates[stage + '_complete_cold_parity'] = stored == cold_rows and cases == cold
                stages.append(dict(stage=stage, cases=cases))
        finally:
            native.close()
    if not all(gates.values()):
        raise RuntimeError('failed gates: ' + ', '.join(k for k, v in gates.items() if not v))
    return dict(seed=seed, integrity_status='PASS', integrity_passed=sum(gates.values()),
                integrity_total=len(gates), gates=gates, stages=stages, native_executed=True,
                answer=None, qualified=False, factual_quality_status='NOT_EVALUATED')


def compact(report):
    return {k: v for k, v in report.items() if k != 'stages'} | dict(
        full_report_sha256=fingerprint(report), stages=[dict(stage=s['stage'], cases=[dict(
            name=c['name'], result_sha256=fingerprint(c['result']),
            raw_target_count=c['result']['raw_target_count'], target_status=c['result']['target_status'],
            structural_roots=[x['payload_id'] for x in c['result']['structural']['packet']['candidates']],
            episodes=[dict(target=e['target'], join_status=e['join_status'],
                           native_status=e['native_evidence']['status'],
                           repeat_question_links=e['native_evidence']['repeat_question_links'],
                           explicit_reply_occurrences=e['native_evidence']['explicit_reply_occurrences'])
                      for e in c['result']['episodes']]) for c in s['cases']]) for s in report['stages']])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--library', type=Path, required=True)
    parser.add_argument('--seed', type=int, default=20261205)
    parser.add_argument('--summary', action='store_true')
    args = parser.parse_args()
    report = probe(args.library, args.seed)
    print(json.dumps(compact(report) if args.summary else report, ensure_ascii=False, indent=2))
