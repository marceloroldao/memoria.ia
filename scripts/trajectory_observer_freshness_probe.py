#!/usr/bin/env python3
"""Frozen declared-tick freshness policy for the opt-in authenticated observer.

No world-value oracle, trust learning or automatic factual qualification.
"""
import argparse
import base64
import json
from pathlib import Path
import tempfile

import authenticated_symbol_observer as signer
import controlled_symbol_observer as world
import trajectory_authenticated_observer_probe as auth
import trajectory_prediction_audit as audit
from mobile_region_replay import NativeProbe
from trajectory_feedback_transfer_stress import write_report
from trajectory_question_frame_probe import collect, persist
from trajectory_region_evidence_probe import fingerprint
from trajectory_window_consistency_probe import window_snapshot

FORMAT = 'observer-declared-tick-freshness-v1'
PREFIX = 'observer-freshness:'
CODEC = FORMAT + ':'


def policy_value(policy):
    if (not isinstance(policy, dict) or set(policy) != {'max_tick_lag'} or
            type(policy['max_tick_lag']) is not int or not 0 <= policy['max_tick_lag'] <= 1000):
        raise ValueError('policy requires only integer max_tick_lag in [0,1000]')
    return dict(policy)


def field(region):
    audit.field(region)
    if region.startswith(PREFIX):
        raise ValueError('freshness controls cannot be a learning region')
    return PREFIX + fingerprint(region)


def policies(native, region):
    found = {}
    for row in window_snapshot(native, field(region))['rows']:
        if row['source_kind'] != 'user_turn' or not row['text'].startswith(CODEC):
            raise ValueError('invalid freshness policy encoding')
        value = json.loads(base64.b64decode(row['text'][len(CODEC):], validate=True).decode('utf-8'))
        if not isinstance(value, dict) or set(value) != {'format', 'region', 'forecast_id', 'forecast_receipt_id', 'policy', 'policy_sha256'}:
            raise ValueError('invalid freshness policy schema')
        policy_value(value['policy']); audit.identity(value['forecast_id'])
        if (value['format'] != FORMAT or value['region'] != region or
                value['policy_sha256'] != fingerprint(value['policy']) or value['forecast_id'] in found or
                row['source_id'] != 'freshness-policy:' + fingerprint(value['forecast_id']) or
                row['sequence'] != len(found) + 1):
            raise ValueError('invalid freshness policy identity or digest')
        found[value['forecast_id']] = value
    return found


def freeze_policy(native, region, forecast_id, policy):
    policy = policy_value(policy)
    _, binding = auth.frozen_task(native, region, forecast_id)
    value = dict(format=FORMAT, region=region, forecast_id=forecast_id,
                 forecast_receipt_id=binding['receipt_id'], policy=policy, policy_sha256=fingerprint(policy))
    previous = policies(native, region)
    if forecast_id in previous:
        if previous[forecast_id] != value:
            raise ValueError('frozen freshness policy cannot be changed')
        audit.flush(native)
        return dict(status='EXACT_REPLAY', binding=value)
    rows = collect(native, [region])
    if (len(rows) != binding['learning_row_count'] or not audit.verify_prefix(rows, binding) or
            any(p['event']['op'] == 'OUTCOME' and p['event']['forecast_id'] == forecast_id for p in audit.journal(native, region))):
        raise ValueError('freshness policy must be frozen before later observations')
    persist(native, [dict(hierarchy_id=field(region), source_id='freshness-policy:' + fingerprint(forecast_id),
        sequence=len(previous)+1, source_kind='user_turn',
        text=CODEC + base64.b64encode(world.canonical(value).encode('utf-8')).decode('ascii'))])
    audit.flush(native)
    return dict(status='APPENDED', binding=value)


def bound_policy(native, region, forecast_id):
    _, binding = auth.frozen_task(native, region, forecast_id)
    value = policies(native, region).get(forecast_id)
    if value is None or value['forecast_receipt_id'] != binding['receipt_id']:
        raise ValueError('freshness policy not frozen for this forecast receipt')
    return value, binding


