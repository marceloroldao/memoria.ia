#!/usr/bin/env python3
"""Audit contextual root filters without promoting inferred links to observed truth."""
import argparse
from dataclasses import asdict
import json
from pathlib import Path
import tempfile

from mobile_personal_proof_gate import region_rows
from mobile_region_replay import NativeProbe
from trajectory_inferred_relation_probe import FIELDS, CASES as BASE_CASES, fixture as base_fixture, inferred_relations, score
from trajectory_native_bridge_probe import address
from trajectory_native_evidence_join_probe import adapt_regions
from trajectory_region_evidence_probe import fingerprint
from trajectory_region_reply_probe import observe, link
from trajectory_response_quality_probe import encode, TrajectoryGenerationExperiment


CASES = BASE_CASES + ('unique_context', 'unique_context_unrelated', 'fragment_only')


def contextual_relations(rows, region, query):
    base = inferred_relations(rows, region, query)
    inputs = [{key: row[key] for key in FIELDS} for row in rows]
    memory, origins = adapt_regions(inputs)
    before = memory.snapshot(), memory.learning_state()
    routes, audits = {}, {}
    for transported, name in ((False, 'contextual_root'), (True, 'transported_contextual_root')):
        hypothesis = memory.contextual_route_hypothesis(encode(query, 'unicode'),
            hierarchy_id=region, transported_source_scope=transported)
        cold = TrajectoryGenerationExperiment.restore(memory.snapshot())
        if asdict(hypothesis) != asdict(cold.contextual_route_hypothesis(encode(query, 'unicode'),
                hierarchy_id=region, transported_source_scope=transported)):
            raise RuntimeError('contextual diagnostic cold parity failed')
        matched = [root for root, sources in origins.items() if any(o[0] == region for o in sources)
                   and hypothesis.hypothesis is not None and memory.expand(root) == hypothesis.hypothesis]
        if len(matched) > 1:
            raise RuntimeError('one complete payload has multiple roots')
        root = matched[0] if matched else None
        episodes, removed = [], []
        for episode in base['routes']['structural_successors']['episodes']:
            keep = [r for r in episode['inferred_relations'] if r['payload_id'] == root]
            removed += [r for r in episode['inferred_relations'] if r['payload_id'] != root]
            episodes.append(dict(target=episode['target'], inferred_relations=keep,
                alternative_payload_ids=sorted({r['payload_id'] for r in keep})))
        proposal = root if len(episodes) == 1 and episodes[0]['alternative_payload_ids'] else None
        reason = ('NO_OBSERVED_TARGET' if not episodes else 'AMBIGUOUS_TARGETS' if len(episodes) > 1 else
                  'NO_CONTEXTUAL_HYPOTHESIS' if hypothesis.hypothesis is None else
                  'NON_ROOT_CONTEXTUAL_HYPOTHESIS' if root is None else
                  'NO_LOCAL_SUCCESSOR_FOR_CONTEXTUAL_ROOT' if not proposal else 'UNIQUE_CONTEXTUAL_ROOT')
        routes[name] = dict(episodes=episodes, proposal_payload_id=proposal, reason=reason,
            answer=None, qualified=False, selected_target=None, selection_used=False)
        audits[name] = dict(contextual_diagnostic=asdict(hypothesis), matched_observed_root=root,
            removed_inferred_relations=removed,
            source_scope_option=transported, learned_fragment_promoted_to_root=False)
    if before != (memory.snapshot(), memory.learning_state()):
        raise RuntimeError('contextual read modified learned state')
    return dict(format='memoria.ia-contextual-relation-view-v1', region=region, query=query,
        observation_sha256=base['observation_sha256'], targets=base['targets'], base=base,
        routes=routes, audits=audits, answer=None, qualified=False, selected_target=None, selection_used=False,
        factual_quality_status='NOT_EVALUATED')


def fixture(seed, case):
    if case == 'fragment_only':
        # Two distinct complete destination roots share an introduced fragment.
        # No fragment payload is observed: a learned fragment cannot become a source-addressed root.
        shift = 100 + seed % 7
        text = lambda xs: ''.join(chr(x + shift) for x in xs)
        region, rows = f'fragment-region:{seed}', []
        for i in range(2):
            for suffix, symbols in [('s', (90 + 2*i, 1, 2, 3, 91 + 2*i)),
                                    ('t', (94 + 2*i, 7, 8, 9, 95 + 2*i))]:
                rows.append(dict(hierarchy_id=region, source_id=f'{i}:{suffix}', sequence=len(rows)+1,
                                 text=text(symbols), source_kind='user_turn'))
        query = text((100, 1, 2, 3, 101))
        rows.append(dict(rows[0], source_id='q', sequence=5, text=query))
        return rows, region, query, []
    rows, region, query, reference = base_fixture(seed,
        'adjacent_true' if case in ('unique_context', 'unique_context_unrelated') else case)
    if case in ('unique_context', 'unique_context_unrelated'):
        rows = [r for r in rows if r['source_id'] not in ('row-8', 'outside')]
        # Retain native source identities and increasing sequences; gaps are valid.
        if case == 'unique_context_unrelated':
            reference = []
    return rows, region, query, reference


