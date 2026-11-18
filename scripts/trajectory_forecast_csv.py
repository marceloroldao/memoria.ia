#!/usr/bin/env python3
"""Validate and replay a bounded CSV into the existing native forecast lab.

The plan is previewable; models receive only the native prefix at each command.
"""
import argparse
from contextlib import nullcontext
import csv
import json
from pathlib import Path
import re
import sys

import trajectory_forecast_lab as forecast

FORMAT='memoria.ia-forecast-csv-v1'
COLUMNS=['observation_id','entity','tick','value']


def validate_records(records):
    if not isinstance(records,list) or not 1<=len(records)<=forecast.LIMITS['observations_per_scope']:
        raise ValueError('CSV requires 1..8 measurements')
    identities=set();entity=None;previous=-1
    for row in records:
        if not isinstance(row,dict) or set(row)!=set(COLUMNS): raise ValueError('invalid measurement fields')
        forecast.identifier(row['observation_id'],'observation_id')
        forecast.base.request_fields(row['entity'],row['tick'])
        if type(row['value']) is not int or not forecast.LIMITS['value_min']<=row['value']<=forecast.LIMITS['value_max']:
            raise ValueError('value requires integer in [-10000,10000]')
        if row['observation_id'] in identities: raise ValueError('CSV observation_id must be unique')
        if entity is not None and row['entity']!=entity: raise ValueError('CSV must describe exactly one entity')
        if row['tick']<=previous: raise ValueError('CSV ticks must strictly increase')
        identities.add(row['observation_id']);entity=row['entity'];previous=row['tick']
    return records


def read_csv(input_stream,delimiter=','):
    if delimiter not in (',',';'): raise ValueError('delimiter must be comma or semicolon')
    reader=csv.DictReader(input_stream,delimiter=delimiter)
    headers=reader.fieldnames
    if headers and headers[0].startswith('\ufeff'): headers[0]=headers[0][1:]
    if headers!=COLUMNS: raise ValueError('CSV header must be observation_id,entity,tick,value in this order')
    records=[]
    for row in reader:
        if len(records)>=forecast.LIMITS['observations_per_scope']: raise ValueError('CSV measurement limit is 8')
        if set(row)!=set(COLUMNS) or any(not isinstance(v,str) for v in row.values()):
            raise ValueError('CSV row has missing or extra cells')
        value={k:v.strip() for k,v in row.items()}
        if not re.fullmatch('[0-9]+',value['tick']) or not re.fullmatch('-?[0-9]+',value['value']):
            raise ValueError('CSV tick and value must be integer strings, not decimals or exponents')
        value.update(tick=int(value['tick']),value=int(value['value']))
        records.append(value)
    return validate_records(records)


def automatic_id(scope,entity,target_tick):
    return 'csv_'+forecast.base.fingerprint([scope,entity,target_tick])[:36]


def make_plan(records,scope='csv'):
    validate_records(records)
    if not isinstance(scope,str) or not re.fullmatch('[A-Za-z0-9_-]{1,32}',scope):
        raise ValueError('invalid CSV scope')
    commands=[];skipped=[];predictions=0
    for index,row in enumerate(records,1):
        commands.append(dict(row=index,after_observations=index,
                             command=dict(op='observe',scope=scope,**row)))
        target=row['tick']+1
        if index<3: reason='WARMUP_FEWER_THAN_THREE_TICKS'
        elif target>forecast.LIMITS['tick_max']: reason='TICK_LIMIT_REACHED'
        elif predictions>=forecast.LIMITS['predictions_per_scope']: reason='PREDICTION_BUDGET_REACHED'
        else: reason=None
        if reason:
            skipped.append(dict(row=index,target_tick=target,reason=reason));continue
        prediction_id=automatic_id(scope,row['entity'],target)
        commands.append(dict(row=index,after_observations=index,command=dict(op='predict',scope=scope,
                             prediction_id=prediction_id,entity=row['entity'],target_tick=target)))
        predictions+=1
    value=dict(format=FORMAT,scope=scope,records=records,commands=commands,skipped_predictions=skipped,
               normalized_input_sha256=forecast.base.fingerprint(records),limits=dict(forecast.LIMITS))
    value['plan_sha256']=forecast.base.fingerprint(value)
    return value


