#!/usr/bin/env python3
"""Restricted arithmetic extrapolation baseline, outside the cognitive core.

The constant-rate model class and numeric decoder are supplied by the programmer.
Only its rate is fitted from observed native history; hypotheses never become facts.
"""
import argparse
from fractions import Fraction
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile

import trajectory_prediction_audit as audit
from mobile_region_replay import NativeProbe
from trajectory_feedback_transfer_stress import write_report
from trajectory_question_frame_probe import collect,persist
from trajectory_region_evidence_probe import fingerprint

FORMAT = 'constant-rate-transition-baseline-v1'
MEASUREMENT = re.compile(r'M\[([a-z]{2});([0-9]{1,4})\]=(-?[0-9]{1,6})\.')
WORKER = Path(__file__).with_name('transition_measurement_world.py')


def request_fields(entity,tick):
    if not isinstance(entity,str) or not re.fullmatch('[a-z]{2}',entity) or type(tick) is not int or not 0<=tick<=1000:
        raise ValueError('entity/tick outside the explicit numeric contract')


def parse(text):
    match = MEASUREMENT.fullmatch(text)
    if match is None:
        return None
    entity,tick,value=match.groups(); tick,value=int(tick),int(value)
    if not 0<=tick<=1000 or not -10000<=value<=10000:
        return None
    return dict(entity=entity,tick=tick,value=value)


def fit(rows,region,entity,target_tick):
    """Pure fit; no worker, expected answer, seed, law, key or future observations."""
    request_fields(entity,target_tick)
    result=dict(format=FORMAT,entity=entity,target_tick=target_tick,model_class='CONSTANT_RATIONAL_RATE',
                status=None,points=[],rate=None,proposal=None,predicted_value_not_observed_for_entity=None,
                qualified=False,learning_applied=False)
    relevant=sorted((r for r in rows if r['hierarchy_id']==region and r['source_kind'] in ('user_turn','user_assertion')),
                    key=lambda r:(r['sequence'],r['source_id']))
    previous_tick=-1
    for row in relevant:
        point=parse(row['text'])
        if point is None:
            if row['text'].startswith('M['+entity+';'):
                result['status']='MALFORMED_TARGET_MEASUREMENT';return result
            continue
        if point['entity']!=entity:
            continue
        if point['tick']<previous_tick:
            result['status']='NONMONOTONIC_DECLARED_TICKS';return result
        previous_tick=point['tick']
        if result['points'] and result['points'][-1]['tick']==point['tick']:
            if result['points'][-1]['value']!=point['value']:
                result['status']='CONFLICTING_VALUES_AT_TICK';return result
            result['points'][-1]['addresses'].append(audit.address(row));continue
        result['points'].append(dict(tick=point['tick'],value=point['value'],addresses=[audit.address(row)]))
    points=result['points']
    if len(points)<3:
        result['status']='INSUFFICIENT_DISTINCT_TICKS';return result
    if target_tick<=points[-1]['tick']:
        result['status']='TARGET_NOT_AFTER_HISTORY';return result
    rates={Fraction(b['value']-a['value'],b['tick']-a['tick']) for a,b in zip(points,points[1:])}
    if len(rates)!=1:
        result['status']='INCONSISTENT_OBSERVED_RATES';return result
    rate=next(iter(rates));result['rate']=dict(numerator=rate.numerator,denominator=rate.denominator)
    predicted=points[-1]['value']+rate*(target_tick-points[-1]['tick'])
    if predicted.denominator!=1:
        result['status']='NONINTEGER_TARGET';return result
    value=predicted.numerator
    if not -10000<=value<=10000:
        result['status']='TARGET_OUT_OF_RANGE';return result
    result.update(status='PROPOSED_UNQUALIFIED_EXTRAPOLATION',proposal=dict(entity=entity,tick=target_tick,value=value,
                  text=f'M[{entity};{target_tick}]={value}.'),
                  predicted_value_not_observed_for_entity=value not in {p['value'] for p in points})
    return result


def query(entity,tick):
    request_fields(entity,tick)
    return f'Next[{entity};{tick}]?'


def freeze(native,region,entity,target_tick,forecast_id,actor_id):
    text=query(entity,target_tick)
    previous=[p for p in audit.journal(native,region) if p['event']['op']=='FORECAST' and p['event']['forecast_id']==forecast_id]
    if previous:
        context=previous[0]['event']['receipt'].get('observation_context')
        if (not isinstance(context,dict) or context.get('format')!=FORMAT or
                context.get('entity')!=entity or context.get('target_tick')!=target_tick):
            raise ValueError('forecast identity reused outside transition contract')
    else:
        context=fit(collect(native,[region]),region,entity,target_tick)
    return audit.forecast(native,region,text,forecast_id,actor_id,observation_context=context)


