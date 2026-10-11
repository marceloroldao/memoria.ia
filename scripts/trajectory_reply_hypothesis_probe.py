#!/usr/bin/env python3
"""Unqualified reply hypotheses from recovered occurrence-local relations."""
import argparse
from collections import Counter
import copy
import json
from pathlib import Path
import tempfile

from mobile_personal_proof_gate import region_rows
from mobile_region_replay import NativeProbe
from trajectory_bounded_refresh_probe import resolve_with_refresh
from trajectory_native_bridge_probe import address
from trajectory_native_evidence_join_probe import synthetic, adapt_regions
from trajectory_region_evidence_probe import fingerprint
from trajectory_region_reply_probe import observe, link


def reply_hypothesis(recovery):
    """A proposal about an observed reply, never a selected factual answer."""
    envelope = dict(answer=None, qualified=False, selected_target=None, selection_used=False,
                    factual_quality_status='NOT_EVALUATED',
                    evidence_sha256=fingerprint(recovery), proposal_payload_id=None, proposal_origins=[])
    if recovery['status'] != 'OK':
        if recovery['outcome'].get('view') is not None:
            raise ValueError('rejected recovery carries a partial view')
        return dict(**envelope, status='UNAVAILABLE', reason=recovery['status'], episodes=[])
    outcome, view = recovery['outcome'], recovery['outcome']['view']
    if (outcome.get('status') != 'OK' or view.get('answer') is not None
            or view.get('qualified') is not False or view.get('selection_used') is not False
            or view.get('selected_target') is not None
            or view.get('evidence_scope') != 'exact_observed_target_addresses'
            or outcome['consistency'].get('status') != 'REGIONAL_TOKEN_UNCHANGED'
            or outcome['consistency'].get('region') != view['region']
            or outcome['consistency'].get('global_snapshot_guaranteed') is not False):
        raise ValueError('requires an accepted unqualified regional recovery')
    episodes, seen_targets, seen_origins = [], set(), set()
    for episode in view['episodes']:
        target = tuple(episode['target'])
        if (len(target) != 3 or target[0] != view['region'] or target in seen_targets
                or not isinstance(target[1], str) or not target[1]
                or type(target[2]) is not int or target[2] < 0):
            raise ValueError('invalid or duplicate local target')
        seen_targets.add(target)
        roots, echoes = {}, []
        for relation in episode['relations']:
            origin, root = tuple(relation['origin']), relation['payload_id']
            if (tuple(relation['target']) != target or len(origin) != 3
                    or origin[0] != target[0] or origin in seen_origins
                    or not isinstance(origin[1], str) or not origin[1]
                    or type(origin[2]) is not int or origin[2] <= target[2]
                    or not isinstance(root, str) or not root
                    or type(relation['native_query_echo']) is not bool):
                raise ValueError('invalid occurrence-local reply relation')
            seen_origins.add(origin)
            if relation['native_query_echo']:
                echoes.append(copy.deepcopy(relation))
            else:
                roots.setdefault(root, []).append(origin)
        episodes.append(dict(target=target, alternatives=[dict(payload_id=root, origins=roots[root])
            for root in sorted(roots)], query_echo_relations=echoes,
            linked_roots_outside_structural_candidates=copy.deepcopy(
                episode['linked_roots_outside_structural_candidates'])))
    if not episodes:
        reason = 'NO_OBSERVED_TARGET'
    elif len(episodes) != 1:
        reason = 'AMBIGUOUS_TARGETS'
    elif not episodes[0]['alternatives']:
        reason = 'NO_DISTINCT_REPLY'
    elif len(episodes[0]['alternatives']) != 1:
        reason = 'COMPETING_REPLIES'
    else:
        reason = 'UNIQUE_OBSERVED_REPLY_HYPOTHESIS'
        alternative = episodes[0]['alternatives'][0]
        envelope.update(proposal_payload_id=alternative['payload_id'], proposal_origins=alternative['origins'])
    return dict(**envelope, status='PROPOSAL' if envelope['proposal_payload_id'] else 'ABSTAIN',
                reason=reason, episodes=episodes)


def unsafe_comparators(recovery):
    """Evaluator-only choices; never installed in a selector or the policy."""
    if recovery['status'] != 'OK':
        return dict(prior_structural_hypothesis=None, first_structural_root=None,
                    occurrence_majority=None, pooled_unique_reply=None)
    view = recovery['outcome']['view']
    roots = [r['payload_id'] for e in view['episodes'] for r in e['relations'] if not r['native_query_echo']]
    counts = Counter(roots)
    winners = [root for root, count in counts.items() if count == max(counts.values())] if counts else []
    candidates = view['structural']['packet']['candidates']
    prior = view['structural']['packet'].get('prior_structural_hypothesis')
    prior_root = next((c['payload_id'] for c in candidates if prior is not None
                       and tuple(c['output']) == tuple(prior)), None)
    return dict(prior_structural_hypothesis=prior_root,
                first_structural_root=candidates[0]['payload_id'] if candidates else None,
                occurrence_majority=winners[0] if len(winners) == 1 else None,
                pooled_unique_reply=next(iter(counts)) if len(counts) == 1 else None)


