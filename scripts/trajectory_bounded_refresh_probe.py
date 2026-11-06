#!/usr/bin/env python3
"""Explicit attempt budget for stale regional reads, with rejection history."""
import argparse
import copy
import json
from pathlib import Path
import tempfile

from mobile_personal_proof_gate import region_rows
from mobile_region_replay import NativeProbe
from trajectory_region_evidence_probe import fingerprint
from trajectory_region_reply_probe import fixtures, observe, link
from trajectory_region_target_probe import enumerate_targets
from trajectory_window_consistency_probe import (
    WindowChanged, window_snapshot, resolve_guarded_region, rejected)

RETRYABLE = frozenset(('STALE_INPUT_ROWS', 'STALE_REGIONAL_WINDOW'))


def replace_region(rows, region, local):
    """Replace one caller region; retain foreign rows and their order."""
    result, inserted = [], False
    for row in rows:
        if row['hierarchy_id'] == region:
            if not inserted:
                result.extend(copy.deepcopy(local))
                inserted = True
        else:
            result.append(copy.deepcopy(row))
    if not inserted:
        result.extend(copy.deepcopy(local))
    return result


def resolve_with_refresh(native, rows, region, query, *, max_attempts, limit=64):
    """An attempt includes its refresh, if needed, and at most one resolution.

    Only stale-window/input rejection permits another attempt. Malformed native
    contracts are never retried. No sleep, write, answer selection or global
    refresh occurs here.
    """
    if type(max_attempts) is not int or not 1 <= max_attempts <= 8:
        raise ValueError('explicit attempt budget must be an integer from 1 to 8')
    if type(limit) is not int or not 1 <= limit <= 64:
        raise ValueError('page size must be an integer from 1 to 64')
    enumerate_targets(rows, region, query)
    current, attempts = copy.deepcopy(rows), []
    for index in range(1, max_attempts + 1):
        phase, refreshed = 'resolve', None
        if index > 1:
            phase = 'refresh'
            try:
                refreshed = window_snapshot(native, region)
            except WindowChanged as error:
                outcome = rejected('STALE_REGIONAL_WINDOW', str(error))
            else:
                current = replace_region(current, region, refreshed['rows'])
                phase = 'resolve'
        if phase == 'resolve':
            outcome = resolve_guarded_region(native, current, region, query, limit)
        attempts.append(dict(attempt=index, phase=phase, status=outcome['status'],
            reason=outcome.get('reason'), outcome_sha256=fingerprint(outcome),
            input_rows_sha256=fingerprint(current),
            foreign_rows_sha256=fingerprint([r for r in current if r['hierarchy_id'] != region]),
            refreshed_window=None if refreshed is None else dict(
                token=refreshed['token'], revision=refreshed['revision'])))
        if outcome['status'] == 'OK':
            status = 'OK'
            break
        if outcome['status'] != 'REJECTED' or outcome.get('reason') not in RETRYABLE:
            status = 'REJECTED'
            break
    else:
        status = 'EXHAUSTED'
    return dict(status=status, outcome=outcome, attempts=attempts,
                attempt_budget=max_attempts, attempts_used=len(attempts),
                answer=None, qualified=False, selected_target=None, selection_used=False,
                factual_quality_status='NOT_EVALUATED', global_snapshot_guaranteed=False,
                refreshed_scope=region if any(a['refreshed_window'] is not None for a in attempts) else None,
                foreign_provenance='caller_supplied_rows')


CASES = {
    'stable': (1, 'OK', 1),
    'stale_input': (2, 'OK', 2),
    'one_local_query': (2, 'OK', 2),
    'one_generated': (2, 'OK', 2),
    'one_nonquery_link': (2, 'OK', 2),
    'budget_one': (1, 'EXHAUSTED', 1),
    'continuous': (2, 'EXHAUSTED', 2),
    'foreign_unlinked': (2, 'OK', 1),
    'matching_link': (2, 'REJECTED', 1),
    'refresh_window_change': (3, 'OK', 3),
}


