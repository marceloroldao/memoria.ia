#!/usr/bin/env python3
"""Bounded local JSON-lines observation/forecast loop using durable native BDR.

Linux pilot, one cooperating owner, no network or LLM. Declared integers only.
"""
import argparse
from contextlib import contextmanager
import json
from pathlib import Path
import re
import sys
import threading

import trajectory_rule_selection_probe as selection
from trajectory_feedback_lab import open_lab as open_native_owner

base=selection.base
ACTOR='forecast-lab'
OBSERVER='local-declared-measurement'
PREFIXES=dict(whole_history='fl:all:',recent_suffix='fl:recent:',selector='fl:select:')
LIMITS=dict(observations_per_scope=8,predictions_per_scope=5,value_min=-10000,value_max=10000,tick_max=1000)


def identifier(value,name):
    if not isinstance(value,str) or not re.fullmatch('[A-Za-z0-9_-]{1,40}',value):
        raise ValueError(name+' requires 1..40 ASCII letters, digits, underscores or hyphens')
    return value


def ids(prediction_id):
    return {r:p+prediction_id for r,p in PREFIXES.items()}


def outcome_id(forecast_id,row):
    return 'fl:o:'+base.fingerprint([forecast_id,base.audit.address(row)])


class ForecastLab:
    def __init__(self,native,lock=None):
        self.native=native
        self.lock=lock if lock is not None else threading.RLock()

    def state(self,region):
        rows=base.collect(self.native,[region]);log=base.audit.journal(self.native,region);groups={}
        if len(rows)>LIMITS['observations_per_scope']:
            raise ValueError('observation limit exceeded by external writer')
        for row in rows:
            if (row['source_kind']!='user_turn' or not row['source_id'].startswith('fl:observation:') or
                    base.parse(row['text']) is None):
                raise ValueError('foreign or malformed observation in laboratory scope')
            identifier(row['source_id'][len('fl:observation:'):],'observation_id')
        for entry in log:
            event=entry['event']
            if event['op']!='FORECAST': continue
            rule=next((r for r,p in PREFIXES.items() if event['forecast_id'].startswith(p)),None)
            if rule is None or event['actor_id']!=ACTOR:
                raise ValueError('foreign forecast in laboratory scope')
            prediction_id=identifier(event['forecast_id'][len(PREFIXES[rule]):],'prediction_id')
            model=event['receipt'].get('observation_context',{})
            expected=selection.FORMAT if rule=='selector' else selection.FORMATS[rule]
            if model.get('format')!=expected:
                raise ValueError('foreign forecast model in laboratory scope')
            group=groups.setdefault(prediction_id,{})
            group[rule]=entry
        if len(groups)>LIMITS['predictions_per_scope']:
            raise ValueError('prediction limit exceeded by external writer')
        for prediction_id,group in groups.items():
            targets={(e['event']['receipt']['observation_context']['entity'],e['event']['receipt']['observation_context']['target_tick']) for e in group.values()}
            if len(targets)!=1:
                raise ValueError('inconsistent partial prediction targets')
            if 'selector' in group:
                model=group['selector']['event']['receipt']['observation_context']
                named=ids(prediction_id)
                if set(group)!=set(PREFIXES) or model['candidate_ids']!={r:named[r] for r in selection.RULES}:
                    raise ValueError('inconsistent selector catalog')
        for entry in log:
            event=entry['event']
            if event['op']=='OUTCOME' and (event['observer_id']!=OBSERVER or event['outcome_id']!=outcome_id(event['forecast_id'],event['observation'])):
                raise ValueError('foreign outcome linkage in laboratory scope')
        return rows,log,groups

    def comparisons(self,region,prediction_id,group):
        model=next(iter(group.values()))['event']['receipt']['observation_context']
        if set(group)!=set(PREFIXES):
            return dict(prediction_id=prediction_id,state='INCOMPLETE',entity=model['entity'],target_tick=model['target_tick'],
                        completed_stages=sorted(group))
        named=ids(prediction_id)
        selected=selection.compare(self.native,region,named['selector'])
        full=base.compare(self.native,region,named['whole_history'])
        recent=selection.recent.compare(self.native,region,named['recent_suffix'])
        return dict(prediction_id=prediction_id,state='COMPLETE',entity=model['entity'],target_tick=model['target_tick'],
                    comparison=selected['status'],proposal=selected['model']['proposal'],
                    decision=selected['model']['status'],selected_rule=selected['model']['selected_rule'],
                    scores=selected['model']['scores'],paired_trial_count=len(selected['model']['paired_trials']),
                    forecast_receipt_id=selected['forecast_receipt_id'],history_verified=all(r['historical_prefix_verified'] for r in (selected,full,recent)),
                    candidates=dict(whole_history=dict(proposal=full['model']['proposal'],comparison=full['status']),
                                    recent_suffix=dict(proposal=recent['model']['proposal'],comparison=recent['status'])))

    def repairs(self,rows,log,groups):
        incomplete=[p for p,g in groups.items() if set(g)!=set(PREFIXES)]
        missing=set()
        for group in groups.values():
            if set(group)!=set(PREFIXES): continue
            model=group['selector']['event']['receipt']['observation_context']
            for row in rows:
                point=base.parse(row['text'])
                if (point['entity'],point['tick'])!=(model['entity'],model['target_tick']): continue
                if any(row['sequence']>e['event']['receipt']['cutoff_sequence'] and not any(
                    item['event']['op']=='OUTCOME' and item['event']['forecast_id']==e['event']['forecast_id'] and
                    base.audit.address(item['event']['observation'])==base.audit.address(row) for item in log) for e in group.values()):
                    missing.add(row['source_id'][len('fl:observation:'):])
        return sorted(incomplete),sorted(missing)

    def check_histories(self,region,groups):
        for prediction_id,group in groups.items():
            if set(group)==set(PREFIXES) and not self.comparisons(region,prediction_id,group)['history_verified']:
                raise ValueError('history cannot be reproduced; laboratory writes blocked')

    def auto_link(self,region,row,groups):
        point=base.parse(row['text']);matched=[]
        for prediction_id,group in groups.items():
            if set(group)!=set(PREFIXES): continue
            model=group['selector']['event']['receipt']['observation_context']
            if (point['entity'],point['tick'])!=(model['entity'],model['target_tick']): continue
            named=ids(prediction_id);address=base.audit.address(row)
            base.link_measurement(self.native,region,named['whole_history'],outcome_id(named['whole_history'],row),OBSERVER,address)
            selection.recent.link_measurement(self.native,region,named['recent_suffix'],outcome_id(named['recent_suffix'],row),OBSERVER,address)
            selection.link_measurement(self.native,region,named['selector'],outcome_id(named['selector'],row),OBSERVER,address)
            matched.append(prediction_id)
        return matched

    def execute(self,request):
        fields={'observe':{'observation_id','entity','tick','value'},'predict':{'prediction_id','entity','target_tick'},
                'prediction':{'prediction_id'},'history':set(),'status':set()}
        if not isinstance(request,dict) or not isinstance(request.get('op'),str) or request['op'] not in fields:
            raise ValueError('unknown laboratory operation')
        op=request['op']
        if set(request)-({'op','scope'}|fields[op]) or not fields[op]<=set(request):
            raise ValueError('missing or unknown command fields')
        scope=request.get('scope','principal')
        if not isinstance(scope,str) or not re.fullmatch('[A-Za-z0-9_-]{1,32}',scope):
            raise ValueError('scope requires 1..32 ASCII letters, digits, underscores or hyphens')
        region='forecast-lab:'+scope
        if op in ('predict','prediction'): identifier(request['prediction_id'],'prediction_id')
        if op=='observe':
            identifier(request['observation_id'],'observation_id');base.request_fields(request['entity'],request['tick'])
            if type(request['value']) is not int or not LIMITS['value_min']<=request['value']<=LIMITS['value_max']:
                raise ValueError('value requires an integer in [-10000,10000]')
        if op=='predict': base.request_fields(request['entity'],request['target_tick'])
        with self.lock:
            rows,log,groups=self.state(region)
            incomplete,missing=self.repairs(rows,log,groups)
            if op=='status':
                result=dict(observation_count=len(rows),prediction_count=len(groups),limits=dict(LIMITS),
                            repair_prediction_ids=incomplete,repair_observation_ids=missing)
            elif op=='history':
                result=dict(entries=rows,journal=log,predictions=[self.comparisons(region,p,g) for p,g in groups.items()],
                            repair_prediction_ids=incomplete,repair_observation_ids=missing)
            elif op=='prediction':
                group=groups.get(request['prediction_id'])
                if group is None: raise ValueError('prediction not found in scope')
                result=dict(prediction=self.comparisons(region,request['prediction_id'],group))
            else:
                self.check_histories(region,groups)
                if op=='observe':
                    if incomplete: raise ValueError('retry incomplete prediction before new observations: '+','.join(incomplete))
                    obs=request['observation_id']
                    if missing and obs not in missing:
                        raise ValueError('retry incomplete observation linkage first: '+','.join(missing))
                    body=f"M[{request['entity']};{request['tick']}]={request['value']}."
                    source='fl:observation:'+obs
                    existing=[r for r in rows if r['source_id']==source]
                    if existing:
                        if len(existing)!=1 or existing[0]['text']!=body: raise ValueError('observation_id reused with different measurement')
                        row=existing[0];status='EXACT_REPLAY'
                    else:
                        if len(rows)>=LIMITS['observations_per_scope']: raise ValueError('observation limit reached; start another scope')
                        if any(r['text']==body for r in rows): raise ValueError('identical measurement already recorded; reuse its observation_id')
                        ticks=[base.parse(r['text'])['tick'] for r in rows if base.parse(r['text'])['entity']==request['entity']]
                        if ticks and request['tick']<max(ticks): raise ValueError('new declared ticks must not decrease')
                        row=dict(hierarchy_id=region,source_id=source,sequence=max((r['sequence'] for r in rows),default=0)+1,
                                 text=body,source_kind='user_turn');status='APPENDED'
                    try:
                        if not existing: base.persist(self.native,[row])
                        base.audit.flush(self.native)
                        linked=self.auto_link(region,row,groups)
                        result=dict(status=status,entry=row,comparisons=[self.comparisons(region,p,groups[p]) for p in linked])
                    except Exception as error:
                        raise RuntimeError('observation may be partially persisted; reopen and retry the same observation_id') from error
                else:
                    prediction_id=request['prediction_id'];named=ids(prediction_id);existing=groups.get(prediction_id)
                    if missing: raise ValueError('retry incomplete observation linkage before prediction: '+','.join(missing))
                    if incomplete and incomplete!=[prediction_id]: raise ValueError('retry incomplete prediction first: '+','.join(incomplete))
                    if existing:
                        model=next(iter(existing.values()))['event']['receipt']['observation_context']
                        if (model['entity'],model['target_tick'])!=(request['entity'],request['target_tick']):
                            raise ValueError('prediction_id reused with different target')
                        if set(existing)==set(PREFIXES):
                            return self.response(op,scope,dict(status='EXACT_REPLAY',prediction=self.comparisons(region,prediction_id,existing)))
                    else:
                        if len(groups)>=LIMITS['predictions_per_scope']: raise ValueError('prediction limit reached; start another scope')
                        for group in groups.values():
                            model=next(iter(group.values()))['event']['receipt']['observation_context']
                            if (model['entity'],model['target_tick'])==(request['entity'],request['target_tick']):
                                raise ValueError('target already has a prediction; reuse its prediction_id')
                        ticks=[base.parse(r['text'])['tick'] for r in rows if base.parse(r['text'])['entity']==request['entity']]
                        if ticks and request['target_tick']<=max(ticks): raise ValueError('prediction target must follow observed ticks')
                    # Bounded models are checked before starting any new stage.
                    for reader in (base.fit,selection.recent.fit):
                        base.audit.metadata(reader(rows,region,request['entity'],request['target_tick']))
                    try:
                        base.freeze(self.native,region,request['entity'],request['target_tick'],named['whole_history'],ACTOR)
                        selection.recent.freeze(self.native,region,request['entity'],request['target_tick'],named['recent_suffix'],ACTOR)
                        selection.freeze(self.native,region,{r:named[r] for r in selection.RULES},named['selector'],ACTOR)
                        _,_,new_groups=self.state(region)
                        result=dict(status='APPENDED' if not existing else 'COMPLETED_RETRY',
                                    prediction=self.comparisons(region,prediction_id,new_groups[prediction_id]))
                    except Exception as error:
                        raise RuntimeError('prediction may be partially persisted; reopen and retry the same prediction_id') from error
            return self.response(op,scope,result)

    @staticmethod
    def response(op,scope,result):
        return dict(format='memoria.ia-forecast-lab-v1',op=op,scope=scope,result=result,
                    answer=None,qualified=False,factual_quality_status='NOT_EVALUATED',
                    limitation='Bounded declared-integer pilot with supplied rules, not a general predictor or authenticated sensor.')


@contextmanager
def open_lab(library,data_dir):
    # Reuse the same advisory owner lock as the existing local feedback lab.
    with open_native_owner(library,data_dir) as owner:
        yield ForecastLab(owner.native,owner.lock)


def serve(lab,input_stream,output_stream):
    for line in input_stream:
        try:
            result=dict(ok=True,**lab.execute(json.loads(line)))
        except (ValueError,TypeError,KeyError) as error:
            result=dict(ok=False,error=str(error),answer=None,qualified=False)
        # Runtime/native failures intentionally terminate. No false 'rejected' reply
        # is sent after a potentially partial mutation.
        output_stream.write(json.dumps(result,ensure_ascii=False)+'\n');output_stream.flush()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--library',type=Path,required=True)
    parser.add_argument('--data-dir',type=Path,required=True)
    args=parser.parse_args()
    with open_lab(args.library,args.data_dir) as lab: serve(lab,sys.stdin,sys.stdout)


if __name__=='__main__': main()