CASES = ('unlinked_structural', 'single_link', 'repeat_same_reply', 'conflict', 'repeated_conflict',
         'echo_only', 'link_plus_echo', 'multiple_targets_same_reply', 'foreign_competition',
         'outside_frame_reply', 'no_raw_target', 'exhausted_recovery', 'refreshed_ambiguous_target')


def trial(library, seed, case):
    requested, query, values = synthetic(seed)
    region, foreign = requested[0]['hierarchy_id'], requested[0]['hierarchy_id'] + '-other'
    target = address(requested[6])
    links = []
    expected_origin = None
    if case not in ('unlinked_structural', 'echo_only', 'outside_frame_reply', 'no_raw_target'):
        source = requested[7]
        links.append((region, source['source_id'], source['sequence'], target[1], target[2]))
        if case in ('single_link', 'repeat_same_reply', 'link_plus_echo', 'foreign_competition'):
            expected_origin = address(source)
    if case in ('conflict', 'repeated_conflict'):
        source = requested[8]
        links.append((region, source['source_id'], source['sequence'], target[1], target[2]))
    if case in ('repeat_same_reply', 'repeated_conflict'):
        for i in range(20):
            source = dict(requested[7], source_id=f'copy-{i}', sequence=20 + i)
            requested.append(source)
            links.append((region, source['source_id'], source['sequence'], target[1], target[2]))
    if case in ('echo_only', 'link_plus_echo'):
        # Different raw payload, same native normalized trail: one raw target remains.
        requested.append(dict(requested[6], source_id='echo', sequence=12, text=query + '!'))
        links.append((region, 'echo', 12, target[1], target[2]))
    if case == 'multiple_targets_same_reply':
        requested += [dict(requested[6], source_id='other-q', sequence=12),
                      dict(requested[7], source_id='other-a', sequence=13)]
        links.append((region, 'other-a', 13, 'other-q', 12))
    if case == 'foreign_competition':
        requested += [dict(r, hierarchy_id=foreign) for r in requested[:9]]
        links.append((foreign, requested[8]['source_id'], requested[8]['sequence'], target[1], target[2]))
    if case == 'outside_frame_reply':
        source = requested[9]
        links.append((region, source['source_id'], source['sequence'], target[1], target[2]))
        expected_origin = address(source)
    read_query = query + 'novel' if case == 'no_raw_target' else query
    scopes = list(dict.fromkeys(r['hierarchy_id'] for r in requested))
    requested = [r for s in scopes for r in requested if r['hierarchy_id'] == s]
    with tempfile.TemporaryDirectory(prefix='memoria-reply-hypothesis-') as directory:
        native = NativeProbe(library, Path(directory))
        try:
            for row in requested:
                observe(native, row)
            for relation in links:
                link(native, relation)
            def all_rows():
                return [dict(r, hierarchy_id=s) for s in scopes for r in region_rows(native, s)]
            stored = all_rows()
            _, origins = adapt_regions(stored)
            expected = next((root for root, sources in origins.items() if expected_origin in sources), None)
            mutations = []
            class Scheduled:
                def call(self, name, request):
                    result = native.call(name, request)
                    if (name == 'probe_structural_linked_replies' and request['offset'] == 0
                            and case in ('exhausted_recovery', 'refreshed_ambiguous_target')
                            and (case == 'exhausted_recovery' or not mutations)):
                        sequence = 100 + len(mutations)
                        observe(native, dict(requested[6], source_id=f'late-{sequence}', sequence=sequence))
                        mutations.append(sequence)
                    return result
            recovery = resolve_with_refresh(Scheduled(), stored, region, read_query, max_attempts=2, limit=1)
            before = fingerprint(recovery)
            after_recovery_rows = all_rows()
            proposal = reply_hypothesis(recovery)
            comparators = unsafe_comparators(recovery)
            expected_reason = ('UNIQUE_OBSERVED_REPLY_HYPOTHESIS' if expected else
                'AMBIGUOUS_TARGETS' if case in ('multiple_targets_same_reply', 'refreshed_ambiguous_target') else
                'COMPETING_REPLIES' if case in ('conflict', 'repeated_conflict') else
                'NO_OBSERVED_TARGET' if case == 'no_raw_target' else
                'EXHAUSTED' if case == 'exhausted_recovery' else 'NO_DISTINCT_REPLY')
            if recovery['status'] == 'OK':
                native.reopen()
                cold_rows = all_rows()
                cold_recovery = resolve_with_refresh(native, cold_rows, region, read_query, max_attempts=1, limit=1)
                cold_proposal = reply_hypothesis(cold_recovery)
                # Recovery history/budget differ; compare the complete decision except its evidence hash.
                parity = {k: v for k, v in proposal.items() if k != 'evidence_sha256'} == {
                    k: v for k, v in cold_proposal.items() if k != 'evidence_sha256'}
            else:
                parity = proposal['status'] == 'UNAVAILABLE' and not proposal['episodes']
            candidate_roots = set() if recovery['status'] != 'OK' else {
                c['payload_id'] for c in recovery['outcome']['view']['structural']['packet']['candidates']}
            checks = dict(
                expected_relation_proposal=proposal['proposal_payload_id'] == expected,
                explicit_reason=proposal['reason'] == expected_reason,
                no_factual_promotion=proposal['answer'] is None and proposal['qualified'] is False
                    and proposal['selection_used'] is False and proposal['selected_target'] is None,
                input_and_native_rows_read_only=before == fingerprint(recovery) and after_recovery_rows == all_rows(),
                cold_decision_or_unavailability=parity,
                no_generated_reply_origin=all(o[1] != 'generated' for o in proposal['proposal_origins']),
                structural_roots_not_required=case != 'outside_frame_reply' or expected not in candidate_roots,
                echoes_retained_without_proposal=case not in ('echo_only', 'link_plus_echo') or
                    sum(len(e['query_echo_relations']) for e in proposal['episodes']) == 1)
            return dict(case=case, recovery=recovery, proposal=proposal, comparators=comparators,
                expected_proposal=expected, expected_reason=expected_reason, checks=checks,
                comparator_matches={name: value == expected for name, value in comparators.items()},
                mutations=mutations)
        finally:
            native.close()


