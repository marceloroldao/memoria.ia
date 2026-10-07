#!/usr/bin/env python3
"""Compare unqualified sequence/structural relations against evaluator-only links."""
import argparse
import copy
import json
from pathlib import Path
import tempfile

from mobile_personal_proof_gate import region_rows
from mobile_region_replay import NativeProbe
from trajectory_native_bridge_probe import address
from trajectory_native_evidence_join_probe import adapt_regions, synthetic
from trajectory_region_evidence_probe import checked, fingerprint
from trajectory_region_reply_probe import observe, link
from trajectory_response_quality_probe import encode


FIELDS = ('hierarchy_id', 'source_id', 'sequence', 'text', 'source_kind')
ROUTES = ('adjacent', 'structural_adjacent', 'structural_successors')
CASES = ('adjacent_true', 'adjacent_unrelated', 'structural_single', 'nonadjacent_true', 'outside_frame',
         'conflicting_successors', 'repeated_single', 'repeated_conflict',
         'multiple_targets', 'generated_barrier', 'foreign_copy', 'no_raw_target', 'terminal_target')


def inferred_relations(rows, region, query):
    """Explicit experimental rules; no reply_to, evaluator roles, or factual selection."""
    if not isinstance(region, str) or not region.strip() or not isinstance(query, str) or not query:
        raise ValueError('nonempty explicit region and raw query required')
    # Whitelist before adaptation: neither reply_to nor native neighbor metadata reaches learning.
    inputs = [{key: row[key] for key in FIELDS} for row in rows]
    memory, origins = adapt_regions(inputs)
    structural = checked(memory, encode(query, 'unicode'), region)
    roots = {c['payload_id'] for c in structural['packet']['candidates']}
    by_origin = {origin: root for root, sources in origins.items() for origin in sources}
    segments, current = [], []
    for row in inputs:
        if row['hierarchy_id'] != region:
            continue
        if row['source_kind'] == 'assistant_generated':
            segments.append(current)
            current = []
        else:
            current.append(row)
    segments.append(current)
    targets = [address(row) for segment in segments for row in segment if row['text'] == query]
    routes = {}
    for name in ROUTES:
        episodes = []
        for segment in segments:
            for index, target_row in enumerate(segment):
                if target_row['text'] != query:
                    continue
                following = segment[index + 1:] if name == 'structural_successors' else segment[index + 1:index + 2]
                relations = []
                for row in following:
                    origin, target = address(row), address(target_row)
                    root = by_origin[origin]
                    if name != 'adjacent' and root not in roots:
                        continue
                    relations.append(dict(origin=origin, target=target, payload_id=root,
                        evidence_kind='INFERRED_SEQUENCE_RELATION', observed_reply_to=False,
                        structural_candidate=root in roots))
                alternatives = sorted({r['payload_id'] for r in relations})
                episodes.append(dict(target=address(target_row), inferred_relations=relations,
                                     alternative_payload_ids=alternatives))
        proposal = (episodes[0]['alternative_payload_ids'][0] if len(episodes) == 1
                    and len(episodes[0]['alternative_payload_ids']) == 1 else None)
        reason = ('NO_OBSERVED_TARGET' if not episodes else 'AMBIGUOUS_TARGETS' if len(episodes) > 1 else
                  'NO_INFERRED_RELATION' if not episodes[0]['alternative_payload_ids'] else
                  'COMPETING_INFERRED_ROOTS' if proposal is None else 'UNIQUE_INFERRED_ROOT')
        routes[name] = dict(episodes=episodes, proposal_payload_id=proposal, reason=reason,
                           answer=None, qualified=False, selected_target=None, selection_used=False)
    return dict(format='memoria.ia-inferred-relation-view-v1', region=region, query=query,
        observation_sha256=fingerprint(inputs), targets=targets, structural=structural, routes=routes,
        inference_rules='immediate successor or all later structural roots within a generated-free local segment',
        answer=None, qualified=False, selected_target=None, selection_used=False,
        factual_quality_status='NOT_EVALUATED')


def fixture(seed, case):
    rows, query, _ = synthetic(seed)
    region = rows[0]['hierarchy_id']
    pairs = [('row-6', 'row-7')]
    if case in ('structural_single', 'repeated_single'):
        rows = [r for r in rows if r['source_id'] != 'row-8']
    if case in ('adjacent_unrelated', 'no_raw_target', 'terminal_target'):
        pairs = []
    if case == 'nonadjacent_true':
        rows = rows[:7] + [rows[9], rows[7], rows[8], rows[10]]
    if case == 'outside_frame':
        rows = rows[:7] + [rows[9], rows[7], rows[8], rows[10]]
        pairs = [('row-6', 'outside')]
    if case in ('conflicting_successors', 'repeated_conflict'):
        pairs.append(('row-6', 'row-8'))
    if case in ('repeated_single', 'repeated_conflict'):
        copies = [dict(next(r for r in rows if r['source_id'] == 'row-7'), source_id=f'copy-{i}') for i in range(20)]
        rows = rows[:-1] + copies + rows[-1:]
        pairs += [('row-6', r['source_id']) for r in copies]
    if case == 'multiple_targets':
        rows += [dict(rows[6], source_id='other-q'), dict(rows[7], source_id='other-a')]
        pairs.append(('other-q', 'other-a'))
    if case == 'generated_barrier':
        rows = rows[:7] + [dict(rows[10], source_id='barrier')] + rows[7:]
    if case == 'foreign_copy':
        rows += [dict(r, hierarchy_id=region + '-foreign') for r in rows]
    if case == 'terminal_target':
        rows = rows[:7]
    counters = {}
    for row in rows:
        scope = row['hierarchy_id']
        counters[scope] = counters.get(scope, 0) + 1
        row['sequence'] = counters[scope]
    indexed = {r['source_id']: r for r in rows if r['hierarchy_id'] == region}
    reference = [(address(indexed[t]), address(indexed[o])) for t, o in pairs]
    return rows, region, query + 'novel' if case == 'no_raw_target' else query, reference


