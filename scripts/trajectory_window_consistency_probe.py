#!/usr/bin/env python3
"""Controlled between-call writes and an opt-in regional window guard."""
import argparse
import json
from pathlib import Path
import re
import tempfile

from mobile_personal_proof_gate import region_rows
from mobile_region_replay import NativeProbe
from trajectory_paged_relation_probe import resolve_paged_region, collect_pages
from trajectory_region_evidence_probe import fingerprint
from trajectory_region_reply_probe import fixtures, observe, link
from trajectory_region_target_probe import enumerate_targets


class WindowChanged(ValueError):
    pass


def projection(rows, region):
    return sorted([dict(source_id=r['source_id'], sequence=r['sequence'],
                        text=r['text'], source_kind=r['source_kind'], reply_to=r.get('reply_to'))
                   for r in rows if r['hierarchy_id'] == region],
                  key=lambda r: (r['sequence'], r['source_id']))


def window_snapshot(native, region):
    """Read all local rows using the existing expected_token page contract."""
    offset, token, revision, rows, identities = 0, None, None, [], set()
    while True:
        request = dict(hierarchy_id=region, offset=offset, limit=64)
        if token is not None:
            request['expected_token'] = token
        status, packet = native.call('read_structural_window', request)
        if status == 2 and packet.get('status') == 'STALE_WINDOW':
            raise WindowChanged('regional window changed while reading rows')
        if (status != 0 or packet.get('status') != 'OK' or packet.get('window_id') != region
                or not isinstance(packet.get('window_token'), str)
                or not re.fullmatch('[0-9a-f]{16}', packet['window_token'])
                or type(packet.get('window_revision')) is not int or packet['window_revision'] < 0):
            raise ValueError('invalid regional window contract')
        if token is None:
            token, revision = packet['window_token'], packet['window_revision']
        elif token != packet['window_token'] or revision != packet['window_revision']:
            raise WindowChanged('regional window metadata changed between pages')
        page, values = packet['page'], packet['observations']
        if (type(page['offset']) is not int or page['offset'] != offset
                or type(page['returned']) is not int or page['returned'] != len(values)
                or len(values) > 64):
            raise ValueError('invalid regional window page')
        for row in values:
            identity = (row['source_id'], row['sequence'])
            if identity in identities:
                raise ValueError('duplicate regional window occurrence')
            identities.add(identity)
            rows.append(dict(row, hierarchy_id=region))
        next_offset = page['next_offset']
        if next_offset is None:
            break
        if (type(next_offset) is not int or next_offset != offset + len(values)
                or next_offset <= offset or next_offset >= revision):
            raise ValueError('invalid regional window continuation')
        offset = next_offset
    if len(rows) != revision:
        raise ValueError('incomplete regional window')
    return dict(token=token, revision=revision, rows=rows)


def rejected(reason, detail):
    return dict(status='REJECTED', reason=reason, detail=detail, view=None,
                answer=None, qualified=False, selected_target=None, selection_used=False,
                factual_quality_status='NOT_EVALUATED')


def resolve_guarded_region(native, rows, region, query, limit=64):
    """Check a caller snapshot and bracket witness transport with a local token.

    This is a bounded consistency check, not a lock or a global snapshot.
    Foreign payload provenance still describes the caller-supplied rows.
    """
    enumerate_targets(rows, region, query)
    if type(limit) is not int or not 1 <= limit <= 64:
        raise ValueError('page size must be an integer from 1 to 64')
    try:
        before = window_snapshot(native, region)
    except WindowChanged as error:
        return rejected('STALE_REGIONAL_WINDOW', str(error))
    if projection(rows, region) != projection(before['rows'], region):
        return rejected('STALE_INPUT_ROWS', 'caller rows differ from current regional observations')
    try:
        result = resolve_paged_region(native, rows, region, query, limit)
    except ValueError as error:
        return rejected('WITNESS_CONTRACT_REJECTED', str(error))
    status, after = native.call('read_structural_window', dict(
        hierarchy_id=region, offset=0, limit=1, expected_token=before['token']))
    if status == 2 and after.get('status') == 'STALE_WINDOW':
        return rejected('STALE_REGIONAL_WINDOW', 'regional token changed during witness transport')
    if (status != 0 or after.get('status') != 'OK' or after.get('window_id') != region
            or after.get('window_token') != before['token']
            or type(after.get('window_revision')) is not int
            or after['window_revision'] != before['revision']):
        raise ValueError('invalid regional token verification')
    return dict(status='OK', **result, consistency=dict(
        status='REGIONAL_TOKEN_UNCHANGED', region=region, window_token=before['token'],
        window_revision=before['revision'], boundary='before_rows_to_after_witness_transport',
        global_snapshot_guaranteed=False, foreign_provenance='caller_supplied_rows'))


