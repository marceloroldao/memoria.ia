#!/usr/bin/env python3
"""Past-only selection between two supplied arithmetic baselines, not fact learning."""
import argparse
import json
from pathlib import Path
import tempfile

import trajectory_recent_regime_probe as recent
from trajectory_feedback_transfer_stress import write_report

base=recent.base
FORMAT='paired-past-loss-rule-selection-v1'
RULES=('whole_history','recent_suffix')
FORMATS={'whole_history':base.FORMAT,'recent_suffix':recent.FORMAT}
POLICY=dict(match_cost=0,abstention_cost=1,mismatch_cost=2,minimum_paired_trials=2)


def checked_model(entry,rows,rule):
    binding=entry['event']['receipt'];model=binding.get('observation_context')
    if not isinstance(model,dict) or model.get('format')!=FORMATS[rule]:
        raise ValueError('wrong candidate model format')
    if binding['query']!=base.query(model['entity'],model['target_tick']) or not base.audit.verify_prefix(rows,binding):
        raise ValueError('candidate prefix or query cannot be reproduced')
    reader=base.fit if rule=='whole_history' else recent.fit
    if reader(rows[:binding['learning_row_count']],binding['region'],model['entity'],model['target_tick'])!=model:
        raise ValueError('candidate model cannot be reproduced')
    return binding,model


def prefix_key(binding):
    return (binding['region'],binding['query'],binding['learning_row_count'],binding['cutoff_sequence'],binding['snapshot_sha256'])


def historical_trials(log,rows,entity,target_tick):
    groups={}
    for entry in log:
        event=entry['event']
        if event['op']!='FORECAST': continue
        model=event['receipt'].get('observation_context',{})
        rule=next((r for r in RULES if model.get('format')==FORMATS[r]),None)
        if rule is None or model.get('entity')!=entity or model.get('target_tick',target_tick)>=target_tick: continue
        group=groups.setdefault(model['target_tick'],{r:[] for r in RULES})
        group[rule].append(entry)
    trials,skipped=[],[]
    for tick,pair in sorted(groups.items()):
        reason=None
        if any(len(pair[r])!=1 for r in RULES):
            reason='MISSING_OR_AMBIGUOUS_CANDIDATE_PAIR'
        else:
            entries={r:pair[r][0] for r in RULES}
            try:
                verified={r:checked_model(entries[r],rows,r) for r in RULES}
                if prefix_key(verified[RULES[0]][0])!=prefix_key(verified[RULES[1]][0]):
                    reason='DIFFERENT_TRAINING_PREFIXES'
                outcomes={r:[p['event'] for p in log if p['event']['op']=='OUTCOME' and
                             p['event']['forecast_id']==entries[r]['event']['forecast_id']] for r in RULES}
                if any(len(outcomes[r])!=1 for r in RULES):
                    reason='MISSING_OR_AMBIGUOUS_OUTCOME_PAIR'
                elif outcomes[RULES[0]][0]['observation']!=outcomes[RULES[1]][0]['observation']:
                    reason='DIFFERENT_MEASUREMENT_OCCURRENCES'
                else:
                    observation=outcomes[RULES[0]][0]['observation'];point=base.parse(observation['text'])
                    if observation not in rows or point is None or (point['entity'],point['tick'])!=(entity,tick):
                        reason='INVALID_TARGET_MEASUREMENT'
                if reason is None:
                    losses={};kinds={}
                    for r in RULES:
                        proposal=verified[r][1]['proposal']
                        kind='abstention' if proposal is None else 'match' if proposal['text']==observation['text'] else 'mismatch'
                        kinds[r]=kind;losses[r]=POLICY[kind+'_cost']
                    trials.append(dict(tick=tick,forecast_ids={r:entries[r]['event']['forecast_id'] for r in RULES},
                                       observation_address=base.audit.address(observation),kinds=kinds,losses=losses))
            except ValueError:
                reason='UNVERIFIABLE_CANDIDATE_HISTORY'
        if reason is not None: skipped.append(dict(tick=tick,reason=reason))
    return trials,skipped