def trial(library, seed, case):
    budget, expected_status, expected_attempts = CASES[case]
    scopes, texts, requested, links, row = fixtures(seed)
    region, foreign = scopes[:2]
    query, first, rival, unknown = texts
    requested += [row(region, 'spare', 6, first), row(region, 'nonquery', 7, unknown),
                  row(region, 'spare-reply', 8, rival)]
    if case == 'refresh_window_change':
        requested += [row(region, f'padding-{i}', 9 + i, unknown) for i in range(60)]
    requested = [r for scope in scopes for r in requested if r['hierarchy_id'] == scope]
    with tempfile.TemporaryDirectory(prefix='memoria-bounded-refresh-') as directory:
        native = NativeProbe(library, Path(directory))
        try:
            for item in requested:
                observe(native, item)
            for item in links:
                link(native, item)
            def all_rows():
                return [dict(r, hierarchy_id=s) for s in scopes for r in region_rows(native, s)]
            stored = all_rows()
            original_hash = fingerprint(stored)
            writes, requests = [], []
            def append(scope, kind='user_turn'):
                sequence = 100 + len(writes)
                source = f'late-{sequence}'
                observe(native, dict(row(scope, source, sequence, query), source_kind=kind))
                writes.append(dict(kind='observation', region=scope, source_id=source, sequence=sequence))
            if case == 'stale_input':
                append(region)
            class Scheduled:
                def call(self, name, request):
                    result = native.call(name, request)
                    requests.append(dict(name=name, request=dict(request)))
                    if name == 'probe_structural_linked_replies' and request['offset'] == 0:
                        if case == 'continuous' or (not writes and case in (
                                'one_local_query', 'budget_one', 'refresh_window_change')):
                            append(region)
                        elif not writes and case == 'one_generated':
                            append(region, 'assistant_generated')
                        elif not writes and case == 'foreign_unlinked':
                            append(foreign)
                        elif not writes and case in ('one_nonquery_link', 'matching_link'):
                            relation = (region, 'spare-reply', 8, 'nonquery', 7) if case == 'one_nonquery_link' else (
                                region, 'spare', 6, 'q', 1)
                            link(native, relation)
                            writes.append(dict(kind='link', address=relation))
                    elif (case == 'refresh_window_change' and len(writes) == 1
                          and name == 'read_structural_window' and request['offset'] == 0
                          and request['limit'] == 64 and 'expected_token' not in request):
                        append(region)
                    return result
            result = resolve_with_refresh(Scheduled(), stored, region, query,
                                          max_attempts=budget, limit=1)
            final_rows = all_rows()
            fresh = resolve_with_refresh(native, final_rows, region, query, max_attempts=1, limit=1)
            native.reopen()
            cold_rows = all_rows()
            cold = resolve_with_refresh(native, cold_rows, region, query, max_attempts=1, limit=1)
            expected_writes = 0 if case == 'stable' else 2 if case in ('continuous', 'refresh_window_change') else 1
            trace = result['attempts']
            foreign_hash = fingerprint([r for r in stored if r['hierarchy_id'] != region])
            checks = dict(
                expected_status=result['status'] == expected_status,
                explicit_budget_obeyed=result['attempts_used'] == expected_attempts <= budget,
                expected_interventions=len(writes) == expected_writes,
                only_stale_rejections_retried=all(a['status'] == 'REJECTED' and a['reason'] in RETRYABLE
                                                 for a in trace[:-1]),
                history_retained=[a['attempt'] for a in trace] == list(range(1, expected_attempts + 1))
                    and (expected_attempts == 1 or trace[0]['status'] == 'REJECTED'),
                input_and_foreign_snapshot_preserved=fingerprint(stored) == original_hash
                    and all(a['foreign_rows_sha256'] == foreign_hash for a in trace),
                no_view_on_terminal_rejection=result['status'] == 'OK' or result['outcome']['view'] is None,
                fresh_and_cold_parity=fresh['status'] == 'OK' and fresh == cold and final_rows == cold_rows,
                no_factual_selection=result['answer'] is None and result['qualified'] is False
                    and result['selected_target'] is None and not result['global_snapshot_guaranteed'])
            return dict(case=case, result=result, writes=writes, requests=requests, checks=checks,
                        initial_target_count=len(enumerate_targets(stored, region, query)),
                        final_target_count=len(enumerate_targets(final_rows, region, query)),
                        final_output_sha256=fingerprint(fresh))
        finally:
            native.close()


def probe(library, seed):
    cases = [trial(library, seed, case) for case in CASES]
    gates = {c['case'] + '_' + name: value for c in cases for name, value in c['checks'].items()}
    if not all(gates.values()):
        raise RuntimeError('failed gates: ' + ', '.join(k for k, v in gates.items() if not v))
    return dict(seed=seed, integrity_status='PASS', integrity_passed=sum(gates.values()),
                integrity_total=len(gates), gates=gates, cases=cases, native_executed=True,
                answer=None, qualified=False, factual_quality_status='NOT_EVALUATED',
                global_snapshot_guaranteed=False)


def compact(report):
    return {k: v for k, v in report.items() if k != 'cases'} | dict(
        full_report_sha256=fingerprint(report), cases=[dict(
            case=c['case'], status=c['result']['status'], attempts=c['result']['attempts'],
            attempt_budget=c['result']['attempt_budget'], attempts_used=c['result']['attempts_used'],
            writes=c['writes'], initial_target_count=c['initial_target_count'],
            final_target_count=c['final_target_count'], final_output_sha256=c['final_output_sha256'],
            outcome_sha256=fingerprint(c['result']['outcome']),
            request_count=len(c['requests']), request_trace_sha256=fingerprint(c['requests'])) for c in report['cases']])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--library', type=Path, required=True)
    parser.add_argument('--seed', type=int, default=20261211)
    parser.add_argument('--summary', action='store_true')
    args = parser.parse_args()
    result = probe(args.library, args.seed)
    print(json.dumps(compact(result) if args.summary else result, ensure_ascii=False, indent=2))
