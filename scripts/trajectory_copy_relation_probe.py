#!/usr/bin/env python3
"""Positive learned copy witnesses route occurrences without declaring reply truth."""
import argparse
import copy
import json
from pathlib import Path
from random import Random
from string import ascii_lowercase, digits
import tempfile

from mobile_personal_proof_gate import region_rows
from mobile_region_replay import NativeProbe
from trajectory_context_boundary_ablation_probe import fixture as context_fixture
from trajectory_contextual_relation_probe import contextual_relations
from trajectory_inferred_relation_probe import FIELDS, score
from trajectory_native_bridge_probe import address
from trajectory_native_evidence_join_probe import adapt_regions
from trajectory_region_evidence_probe import fingerprint
from trajectory_region_reply_probe import observe, link


CASES = ('matched_context', 'switched_context', 'context_unrelated', 'same_context_rival',
         'repeated_conflict', 'unknown_context', 'missing_context', 'hidden_training_context',
         'generated_barrier', 'foreign_matching_root', 'multiple_targets', 'explicit_separator')


def copy_relations(rows, region, query):
    base = contextual_relations(rows, region, query)
    inputs = [{k:r[k] for k in FIELDS} for r in rows]
    _, origins = adapt_regions(inputs)
    by_origin = {o:root for root,sources in origins.items() for o in sources}
    diagnostic = base['base']['structural']['diagnostic']
    supported = {root for cut in diagnostic['cuts'] for root in cut['supported_roots']}
    witnesses = {root:[dict(layout_id=c['layout_id'], source_position=c['source_position'],
                           slots=c['slots'], frame_ids=c['frame_ids'])
                     for c in diagnostic['cuts'] if root in c['supported_roots']] for root in sorted(supported)}
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
    routes = copy.deepcopy(base['base']['routes']) | copy.deepcopy(base['routes'])
    for name in ('all_sequence_successors', 'positive_copy_witness'):
        episodes = []
        for segment in segments:
            for i, target in enumerate(segment):
                if target['text'] != query:
                    continue
                relations = []
                for row in segment[i + 1:]:
                    root = by_origin[address(row)]
                    if name == 'positive_copy_witness' and root not in supported:
                        continue
                    relations.append(dict(target=address(target), origin=address(row), payload_id=root,
                        evidence_kind='INFERRED_SEQUENCE_RELATION', observed_reply_to=False,
                        positive_copy_witnesses=copy.deepcopy(witnesses.get(root, []))))
                episodes.append(dict(target=address(target), inferred_relations=relations,
                                     alternative_payload_ids=sorted({r['payload_id'] for r in relations})))
        proposal = (episodes[0]['alternative_payload_ids'][0] if len(episodes) == 1
                    and len(episodes[0]['alternative_payload_ids']) == 1 else None)
        reason = ('NO_OBSERVED_TARGET' if not episodes else 'AMBIGUOUS_TARGETS' if len(episodes)>1 else
                  'NO_POSITIVE_COPY_WITNESS' if name == 'positive_copy_witness' and not supported else
                  'NO_LOCAL_SUCCESSOR' if not episodes[0]['alternative_payload_ids'] else
                  'COMPETING_INFERRED_ROOTS' if proposal is None else 'UNIQUE_INFERRED_ROOT')
        routes[name] = dict(episodes=episodes, proposal_payload_id=proposal, reason=reason,
                           answer=None, qualified=False, selected_target=None, selection_used=False)
    return dict(format='memoria.ia-positive-copy-relation-view-v1', region=region, query=query,
        targets=base['targets'], base=base, routes=routes, positive_copy_witnesses=witnesses,
        unknown_cuts=copy.deepcopy([c for c in diagnostic['cuts'] if c['status'] == 'UNKNOWN']),
        cut_exclusion_used=False, global_reply_exclusion_guaranteed=False,
        answer=None, qualified=False, selected_target=None, selection_used=False,
        factual_quality_status='NOT_EVALUATED')


def fixture(seed, case):
    mode = 'explicit' if case == 'explicit_separator' else 'absent'
    d = context_fixture(seed, mode)
    payloads = [x for pair in d['training_pairs'] for x in pair] + list(d['facts']) + [d['rival']]
    payloads += [q for _, q in d['queries']]
    hidden = lambda source: source[:1] + source[3:]
    payloads += [hidden(s) for s,_ in d['training_pairs']]
    symbols = sorted({x for p in payloads for x in p})
    alphabet = list(ascii_lowercase + digits + ''.join(map(chr, range(224, 256))))
    Random(seed).shuffle(alphabet)
    if len(symbols) > len(alphabet):
        raise ValueError('fixture exceeds injective raw alphabet')
    mapping = dict(zip(symbols, alphabet))
    text = lambda xs: ''.join(mapping[x] for x in xs)
    region, rows = f'conversation:copy-{seed}', []
    def add(symbols, source, kind='user_turn', scope=None):
        scope = region if scope is None else scope
        rows.append(dict(hierarchy_id=scope, source_id=source,
                         sequence=1+sum(r['hierarchy_id']==scope for r in rows),
                         text=text(symbols), source_kind=kind))
    for i,(source,target) in enumerate(d['training_pairs']):
        add(hidden(source) if case == 'hidden_training_context' else source, f'train-s-{i}')
        add(target, f'train-t-{i}')
        add(target, f'barrier-{i}', 'assistant_generated')
    query = dict(d['queries'])['swapped_context' if case == 'switched_context' else
                                'unknown_context' if case == 'unknown_context' else
                                'missing_context' if case == 'missing_context' else 'first']
    add(query, 'q')
    if case == 'generated_barrier':
        add(d['facts'][0], 'generated-between', 'assistant_generated')
    if case != 'foreign_matching_root':
        add(d['facts'][0], 'a')
    add(d['facts'][1], 'b')
    pairs = [('q', 'b' if case == 'switched_context' else 'a')]
    if case in ('context_unrelated', 'unknown_context', 'missing_context', 'foreign_matching_root'):
        pairs = []
    if case in ('same_context_rival', 'repeated_conflict'):
        add(d['rival'], 'rival')
        pairs.append(('q', 'rival'))
    if case == 'repeated_conflict':
        for i in range(20):
            add(d['facts'][0], f'copy-{i}')
            pairs.append(('q', f'copy-{i}'))
    if case == 'foreign_matching_root':
        add(d['facts'][0], 'foreign-a', scope=region+'-foreign')
    if case == 'multiple_targets':
        add(d['facts'][0], 'episode-barrier', 'assistant_generated')
        add(query, 'q2')
        add(d['facts'][0], 'a2')
        pairs.append(('q2', 'a2'))
    indexed = {r['source_id']:r for r in rows if r['hierarchy_id']==region}
    return rows, region, text(query), [(address(indexed[t]),address(indexed[o])) for t,o in pairs]