class Interleaved:
    """Evaluator-only deterministic write after a native witness response."""
    def __init__(self, native, action=None, after_last=False):
        self.native, self.action, self.after_last = native, action, after_last
        self.requests, self.fired = [], False

    def call(self, name, request):
        self.requests.append(dict(name=name, request=dict(request)))
        result = self.native.call(name, request)
        if (name == 'probe_structural_linked_replies' and self.action and not self.fired
                and (not self.after_last or result[1]['page']['next_offset'] is None)):
            self.action()
            self.fired = True
        return result


CASES = ('stable', 'local_unlinked_query', 'local_generated_query', 'local_nonquery_link',
         'local_matching_link', 'foreign_unlinked_query', 'foreign_matching_link',
         'local_unlinked_after_last_page')


def trial(library, seed, case, guarded):
    scopes, texts, requested, links, row = fixtures(seed)
    region, foreign = scopes[:2]
    query, first, rival, unknown = texts
    requested += [row(region, 'spare', 6, first), row(region, 'nonquery', 7, unknown),
                  row(region, 'spare-reply', 8, rival)]
    # Preserve per-region order after adding local observations.
    requested = [r for s in scopes for r in requested if r['hierarchy_id'] == s]
    with tempfile.TemporaryDirectory(prefix='memoria-window-consistency-') as directory:
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
            before = window_snapshot(native, region)
            baseline = resolve_paged_region(native, stored, region, query, 1)
            initial_header = collect_pages(native, query, 64)['summary']
            def action():
                if case in ('local_unlinked_query', 'local_unlinked_after_last_page'):
                    observe(native, row(region, 'late-query', 100, query))
                elif case == 'local_generated_query':
                    observe(native, dict(row(region, 'late-generated', 100, query),
                                         source_kind='assistant_generated'))
                elif case == 'local_nonquery_link':
                    link(native, (region, 'spare-reply', 8, 'nonquery', 7))
                elif case == 'local_matching_link':
                    link(native, (region, 'spare', 6, 'q', 1))
                elif case == 'foreign_unlinked_query':
                    observe(native, row(foreign, 'late-query', 100, query))
                elif case == 'foreign_matching_link':
                    observe(native, row(foreign, 'late-reply', 100, first))
                    link(native, (foreign, 'late-reply', 100, 'q', 1))
            interleaved = Interleaved(native, action if case != 'stable' else None,
                                     after_last=case == 'local_unlinked_after_last_page')
            try:
                output = (resolve_guarded_region if guarded else resolve_paged_region)(
                    interleaved, stored, region, query, 1)
                accepted = not guarded or output['status'] == 'OK'
            except ValueError as error:
                output, accepted = rejected('WITNESS_CONTRACT_REJECTED', str(error)), False
            after = window_snapshot(native, region)
            current_rows = all_rows()
            final_header = collect_pages(native, query, 64)['summary']
            fresh = resolve_guarded_region(native, current_rows, region, query, 1)
            native.reopen()
            cold_rows = all_rows()
            cold = resolve_guarded_region(native, cold_rows, region, query, 1)
            return dict(mode='guarded' if guarded else 'original', accepted=accepted,
                intervention_fired=interleaved.fired, initial_header=initial_header,
                final_header=final_header, before_token=before['token'], after_token=after['token'],
                before_revision=before['revision'], after_revision=after['revision'],
                output=output, accepted_view_equals_baseline=accepted and output['view'] == baseline['view'],
                current_window_check='FAIL' if accepted and before['token'] != after['token'] else 'PASS',
                before_target_count=len(enumerate_targets(stored, region, query)),
                after_target_count=len(enumerate_targets(current_rows, region, query)),
                input_rows_unchanged=original_hash == fingerprint(stored),
                fresh_guard_status=fresh['status'], fresh_cold_equal=fresh == cold and current_rows == cold_rows,
                fresh_output_sha256=fingerprint(fresh))
        finally:
            native.close()