def choose(proposals,trials):
    scores={r:dict(total_loss=sum(t['losses'][r] for t in trials),
                   matches=sum(t['kinds'][r]=='match' for t in trials),
                   mismatches=sum(t['kinds'][r]=='mismatch' for t in trials),
                   abstentions=sum(t['kinds'][r]=='abstention' for t in trials)) for r in RULES}
    leader=None
    if len(trials)>=POLICY['minimum_paired_trials'] and scores[RULES[0]]['total_loss']!=scores[RULES[1]]['total_loss']:
        leader=min(RULES,key=lambda r:scores[r]['total_loss'])
    if leader is not None:
        proposal=proposals[leader]
        status='PAST_LOSS_LEADER' if proposal is not None else 'ABSTAIN_LEADER_HAS_NO_PROPOSAL'
    elif all(proposals[r] is not None for r in RULES) and proposals[RULES[0]]==proposals[RULES[1]]:
        proposal=proposals[RULES[0]];status='CONSENSUS_WITHOUT_LEADER'
    else:
        proposal=None;status='ABSTAIN_NO_SUPPORTED_LEADER'
    return dict(status=status,selected_rule=leader,proposal=proposal,scores=scores)


def decision(log,rows,region,candidate_ids):
    if not isinstance(candidate_ids,dict) or set(candidate_ids)!=set(RULES) or len(set(candidate_ids.values()))!=2:
        raise ValueError('requires two distinct named candidate forecasts')
    entries={}
    for r in RULES:
        found=[e for e in log if e['event']['op']=='FORECAST' and e['event']['forecast_id']==candidate_ids[r]]
        if len(found)!=1: raise ValueError('candidate forecast not found')
        entries[r]=found[0]
    verified={r:checked_model(entries[r],rows,r) for r in RULES}
    first_binding,first_model=verified[RULES[0]]
    if (any(prefix_key(verified[r][0])!=prefix_key(first_binding) or verified[r][1]['entity']!=first_model['entity'] or
            verified[r][1]['target_tick']!=first_model['target_tick'] for r in RULES) or
            first_binding['region']!=region or first_binding['learning_row_count']!=len(rows) or
            any(p['event']['op']=='OUTCOME' and p['event']['forecast_id'] in candidate_ids.values() for p in log)):
        raise ValueError('current candidates must share current prefix and remain unobserved')
    trials,skipped=historical_trials(log,rows,first_model['entity'],first_model['target_tick'])
    result=choose({r:verified[r][1]['proposal'] for r in RULES},trials)
    return dict(format=FORMAT,entity=first_model['entity'],target_tick=first_model['target_tick'],policy=dict(POLICY),
                candidate_ids=candidate_ids,candidate_receipt_ids={r:verified[r][0]['receipt_id'] for r in RULES},
                journal_prefix_count=len(log),journal_prefix_sha256=base.fingerprint(log),paired_trials=trials,
                skipped_trials=skipped,**result,qualified=False,learning_applied=False)


def freeze(native,region,candidate_ids,forecast_id,actor_id):
    log=base.audit.journal(native,region)
    previous=[p for p in log if p['event']['op']=='FORECAST' and p['event']['forecast_id']==forecast_id]
    if previous:
        model=previous[0]['event']['receipt'].get('observation_context')
        if not isinstance(model,dict) or model.get('format')!=FORMAT or model.get('candidate_ids')!=candidate_ids:
            raise ValueError('selector identity reused with different candidates')
    else:
        model=decision(log,base.collect(native,[region]),region,candidate_ids)
    return base.audit.forecast(native,region,base.query(model['entity'],model['target_tick']),forecast_id,actor_id,
                              observation_context=model)


