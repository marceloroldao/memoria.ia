#!/usr/bin/env python3
"""Addressed CONTENT/FRAME controls and WITNESS journal support.

Active WITNESS controls require the separate witness-aware reader.
"""
import argparse
import base64
import json
from pathlib import Path
import tempfile

from mobile_region_replay import NativeProbe
from trajectory_feedback_continuity_probe import continuity_decision, historical_proofs, witness_provenance
from trajectory_feedback_ledger_probe import canonical, receipt
from trajectory_feedback_withdrawal_probe import withdrawal_read, withdrawal_region
from trajectory_question_frame_probe import collect, persist, score
from trajectory_region_evidence_probe import fingerprint
from trajectory_route_feedback_probe import make_fixture, witness_origins
from trajectory_route_relation_probe import read
from trajectory_window_consistency_probe import window_snapshot
from trajectory_native_evidence_join_probe import adapt_regions


PREFIX = 'addressed-feedback:'
CODEC = 'addressed-feedback-json-base64-v1:'
FORMAT = 'memoria.ia-addressed-feedback-v1'


def journal_region(region):
    withdrawal_region(region)
    if region.startswith(PREFIX):
        raise ValueError('control journal cannot be a learning region')
    return PREFIX + fingerprint(region)


def operations(native, region):
    result = []
    for row in window_snapshot(native, journal_region(region))['rows']:
        if not row['text'].startswith(CODEC):
            raise ValueError('invalid addressed-feedback codec')
        event = json.loads(base64.b64decode(row['text'][len(CODEC):], validate=True).decode('utf-8'))
        if not isinstance(event, dict):
            raise ValueError('invalid journal envelope')
        if event.get('op') == 'FEEDBACK' and (not isinstance(event.get('receipt'), dict) or event['receipt'].get('region') != region):
            raise ValueError('stored feedback scope mismatch')
        result.append(dict(address=dict(region=row['hierarchy_id'], source_id=row['source_id'],
                                        sequence=row['sequence']), event=event))
    return result


def projection(log):
    """Replay one append-only stream; withdrawal addresses one prior feedback occurrence."""
    feedback, identities = [], set()
    for entry in log:
        event = entry['event']
        if event.get('format') != FORMAT or event.get('op') not in ('FEEDBACK', 'WITHDRAW'):
            raise ValueError('invalid journal event')
        identity = (event['op'], event['event_id'] if event['op'] == 'FEEDBACK' else event['request_id'])
        if identity in identities:
            raise ValueError('duplicate operation identity in journal')
        identities.add(identity)
        if event['op'] == 'FEEDBACK':
            binding = event['receipt']
            if (set(event) != {'format', 'op', 'event_id', 'actor_id', 'stance', 'receipt', 'target'} or
                    not isinstance(binding, dict) or
                    fingerprint({k: v for k, v in binding.items() if k != 'receipt_id'}) != binding.get('receipt_id')):
                raise ValueError('invalid feedback envelope or receipt digest')
            if event['stance'] not in ('support', 'oppose') or event['target']['kind'] not in ('CONTENT', 'FRAME', 'WITNESS'):
                raise ValueError('invalid feedback target or stance')
            expected_fields = {'CONTENT': {'kind'}, 'FRAME': {'kind', 'frame', 'witness_provenance'},
                               'WITNESS': {'kind', 'frame', 'witness', 'occurrence'}}[event['target']['kind']]
            if set(event['target']) != expected_fields:
                raise ValueError('invalid stored target schema')
            feedback.append(dict(entry, active=True, withdrawal=None))
        else:
            if set(event) != {'format', 'op', 'request_id', 'actor_id', 'target_event_id', 'target_address', 'target_sha256'}:
                raise ValueError('invalid withdrawal envelope')
            matches = [p for p in feedback if fingerprint(dict(address=p['address'], event=p['event'])) == event['target_sha256']]
            if (len(matches) != 1 or not matches[0]['active'] or
                    matches[0]['address'] != event['target_address'] or
                    matches[0]['event']['event_id'] != event['target_event_id'] or
                    matches[0]['event']['actor_id'] != event['actor_id']):
                raise ValueError('invalid withdrawal history')
            matches[0].update(active=False, withdrawal=entry)
    return feedback


