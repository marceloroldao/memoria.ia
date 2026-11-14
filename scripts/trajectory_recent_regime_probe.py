#!/usr/bin/env python3
"""Restricted recent-rate suffix baseline, preserving every previous forecast.

Selection rule and arithmetic operators are programmed, not discovered by the core.
"""
import argparse
from fractions import Fraction
import json
from pathlib import Path
import tempfile

import trajectory_transition_forecast_probe as base
from trajectory_feedback_transfer_stress import write_report

FORMAT='recent-constant-rate-regime-baseline-v1'
POLICY=dict(selection='LATEST_EQUAL_RATE_SUFFIX',minimum_distinct_ticks=3)


def fit(rows,region,entity,target_tick):
    historical=base.fit(rows,region,entity,target_tick)
    points=historical['points']
    result=dict(format=FORMAT,entity=entity,target_tick=target_tick,policy=dict(POLICY),
                historical_status=historical['status'],history_points=points,
                active_from_tick=None,active_tick_count=0,excluded_earlier_point_count=0,
                status=historical['status'],rate=None,proposal=None,
                predicted_value_not_observed_for_entity=None,qualified=False,learning_applied=False)
    if historical['status'] not in ('PROPOSED_UNQUALIFIED_EXTRAPOLATION','INCONSISTENT_OBSERVED_RATES'):
        return result
    start=0
    if historical['status']=='INCONSISTENT_OBSERVED_RATES':
        start=len(points)-2
        rate=Fraction(points[-1]['value']-points[-2]['value'],points[-1]['tick']-points[-2]['tick'])
        while start>0:
            previous=Fraction(points[start]['value']-points[start-1]['value'],points[start]['tick']-points[start-1]['tick'])
            if previous!=rate:
                break
            start-=1
    suffix=points[start:]
    result.update(active_from_tick=suffix[0]['tick'],active_tick_count=len(suffix),excluded_earlier_point_count=start)
    if len(suffix)<POLICY['minimum_distinct_ticks']:
        result['status']='SUSPENDED_PENDING_STABLE_SUFFIX'
        return result
    addresses={tuple(a) for point in suffix for a in point['addresses']}
    selected=[r for r in rows if tuple(base.audit.address(r)) in addresses]
    active=base.fit(selected,region,entity,target_tick)
    result.update(status='PROPOSED_RECENT_REGIME_EXTRAPOLATION' if active['proposal'] is not None else active['status'],
                  rate=active['rate'],proposal=active['proposal'],
                  predicted_value_not_observed_for_entity=None if active['proposal'] is None else active['proposal']['value'] not in {p['value'] for p in points})
    return result


def freeze(native,region,entity,target_tick,forecast_id,actor_id):
    text=base.query(entity,target_tick)
    previous=[p for p in base.audit.journal(native,region) if p['event']['op']=='FORECAST' and p['event']['forecast_id']==forecast_id]
    if previous:
        model=previous[0]['event']['receipt'].get('observation_context')
        if (not isinstance(model,dict) or model.get('format')!=FORMAT or model.get('entity')!=entity or model.get('target_tick')!=target_tick):
            raise ValueError('forecast identity reused outside recent-regime contract')
    else:
        model=fit(base.collect(native,[region]),region,entity,target_tick)
    return base.audit.forecast(native,region,text,forecast_id,actor_id,observation_context=model)


def context(native,region,forecast_id):
    entries=[p for p in base.audit.journal(native,region) if p['event']['op']=='FORECAST' and p['event']['forecast_id']==forecast_id]
    if len(entries)!=1:
        raise ValueError('recent-regime forecast not found')
    binding=entries[0]['event']['receipt'];model=binding.get('observation_context')
    if not isinstance(model,dict) or model.get('format')!=FORMAT or binding['query']!=base.query(model['entity'],model['target_tick']):
        raise ValueError('invalid recent-regime forecast context')
    return binding,model