def validate_existing(lab,plan):
    """Read-only preflight. No historical prediction may be backfilled."""
    # Rebuild instead of trusting an edited preview plan supplied by a caller.
    if make_plan(plan['records'],plan['scope'])!=plan: raise ValueError('CSV plan was changed after validation')
    region='forecast-lab:'+plan['scope'];rows,log,groups=lab.state(region)
    records=plan['records']
    if len(rows)>len(records): raise ValueError('CSV must include the entire already stored prefix')
    for i,row in enumerate(rows):
        expected=records[i]
        text=f"M[{expected['entity']};{expected['tick']}]={expected['value']}."
        if (row['source_id']!='fl:observation:'+expected['observation_id'] or row['text']!=text or row['sequence']!=i+1):
            raise ValueError('CSV differs from the already stored measurement prefix')
    planned={item['command']['prediction_id']:item for item in plan['commands'] if item['command']['op']=='predict'}
    for prediction_id,group in groups.items():
        if prediction_id not in planned: raise ValueError('scope contains a prediction outside this CSV plan')
        item=planned[prediction_id];command=item['command'];count=item['after_observations']
        if set(group) not in ({'whole_history'},{'whole_history','recent_suffix'},set(forecast.PREFIXES)):
            raise ValueError('out-of-order partial prediction cannot be resumed')
        for rule,entry in group.items():
            binding=entry['event']['receipt'];model=binding['observation_context']
            if ((model['entity'],model['target_tick'])!=(command['entity'],command['target_tick']) or
                    binding['learning_row_count']!=count or not forecast.base.audit.verify_prefix(rows,binding)):
                raise ValueError('existing prediction does not match its planned earlier prefix')
            if rule!='selector': forecast.selection.checked_model(entry,rows,rule)
        if set(group)!=set(forecast.PREFIXES) and count!=len(rows):
            raise ValueError('cannot resume partial prediction after later observations')
    for prediction_id,item in planned.items():
        if item['after_observations']<len(rows) and prediction_id not in groups:
            raise ValueError('missing prediction before already stored measurements; historical backfill refused')
    lab.check_histories(region,groups)
    incomplete,missing=lab.repairs(rows,log,groups)
    if incomplete and missing: raise ValueError('mixed partial operations require manual recovery')
    observations={item['command']['observation_id']:item for item in plan['commands'] if item['command']['op']=='observe'}
    if any(o not in observations for o in missing): raise ValueError('repair observation is absent from CSV')
    repairs=[observations[o] for o in missing]+[planned[p] for p in incomplete]
    return sorted(repairs,key=lambda item:item['row'])


def emit(output_stream,value):
    output_stream.write(json.dumps(value,ensure_ascii=False)+'\n');output_stream.flush()


def apply_plan(lab,plan,repairs,output_stream):
    processed=0
    for phase,items in (('recovery',repairs),('apply',plan['commands'])):
        for item in items:
            response=lab.execute(item['command'])
            emit(output_stream,dict(ok=True,format=FORMAT,phase=phase,row=item['row'],
                 plan_sha256=plan['plan_sha256'],response=response,qualified=False))
            processed+=1
    status=lab.execute(dict(op='status',scope=plan['scope']))['result']
    summary=dict(ok=True,format=FORMAT,phase='summary',scope=plan['scope'],plan_sha256=plan['plan_sha256'],
                 normalized_input_sha256=plan['normalized_input_sha256'],commands_processed=processed,
                 recovery_commands=len(repairs),status=status,skipped_predictions=plan['skipped_predictions'],
                 answer=None,qualified=False,factual_quality_status='NOT_EVALUATED')
    emit(output_stream,summary)
    return summary


def import_plan(lab,plan,output_stream):
    with lab.lock:
        return apply_plan(lab,plan,validate_existing(lab,plan),output_stream)


def validation_error(error):
    return dict(ok=False,format=FORMAT,phase='validation',error=str(error),
                data_operations_started=False,answer=None,qualified=False)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',default='-',help='CSV file, or - for stdin')
    parser.add_argument('--delimiter',choices=[',',';'],default=',')
    parser.add_argument('--scope',default='csv')
    parser.add_argument('--dry-run',action='store_true')
    parser.add_argument('--library',type=Path)
    parser.add_argument('--data-dir',type=Path)
    args=parser.parse_args()
    if not args.dry_run and (args.library is None or args.data_dir is None):
        parser.error('--library and --data-dir are required without --dry-run')
    try:
        source=nullcontext(sys.stdin) if args.input=='-' else Path(args.input).open('r',encoding='utf-8-sig',newline='')
        with source as stream: plan=make_plan(read_csv(stream,args.delimiter),args.scope)
    except (ValueError,TypeError,KeyError,csv.Error,UnicodeError,OSError) as error:
        emit(sys.stdout,validation_error(error));return 2
    if args.dry_run:
        emit(sys.stdout,dict(ok=True,format=FORMAT,phase='plan',plan=plan,data_operations_started=False,qualified=False));return 0
    with forecast.open_lab(args.library,args.data_dir) as lab,lab.lock:
        try: repairs=validate_existing(lab,plan)
        except (ValueError,TypeError,KeyError) as error:
            emit(sys.stdout,validation_error(error));return 2
        # After preflight, failures propagate and terminate. Successful preceding
        # command replies remain valid; no batch rollback or false rejection claim.
        apply_plan(lab,plan,repairs,sys.stdout)
    return 0


if __name__=='__main__': raise SystemExit(main())
