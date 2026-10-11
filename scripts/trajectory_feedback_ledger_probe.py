#!/usr/bin/env python3
"""Explicit caller feedback on an exact retrieval receipt; no factual learning."""
import argparse
import base64
import json
from pathlib import Path
import tempfile

from mobile_region_replay import NativeProbe
from trajectory_question_frame_probe import collect, persist
from trajectory_region_evidence_probe import fingerprint
from trajectory_route_relation_probe import fixture, read
from trajectory_window_consistency_probe import window_snapshot


PREFIX = 'feedback-ledger:'
CODEC = 'feedback-json-utf8-base64-v1:'


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def ledger_region(region):
    if not isinstance(region, str) or not region or region.startswith(PREFIX):
        raise ValueError('invalid learning region')
    return PREFIX + fingerprint(region)


def receipt(native, region, query, payload_id):
    """Bind all candidate evidence to exact raw scope, query and projected snapshot."""
    ledger_region(region)
    if not isinstance(query, str) or not query:
        raise ValueError('invalid query')
    rows = collect(native, [region])
    view = read(rows, region, query)
    candidates = [c for c in view['candidates'] if c['payload_id'] == payload_id]
    if len(candidates) != 1:
        raise ValueError('candidate is not in this retrieval')
    binding = dict(format='memoria.ia-feedback-receipt-v1', region=region,
                   query=query, snapshot_sha256=fingerprint(rows),
                   view_sha256=fingerprint(view), candidate=candidates[0])
    binding['receipt_id'] = fingerprint(binding)
    # Stable JSON types across storage/reopen, including tuple-valued evidence.
    return json.loads(canonical(binding))


def events(native, region):
    rows = window_snapshot(native, ledger_region(region))['rows']
    result = []
    for row in rows:
        if not row['text'].startswith(CODEC):
            raise ValueError('unknown feedback storage codec')
        encoded = row['text'][len(CODEC):]
        event = json.loads(base64.b64decode(encoded, validate=True).decode('utf-8'))
        result.append(dict(address=dict(region=row['hierarchy_id'], source_id=row['source_id'],
                                       sequence=row['sequence']), event=event))
    return result


def record(native, binding, event_id, actor_id, stance):
    """Single-writer lab operation. Feedback identities are caller supplied, not authenticated."""
    if not isinstance(binding, dict):
        raise ValueError('invalid receipt')
    region = binding.get('region')
    field = ledger_region(region)
    if any(not isinstance(v, str) or not v for v in (event_id, actor_id)):
        raise ValueError('event and actor identities must be nonempty strings')
    if stance not in ('support', 'oppose'):
        raise ValueError('unsupported feedback stance')
    event = dict(format='memoria.ia-explicit-feedback-event-v1', event_id=event_id,
                 actor_id=actor_id, stance=stance, receipt=binding)
    encoded = canonical(event)
    existing = events(native, region)
    previous = [e for e in existing if e['event']['event_id'] == event_id]
    if previous:
        if len(previous) != 1 or canonical(previous[0]['event']) != encoded:
            raise ValueError('event identity reused with different content')
        return dict(status='EXACT_REPLAY', **previous[0])
    try:
        current = receipt(native, region, binding['query'], binding['candidate']['payload_id'])
    except (KeyError, TypeError) as error:
        raise ValueError('invalid receipt structure') from error
    if canonical(current) != canonical(binding):
        raise ValueError('stale or altered retrieval receipt')
    sequence = len(existing) + 1
    source = 'feedback-event:' + fingerprint(event_id)
    status, response = native.call('observe_structural_text', dict(
        hierarchy_id=field, source_id=source, sequence=sequence,
        # The existing text ABI preserves escaped quotes in nested JSON strings.
        # Encode the ledger envelope explicitly instead of rewriting user facts or ABI.
        text=CODEC + base64.b64encode(encoded.encode('utf-8')).decode('ascii'), source_kind='user_turn'))
    if status != 0 or response.get('duplicate'):
        raise RuntimeError('feedback persistence failed')
    return dict(status='APPENDED', address=dict(region=field, source_id=source,
                                               sequence=sequence), event=event)


def addressed_feedback(native, binding):
    """Historical exact-receipt lookup; active iff the same retrieval can be reproduced."""
    region = binding['region']
    matches = [e for e in events(native, region)
               if canonical(e['event']['receipt']) == canonical(binding)]
    try:
        current = receipt(native, region, binding['query'], binding['candidate']['payload_id'])
        active = canonical(current) == canonical(binding)
    except ValueError:
        active = False
    return dict(events=matches, active_for_current_snapshot=active,
                factual_quality_status='NOT_EVALUATED', answer=None,
                qualified=False, selected_target=None, selection_used=False)