def assess(native, region, forecast_id, envelope, keyring):
    """Read-only. Authenticates declarations, not physical time or world value."""
    value, binding = bound_policy(native, region, forecast_id)
    task, _ = auth.frozen_task(native, region, forecast_id)
    packet = signer.verify(envelope, task, auth.trusted_key(task, keyring))
    auth.controlled.validate_packet(packet)
    if packet['request'] != task['request']:
        raise ValueError('packet request differs from frozen task')
    if not audit.verify_prefix(collect(native, [region]), binding):
        raise ValueError('frozen history unavailable')
    lag = task['request']['tick'] - packet['reported_tick']
    meets_policy = 0 <= lag <= value['policy']['max_tick_lag']
    return dict(format=FORMAT, forecast_receipt_id=binding['receipt_id'],
                policy_sha256=value['policy_sha256'], envelope_sha256=fingerprint(envelope),
                declared_tick_lag=lag, status='MEETS_DECLARED_TICK_POLICY' if meets_policy else 'STALE_DECLARED_TICK',
                truth_established=False, learning_applied=False)


def admit(native, region, forecast_id, outcome_id, envelope, keyring):
    audit.identity(outcome_id)
    assessment = assess(native, region, forecast_id, envelope, keyring)
    if assessment['status'] != 'MEETS_DECLARED_TICK_POLICY':
        return dict(status='NOT_ADMITTED', assessment=assessment, link=None)
    link = auth.ingest_result(native, region, forecast_id, outcome_id, envelope, keyring)
    return dict(status='ADMITTED', assessment=assessment, link=link)


def assess_history(native, region, forecast_id, keyring):
    """Reevaluate persisted outcomes, including bypasses, under the frozen policy."""
    bound_policy(native, region, forecast_id)
    authentication = auth.authenticate_history(native, region, forecast_id, keyring)
    comparison = audit.reconcile(native, region, forecast_id)
    if not comparison['historical_prefix_verified']:
        raise ValueError('frozen history unavailable')
    results = [dict(outcome_id=p['event']['outcome_id'], assessment=assess(native, region, forecast_id,
                        p['event'].get('source_receipt'), keyring))
               for p in audit.journal(native, region) if p['event']['op'] == 'OUTCOME'
               and p['event']['forecast_id'] == forecast_id]
    return dict(format=FORMAT, authentication=authentication, outcomes=results,
                truth_established=False, learning_applied=False)


SCENARIOS = ('faithful_strict', 'lagged_strict', 'lagged_tolerated', 'zero_tick_lagged',
             'authorized_false_current_tick', 'unsigned_forgery', 'revoked_key', 'late_policy')