def trial(library, seed, case):
    rows, region, query, reference = fixture(seed, case)
    scopes = list(dict.fromkeys(r['hierarchy_id'] for r in rows))
    with tempfile.TemporaryDirectory(prefix='memoria-contextual-relation-') as directory:
        native = NativeProbe(library, Path(directory))
        try:
            for row in rows:
                observe(native, row)
            def collect():
                return [dict(r, hierarchy_id=s) for s in scopes for r in region_rows(native, s)]
            stored = collect()
            before = fingerprint(stored)
            view = contextual_relations(stored, region, query)
            unchanged = before == fingerprint(stored) and collect() == stored
            for target, origin in reference:
                link(native, (origin[0], origin[1], origin[2], target[1], target[2]))
            masked = view == contextual_relations(collect(), region, query)
            native.reopen()
            cold = collect()
            allowed = {address(r) for r in stored if r['hierarchy_id'] == region
                       and r['source_kind'] in ('user_turn', 'user_assertion')}
            checks = dict(native_read_only=unchanged,
                link_intervention_masked=masked, complete_native_cold_parity=view == contextual_relations(cold, region, query),
                unqualified=all(r['answer'] is None and r['qualified'] is False
                    and r['selected_target'] is None and r['selection_used'] is False for r in view['routes'].values()),
                all_inferred_origins_observed_local_users=all(tuple(r['origin']) in allowed
                    and tuple(r['target']) in allowed and r['origin'][2] > r['target'][2]
                    and r['observed_reply_to'] is False for route in view['routes'].values()
                    for e in route['episodes'] for r in e['inferred_relations']),
                base_evidence_retained=view['base'] == inferred_relations(stored, region, query),
                fragment_not_root=case != 'fragment_only' or all(
                    a['contextual_diagnostic']['hypothesis'] is not None and a['matched_observed_root'] is None
                    and not a['learned_fragment_promoted_to_root'] for a in view['audits'].values()))
            return dict(case=case, view=view, reference_relations=reference, checks=checks,
                        scores=score(view, reference, stored), base_scores=score(view['base'], reference, stored))
        finally:
            native.close()


def probe(library, seed):
    cases = [trial(library, seed, case) for case in CASES]
    gates = {c['case'] + '_' + k: v for c in cases for k, v in c['checks'].items()}
    twins = [cases[:2], [next(c for c in cases if c['case'] == name)
                        for name in ('unique_context', 'unique_context_unrelated')]]
    for i, pair in enumerate(twins):
        gates[f'twins_{i}_same_complete_view'] = pair[0]['view'] == pair[1]['view']
        gates[f'twins_{i}_different_reference'] = pair[0]['reference_relations'] != pair[1]['reference_relations']
    if not all(gates.values()):
        raise RuntimeError('failed gates: ' + ', '.join(k for k, v in gates.items() if not v))
    metrics = ('true_positive', 'false_positive', 'false_negative', 'exact_relation_set', 'proposal_matches')
    totals = {name: {m: sum(c['scores'][name][m] for c in cases) for m in metrics} for name in cases[0]['scores']}
    return dict(seed=seed, cases=cases, gates=gates, integrity_status='PASS',
        integrity_passed=sum(gates.values()), integrity_total=len(gates), route_totals=totals,
        base_route_totals={name:{m:sum(c['base_scores'][name][m] for c in cases) for m in metrics}
                           for name in cases[0]['base_scores']},
        relation_quality_status='PASS' if all(t['exact_relation_set'] == len(cases) for t in totals.values())
                                else 'FAIL_FALSE_OR_MISSING_RELATIONS',
        semantic_quality_status='FAIL_HIDDEN_RELATION_TWINS', factual_quality_status='NOT_EVALUATED',
        hidden_relation_twins=[dict(identical_view=True, view_sha256=fingerprint(pair[0]['view']),
            route_matches={name:sum(c['scores'][name]['exact_relation_set'] for c in pair) for name in totals},total=2)
            for pair in twins], native_executed=True, engine_changed=False, answer=None, qualified=False)


def compact(report):
    return {k:v for k,v in report.items() if k != 'cases'} | dict(full_report_sha256=fingerprint(report),
        cases=[dict(case=c['case'], view_sha256=fingerprint(c['view']), targets=c['view']['targets'],
            routes=c['view']['routes'], reference_relations=c['reference_relations'], checks=c['checks'],
            scores=c['scores'], base_scores=c['base_scores'], audits={name:dict(
                contextual_reason=a['contextual_diagnostic']['reason'],
                contextual_hypothesis=a['contextual_diagnostic']['hypothesis'],
                contextual_diagnostic_sha256=fingerprint(a['contextual_diagnostic']),
                matched_observed_root=a['matched_observed_root'],
                removed_inferred_relations=a['removed_inferred_relations'],
                source_scope_option=a['source_scope_option'], learned_fragment_promoted_to_root=False)
                for name,a in c['view']['audits'].items()}) for c in report['cases']])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--library', type=Path, required=True)
    parser.add_argument('--seed', type=int, default=20261217)
    parser.add_argument('--summary', action='store_true')
    args = parser.parse_args()
    report = probe(args.library, args.seed)
    print(json.dumps(compact(report) if args.summary else report, ensure_ascii=False, indent=2))