def context(native,region,forecast_id):
    entries=[p for p in audit.journal(native,region) if p['event']['op']=='FORECAST' and p['event']['forecast_id']==forecast_id]
    if len(entries)!=1:
        raise ValueError('transition forecast not found')
    binding=entries[0]['event']['receipt'];model=binding.get('observation_context')
    if not isinstance(model,dict) or model.get('format')!=FORMAT or binding['query']!=query(model['entity'],model['target_tick']):
        raise ValueError('invalid transition forecast context')
    return binding,model


def link_measurement(native,region,forecast_id,outcome_id,observer_id,observation_address):
    _,model=context(native,region,forecast_id)
    matches=[r for r in collect(native,[region]) if audit.address(r)==observation_address]
    if len(matches)!=1:
        raise ValueError('measurement occurrence not found')
    point=parse(matches[0]['text'])
    if point is None or (point['entity'],point['tick'])!=(model['entity'],model['target_tick']):
        raise ValueError('measurement does not match target entity and tick')
    return audit.observe_outcome(native,region,forecast_id,outcome_id,observer_id,observation_address)


def compare(native,region,forecast_id):
    binding,model=context(native,region,forecast_id)
    raw=audit.reconcile(native,region,forecast_id)
    prefix=collect(native,[region])[:binding['learning_row_count']]
    verified=raw['historical_prefix_verified'] and fit(prefix,region,model['entity'],model['target_tick'])==model
    observations=[p['outcome']['event']['observation'] for p in raw['comparisons']]
    if any(parse(r['text']) is None or (parse(r['text'])['entity'],parse(r['text'])['tick'])!=(model['entity'],model['target_tick']) for r in observations):
        verified=False
    distinct={r['text'] for r in observations}
    if not verified:
        status='UNVERIFIABLE_HISTORY'
    elif not observations:
        status='PENDING'
    elif model['proposal'] is None:
        status='ABSTAINED_BEFORE_OBSERVATION'
    elif len(distinct)>1:
        status='DIVERGENT_LATER_MEASUREMENTS'
    elif observations[0]['text']==model['proposal']['text']:
        status='MATCHES_PROPOSED_TRANSITION'
    else:
        status='DIFFERS_FROM_PROPOSED_TRANSITION'
    return dict(format=FORMAT,forecast_receipt_id=binding['receipt_id'],model=model,
                status=status,historical_prefix_verified=verified,observations=observations,
                answer=None,qualified=False,learning_applied=False,provenance_independence='NOT_ESTABLISHED',
                limitation='Programmer-supplied arithmetic model and measurement grammar, not general trajectory induction or factual confirmation.')


def measure(seed,entity,tick,law):
    response=subprocess.run([sys.executable,str(WORKER)],input=json.dumps(dict(seed=seed,entity=entity,tick=tick,law=law))+'\n',
                            capture_output=True,text=True,check=True,timeout=10)
    value=json.loads(response.stdout)
    if value.get('ok') is not True:
        raise ValueError('measurement worker rejected request')
    return value['measurement']


SCENARIOS=('linear_up','linear_down','constant','hidden_break','accelerating','two_points','repeated_one_point',
           'conflicting_tick','generated_training','foreign_training','unlinked_later','self_copy_as_observation')


