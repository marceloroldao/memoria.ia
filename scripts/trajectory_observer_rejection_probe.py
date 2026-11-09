#!/usr/bin/env python3
"""Separate native receipts for authenticated stale observations; never facts."""
import argparse
import base64
import copy
import json
from pathlib import Path
import tempfile

import trajectory_observer_freshness_probe as fresh
from mobile_region_replay import NativeProbe
from trajectory_feedback_transfer_stress import write_report
from trajectory_question_frame_probe import collect, persist
from trajectory_region_evidence_probe import fingerprint
from trajectory_window_consistency_probe import window_snapshot

FORMAT = 'observer-stale-rejection-journal-v1'
PREFIX = 'observer-rejections:'
CODEC = FORMAT + ':'


def field(region):
    fresh.field(region)
    if region.startswith(PREFIX):
        raise ValueError('rejection controls cannot be a learning region')
    return PREFIX + fingerprint(region)


def structural_receipt(value, region):
    required = {'format','region','rejection_id','forecast_id','policy_binding','envelope',
                'assessment','previous_sha256','receipt_sha256'}
    if not isinstance(value,dict) or set(value)!=required:
        raise ValueError('invalid rejection receipt schema')
    fresh.audit.identity(value['rejection_id']); fresh.audit.identity(value['forecast_id'])
    if value['format']!=FORMAT or value['region']!=region:
        raise ValueError('invalid rejection receipt scope')
    binding = value['policy_binding']
    expected = {'format','region','forecast_id','forecast_receipt_id','policy','policy_sha256'}
    if not isinstance(binding,dict) or set(binding)!=expected:
        raise ValueError('invalid recorded policy schema')
    fresh.policy_value(binding['policy'])
    if (binding['format']!=fresh.FORMAT or binding['region']!=region or
            binding['forecast_id']!=value['forecast_id'] or binding['policy_sha256']!=fingerprint(binding['policy'])):
        raise ValueError('invalid recorded policy scope or digest')
    envelope = fresh.audit.metadata(value['envelope'])
    if (not isinstance(envelope,dict) or set(envelope)!={'body','mac'} or
            not isinstance(envelope['body'],dict) or set(envelope['body'])!={'task','packet'}):
        raise ValueError('invalid recorded envelope schema')
    packet, task = envelope['body']['packet'], envelope['body']['task']
    fresh.auth.controlled.validate_packet(packet)
    # This reader verifies structure, not current key trust or executable versions.
    if (not isinstance(task,dict) or task.get('region')!=region or task.get('forecast_id')!=value['forecast_id'] or
            packet['request']!=task.get('request')):
        raise ValueError('invalid recorded envelope scope')
    lag = packet['request']['tick'] - packet['reported_tick']
    expected_assessment = dict(format=fresh.FORMAT,forecast_receipt_id=binding['forecast_receipt_id'],
        policy_sha256=binding['policy_sha256'],envelope_sha256=fingerprint(envelope),declared_tick_lag=lag,
        status='STALE_DECLARED_TICK',truth_established=False,learning_applied=False)
    if (lag<=binding['policy']['max_tick_lag'] or value['assessment']!=expected_assessment or
            value['receipt_sha256']!=fingerprint({k:v for k,v in value.items() if k!='receipt_sha256'})):
        raise ValueError('invalid recorded stale assessment or receipt digest')
    return value


def journal(native, region):
    records, identities, pairs = [], set(), set()
    previous = None
    for row in window_snapshot(native,field(region))['rows']:
        if row['source_kind']!='user_turn' or not row['text'].startswith(CODEC):
            raise ValueError('invalid rejection journal encoding')
        value = structural_receipt(json.loads(base64.b64decode(row['text'][len(CODEC):],validate=True).decode('utf-8')),region)
        pair = (value['forecast_id'],value['assessment']['envelope_sha256'])
        if (value['rejection_id'] in identities or pair in pairs or value['previous_sha256']!=previous or
                row['source_id']!='observer-rejection:'+fingerprint(value['rejection_id']) or row['sequence']!=len(records)+1):
            raise ValueError('invalid rejection identity, order or chain')
        identities.add(value['rejection_id']); pairs.add(pair)
        previous = value['receipt_sha256']
        records.append(value)
    return records