def context(native,region,forecast_id):
    log=base.audit.journal(native,region)
    entries=[p for p in log if p['event']['op']=='FORECAST' and p['event']['forecast_id']==forecast_id]
    if len(entries)!=1: raise ValueError('selector forecast not found')
    binding=entries[0]['event']['receipt'];model=binding.get('observation_context')
    if not isinstance(model,dict) or model.get('format')!=FORMAT or binding['query']!=base.query(model['entity'],model['target_tick']):
        raise ValueError('invalid selector forecast context')
    return binding,model,log


def link_measurement(native,region,forecast_id,outcome_id,observer_id,observation_address):
    _,model,_=context(native,region,forecast_id)
    found=[r for r in base.collect(native,[region]) if base.audit.address(r)==observation_address]
    point=base.parse(found[0]['text']) if len(found)==1 else None
    if point is None or (point['entity'],point['tick'])!=(model['entity'],model['target_tick']):
        raise ValueError('measurement does not match selector target')
    return base.audit.observe_outcome(native,region,forecast_id,outcome_id,observer_id,observation_address)


def compare(native,region,forecast_id):
    binding,model,log=context(native,region,forecast_id)
    raw=base.audit.reconcile(native,region,forecast_id)
    rows=base.collect(native,[region]);prefix=rows[:binding['learning_row_count']]
    prior=log[:model['journal_prefix_count']]
    verified=(raw['historical_prefix_verified'] and base.fingerprint(prior)==model['journal_prefix_sha256'] and
              decision(prior,prefix,region,model['candidate_ids'])==model)
    observations=[p['outcome']['event']['observation'] for p in raw['comparisons']]
    if any(base.parse(r['text']) is None or (base.parse(r['text'])['entity'],base.parse(r['text'])['tick'])!=(model['entity'],model['target_tick']) for r in observations): verified=False
    if not verified: status='UNVERIFIABLE_HISTORY'
    elif not observations: status='PENDING'
    elif model['proposal'] is None: status='ABSTAINED_BEFORE_OBSERVATION'
    elif len({r['text'] for r in observations})>1: status='DIVERGENT_LATER_MEASUREMENTS'
    elif observations[0]['text']==model['proposal']['text']: status='MATCHES_SELECTED_PROPOSAL'
    else: status='DIFFERS_FROM_SELECTED_PROPOSAL'
    return dict(format=FORMAT,forecast_receipt_id=binding['receipt_id'],model=model,status=status,
                historical_prefix_verified=verified,observations=observations,answer=None,qualified=False,
                learning_applied=False,provenance_independence='NOT_ESTABLISHED',
                limitation='Past paired loss over declared measurements, not source truth, independent consensus or general model discovery.')


SCENARIOS=('stable','hidden_break','accelerating','poisoned_labels','self_copy_labels')