def witness_occurrence_map(rows, region):
    """Resolve learned payload-pair/stream witnesses to actual adjacent native rows.

    Equal payloads remain distinct occurrences. Generated rows break streams in
    the unchanged adapter. No new adjacency is inferred by removing observations.
    """
    selected = [r for r in rows if r['hierarchy_id'] == region]
    memory, _ = adapt_regions(selected)
    previous, result = {}, {}
    for observation in memory.snapshot()['observations']:
        index = int(observation['observation_id'].split(':')[1])
        row = selected[index]
        scope = observation['hierarchy_id'], observation['stream_id']
        old = previous.get(scope)
        if old is not None and old[0] != observation['payload_id']:
            witness = (old[0], observation['payload_id'], observation['stream_id'])
            result.setdefault(canonical(witness), []).append(dict(source=old[1], target=row))
        previous[scope] = observation['payload_id'], row
    return result


def target_packet(view, binding, target, *, rows=None):
    if not isinstance(target, dict):
        raise ValueError('explicit target is required')
    if target == {'kind': 'CONTENT'}:
        return dict(kind='CONTENT')
    kind = target.get('kind')
    expected = ({'kind', 'frame_id'} if kind == 'FRAME' else
                {'kind', 'frame_id', 'witness', 'source_address', 'target_address'} if kind == 'WITNESS' else set())
    if not expected or set(target) != expected:
        raise ValueError('target must be CONTENT, FRAME or an exact WITNESS occurrence')
    if target['frame_id'] not in binding['candidate']['frame_ids']:
        raise ValueError('frame did not generate the addressed candidate')
    frame = next(f for f in view['frames'] if f['frame_id'] == target['frame_id'])
    if kind == 'WITNESS':
        if rows is None or canonical(target['witness']) not in {canonical(w) for w in frame['witnesses']}:
            raise ValueError('witness does not belong to addressed frame')
        def address(row):
            return [row['hierarchy_id'], row['source_id'], row['sequence']]
        matches = [p for p in witness_occurrence_map(rows, binding['region']).get(canonical(target['witness']), [])
                   if canonical(address(p['source'])) == canonical(target['source_address'])
                   and canonical(address(p['target'])) == canonical(target['target_address'])]
        if len(matches) != 1:
            raise ValueError('witness occurrence addresses are not an observed adjacent pair')
        return json.loads(canonical(dict(kind='WITNESS', frame=frame,
                                        witness=target['witness'], occurrence=matches[0])))
    return json.loads(canonical(dict(kind='FRAME', frame=frame,
                                    witness_provenance=witness_origins(view, frame))))


def append(native, region, event, log):
    status, value = native.call('observe_structural_text', dict(
        hierarchy_id=journal_region(region), sequence=len(log) + 1,
        source_id='addressed-operation:' + fingerprint((event['op'], event.get('event_id', event.get('request_id')))),
        source_kind='user_turn', text=CODEC + base64.b64encode(canonical(event).encode('utf-8')).decode('ascii')))
    if status != 0 or value.get('duplicate'):
        raise RuntimeError('addressed operation persistence failed')
    if native.lib.memoria_mobile_flush(native.handle) != 0:
        raise RuntimeError('flush failed; operation outcome uncertain')
    return dict(status='APPENDED', address=dict(region=journal_region(region),
                sequence=len(log) + 1, source_id='addressed-operation:' + fingerprint((event['op'], event.get('event_id', event.get('request_id'))))), event=event)