def record_rejection(native, region, forecast_id, rejection_id, envelope, keyring):
    fresh.audit.identity(rejection_id)
    # Current trust and frozen policy must be checked even for an exact retry.
    assessment = fresh.assess(native,region,forecast_id,envelope,keyring)
    if assessment['status']!='STALE_DECLARED_TICK':
        raise ValueError('only authenticated stale observations belong in this journal')
    binding,_ = fresh.bound_policy(native,region,forecast_id)
    envelope = fresh.audit.metadata(envelope)
    records = journal(native,region)
    for old in records:
        if old['rejection_id']==rejection_id:
            if (old['forecast_id']!=forecast_id or old['envelope']!=envelope or
                    old['assessment']!=assessment or old['policy_binding']!=binding):
                raise ValueError('rejection identity reused with different receipt')
            fresh.audit.flush(native)
            return dict(status='EXACT_REPLAY',receipt=old)
        if old['forecast_id']==forecast_id and old['assessment']['envelope_sha256']==assessment['envelope_sha256']:
            raise ValueError('same envelope already recorded under another rejection identity')
    value = dict(format=FORMAT,region=region,rejection_id=rejection_id,forecast_id=forecast_id,
                 policy_binding=binding,envelope=envelope,assessment=assessment,
                 previous_sha256=records[-1]['receipt_sha256'] if records else None)
    value['receipt_sha256'] = fingerprint(value)
    structural_receipt(value,region)
    persist(native,[dict(hierarchy_id=field(region),source_id='observer-rejection:'+fingerprint(rejection_id),
                        sequence=len(records)+1,source_kind='user_turn',
                        text=CODEC+base64.b64encode(fresh.world.canonical(value).encode('utf-8')).decode('ascii'))])
    fresh.audit.flush(native)
    return dict(status='APPENDED',receipt=value)


def admit_with_rejections(native, region, forecast_id, outcome_id, envelope, keyring):
    fresh.audit.identity(outcome_id)
    journal(native,region)
    assessment = fresh.assess(native,region,forecast_id,envelope,keyring)
    if assessment['status']=='STALE_DECLARED_TICK':
        recorded = record_rejection(native,region,forecast_id,outcome_id,envelope,keyring)
        return dict(status='NOT_ADMITTED',assessment=assessment,link=None,rejection=recorded)
    return dict(**fresh.admit(native,region,forecast_id,outcome_id,envelope,keyring),rejection=None)


def review(native, region, keyring):
    """Read-only current verification; original receipts survive loss of trust."""
    results = []
    for value in journal(native,region):
        result = dict(rejection_id=value['rejection_id'],receipt_sha256=value['receipt_sha256'])
        try:
            binding,_ = fresh.bound_policy(native,region,value['forecast_id'])
            if binding!=value['policy_binding']:
                raise ValueError('recorded policy differs from current frozen policy')
            assessment = fresh.assess(native,region,value['forecast_id'],value['envelope'],keyring)
            if assessment!=value['assessment']:
                raise ValueError('recorded assessment cannot be reproduced')
            result.update(status='REVERIFIED_STALE',assessment=assessment,reason=None)
        except ValueError as error:
            result.update(status='CURRENT_VERIFICATION_FAILED',assessment=None,reason=str(error))
        results.append(result)
    return dict(format=FORMAT,receipts=results,truth_established=False,learning_applied=False)


SCENARIOS = ('stale_retained','renamed_replay','conflicting_identity','revoked_before_record',
             'revoked_after_record','tampered_packet','fresh_routed','authorized_false_fresh')


def snapshot(native, region):
    return dict(rows=collect(native,[region]),predictions=fresh.audit.journal(native,region),
                policies=fresh.policies(native,region),rejections=journal(native,region))