def scenario(library,seed,name):
    region='rule-selection';entity=chr(97+seed%26)+chr(97+(seed//26)%26)
    law='hidden_break' if name in ('hidden_break','self_copy_labels') else 'accelerating' if name=='accelerating' else 'linear_up'
    initial=[dict(hierarchy_id=region,source_id=f'm{i}',sequence=i+1,text=base.measure(seed,entity,i,law)['text'],source_kind='user_turn') for i in range(3)]
    with tempfile.TemporaryDirectory(prefix='memoria-rule-selection-') as directory:
        native=base.NativeProbe(library,Path(directory))
        try:
            base.persist(native,initial);steps=[];checks={}
            for tick in range(3,8):
                ids=dict(whole_history=f'all-{tick}',recent_suffix=f'recent-{tick}');fid=f'select-{tick}'
                before=base.collect(native,[region])
                base.freeze(native,region,entity,tick,ids['whole_history'],'whole-baseline')
                recent.freeze(native,region,entity,tick,ids['recent_suffix'],'recent-baseline')
                selected=freeze(native,region,ids,fid,'selector')
                pending=compare(native,region,fid);frozen_log=base.audit.journal(native,region)
                after_freeze=base.collect(native,[region])
                actual=base.measure(seed,entity,tick,law);supplied=actual['text']
                if name=='poisoned_labels': supplied=f"M[{entity};{tick}]={actual['value']+10}."
                elif name=='self_copy_labels': supplied=pending['model']['proposal']['text']
                row=dict(hierarchy_id=region,source_id=f'm{tick}',sequence=tick+1,text=supplied,source_kind='user_turn')
                base.persist(native,[row]);address=base.audit.address(row)
                base.link_measurement(native,region,ids['whole_history'],'o-'+ids['whole_history'],'caller',address)
                recent.link_measurement(native,region,ids['recent_suffix'],'o-'+ids['recent_suffix'],'caller',address)
                link_measurement(native,region,fid,'o-'+fid,'caller',address)
                result=compare(native,region,fid)
                saved_rows,saved_log=base.collect(native,[region]),base.audit.journal(native,region)
                conditions=dict(no_proposal_ingested=after_freeze==before,initial_pending=pending['status']=='PENDING',
                                old_events_unchanged=saved_log[:len(frozen_log)]==frozen_log,
                                selector_does_not_use_later_result=pending['model']==result['model'],
                                only_earlier_ticks_scored=all(t['tick']<tick for t in result['model']['paired_trials']),
                                no_factual_promotion=result['answer'] is None and not result['qualified'] and not result['learning_applied'],
                                read_only_comparison=compare(native,region,fid)==result and base.collect(native,[region])==saved_rows and base.audit.journal(native,region)==saved_log)
                retry=freeze(native,region,ids,fid,'selector')
                conditions['retry_no_rescoring']=retry['status']=='EXACT_REPLAY' and base.audit.journal(native,region)==saved_log
                native.reopen();conditions['cold_decision_equal']=compare(native,region,fid)==result
                checks.update({f'{tick}:{k}':v for k,v in conditions.items()})
                proposal=result['model']['proposal']
                steps.append(dict(tick=tick,forecast=selected,result=result,actual=actual,supplied=row,
                                  evaluator=dict(proposal_matches_world=None if proposal is None else proposal['value']==actual['value'],
                                                 supplied_matches_world=base.parse(supplied)['value']==actual['value'],truth_used_for_selection=False)))
            final=steps[-1]['result'];checks['first_decision_unchanged']=compare(native,region,'select-3')==steps[0]['result']
            return dict(scenario=name,initial_rows=initial,steps=steps,checks=checks,final_rows=base.collect(native,[region]),
                        final_journal=base.audit.journal(native,region),final_selected_rule=final['model']['selected_rule'])
        finally: native.close()


def probe(library,seed):
    cases=[scenario(library,seed,name) for name in SCENARIOS]
    checks={f'{i}:{k}':v for i,c in enumerate(cases) for k,v in c['checks'].items()}
    by_name={c['scenario']:c for c in cases}
    return dict(format='memoria-past-rule-selection-probe-v1',seed=seed,cases=cases,checks=checks,
                integrity_status='PASS' if all(checks.values()) else 'FAIL',integrity_passed=sum(checks.values()),integrity_total=len(checks),
                hidden_break_final_selection=by_name['hidden_break']['final_selected_rule'],
                limitation='Programmed candidate catalog, costs and minimum support. Only earlier paired native results inform choice. False labels can select a rule wrong for the world; correlated consensus is not independent confirmation. No core model discovery or factual promotion.')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--library',type=Path,required=True)
    parser.add_argument('--seed',type=int,default=20270131)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();result=probe(args.library,args.seed);result['report_content_sha256']=base.fingerprint(result)
    write_report(args.output,result)
    print(json.dumps({k:result[k] for k in ('seed','integrity_status','integrity_passed','integrity_total','hidden_break_final_selection','report_content_sha256')}))
    raise SystemExit(0 if result['integrity_status']=='PASS' else 1)


if __name__=='__main__': main()