def record_addressed(native, binding, event_id, actor_id, stance, target):
    if not isinstance(binding, dict):
        raise ValueError('invalid receipt')
    region = binding.get('region')
    journal_region(region)
    if any(not isinstance(v, str) or not v for v in (event_id, actor_id)) or stance not in ('support', 'oppose'):
        raise ValueError('invalid identity or stance')
    log = operations(native, region)
    projection(log)
    previous = [p for p in log if p['event']['op'] == 'FEEDBACK' and p['event']['event_id'] == event_id]
    if previous:
        old = previous[0]['event']
        requested = {'kind': old['target']['kind']}
        if requested['kind'] in ('FRAME', 'WITNESS'):
            requested['frame_id'] = old['target']['frame']['frame_id']
        if requested['kind'] == 'WITNESS':
            requested['witness'] = old['target']['witness']
            for role in ('source', 'target'):
                row = old['target']['occurrence'][role]
                requested[role + '_address'] = [row['hierarchy_id'], row['source_id'], row['sequence']]
        if (old['actor_id'] != actor_id or old['stance'] != stance or
                canonical(old['receipt']) != canonical(binding) or canonical(requested) != canonical(target)):
            raise ValueError('feedback identity reused with different content')
        return dict(status='EXACT_REPLAY', **previous[0])
    try:
        current = receipt(native, region, binding['query'], binding['candidate']['payload_id'])
    except (KeyError, TypeError) as error:
        raise ValueError('invalid receipt structure') from error
    if canonical(current) != canonical(binding):
        raise ValueError('stale or altered receipt')
    rows = collect(native, [region])
    view = read(rows, region, binding['query'])
    event = dict(format=FORMAT, op='FEEDBACK', event_id=event_id, actor_id=actor_id,
                 stance=stance, receipt=binding, target=target_packet(view, binding, target, rows=rows))
    return append(native, region, event, log)


def withdraw_addressed(native, region, request_id, actor_id, event_id):
    journal_region(region)
    if any(not isinstance(v, str) or not v for v in (request_id, actor_id, event_id)):
        raise ValueError('invalid withdrawal identity')
    log = operations(native, region)
    projected = projection(log)
    targets = [p for p in projected if p['event']['event_id'] == event_id]
    if len(targets) != 1 or targets[0]['event']['actor_id'] != actor_id:
        raise ValueError('target feedback or actor mismatch')
    entry = dict(address=targets[0]['address'], event=targets[0]['event'])
    event = dict(format=FORMAT, op='WITHDRAW', request_id=request_id, actor_id=actor_id,
                 target_event_id=event_id, target_address=entry['address'], target_sha256=fingerprint(entry))
    previous = [p for p in log if p['event']['op'] == 'WITHDRAW' and p['event']['request_id'] == request_id]
    if previous:
        if canonical(previous[0]['event']) != canonical(event):
            raise ValueError('withdrawal identity reused with different content')
        return dict(status='EXACT_REPLAY', **previous[0])
    if not targets[0]['active']:
        raise ValueError('feedback already withdrawn')
    return append(native, region, event, log)