def scenario(library, seed, name):
    rows,region,query,entity,past = fresh.auth.controlled.prepare_rows(seed)
    request = dict(world_seed=seed,entity=entity,tick=1,
                   sensor_mode='faithful' if name in ('fresh_routed','authorized_false_fresh') else 'lagged')
    keyring = {('sensor-a','key-1'):fresh.auth.TEST_KEY}
    with tempfile.TemporaryDirectory(prefix='memoria-rejections-') as directory:
        native = NativeProbe(library,Path(directory))
        try:
            persist(native,rows)
            frozen = fresh.auth.freeze_task(native,region,query,'f1','forecaster',request,'sensor-a','key-1',
                                           challenge=fresh.world.digest([seed,name]))
            fresh.freeze_policy(native,region,'f1',{'max_tick_lag':0})
            task = frozen['event']['receipt']['observation_context']
            issued = fresh.auth.run_observer(task,fresh.auth.TEST_KEY)
            envelope = copy.deepcopy(issued)
            if name in ('tampered_packet','authorized_false_fresh'):
                packet = envelope['body']['packet']
                packet['value'] = past['value'] if name=='authorized_false_fresh' else packet['value']+1
                packet['text'] = fresh.world.render(entity,packet['value'])
                packet['result_sha256'] = fresh.world.digest({k:v for k,v in packet.items() if k!='result_sha256'})
                if name=='authorized_false_fresh':
                    envelope['mac'] = fresh.signer.mac(envelope['body'],fresh.auth.TEST_KEY)
            if name=='revoked_before_record':
                keyring = {}
            before = snapshot(native,region)
            result, error, followup_error = None,None,None
            try:
                result = admit_with_rejections(native,region,'f1','receipt-1',envelope,keyring)
            except ValueError as exception:
                if name not in ('revoked_before_record','tampered_packet'):
                    raise
                error = str(exception)
            saved = snapshot(native,region)
            if name in ('renamed_replay','conflicting_identity'):
                changed = copy.deepcopy(envelope)
                identity = 'renamed' if name=='renamed_replay' else 'receipt-1'
                if name=='conflicting_identity':
                    packet = changed['body']['packet'];packet['value']+=1
                    packet['text'] = fresh.world.render(entity,packet['value'])
                    packet['result_sha256'] = fresh.world.digest({k:v for k,v in packet.items() if k!='result_sha256'})
                    changed['mac'] = fresh.signer.mac(changed['body'],fresh.auth.TEST_KEY)
                try:
                    admit_with_rejections(native,region,'f1',identity,changed,keyring)
                except ValueError as exception:
                    followup_error = str(exception)
            accepted = name in ('fresh_routed','authorized_false_fresh')
            rejected = name in ('revoked_before_record','tampered_packet')
            checks = dict(expected_route=(result is not None and result['status']=='ADMITTED')==accepted,
                          expected_initial_error=bool(error)==rejected,
                          expected_followup_error=bool(followup_error)==(name in ('renamed_replay','conflicting_identity')),
                          frozen_policy_unchanged=saved['policies']==before['policies'],
                          forecast_unchanged=saved['predictions'][0]==before['predictions'][0],
                          identity_conflict_no_write=snapshot(native,region)==saved)
            if not accepted:
                checks['main_observations_unchanged'] = saved['rows']==before['rows']
                checks['no_prediction_outcome'] = saved['predictions']==before['predictions']
            if rejected:
                checks['invalid_packet_no_control_write'] = saved==before
            elif accepted:
                checks['fresh_path_no_rejection_receipt'] = saved['rejections']==[]
            else:
                checks['complete_envelope_retained'] = len(saved['rejections'])==1 and saved['rejections'][0]['envelope']==envelope
                retry = admit_with_rejections(native,region,'f1','receipt-1',envelope,keyring)
                checks['exact_replay_no_extra_receipt'] = retry['rejection']['status']=='EXACT_REPLAY' and snapshot(native,region)==saved
            if name=='revoked_after_record':
                keyring = {}
            reviewed = review(native,region,keyring)
            if saved['rejections']:
                expected = 'CURRENT_VERIFICATION_FAILED' if name=='revoked_after_record' else 'REVERIFIED_STALE'
                checks['current_trust_explicit'] = reviewed['receipts'][0]['status']==expected
            checks['review_read_only'] = snapshot(native,region)==saved
            comparison = fresh.audit.reconcile(native,region,'f1')
            checks['no_factual_promotion'] = comparison['answer'] is None and not comparison['qualified'] and not comparison['learning_applied']
            checks['no_secret_in_control_journal'] = fresh.auth.TEST_KEY.hex() not in fresh.world.canonical(saved) and fresh.auth.TEST_KEY.decode() not in fresh.world.canonical(saved)
            native.reopen()
            checks['cold_full_snapshot_equal'] = snapshot(native,region)==saved
            checks['cold_review_equal'] = review(native,region,keyring)==reviewed
            checks['cold_comparison_equal'] = fresh.audit.reconcile(native,region,'f1')==comparison
            return dict(scenario=name,rows=rows,request=request,frozen=frozen,issued_envelope=issued,received_envelope=envelope,
                        result=result,error=error,followup_error=followup_error,quarantine=saved['rejections'],review=reviewed,
                        comparison=comparison,checks=checks,
                        evaluator=dict(linked_reports_agree_with_world=[p['outcome']['event']['source_receipt']['body']['packet']['value']==fresh.world.world_value(seed,entity,1) for p in comparison['comparisons']],truth_used_for_learning=False))
        finally:
            native.close()


def probe(library, seed):
    cases = [scenario(library,seed,name) for name in SCENARIOS]
    checks = {f'{i}:{k}':v for i,c in enumerate(cases) for k,v in c['checks'].items()}
    return dict(format='memoria-observer-rejection-probe-v1',seed=seed,cases=cases,checks=checks,
                integrity_status='PASS' if all(checks.values()) else 'FAIL',integrity_passed=sum(checks.values()),integrity_total=len(checks),
                limitation='Optional separate journal for authenticated stale envelopes only. Current trust may fail later without erasing history. Hash chain is not an externally authenticated audit log or truncation proof. False current-tick values still pass; no factual promotion.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--library',type=Path,required=True)
    parser.add_argument('--seed',type=int,default=20270125)
    parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args()
    result = probe(args.library,args.seed)
    result['report_content_sha256'] = fingerprint(result)
    write_report(args.output,result)
    print(json.dumps({k:result[k] for k in ('seed','integrity_status','integrity_passed','integrity_total','report_content_sha256')}))
    raise SystemExit(0 if result['integrity_status']=='PASS' else 1)


if __name__=='__main__':
    main()