def link_measurement(native,region,forecast_id,outcome_id,observer_id,observation_address):
    _,model=context(native,region,forecast_id)
    matches=[r for r in base.collect(native,[region]) if base.audit.address(r)==observation_address]
    if len(matches)!=1:
        raise ValueError('measurement occurrence not found')
    point=base.parse(matches[0]['text'])
    if point is None or (point['entity'],point['tick'])!=(model['entity'],model['target_tick']):
        raise ValueError('measurement does not match target entity and tick')
    return base.audit.observe_outcome(native,region,forecast_id,outcome_id,observer_id,observation_address)


def compare(native,region,forecast_id):
    binding,model=context(native,region,forecast_id)
    raw=base.audit.reconcile(native,region,forecast_id)
    prefix=base.collect(native,[region])[:binding['learning_row_count']]
    verified=raw['historical_prefix_verified'] and fit(prefix,region,model['entity'],model['target_tick'])==model
    observations=[p['outcome']['event']['observation'] for p in raw['comparisons']]
    if any(base.parse(r['text']) is None or (base.parse(r['text'])['entity'],base.parse(r['text'])['tick'])!=(model['entity'],model['target_tick']) for r in observations):
        verified=False
    distinct={r['text'] for r in observations}
    if not verified: status='UNVERIFIABLE_HISTORY'
    elif not observations: status='PENDING'
    elif model['proposal'] is None: status='ABSTAINED_BEFORE_OBSERVATION'
    elif len(distinct)>1: status='DIVERGENT_LATER_MEASUREMENTS'
    elif observations[0]['text']==model['proposal']['text']: status='MATCHES_PROPOSED_TRANSITION'
    else: status='DIFFERS_FROM_PROPOSED_TRANSITION'
    return dict(format=FORMAT,forecast_receipt_id=binding['receipt_id'],model=model,status=status,
                historical_prefix_verified=verified,observations=observations,answer=None,qualified=False,
                learning_applied=False,provenance_independence='NOT_ESTABLISHED',
                limitation='Programmed recent-rate suffix rule, not general error-driven learning, source quality or truth.')


SCENARIOS=('stable_up','hidden_break','accelerating','poisoned_tail','self_copy_feedback','generated_tail')