def addressed_read(native, region, query, *, enabled=False, _allow_witness=False):
    journal_region(region)
    if not isinstance(query, str) or not query:
        raise ValueError('query must be a nonempty string')
    base = withdrawal_read(native, region, query, enabled=enabled)
    base.update(format='memoria.ia-addressed-target-view-v1', addressed_feedback_enabled=enabled,
                general_learning_status='NOT_ESTABLISHED')
    if not enabled:
        return base
    log = operations(native, region)
    projected = projection(log)
    active = [dict(address=p['address'], event=p['event']) for p in projected if p['active']]
    if not _allow_witness and any(p['event']['target']['kind'] == 'WITNESS' for p in active):
        raise ValueError('active WITNESS controls require the witness-aware reader')
    rows, view = collect(native, [region]), base['raw_view']
    proofs = historical_proofs(rows, active)
    content = [p for p in active if p['event']['target']['kind'] == 'CONTENT']
    frames = {f['frame_id']: f for f in view['frames']}
    blocked, frame_events = {}, []
    for entry in active:
        event = entry['event']
        if event['target']['kind'] != 'FRAME':
            continue
        target = event['target']
        current = frames.get(target['frame']['frame_id'])
        proof = proofs.get(event['receipt']['receipt_id'])
        valid = False
        if proof is not None:
            historical = read(rows[:proof['prefix_rows']], region, event['receipt']['query'])
            expected = target_packet(historical, event['receipt'], dict(kind='FRAME', frame_id=target['frame']['frame_id']))
            valid = (canonical(expected) == canonical(target) and current is not None and
                     canonical(current) == canonical(target['frame']) and
                     canonical(witness_origins(view, current)) == canonical(target['witness_provenance']))
        frame_events.append(dict(feedback=entry, current_evidence_matches=valid))
        if valid and event['stance'] == 'oppose':
            blocked.setdefault(current['frame_id'], []).append(entry)
    legacy = {c['payload_id'] for c in base['withheld_candidates']}
    available, withheld, decisions = [], [], []
    for candidate in view['candidates']:
        binding = receipt(native, region, query, candidate['payload_id'])
        local = continuity_decision(binding, content, current_provenance=witness_provenance(view, candidate), proofs=proofs)
        penalized = [f for f in candidate['frame_ids'] if f in blocked]
        surviving = [f for f in candidate['frame_ids'] if f not in blocked]
        suspend = candidate['payload_id'] in legacy or local['withheld'] or (bool(penalized) and not surviving)
        decisions.append(dict(payload_id=candidate['payload_id'], content_decision=local,
                              legacy_content_withheld=candidate['payload_id'] in legacy,
                              penalized_frame_ids=penalized, surviving_frame_ids=surviving,
                              withheld=suspend))
        (withheld if suspend else available).append(candidate)
    base.update(addressed_operations=log, addressed_projection=projected, frame_feedback=frame_events,
                blocked_frames=blocked, addressed_decisions=decisions,
                available_candidates=available, withheld_candidates=withheld, candidate_filter_used=bool(withheld))
    return base


SCENARIOS = ('content_only', 'explicit_frame', 'wrong_frame', 'ambiguous_explicit_frame', 'hidden_reference_twin')


