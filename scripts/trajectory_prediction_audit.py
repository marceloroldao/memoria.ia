#!/usr/bin/env python3
"""Freeze recalled hypotheses before linking later native observations.

Exact recurrence is not factual validation, independent evidence or new-value prediction.
"""
import argparse
import base64
import json
from pathlib import Path
import tempfile

from mobile_region_replay import NativeProbe
from trajectory_addressed_feedback_probe import journal_region
from trajectory_feedback_ledger_probe import canonical
from trajectory_feedback_transfer_stress import workload, write_report
from trajectory_question_frame_probe import collect, persist
from trajectory_region_evidence_probe import fingerprint
from trajectory_route_relation_probe import read


PREFIX = 'prediction-audit:'
CODEC = 'prediction-audit-json-base64-v1:'
FORMAT = 'memoria.ia-prediction-audit-v1'


def field(region):
    journal_region(region)
    if region.startswith(PREFIX):
        raise ValueError('prediction controls cannot be a learning region')
    return PREFIX + fingerprint(region)


def identity(value):
    if not isinstance(value, str) or not value.strip() or len(value) > 128:
        raise ValueError('identity must be a nonempty string of at most 128 characters')
    return value


def address(row):
    return [row['hierarchy_id'], row['source_id'], row['sequence']]


def journal(native, region):
    from trajectory_window_consistency_probe import window_snapshot
    log, forecasts, outcomes, pairs = [], {}, set(), set()
    for row in window_snapshot(native, field(region))['rows']:
        if not row['text'].startswith(CODEC):
            raise ValueError('invalid prediction journal codec')
        event = json.loads(base64.b64decode(row['text'][len(CODEC):], validate=True).decode('utf-8'))
        if not isinstance(event, dict) or event.get('format') != FORMAT:
            raise ValueError('invalid prediction envelope')
        entry = dict(address=address(row), event=event)
        if event.get('op') == 'FORECAST':
            if set(event) != {'format', 'op', 'forecast_id', 'actor_id', 'receipt'}:
                raise ValueError('invalid forecast schema')
            identity(event['forecast_id']); identity(event['actor_id'])
            binding = event['receipt']
            if 'observation_context' in binding and metadata(binding['observation_context']) is None:
                raise ValueError('invalid observation context')
            if (binding['region'] != region or event['forecast_id'] in forecasts or
                    fingerprint({k: v for k, v in binding.items() if k != 'receipt_id'}) != binding['receipt_id']):
                raise ValueError('invalid forecast receipt or duplicate identity')
            forecasts[event['forecast_id']] = entry
        elif event.get('op') == 'OUTCOME':
            required = {'format', 'op', 'outcome_id', 'observer_id', 'forecast_id',
                        'forecast_address', 'forecast_sha256', 'observation'}
            if set(event) not in (required, required | {'source_receipt'}):
                raise ValueError('invalid outcome schema')
            if 'source_receipt' in event and metadata(event['source_receipt']) is None:
                raise ValueError('invalid source receipt')
            identity(event['outcome_id']); identity(event['observer_id'])
            forecast = forecasts.get(event['forecast_id'])
            pair = canonical((event['forecast_id'], address(event['observation'])))
            if (forecast is None or event['outcome_id'] in outcomes or pair in pairs or
                    event['forecast_address'] != forecast['address'] or
                    event['forecast_sha256'] != fingerprint(forecast) or
                    event['observation']['hierarchy_id'] != region or
                    event['observation']['source_kind'] not in ('user_turn', 'user_assertion') or
                    event['observation']['sequence'] <= forecast['event']['receipt']['cutoff_sequence']):
                raise ValueError('invalid outcome linkage, role or temporal order')
            outcomes.add(event['outcome_id']); pairs.add(pair)
        else:
            raise ValueError('unknown prediction operation')
        log.append(entry)
    return log


