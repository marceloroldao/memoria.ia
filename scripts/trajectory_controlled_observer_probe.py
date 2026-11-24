#!/usr/bin/env python3
"""A separate simulated observer with a request bound before observation.

Conditional data-flow independence is tested; digests do not authenticate a source.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

import controlled_symbol_observer as world
from mobile_region_replay import NativeProbe
from trajectory_feedback_ledger_probe import canonical
from trajectory_feedback_transfer_stress import workload, write_report
from trajectory_prediction_audit import address, forecast, identity, journal, observe_outcome, reconcile, verify_prefix
from trajectory_question_frame_probe import collect, persist
from trajectory_region_evidence_probe import fingerprint


WORKER = Path(__file__).with_name('controlled_symbol_observer.py')


def code_digest():
    return hashlib.sha256(WORKER.read_bytes()).hexdigest()


def run_observer(request):
    request = world.validate_request(request)
    # The worker gets only this JSON object, not a BDR directory or hypothesis.
    result = subprocess.run([sys.executable, str(WORKER)], input=world.canonical(request) + '\n',
                            text=True, capture_output=True, check=True, timeout=10)
    response = json.loads(result.stdout)
    if response.get('ok') is not True:
        raise ValueError('controlled observer rejected request')
    return response['observation']


def freeze_task(native, region, query, forecast_id, actor_id, request):
    request = world.validate_request(request)
    if query != 'Q[' + request['entity'] + ']?':
        raise ValueError('query and observer entity mismatch')
    context = dict(format=world.FORMAT, request=request, request_sha256=world.digest(request), observer_code_sha256=code_digest())
    return forecast(native, region, query, forecast_id, actor_id, observation_context=context)


def validate_packet(packet):
    if not isinstance(packet, dict) or set(packet) != {'format', 'request', 'request_sha256', 'reported_tick', 'value', 'text', 'result_sha256'}:
        raise ValueError('invalid observer packet schema')
    request = world.validate_request(packet['request'])
    expected_tick = request['tick'] if request['sensor_mode'] == 'faithful' else max(0, request['tick'] - 1)
    if (packet['format'] != world.FORMAT or packet['request_sha256'] != world.digest(request) or
            type(packet['value']) is not int or not 0 <= packet['value'] <= 10000 or
            type(packet['reported_tick']) is not int or packet['reported_tick'] != expected_tick or
            packet['text'] != world.render(request['entity'], packet['value']) or
            packet['result_sha256'] != world.digest({k: v for k, v in packet.items() if k != 'result_sha256'})):
        raise ValueError('invalid observer packet integrity or format')
    return packet


def ingest_result(native, region, forecast_id, outcome_id, packet):
    identity(forecast_id); identity(outcome_id)
    packet = validate_packet(packet)
    log = journal(native, region)
    forecasts = [p for p in log if p['event']['op'] == 'FORECAST' and p['event']['forecast_id'] == forecast_id]
    if len(forecasts) != 1:
        raise ValueError('forecast not found')
    binding = forecasts[0]['event']['receipt']
    context = binding.get('observation_context')
    if (not isinstance(context, dict) or context.get('format') != world.FORMAT or
            context.get('observer_code_sha256') != code_digest() or
            context.get('request_sha256') != packet['request_sha256'] or
            canonical(context.get('request')) != canonical(packet['request']) or
            binding['query'] != 'Q[' + packet['request']['entity'] + ']?'):
        raise ValueError('observer result does not match frozen task context')
    previous = [p for p in log if p['event']['op'] == 'OUTCOME' and p['event']['outcome_id'] == outcome_id]
    if previous:
        old = previous[0]['event']
        if old['forecast_id'] != forecast_id or canonical(old.get('source_receipt')) != canonical(packet):
            raise ValueError('outcome identity reused with different source receipt')
        return observe_outcome(native, region, forecast_id, outcome_id, 'controlled-observer',
                               address(old['observation']), source_receipt=packet)
    rows = collect(native, [region])
    if not verify_prefix(rows, binding):
        raise ValueError('frozen hypothesis history unavailable')
    # Replaying one wire packet cannot manufacture a newer native occurrence.
    source_id = 'controlled-observation:' + packet['result_sha256']
    existing = [r for r in rows if r['source_id'] == source_id]
    if existing:
        if len(existing) != 1 or existing[0]['text'] != packet['text'] or existing[0]['source_kind'] != 'user_turn':
            raise ValueError('observation identity conflict')
        row = existing[0]
    else:
        row = dict(hierarchy_id=region, source_id=source_id,
                   sequence=max((r['sequence'] for r in rows), default=-1) + 1,
                   text=packet['text'], source_kind='user_turn')
        persist(native, [row])
    return observe_outcome(native, region, forecast_id, outcome_id, 'controlled-observer',
                           address(row), source_receipt=packet)


def observe_task(native, region, forecast_id, outcome_id):
    predictions = [p for p in journal(native, region) if p['event']['op'] == 'FORECAST'
                   and p['event']['forecast_id'] == forecast_id]
    if len(predictions) != 1:
        raise ValueError('forecast not found')
    context = predictions[0]['event']['receipt'].get('observation_context')
    if not isinstance(context, dict) or context.get('format') != world.FORMAT:
        raise ValueError('forecast has no controlled observer task')
    packet = run_observer(context['request'])
    return dict(packet=packet, link=ingest_result(native, region, forecast_id, outcome_id, packet))


def prepare_rows(seed, *, no_coverage=False, memory_bias=0):
    rows, region, queries = workload(seed, 'brackets', 'minimal')
    query = queries[0]['text']
    entity = query[2:-2]
    past_request = dict(world_seed=seed, entity=entity, tick=0, sensor_mode='faithful')
    past = run_observer(past_request)
    for row in rows:
        if row['source_id'] in ('expected-anchor', 'extra-anchor'):
            row['text'] = row['text'].split('=')[0] + '=' + str(past['value'] + memory_bias) + '.'
    if no_coverage:
        rows = [r for r in rows if r['source_id'] not in ('expected-anchor', 'extra-anchor')]
    return rows, region, query, entity, past


SCENARIOS = ('stable', 'state_changed', 'lagged', 'no_coverage', 'wrong_task',
             'tampered_packet', 'self_consistent_forgery', 'conflicting_reports')


def scenario(library, seed, name):
    rows, region, query, entity, past = prepare_rows(seed, no_coverage=name == 'no_coverage')
    tick = 1 if name in ('state_changed', 'lagged', 'self_consistent_forgery') else 0
    request = dict(world_seed=seed, entity=entity, tick=tick, sensor_mode='lagged' if name == 'lagged' else 'faithful')
    with tempfile.TemporaryDirectory(prefix='memoria-observer-') as directory:
        native = NativeProbe(library, Path(directory))
        try:
            persist(native, rows)
            frozen = freeze_task(native, region, query, 'f1', 'scripted-forecaster', request)
            before_rows, before_log = collect(native, [region]), journal(native, region)
            actual_request = dict(request, entity='zz' if entity != 'zz' else 'aa') if name == 'wrong_task' else request
            issued = run_observer(actual_request)
            received = json.loads(canonical(issued))
            if name == 'tampered_packet':
                received['value'] += 1
                received['text'] = world.render(received['request']['entity'], received['value'])
            elif name == 'self_consistent_forgery':
                received['value'] = past['value']
                received['text'] = world.render(entity, past['value'])
                received['result_sha256'] = world.digest({k: v for k, v in received.items() if k != 'result_sha256'})
            rejection = None
            try:
                linked = ingest_result(native, region, 'f1', 'o1', received)
            except ValueError as error:
                if name not in ('wrong_task', 'tampered_packet'):
                    raise
                linked, rejection = None, str(error)
            if name == 'conflicting_reports':
                altered = json.loads(canonical(received))
                altered['value'] += 1
                altered['text'] = world.render(entity, altered['value'])
                altered['result_sha256'] = world.digest({k: v for k, v in altered.items() if k != 'result_sha256'})
                ingest_result(native, region, 'f1', 'o2', altered)
            after = reconcile(native, region, 'f1')
            saved_rows, saved_log = collect(native, [region]), journal(native, region)
            checks = dict(request_frozen_before_link=frozen['event']['receipt']['observation_context']['request'] == request,
                          forecast_prefix_preserved=saved_rows[:len(before_rows)] == before_rows,
                          forecast_immutable=saved_log[0] == before_log[0],
                          generated_by_separate_worker=issued == run_observer(actual_request),
                          comparison_read_only=reconcile(native, region, 'f1') == after and collect(native, [region]) == saved_rows and journal(native, region) == saved_log,
                          no_factual_promotion=after['answer'] is None and not after['qualified'] and not after['learning_applied'],
                          no_authentication_claim=after['provenance_independence'] == 'NOT_ESTABLISHED')
            if rejection:
                checks['invalid_receipt_no_write'] = saved_rows == before_rows and saved_log == before_log
            else:
                checks['complete_source_receipt_persisted'] = saved_log[1]['event']['source_receipt'] == received
                replay = ingest_result(native, region, 'f1', 'o1', received)
                checks['exact_replay_no_extra_occurrence'] = replay['status'] == 'EXACT_REPLAY' and collect(native, [region]) == saved_rows and journal(native, region) == saved_log
            native.reopen()
            checks['cold_full_comparison_equal'] = reconcile(native, region, 'f1') == after
            # Evaluator only: this truth is never passed to the forecast or bridge.
            truth = world.world_value(seed, entity, tick)
            return dict(scenario=name, rows=rows, past_observation=past, request=request, issued_packet=issued, received_packet=received,
                        ingested_packet=received if linked else None, rejection=rejection, result=after, checks=checks,
                        evaluator=dict(world_value=truth,
                                       linked_report_values=[p['outcome']['event']['source_receipt']['value'] for p in after['comparisons']],
                                       linked_reports_agree_with_world=[p['outcome']['event']['source_receipt']['value'] == truth for p in after['comparisons']],
                                       truth_used_for_learning=False))
        finally:
            native.close()


def independence_intervention(library, seed):
    runs = []
    for bias in (0, 17):
        rows, region, query, entity, _ = prepare_rows(seed, memory_bias=bias)
        request = dict(world_seed=seed, entity=entity, tick=1, sensor_mode='faithful')
        with tempfile.TemporaryDirectory(prefix='memoria-observer-intervention-') as directory:
            native = NativeProbe(library, Path(directory))
            try:
                persist(native, rows)
                frozen = freeze_task(native, region, query, 'intervention', 'scripted-forecaster', request)
                observed = observe_task(native, region, 'intervention', 'observed')
                runs.append(dict(memory_bias=bias, rows=rows, forecast=frozen, worker=observed,
                                 comparison=reconcile(native, region, 'intervention')))
            finally:
                native.close()
    checks = dict(same_request=runs[0]['worker']['packet']['request'] == runs[1]['worker']['packet']['request'],
                  changed_frozen_hypotheses=runs[0]['forecast']['event']['receipt']['view'] != runs[1]['forecast']['event']['receipt']['view'],
                  unchanged_worker_result=runs[0]['worker']['packet'] == runs[1]['worker']['packet'],
                  no_factual_promotion=all(not r['comparison']['qualified'] for r in runs))
    return dict(runs=runs, checks=checks,
                limitation='Counterfactual memory contents, not a predictive-accuracy experiment or security noninterference proof.')


def probe(library, seed):
    cases = [scenario(library, seed, name) for name in SCENARIOS]
    checks = {f'{i}:{k}': value for i, case in enumerate(cases) for k, value in case['checks'].items()}
    intervention = independence_intervention(library, seed)
    checks.update({'intervention:' + k: v for k, v in intervention['checks'].items()})
    return dict(format='memoria.ia-controlled-observer-probe-v1', seed=seed, cases=cases, independence_intervention=intervention, checks=checks,
                integrity_status='PASS' if all(checks.values()) else 'FAIL', integrity_passed=sum(checks.values()), integrity_total=len(checks),
                statuses={c['scenario']: c['result']['status'] for c in cases},
                generation_independence_scope='FIXED_REQUEST_SUBPROCESS_CONTRACT',
                source_authentication='NOT_ESTABLISHED', factual_quality_status='NOT_EVALUATED',
                limitation='Deterministic simulated observer does not receive hypotheses or memory path. '
                'Conditional data-flow separation is not authentication or real-world truth. Lagged or forged observations '
                'can match stale hypotheses. Native audit compares recalled contents, not new-value predictions.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--library', type=Path, required=True)
    parser.add_argument('--seed', type=int, default=20270119)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = probe(args.library, args.seed)
    result['report_content_sha256'] = fingerprint(result)
    write_report(args.output, result)
    print(json.dumps({k: result[k] for k in ('seed', 'integrity_status', 'integrity_passed', 'integrity_total', 'statuses', 'report_content_sha256')}))
    raise SystemExit(0 if result['integrity_status'] == 'PASS' else 1)


if __name__ == '__main__':
    main()