def probe(library, seed):
    cases = [trial(library, seed, case) for case in CASES]
    gates = {c['case'] + '_' + name: value for c in cases for name, value in c['checks'].items()}
    unique = next(c for c in cases if c['case'] == 'single_link')
    # Hidden interpretations are assigned only after obtaining exactly the same input/result.
    twins = [copy.deepcopy(unique['proposal']) for _ in range(2)]
    contracts = [('observed_reply_requested', unique['expected_proposal']), ('reply_not_factual_answer', None)]
    role_cases = [dict(evaluator_role=role, expected=expected,
        actual_answer=result['answer'], actual_proposal=result['proposal_payload_id'],
        answer_matches=(result['answer'] == expected),
        unsafe_promotion_matches=(result['proposal_payload_id'] == expected))
        for (role, expected), result in zip(contracts, twins)]
    gates['hidden_roles_do_not_change_result'] = twins[0] == twins[1]
    gates['repetition_does_not_change_single_reply_root'] = unique['proposal']['proposal_payload_id'] == next(
        c for c in cases if c['case'] == 'repeat_same_reply')['proposal']['proposal_payload_id']
    if not all(gates.values()):
        raise RuntimeError('failed gates: ' + ', '.join(k for k, v in gates.items() if not v))
    return dict(seed=seed, integrity_status='PASS', integrity_passed=sum(gates.values()),
        integrity_total=len(gates), gates=gates, cases=cases, native_executed=True,
        relation_contract_counts=dict(cases=len(cases), passed=sum(c['checks']['expected_relation_proposal'] for c in cases)),
        unsafe_comparator_counts={name: dict(cases=len(cases), passed=sum(c['comparator_matches'][name] for c in cases))
                                  for name in unique['comparators']},
        hidden_role_twins=dict(result_sha256=fingerprint(twins[0]), identical=True, cases=role_cases,
            answer_passed=sum(c['answer_matches'] for c in role_cases),
            unsafe_promotion_passed=sum(c['unsafe_promotion_matches'] for c in role_cases), total=2),
        semantic_quality_status='FAIL_HIDDEN_ROLE_TWINS', factual_quality_status='NOT_EVALUATED',
        answer=None, qualified=False, engine_changed=False)


def compact(report):
    return {k: v for k, v in report.items() if k != 'cases'} | dict(
        full_report_sha256=fingerprint(report), cases=[dict(case=c['case'],
            proposal=c['proposal'], expected_proposal=c['expected_proposal'], expected_reason=c['expected_reason'],
            comparators=c['comparators'], comparator_matches=c['comparator_matches'], mutations=c['mutations'],
            recovery_status=c['recovery']['status'], attempts=c['recovery']['attempts'],
            recovery_sha256=fingerprint(c['recovery'])) for c in report['cases']])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--library', type=Path, required=True)
    parser.add_argument('--seed', type=int, default=20261213)
    parser.add_argument('--summary', action='store_true')
    args = parser.parse_args()
    report = probe(args.library, args.seed)
    print(json.dumps(compact(report) if args.summary else report, ensure_ascii=False, indent=2))