def score(view, reference, rows):
    """Reference links are supplied only after inference; absence here is fixture ground truth."""
    _, origins = adapt_regions([{key: r[key] for key in FIELDS} for r in rows])
    by_origin = {o: root for root, sources in origins.items() for o in sources}
    expected = set(reference)
    reply_roots = {by_origin[o] for _, o in expected}
    expected_proposal = next(iter(reply_roots)) if len(view['targets']) == 1 and len(reply_roots) == 1 else None
    scores = {}
    for name, route in view['routes'].items():
        inferred = {(tuple(r['target']), tuple(r['origin'])) for e in route['episodes'] for r in e['inferred_relations']}
        scores[name] = dict(true_positive=len(inferred & expected), false_positive=len(inferred - expected),
            false_negative=len(expected - inferred), exact_relation_set=inferred == expected,
            proposal_matches=route['proposal_payload_id'] == expected_proposal,
            expected_proposal=expected_proposal)
    return scores


def trial(library, seed, case):
    rows, region, query, reference = fixture(seed, case)
    scopes = list(dict.fromkeys(r['hierarchy_id'] for r in rows))
    with tempfile.TemporaryDirectory(prefix='memoria-inferred-relation-') as directory:
        native = NativeProbe(library, Path(directory))
        try:
            for row in rows:
                observe(native, row)
            def collect():
                return [dict(r, hierarchy_id=s) for s in scopes for r in region_rows(native, s)]
            stored = collect()
            before = fingerprint(stored)
            view = inferred_relations(stored, region, query)
            unchanged = before == fingerprint(stored) and stored == collect()
            # Intervene on observed links after inference. They remain evaluator-only.
            for target, origin in reference:
                link(native, (origin[0], origin[1], origin[2], target[1], target[2]))
            linked = collect()
            masked_parity = view == inferred_relations(linked, region, query)
            native.reopen()
            cold = collect()
            checks = dict(native_rows_read_only=unchanged,
                native_roundtrip_matches_request=all({k: r[k] for k in FIELDS} == wanted
                    for r, wanted in zip(stored, rows)) and len(stored) == len(rows),
                explicit_links_do_not_change_inference=masked_parity,
                cold_complete_view_parity=view == inferred_relations(cold, region, query),
                no_factual_promotion=all(r['answer'] is None and r['qualified'] is False
                    and r['selected_target'] is None and r['selection_used'] is False for r in view['routes'].values()),
                inferred_origins_local_and_not_generated=all(r['origin'][0] == region
                    and r['origin'][1] not in ('generated', 'barrier') and r['observed_reply_to'] is False
                    for route in view['routes'].values() for e in route['episodes'] for r in e['inferred_relations']))
            return dict(case=case, view=view, reference_relations=reference, checks=checks,
                        scores=score(view, reference, stored))
        finally:
            native.close()


def probe(library, seed):
    cases = [trial(library, seed, case) for case in CASES]
    gates = {c['case'] + '_' + name: value for c in cases for name, value in c['checks'].items()}
    twins = cases[:2]
    gates['hidden_relation_twins_identical_view'] = twins[0]['view'] == twins[1]['view']
    gates['hidden_relation_twins_different_reference'] = twins[0]['reference_relations'] != twins[1]['reference_relations']
    if not all(gates.values()):
        raise RuntimeError('failed gates: ' + ', '.join(k for k, v in gates.items() if not v))
    totals = {name: {metric: sum(c['scores'][name][metric] for c in cases)
                    for metric in ('true_positive', 'false_positive', 'false_negative', 'exact_relation_set', 'proposal_matches')}
              for name in ROUTES}
    return dict(seed=seed, cases=cases, gates=gates, integrity_status='PASS',
        integrity_passed=sum(gates.values()), integrity_total=len(gates), route_totals=totals,
        relation_quality_status='FAIL_FALSE_OR_MISSING_RELATIONS', semantic_quality_status='FAIL_HIDDEN_RELATION_TWINS',
        factual_quality_status='NOT_EVALUATED', native_executed=True, engine_changed=False,
        answer=None, qualified=False,
        hidden_relation_twins=dict(identical_view=True, view_sha256=fingerprint(twins[0]['view']),
            route_matches={name: sum(c['scores'][name]['exact_relation_set'] for c in twins) for name in ROUTES}, total=2))


def compact(report):
    return {k: v for k, v in report.items() if k != 'cases'} | dict(
        full_report_sha256=fingerprint(report), cases=[dict(case=c['case'],
            view_sha256=fingerprint(c['view']), targets=c['view']['targets'], routes=c['view']['routes'],
            reference_relations=c['reference_relations'], checks=c['checks'], scores=c['scores']) for c in report['cases']])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--library', type=Path, required=True)
    parser.add_argument('--seed', type=int, default=20261215)
    parser.add_argument('--summary', action='store_true')
    args = parser.parse_args()
    report = probe(args.library, args.seed)
    print(json.dumps(compact(report) if args.summary else report, ensure_ascii=False, indent=2))