def append(native, region, event, log):
    sequence = len(log) + 1
    source_id = 'prediction-operation:' + fingerprint((event['op'], event.get('forecast_id') if event['op'] == 'FORECAST' else event['outcome_id']))
    status, result = native.call('observe_structural_text', dict(hierarchy_id=field(region), source_id=source_id,
        sequence=sequence, source_kind='user_turn',
        text=CODEC + base64.b64encode(canonical(event).encode('utf-8')).decode('ascii')))
    if status != 0 or result.get('duplicate'):
        raise RuntimeError('prediction journal append failed')
    flush(native)
    return dict(status='APPENDED', address=[field(region), source_id, sequence], event=event)


def flush(native):
    if native.lib.memoria_mobile_flush(native.handle) != 0:
        raise RuntimeError('flush failed; append outcome uncertain')


def metadata(value):
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError('optional metadata must be a JSON object of at most 4096 characters')
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)
    if len(encoded) > 4096:
        raise ValueError('optional metadata must be a JSON object of at most 4096 characters')
    return json.loads(encoded)


def forecast(native, region, query, forecast_id, actor_id, *, observation_context=None):
    field(region); identity(forecast_id); identity(actor_id)
    observation_context = metadata(observation_context)
    if not isinstance(query, str) or not query.strip() or len(query) > 4096:
        raise ValueError('invalid forecast query')
    log = journal(native, region)
    previous = [p for p in log if p['event']['op'] == 'FORECAST' and p['event']['forecast_id'] == forecast_id]
    if previous:
        old = previous[0]
        if (old['event']['actor_id'] != actor_id or old['event']['receipt']['query'] != query or
                canonical(old['event']['receipt'].get('observation_context')) != canonical(observation_context)):
            raise ValueError('forecast identity reused with different request')
        flush(native)
        return dict(status='EXACT_REPLAY', **old)
    rows = collect(native, [region])
    binding = dict(region=region, query=query, learning_row_count=len(rows),
                   cutoff_sequence=max((r['sequence'] for r in rows), default=-1),
                   snapshot_sha256=fingerprint(rows), source_policy='RAW_OBSERVED_FRAME_CANDIDATES',
                   view=read(rows, region, query))
    if observation_context is not None:
        binding['observation_context'] = observation_context
    binding['receipt_id'] = fingerprint(binding)
    binding = json.loads(canonical(binding))
    return append(native, region, dict(format=FORMAT, op='FORECAST', forecast_id=forecast_id,
                                     actor_id=actor_id, receipt=binding), log)


def verify_prefix(rows, binding):
    count = binding['learning_row_count']
    if type(count) is not int or count < 0:
        return False
    prefix = rows[:count]
    return (len(prefix) == count and
            fingerprint(prefix) == binding['snapshot_sha256'] and
            max((r['sequence'] for r in prefix), default=-1) == binding['cutoff_sequence'] and
            canonical(read(prefix, binding['region'], binding['query'])) == canonical(binding['view']))


def observe_outcome(native, region, forecast_id, outcome_id, observer_id, observation_address, *, source_receipt=None):
    field(region); identity(forecast_id); identity(outcome_id); identity(observer_id)
    source_receipt = metadata(source_receipt)
    log = journal(native, region)
    predictions = [p for p in log if p['event']['op'] == 'FORECAST' and p['event']['forecast_id'] == forecast_id]
    if len(predictions) != 1:
        raise ValueError('forecast not found in scope')
    prediction = predictions[0]
    previous = [p for p in log if p['event']['op'] == 'OUTCOME' and p['event']['outcome_id'] == outcome_id]
    if previous:
        old = previous[0]['event']
        if (old['observer_id'] != observer_id or old['forecast_id'] != forecast_id or
                canonical(address(old['observation'])) != canonical(observation_address) or
                canonical(old.get('source_receipt')) != canonical(source_receipt)):
            raise ValueError('outcome identity reused with different request')
        flush(native)
        return dict(status='EXACT_REPLAY', **previous[0])
    rows = collect(native, [region])
    matches = [r for r in rows if canonical(address(r)) == canonical(observation_address)]
    if len(matches) != 1 or matches[0]['source_kind'] not in ('user_turn', 'user_assertion'):
        raise ValueError('outcome requires one observed user/source occurrence')
    observation = matches[0]
    binding = prediction['event']['receipt']
    if observation['sequence'] <= binding['cutoff_sequence']:
        raise ValueError('observation is not later than the forecast cutoff')
    if not verify_prefix(rows, binding):
        raise ValueError('forecast history cannot be reproduced')
    if any(p['event']['op'] == 'OUTCOME' and p['event']['forecast_id'] == forecast_id
           and address(p['event']['observation']) == address(observation) for p in log):
        raise ValueError('observation already linked to this forecast')
    event = dict(format=FORMAT, op='OUTCOME', outcome_id=outcome_id, observer_id=observer_id,
                 forecast_id=forecast_id, forecast_address=prediction['address'], forecast_sha256=fingerprint(prediction),
                 observation=observation)
    if source_receipt is not None:
        event['source_receipt'] = source_receipt
    return append(native, region, event, log)