def probe(library, seed):
    gates, cases = {}, []
    for case in CASES:
        original, guarded = [trial(library, seed, case, flag) for flag in (False, True)]
        header_change = case in ('local_matching_link', 'foreign_matching_link')
        local_change = case.startswith('local_')
        expected_accept = case in ('stable', 'foreign_unlinked_query')
        checks = dict(
            intervention_boundary_executed=all(r['intervention_fired'] == (case != 'stable')
                                               for r in (original, guarded)),
            native_header_effect=all((r['initial_header'] != r['final_header']) == header_change
                                     for r in (original, guarded)),
            native_local_token_effect=all((r['before_token'] != r['after_token']) == local_change
                                          for r in (original, guarded)),
            original_limit_recorded=original['accepted'] == (not header_change)
                and original['current_window_check'] == ('FAIL' if local_change and not header_change else 'PASS'),
            guarded_acceptance_boundary=guarded['accepted'] == expected_accept,
            no_partial_view_on_rejection=guarded['accepted'] or guarded['output']['view'] is None,
            inputs_not_mutated=all(r['input_rows_unchanged'] for r in (original, guarded)),
            fresh_rows_and_cold_reopen=all(r['fresh_guard_status'] == 'OK' and r['fresh_cold_equal']
                                         for r in (original, guarded)),
            no_answer_selection=all(r['output'].get('view') is None or
                (r['output']['view']['answer'] is None and r['output']['view']['qualified'] is False
                 and r['output']['view']['selected_target'] is None) for r in (original, guarded)))
        gates.update({case + '_' + name: value for name, value in checks.items()})
        cases.append(dict(case=case, original=original, guarded=guarded))
    if not all(gates.values()):
        raise RuntimeError('failed gates: ' + ', '.join(k for k, v in gates.items() if not v))
    return dict(seed=seed, integrity_status='PASS', integrity_passed=sum(gates.values()),
                integrity_total=len(gates), gates=gates, cases=cases, native_executed=True,
                original_current_window_failures=sum(c['original']['current_window_check'] == 'FAIL' for c in cases),
                answer=None, qualified=False, factual_quality_status='NOT_EVALUATED',
                global_snapshot_guaranteed=False)


def compact(report):
    return {k: v for k, v in report.items() if k != 'cases'} | dict(
        full_report_sha256=fingerprint(report), cases=[dict(case=c['case'], **{
            mode: {k: v for k, v in c[mode].items() if k != 'output'} | dict(
                output_status=c[mode]['output'].get('status', 'ORIGINAL_ACCEPTED'),
                rejection_reason=c[mode]['output'].get('reason'),
                output_sha256=fingerprint(c[mode]['output'])) for mode in ('original', 'guarded')})
            for c in report['cases']])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--library', type=Path, required=True)
    parser.add_argument('--seed', type=int, default=20261209)
    parser.add_argument('--summary', action='store_true')
    args = parser.parse_args()
    result = probe(args.library, args.seed)
    print(json.dumps(compact(result) if args.summary else result, ensure_ascii=False, indent=2))