def probe(library, seed):
    cases = []
    checks = {}
    for renamed in (False, True):
        for case in ('same_root_two_routes', 'shared_conflict', 'wrong_transform'):
            rows, region, queries = fixture(case, seed, renamed)
            query_name = 'covered' if case == 'wrong_transform' else 'literal_cue'
            query = next(q['text'] for q in queries if q['name'] == query_name)
            # Feedback is scripted caller input; expected answers are never consumed.
            with tempfile.TemporaryDirectory(prefix='memoria-feedback-ledger-') as directory:
                native = NativeProbe(library, Path(directory))
                local = {}
                rejections = {}
                try:
                    persist(native, rows)
                    before_rows = collect(native, [region])
                    before_view = read(before_rows, region, query)
                    binding = receipt(native, region, query, before_view['candidates'][0]['payload_id'])
                    first = record(native, binding, 'return-1', 'caller-a', 'support')
                    opposed = record(native, binding, 'return-2', 'caller-b', 'oppose')
                    replay = record(native, binding, 'return-1', 'caller-a', 'support')
                    local['exact_replay_no_append'] = replay['status'] == 'EXACT_REPLAY' and len(events(native, region)) == 2
                    local['opposed_events_preserved'] = [e['event']['stance'] for e in events(native, region)] == ['support', 'oppose']
                    local['distinct_native_addresses'] = first['address'] != opposed['address']
                    local['learning_rows_unchanged'] = collect(native, [region]) == before_rows
                    local['retrieval_completely_unchanged'] = read(collect(native, [region]), region, query) == before_view
                    local['current_receipt_active'] = addressed_feedback(native, binding)['active_for_current_snapshot']
                    def reject(name, operation):
                        before = events(native, region)
                        try:
                            operation()
                        except ValueError as error:
                            rejections[name] = str(error)
                            local[name] = events(native, region) == before
                        else:
                            local[name] = False
                    reject('identity_conflict_rejected', lambda: record(native, binding, 'return-1', 'caller-a', 'oppose'))
                    altered = json.loads(canonical(binding)); altered['query'] += '!'
                    reject('changed_query_rejected', lambda: record(native, altered, 'return-3', 'caller-a', 'support'))
                    altered_root = json.loads(canonical(binding)); altered_root['candidate']['payload_id'] = 'missing-root'
                    reject('missing_candidate_rejected', lambda: record(native, altered_root, 'return-3', 'caller-a', 'support'))
                    reject('invalid_stance_rejected', lambda: record(native, binding, 'return-3', 'caller-a', 'true'))
                    historical = events(native, region)
                    append = dict(hierarchy_id=region, source_id='after-feedback', sequence=max(r['sequence'] for r in before_rows)+1,
                                  text='Observação posterior.', source_kind='user_turn')
                    persist(native, [append])
                    reject('stale_snapshot_rejected', lambda: record(native, binding, 'return-3', 'caller-a', 'support'))
                    historical_view = addressed_feedback(native, binding)
                    local['historical_events_preserved'] = events(native, region) == historical
                    local['historical_receipt_inactive'] = not historical_view['active_for_current_snapshot'] and len(historical_view['events']) == 2
                    local['historical_retry_idempotent'] = record(native, binding, 'return-1', 'caller-a', 'support')['status'] == 'EXACT_REPLAY'
                    after_rows = collect(native, [region]); after_view = read(after_rows, region, query)
                    new_binding = receipt(native, region, query, binding['candidate']['payload_id'])
                    local['new_snapshot_no_inherited_feedback'] = addressed_feedback(native, new_binding)['events'] == []
                    record(native, new_binding, 'return-3', 'caller-a', 'oppose')
                    local['snapshot_receipts_distinct'] = new_binding['receipt_id'] != binding['receipt_id']
                    local['new_feedback_read_only_for_learning'] = collect(native, [region]) == after_rows and read(after_rows, region, query) == after_view
                    before_cold = events(native, region)
                    native.reopen()
                    local['cold_ledger_equal'] = events(native, region) == before_cold
                    local['cold_learning_equal'] = collect(native, [region]) == after_rows
                    local['cold_complete_retrieval_equal'] = read(collect(native, [region]), region, query) == after_view
                    local['cold_historical_lookup_equal'] = addressed_feedback(native, binding) == historical_view
                    local['envelopes_unqualified'] = all(v['answer'] is None and not v['qualified'] and v['selected_target'] is None and not v['selection_used'] for v in (before_view, after_view, historical_view))
                    cases.append(dict(case=case, renamed=renamed, raw_rows=before_rows,
                                      binding=binding, new_binding=new_binding, events=before_cold,
                                      rejections=rejections, checks=local))
                    checks.update({f'{case}:{renamed}:{k}': v for k, v in local.items()})
                finally:
                    native.close()
    return dict(format='memoria.ia-feedback-ledger-probe-v1', seed=seed, cases=cases,
                checks=checks, integrity_status='PASS' if all(checks.values()) else 'FAIL',
                integrity_passed=sum(checks.values()), integrity_total=len(checks),
                factual_quality_status='NOT_EVALUATED', retrieval_improvement_status='NOT_IMPLEMENTED',
                limitation='Scripted explicit caller feedback, separate native fields, single writer. No authentication, cross-field transaction, factual vote, automatic selection or learned penalty.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--library', type=Path, required=True)
    parser.add_argument('--seed', type=int, default=20261231)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    report = probe(args.library, args.seed)
    body = json.dumps(report, ensure_ascii=False, indent=1) + '\n'
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(body, encoding='utf-8')
    print(body, end='')
    raise SystemExit(0 if report['integrity_status'] == 'PASS' else 1)


if __name__ == '__main__':
    main()