def reconcile(native, region, forecast_id):
    field(region); identity(forecast_id)
    log = journal(native, region)
    predictions = [p for p in log if p['event']['op'] == 'FORECAST' and p['event']['forecast_id'] == forecast_id]
    if len(predictions) != 1:
        raise ValueError('forecast not found in scope')
    prediction = predictions[0]
    binding = prediction['event']['receipt']
    rows = collect(native, [region])
    verified = verify_prefix(rows, binding)
    candidates = binding['view']['candidates']
    comparisons = []
    for entry in log:
        event = entry['event']
        if event['op'] != 'OUTCOME' or event['forecast_id'] != forecast_id:
            continue
        observation = event['observation']
        if observation not in rows:
            verified = False
        comparisons.append(dict(outcome=entry, matched_payload_ids=[c['payload_id'] for c in candidates if c['text'] == observation['text']]))
    distinct = {c['outcome']['event']['observation']['text'] for c in comparisons}
    if not verified:
        status = 'UNVERIFIABLE_HISTORY'
    elif not comparisons:
        status = 'PENDING'
    elif len(distinct) > 1:
        status = 'DIVERGENT_LATER_OBSERVATIONS'
    elif not candidates:
        status = 'NO_CANDIDATES_AT_CUTOFF'
    elif not comparisons[0]['matched_payload_ids']:
        status = 'OUTSIDE_FROZEN_SET'
    else:
        status = 'MATCHES_ONLY_CANDIDATE' if len(candidates) == 1 else 'MATCHES_ONE_OF_MULTIPLE'
    return dict(format='memoria.ia-prediction-comparison-v1', forecast=prediction, comparisons=comparisons,
                status=status, historical_prefix_verified=verified, frozen_candidate_count=len(candidates),
                distinct_later_contents=len(distinct), answer=None, qualified=False, selection_used=False,
                selected_target=None, proposal_payload_id=None,
                factual_quality_status='NOT_EVALUATED', provenance_independence='NOT_ESTABLISHED',
                caller_reliability_estimated=False, learning_applied=False,
                limitation='Exact later recurrence in caller-linked native observations, not factual confirmation, '
                'source authentication, semantic contradiction or new-value forecasting. Multiple observations may reflect state change.')


SCENARIOS = ('single_match', 'ambiguous_match', 'outside_set', 'divergent', 'generated', 'old_occurrence', 'empty_set', 'self_copy_as_user')