def scenario(library, name, seed, renamed):
    fixture_name = ('wrong_feedback' if name == 'wrong_frame' else 'ambiguous_attribution' if name == 'ambiguous_explicit_frame'
                    else 'hidden_reference_twin' if name == 'hidden_reference_twin' else 'extra_route')
    rows, region, source, query, expected = make_fixture(fixture_name, seed, renamed)
    with tempfile.TemporaryDirectory(prefix='memoria-addressed-') as directory:
        native = NativeProbe(library, Path(directory))
        try:
            persist(native, rows)
            source_view = addressed_read(native, region, source, enabled=True)['raw_view']
            candidate = (source_view['candidates'][0] if name in ('wrong_frame', 'ambiguous_explicit_frame') else
                         next(c for c in source_view['candidates'] if any(o[1] == 'added-map-target' for o in c['origins'])))
            binding = receipt(native, region, source, candidate['payload_id'])
            target = dict(kind='CONTENT') if name == 'content_only' else dict(kind='FRAME', frame_id=candidate['frame_ids'][0])
            before = addressed_read(native, region, query, enabled=True)
            first = record_addressed(native, binding, 'explicit-1', 'scripted-caller', 'oppose', target)
            local = addressed_read(native, region, source, enabled=True)
            after = addressed_read(native, region, query, enabled=True)
            log = operations(native, region)
            checks = dict(raw_read_unchanged=before['raw_view'] == after['raw_view'],
                          query_read_only=collect(native, [region]) == rows and operations(native, region) == log,
                          explicit_kind=log[0]['event']['target']['kind'] == target['kind'],
                          exact_replay=record_addressed(native, binding, 'explicit-1', 'scripted-caller', 'oppose', target)['status'] == 'EXACT_REPLAY',
                          no_replay_append=operations(native, region) == log,
                          content_does_not_penalize_frame=(not after['blocked_frames']) if name == 'content_only' else True,
                          content_local_withheld=bool(local['withheld_candidates']) if name == 'content_only' else True,
                          disabled_unchanged=addressed_read(native, region, query)['available_candidates'] == before['available_candidates'],
                          unqualified=after['answer'] is None and not after['qualified'] and not after['selection_used'])
            native.reopen()
            checks['cold_full_view_equal'] = addressed_read(native, region, query, enabled=True) == after
            control = withdraw_addressed(native, region, 'withdraw-1', 'scripted-caller', 'explicit-1')
            restored = addressed_read(native, region, query, enabled=True)
            checks['withdrawal_restores'] = restored['available_candidates'] == before['available_candidates']
            checks['history_preserved'] = operations(native, region)[0] == {k: first[k] for k in ('address', 'event')}
            checks['withdrawal_replay'] = withdraw_addressed(native, region, 'withdraw-1', 'scripted-caller', 'explicit-1')['status'] == 'EXACT_REPLAY'
            checks['feedback_replay_no_reactivation'] = record_addressed(native, binding, 'explicit-1', 'scripted-caller', 'oppose', target)['status'] == 'EXACT_REPLAY' and not projection(operations(native, region))[0]['active']
            native.reopen()
            checks['withdrawal_cold_equal'] = addressed_read(native, region, query, enabled=True) == restored
            return dict(scenario=name, renamed=renamed, rows=rows, source_query=source, heldout_query=query,
                        expected=expected, receipt=binding, requested_target=target, after=after,
                        withdrawal=control, checks=checks,
                        before_score=score([c['text'] for c in before['available_candidates']], expected),
                        after_score=score([c['text'] for c in after['available_candidates']], expected))
        finally:
            native.close()


def probe(library, seed):
    cases = [scenario(library, n, seed, r) for r in (False, True) for n in SCENARIOS]
    checks = {f'{i}:{k}': v for i, c in enumerate(cases) for k, v in c['checks'].items()}
    for i, name in enumerate(SCENARIOS):
        checks['rename:' + name] = all(cases[i][k] == cases[i + len(SCENARIOS)][k] for k in ('before_score', 'after_score'))
    for offset in (0, len(SCENARIOS)):
        positive, twin = cases[offset + 1], cases[offset + 4]
        checks[f'twin_inputs:{offset}'] = positive['rows'] == twin['rows'] and positive['receipt'] == twin['receipt']
        checks[f'twin_reads:{offset}'] = positive['after'] == twin['after']
    return dict(format='memoria.ia-addressed-feedback-probe-v1', seed=seed, cases=cases, checks=checks,
                integrity_status='PASS' if all(checks.values()) else 'FAIL', integrity_passed=sum(checks.values()), integrity_total=len(checks),
                effects={c['scenario']: {k: c[k] for k in ('before_score', 'after_score')} for c in cases if not c['renamed']},
                general_learning_status='NOT_ESTABLISHED', factual_quality_status='NOT_EVALUATED',
                limitation='Explicit caller CONTENT/FRAME attribution, not discovered route fault. Wrong addressed frame propagates loss. '
                'Caller identity is not authenticated. Single-writer replay; no default or console integration.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--library', type=Path, required=True)
    parser.add_argument('--seed', type=int, default=20270111)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = probe(args.library, args.seed)
    result['report_content_sha256'] = fingerprint(result)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(canonical(result) + '\n', encoding='utf-8')
    print(json.dumps({k: result[k] for k in ('seed', 'integrity_status', 'integrity_passed', 'integrity_total', 'effects', 'report_content_sha256')}))
    raise SystemExit(0 if result['integrity_status'] == 'PASS' else 1)


if __name__ == '__main__':
    main()