def scenario(library,seed,name):
    region='recent-regime-baseline';entity=chr(97+seed%26)+chr(97+(seed//26)%26)
    law='hidden_break' if name in ('hidden_break','self_copy_feedback','generated_tail') else 'accelerating' if name=='accelerating' else 'linear_up'
    rows=[dict(hierarchy_id=region,source_id=f'm{i}',sequence=i+1,
               text=base.measure(seed,entity,i,law)['text'],source_kind='user_turn') for i in range(3)]
    with tempfile.TemporaryDirectory(prefix='memoria-recent-regime-') as directory:
        native=base.NativeProbe(library,Path(directory))
        try:
            base.persist(native,rows)
            steps=[];checks={}
            for tick in range(3,7):
                old_id,new_id=f'all-{tick}',f'recent-{tick}'
                before=base.collect(native,[region])
                old=base.freeze(native,region,entity,tick,old_id,'whole-history-baseline')
                new=freeze(native,region,entity,tick,new_id,'recent-regime-baseline')
                prior=compare(native,region,new_id)
                frozen_log=base.audit.journal(native,region)
                main_after_freeze=base.collect(native,[region])
                actual=base.measure(seed,entity,tick,law)
                supplied=actual['text'];kind='user_turn'
                if name=='poisoned_tail' and tick in (3,4,5):
                    supplied=f"M[{entity};{tick}]={actual['value']+10}."
                elif name=='self_copy_feedback':
                    supplied=prior['model']['proposal']['text']
                elif name=='generated_tail' and tick in (4,5):
                    kind='assistant_generated'
                row=dict(hierarchy_id=region,source_id=f'm{tick}',sequence=tick+1,text=supplied,source_kind=kind)
                base.persist(native,[row])
                if kind=='user_turn':
                    base.link_measurement(native,region,old_id,'o-'+old_id,'caller',base.audit.address(row))
                    link_measurement(native,region,new_id,'o-'+new_id,'caller',base.audit.address(row))
                full=base.compare(native,region,old_id);recent=compare(native,region,new_id)
                saved_rows,saved_log=base.collect(native,[region]),base.audit.journal(native,region)
                conditions=dict(no_proposal_ingested=main_after_freeze==before,
                                previous_events_preserved=saved_log[:len(frozen_log)]==frozen_log,
                                frozen_recent_model=prior['model']==recent['model'],
                                no_factual_promotion=recent['answer'] is None and not recent['qualified'] and not recent['learning_applied'],
                                no_independence_claim=recent['provenance_independence']=='NOT_ESTABLISHED',
                                read_only_comparison=compare(native,region,new_id)==recent and base.collect(native,[region])==saved_rows and base.audit.journal(native,region)==saved_log)
                retry=freeze(native,region,entity,tick,new_id,'recent-regime-baseline')
                conditions['retry_does_not_refit']=retry['status']=='EXACT_REPLAY' and base.audit.journal(native,region)==saved_log
                native.reopen()
                conditions['cold_comparison_equal']=compare(native,region,new_id)==recent and base.compare(native,region,old_id)==full
                checks.update({f'{tick}:{k}':v for k,v in conditions.items()})
                steps.append(dict(tick=tick,whole_forecast=old,recent_forecast=new,actual=actual,supplied=row,
                                  whole_result=full,recent_result=recent,
                                  evaluator=dict(whole_matches_world=None if full['model']['proposal'] is None else full['model']['proposal']['value']==actual['value'],
                                                 recent_matches_world=None if recent['model']['proposal'] is None else recent['model']['proposal']['value']==actual['value'],
                                                 supplied_matches_world=base.parse(supplied)['value']==actual['value'],truth_used_for_learning=False)))
            final_rows=base.collect(native,[region]);final_log=base.audit.journal(native,region)
            # Earlier failures are reproduced after all later observations, never rewritten.
            checks['original_failure_preserved']=base.compare(native,region,'all-3')==steps[0]['whole_result'] and compare(native,region,'recent-3')==steps[0]['recent_result']
            checks['old_comparison_read_only']=base.collect(native,[region])==final_rows and base.audit.journal(native,region)==final_log
            return dict(scenario=name,initial_rows=rows,steps=steps,final_rows=final_rows,checks=checks)
        finally:
            native.close()


def score(case,which):
    values=[s['evaluator'][which+'_matches_world'] for s in case['steps']]
    return dict(matches=sum(v is True for v in values),misses=sum(v is False for v in values),abstentions=sum(v is None for v in values))


def probe(library,seed):
    cases=[scenario(library,seed,name) for name in SCENARIOS]
    checks={f'{i}:{k}':v for i,c in enumerate(cases) for k,v in c['checks'].items()}
    hidden=next(c for c in cases if c['scenario']=='hidden_break')
    return dict(format='memoria-recent-regime-baseline-probe-v1',seed=seed,cases=cases,checks=checks,
                integrity_status='PASS' if all(checks.values()) else 'FAIL',integrity_passed=sum(checks.values()),integrity_total=len(checks),
                hidden_break_comparison=dict(whole_history=score(hidden,'whole'),recent_suffix=score(hidden,'recent')),
                limitation='Programmed suffix and arithmetic, not discovered operators or general learning from errors. Initial break remains unpredictable; poisoned or copied observations can mislead. No factual promotion or automatic integration into core.')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--library',type=Path,required=True)
    parser.add_argument('--seed',type=int,default=20270129)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    result=probe(args.library,args.seed);result['report_content_sha256']=base.fingerprint(result)
    write_report(args.output,result)
    print(json.dumps({k:result[k] for k in ('seed','integrity_status','integrity_passed','integrity_total','hidden_break_comparison','report_content_sha256')}))
    raise SystemExit(0 if result['integrity_status']=='PASS' else 1)


if __name__=='__main__': main()