def scenario(library,seed,name):
    region='transition-baseline';entity=chr(97+seed%26)+chr(97+(seed//26)%26)
    law=name if name in ('linear_up','linear_down','constant','hidden_break','accelerating') else 'hidden_break' if name=='self_copy_as_observation' else 'linear_up'
    ticks=[0,1] if name=='two_points' else [0,0,0] if name=='repeated_one_point' else [0,1,2]
    rows=[]
    for i,tick in enumerate(ticks):
        point=measure(seed,entity,tick,law)
        rows.append(dict(hierarchy_id=region+'-foreign' if name=='foreign_training' else region,
                         source_id=f'measure-{i}',sequence=i+1,text=point['text'],
                         source_kind='assistant_generated' if name=='generated_training' else 'user_turn'))
    if name=='conflicting_tick':
        value=parse(rows[-1]['text'])
        rows.append(dict(hierarchy_id=region,source_id='conflicting',sequence=4,
                         text=f"M[{entity};2]={value['value']+1}.",source_kind='user_turn'))
    with tempfile.TemporaryDirectory(prefix='memoria-transition-') as directory:
        native=NativeProbe(library,Path(directory))
        try:
            persist(native,rows)
            before=collect(native,[region])
            frozen=freeze(native,region,entity,3,'f1','baseline-forecaster')
            initial=compare(native,region,'f1')
            frozen_log=audit.journal(native,region)
            main_after_freeze=collect(native,[region])
            # Only after freeze is the later world measurement requested.
            actual=measure(seed,entity,3,law)
            supplied=initial['model']['proposal']['text'] if name=='self_copy_as_observation' else actual['text']
            row=dict(hierarchy_id=region,source_id='later-measurement',sequence=max((r['sequence'] for r in before),default=0)+1,
                     text=supplied,source_kind='user_turn')
            persist(native,[row])
            if name!='unlinked_later':
                link_measurement(native,region,'f1','o1','caller-linked-source',audit.address(row))
            result=compare(native,region,'f1')
            saved_rows,saved_log=collect(native,[region]),audit.journal(native,region)
            checks=dict(freeze_does_not_ingest_hypothesis=main_after_freeze==before,
                        initial_pending=initial['status']=='PENDING',
                        proposal_frozen=initial['model']==result['model'],
                        freeze_receipt_immutable=saved_log[0]==frozen_log[0],
                        no_factual_promotion=result['answer'] is None and not result['qualified'] and not result['learning_applied'],
                        no_independence_claim=result['provenance_independence']=='NOT_ESTABLISHED',
                        comparison_read_only=compare(native,region,'f1')==result and collect(native,[region])==saved_rows and audit.journal(native,region)==saved_log)
            retry=freeze(native,region,entity,3,'f1','baseline-forecaster')
            checks['freeze_retry_no_refresh']=retry['status']=='EXACT_REPLAY' and audit.journal(native,region)==saved_log
            native.reopen()
            checks['cold_full_comparison_equal']=compare(native,region,'f1')==result
            proposal=result['model']['proposal']
            return dict(scenario=name,rows=rows,frozen=frozen,initial=initial,actual_world_measurement=actual,
                        supplied_later_row=row,result=result,checks=checks,
                        evaluator=dict(proposal_matches_world=None if proposal is None else proposal['value']==actual['value'],
                                       supplied_measurement_matches_world=parse(supplied)['value']==actual['value'],
                                       truth_used_for_learning=False))
        finally:
            native.close()


def probe(library,seed):
    cases=[scenario(library,seed,name) for name in SCENARIOS]
    checks={f'{i}:{k}':v for i,c in enumerate(cases) for k,v in c['checks'].items()}
    by_name={c['scenario']:c for c in cases}
    checks['identical_prefix_different_future']=by_name['linear_up']['rows']==by_name['hidden_break']['rows'] and by_name['linear_up']['actual_world_measurement']!=by_name['hidden_break']['actual_world_measurement']
    checks['identical_prefix_same_proposal']=by_name['linear_up']['initial']['model']==by_name['hidden_break']['initial']['model']
    scored=[by_name[n] for n in ('linear_up','linear_down','constant','hidden_break')]
    return dict(format='memoria-transition-forecast-baseline-probe-v1',seed=seed,cases=cases,checks=checks,
                integrity_status='PASS' if all(checks.values()) else 'FAIL',integrity_passed=sum(checks.values()),integrity_total=len(checks),
                controlled_four_law_score=dict(proposed=len(scored),matches=sum(c['evaluator']['proposal_matches_world'] for c in scored),
                                               misses=sum(not c['evaluator']['proposal_matches_world'] for c in scored)),
                limitation='Restricted arithmetic baseline outside core. Model class, decoder and simulator supplied by programmer. One hidden-future-break miss preserved; self-copy match is not independent confirmation. No general induction, causal learning or factual promotion.')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--library',type=Path,required=True)
    parser.add_argument('--seed',type=int,default=20270127)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    result=probe(args.library,args.seed);result['report_content_sha256']=fingerprint(result)
    write_report(args.output,result)
    print(json.dumps({k:result[k] for k in ('seed','integrity_status','integrity_passed','integrity_total','controlled_four_law_score','report_content_sha256')}))
    raise SystemExit(0 if result['integrity_status']=='PASS' else 1)


if __name__=='__main__':
    main()