def scenario(library, name, seed):
    rows, region, queries = workload(seed, 'brackets', 'minimal')
    if name == 'single_match':
        rows = [r for r in rows if not r['source_id'].startswith(('transform-', 'extra-'))]
        rows = [dict(r, sequence=i + 1) for i, r in enumerate(rows)]
    if name == 'empty_set':
        rows = []
    query = queries[0]['text']
    with tempfile.TemporaryDirectory(prefix='memoria-prediction-') as directory:
        native = NativeProbe(library, Path(directory))
        try:
            persist(native, rows)
            first = forecast(native, region, query, 'prediction-1', 'scripted-forecaster')
            frozen = first['event']['receipt']['view']['candidates']
            checks = dict(forecast_does_not_learn=collect(native, [region]) == rows,
                          initially_pending=reconcile(native, region, 'prediction-1')['status'] == 'PENDING',
                          idempotent_forecast=forecast(native, region, query, 'prediction-1', 'scripted-forecaster')['status'] == 'EXACT_REPLAY')
            initial_log = journal(native, region)
            rejection = None
            if name == 'old_occurrence':
                target = next(r for r in rows if r['source_id'] == 'expected-anchor')
                try:
                    observe_outcome(native, region, 'prediction-1', 'outcome-1', 'scripted-observer', address(target))
                except ValueError as error:
                    rejection = str(error)
                checks['old_occurrence_rejected_without_write'] = rejection is not None and journal(native, region) == initial_log
            else:
                texts = ([frozen[0]['text'], frozen[1]['text']] if name == 'divergent' else
                         [frozen[0]['text'][:-1] + '9' + frozen[0]['text'][-1]] if name == 'outside_set' else
                         ['New unforecasted observation.'] if name == 'empty_set' else [frozen[0]['text']])
                for i, text in enumerate(texts):
                    row = dict(hierarchy_id=region, source_id='later-' + str(i),
                               sequence=max((r['sequence'] for r in collect(native, [region])), default=-1) + 1,
                               text=text, source_kind='assistant_generated' if name == 'generated' else 'user_turn')
                    persist(native, [row])
                    try:
                        observe_outcome(native, region, 'prediction-1', 'outcome-' + str(i), 'scripted-observer', address(row))
                    except ValueError as error:
                        if name != 'generated':
                            raise
                        rejection = str(error)
                if name == 'generated':
                    checks['generated_rejected_without_control_write'] = rejection is not None and journal(native, region) == initial_log
            before_rows, before_log = collect(native, [region]), journal(native, region)
            result = reconcile(native, region, 'prediction-1')
            checks.update(comparison_read_only=collect(native, [region]) == before_rows and journal(native, region) == before_log,
                          frozen_view_unchanged=journal(native, region)[0] == {k: first[k] for k in ('address', 'event')},
                          no_learning_or_factual_promotion=not result['learning_applied'] and result['answer'] is None and not result['qualified'],
                          no_independence_assumption=result['provenance_independence'] == 'NOT_ESTABLISHED')
            native.reopen()
            checks['cold_full_comparison_equal'] = reconcile(native, region, 'prediction-1') == result
            return dict(scenario=name, initial_rows=rows, query=query, result=result,
                        later_rows=before_rows[len(rows):], rejection=rejection, checks=checks)
        finally:
            native.close()


def probe(library, seed):
    cases = [scenario(library, name, seed) for name in SCENARIOS]
    checks = {f'{i}:{k}': v for i, c in enumerate(cases) for k, v in c['checks'].items()}
    checks['copied_hypothesis_indistinguishable_from_declared_observation'] = cases[1]['result'] == cases[7]['result']
    return dict(format='memoria.ia-prediction-audit-probe-v1', seed=seed, cases=cases, checks=checks,
                integrity_status='PASS' if all(checks.values()) else 'FAIL', integrity_passed=sum(checks.values()), integrity_total=len(checks),
                statuses={c['scenario']: c['result']['status'] for c in cases},
                factual_quality_status='NOT_EVALUATED', independence_status='NOT_ESTABLISHED', general_learning_status='NOT_ESTABLISHED')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--library', type=Path, required=True)
    parser.add_argument('--seed', type=int, default=20270117)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = probe(args.library, args.seed)
    result['report_content_sha256'] = fingerprint(result)
    write_report(args.output, result)
    print(json.dumps({k: result[k] for k in ('seed', 'integrity_status', 'integrity_passed', 'integrity_total', 'statuses', 'report_content_sha256')}))
    raise SystemExit(0 if result['integrity_status'] == 'PASS' else 1)


if __name__ == '__main__':
    main()