def trial(library, seed, case):
    rows, region, query, reference = fixture(seed, case)
    scopes = list(dict.fromkeys(r['hierarchy_id'] for r in rows))
    with tempfile.TemporaryDirectory(prefix='memoria-copy-relation-') as directory:
        native = NativeProbe(library, Path(directory))
        try:
            for row in rows:
                observe(native,row)
            def collect():
                return [dict(r,hierarchy_id=s) for s in scopes for r in region_rows(native,s)]
            stored = collect()
            view = copy_relations(stored,region,query)
            read_only = stored == collect()
            for target,origin in reference:
                link(native,(origin[0],origin[1],origin[2],target[1],target[2]))
            masked = view == copy_relations(collect(),region,query)
            native.reopen()
            allowed = {address(r) for r in rows if r['hierarchy_id']==region and r['source_kind'] in ('user_turn','user_assertion')}
            checks = dict(native_read_only=read_only, masked_links=masked,
                complete_cold_parity=view==copy_relations(collect(),region,query),
                unqualified=all(r['answer'] is None and r['qualified'] is False and r['selected_target'] is None
                    and r['selection_used'] is False for r in view['routes'].values()),
                source_addresses_local_and_user=all(tuple(r['origin']) in allowed and tuple(r['target']) in allowed
                    and r['origin'][2]>r['target'][2] and r['observed_reply_to'] is False
                    for route in view['routes'].values() for e in route['episodes'] for r in e['inferred_relations']),
                unknown_cuts_not_excluded=view['cut_exclusion_used'] is False and
                    all(c['cut_excluded'] is False for c in view['unknown_cuts']),
                every_positive_relation_has_witness=all(r['positive_copy_witnesses']
                    for e in view['routes']['positive_copy_witness']['episodes'] for r in e['inferred_relations']))
            return dict(case=case,view=view,reference_relations=reference,checks=checks,scores=score(view,reference,stored))
        finally:
            native.close()


def probe(library,seed):
    cases = [trial(library,seed,c) for c in CASES]
    gates = {c['case']+'_'+k:v for c in cases for k,v in c['checks'].items()}
    positive,negative = cases[0],cases[2]
    gates['hidden_twins_same_complete_view'] = positive['view']==negative['view']
    gates['hidden_twins_different_reference'] = positive['reference_relations']!=negative['reference_relations']
    if not all(gates.values()):
        raise RuntimeError('failed gates: '+', '.join(k for k,v in gates.items() if not v))
    metrics = ('true_positive','false_positive','false_negative','exact_relation_set','proposal_matches')
    totals = {name:{m:sum(c['scores'][name][m] for c in cases) for m in metrics} for name in positive['scores']}
    return dict(seed=seed,cases=cases,gates=gates,integrity_status='PASS',integrity_passed=sum(gates.values()),
        integrity_total=len(gates),route_totals=totals,hidden_relation_twins=dict(identical_view=True,
            route_matches={name:positive['scores'][name]['exact_relation_set']+negative['scores'][name]['exact_relation_set']
                           for name in totals},total=2),
        relation_quality_status='FAIL_FALSE_OR_MISSING_RELATIONS',semantic_quality_status='FAIL_HIDDEN_RELATION_TWINS',
        factual_quality_status='NOT_EVALUATED',native_executed=True,engine_changed=False,answer=None,qualified=False)


def compact(report):
    return {k:v for k,v in report.items() if k!='cases'} | dict(full_report_sha256=fingerprint(report),
        cases=[dict(case=c['case'],view_sha256=fingerprint(c['view']),routes=c['view']['routes'],
            positive_copy_witnesses=c['view']['positive_copy_witnesses'],unknown_cuts=c['view']['unknown_cuts'],
            reference_relations=c['reference_relations'],checks=c['checks'],scores=c['scores']) for c in report['cases']])


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--library',type=Path,required=True)
    parser.add_argument('--seed',type=int,default=20261219)
    parser.add_argument('--summary',action='store_true')
    args=parser.parse_args()
    report=probe(args.library,args.seed)
    print(json.dumps(compact(report) if args.summary else report,ensure_ascii=False,indent=2))