def scenario(library, seed, name):
    rows, region, query, entity, past = auth.controlled.prepare_rows(seed)
    request = dict(world_seed=seed, entity=entity, tick=0 if name == 'zero_tick_lagged' else 1,
                   sensor_mode='lagged' if name in ('lagged_strict', 'lagged_tolerated', 'zero_tick_lagged') else 'faithful')
    policy = dict(max_tick_lag=1 if name == 'lagged_tolerated' else 0)
    keyring = {('sensor-a','key-1'):auth.TEST_KEY}
    with tempfile.TemporaryDirectory(prefix='memoria-freshness-') as directory:
        native = NativeProbe(library, Path(directory))
        try:
            persist(native, rows)
            frozen = auth.freeze_task(native, region, query, 'f1', 'forecaster', request, 'sensor-a', 'key-1',
                                      challenge=world.digest([seed,name]))
            task = frozen['event']['receipt']['observation_context']
            if name != 'late_policy':
                freeze_policy(native, region, 'f1', policy)
            envelope = auth.run_observer(task, auth.TEST_KEY)
            if name in ('authorized_false_current_tick', 'unsigned_forgery'):
                packet = envelope['body']['packet']
                packet.update(value=past['value'], text=world.render(entity,past['value']))
                packet['result_sha256'] = world.digest({k:v for k,v in packet.items() if k!='result_sha256'})
                if name == 'authorized_false_current_tick':
                    envelope['mac'] = signer.mac(envelope['body'],auth.TEST_KEY)
            if name == 'revoked_key':
                keyring = {}
            if name == 'late_policy':
                auth.ingest_result(native,region,'f1','outside-gate',envelope,keyring)
            before = dict(rows=collect(native,[region]), log=audit.journal(native,region), policies=policies(native,region))
            rejection, result = None, None
            try:
                if name == 'late_policy':
                    freeze_policy(native,region,'f1',policy)
                else:
                    result = admit(native,region,'f1','o1',envelope,keyring)
            except ValueError as error:
                if name not in ('unsigned_forgery','revoked_key','late_policy'):
                    raise
                rejection = str(error)
            comparison = audit.reconcile(native,region,'f1')
            saved = dict(rows=collect(native,[region]),log=audit.journal(native,region),policies=policies(native,region))
            accepted = name in ('faithful_strict','lagged_tolerated','zero_tick_lagged','authorized_false_current_tick')
            checks = dict(expected_admission=bool(result and result['status']=='ADMITTED') == accepted,
                          expected_error=bool(rejection) == (name in ('unsigned_forgery','revoked_key','late_policy')),
                          frozen_hypotheses_unchanged=saved['log'][0] == before['log'][0],
                          control_policy_unchanged=saved['policies'] == before['policies'],
                          no_factual_promotion=comparison['answer'] is None and not comparison['qualified'] and not comparison['learning_applied'],
                          no_secret_in_controls=auth.TEST_KEY.hex() not in world.canonical(saved) and auth.TEST_KEY.decode() not in world.canonical(saved))
            history = None
            if accepted:
                history = assess_history(native,region,'f1',keyring)
                checks['cold_history_expected_count'] = len(history['outcomes']) == 1
                replay = admit(native,region,'f1','o1',envelope,keyring)
                checks['exact_replay_no_write'] = replay['link']['status']=='EXACT_REPLAY' and collect(native,[region])==saved['rows'] and audit.journal(native,region)==saved['log']
            else:
                checks['nonadmission_no_write'] = saved == before
            if name == 'lagged_strict':
                checks['stale_explicitly_retained'] = result['assessment']['status']=='STALE_DECLARED_TICK' and comparison['status']=='PENDING'
            if name not in ('unsigned_forgery','revoked_key','late_policy'):
                checks['assessment_read_only'] = assess(native,region,'f1',envelope,keyring)==result['assessment'] and collect(native,[region])==saved['rows'] and audit.journal(native,region)==saved['log'] and policies(native,region)==saved['policies']
            native.reopen()
            checks['cold_comparison_equal'] = audit.reconcile(native,region,'f1')==comparison
            checks['cold_policy_equal'] = policies(native,region)==saved['policies']
            if accepted:
                checks['cold_history_equal'] = assess_history(native,region,'f1',keyring)==history
            return dict(scenario=name, rows=rows, request=request, policy=policy, frozen=frozen,
                        envelope=envelope, result=result, rejection=rejection, comparison=comparison,
                        saved_policies=saved['policies'], history=history, checks=checks,
                        evaluator=dict(linked_reports_agree_with_world=[p['outcome']['event']['source_receipt']['body']['packet']['value']==world.world_value(seed,entity,request['tick']) for p in comparison['comparisons']],truth_used_for_learning=False))
        finally:
            native.close()


def probe(library, seed):
    cases = [scenario(library,seed,name) for name in SCENARIOS]
    checks = {f'{i}:{k}':v for i,c in enumerate(cases) for k,v in c['checks'].items()}
    return dict(format='memoria-observer-freshness-probe-v1',seed=seed,cases=cases,checks=checks,
                integrity_status='PASS' if all(checks.values()) else 'FAIL',integrity_passed=sum(checks.values()),integrity_total=len(checks),
                limitation='Frozen caller policy over authenticated declared simulation ticks. No physical freshness, sensor accuracy, general quality or truth guarantee. Authorized false current-tick values pass. No automatic learning.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--library',type=Path,required=True)
    parser.add_argument('--seed',type=int,default=20270123)
    parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args()
    result = probe(args.library,args.seed)
    result['report_content_sha256'] = fingerprint(result)
    write_report(args.output,result)
    print(json.dumps({k:result[k] for k in ('seed','integrity_status','integrity_passed','integrity_total','report_content_sha256')}))
    raise SystemExit(0 if result['integrity_status']=='PASS' else 1)


if __name__ == '__main__':
    main()
