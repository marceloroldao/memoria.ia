#!/usr/bin/env python3
"""Append-only withdrawal of an exact feedback occurrence; no erasure or truth claim."""
import argparse
import base64
import json
from pathlib import Path
import tempfile

from mobile_region_replay import NativeProbe
from trajectory_feedback_continuity_probe import continuity_decision, historical_proofs, witness_provenance
from trajectory_feedback_gate_probe import gated_read
from trajectory_feedback_ledger_probe import canonical, events, ledger_region, receipt, record
from trajectory_question_frame_probe import collect, persist, score
from trajectory_region_evidence_probe import fingerprint
from trajectory_route_relation_probe import fixture
from trajectory_window_consistency_probe import window_snapshot


PREFIX='feedback-withdrawals:'
CODEC='feedback-withdrawal-json-utf8-base64-v1:'


def withdrawal_region(region):
    ledger_region(region)
    if region.startswith(PREFIX): raise ValueError('invalid learning region')
    return PREFIX+fingerprint(region)


def withdrawals(native, region):
    result=[]
    for row in window_snapshot(native,withdrawal_region(region))['rows']:
        if not row['text'].startswith(CODEC): raise ValueError('unknown withdrawal codec')
        event=json.loads(base64.b64decode(row['text'][len(CODEC):],validate=True).decode('utf-8'))
        result.append(dict(address=dict(region=row['hierarchy_id'],source_id=row['source_id'],sequence=row['sequence']),event=event))
    return result


def feedback_projection(ledger, controls):
    """Validate exact addresses/content and keep every original event auditable."""
    by_digest={fingerprint(entry):entry for entry in ledger}
    if len(by_digest)!=len(ledger): raise ValueError('duplicate feedback occurrence')
    withdrawn={}; requests=set()
    for control in controls:
        event=control['event']; digest=event['target_sha256']; target=by_digest.get(digest)
        if (event['format']!='memoria.ia-feedback-withdrawal-v1' or target is None
            or event['target_address']!=target['address']
            or event['target_event_id']!=target['event']['event_id']
            or event['target_receipt_id']!=target['event']['receipt']['receipt_id']
            or event['actor_id']!=target['event']['actor_id']
            or event['request_id'] in requests or digest in withdrawn):
            raise ValueError('invalid or conflicting withdrawal history')
        requests.add(event['request_id']);withdrawn[digest]=control
    return [dict(entry,active=fingerprint(entry) not in withdrawn,
                 withdrawal=withdrawn.get(fingerprint(entry))) for entry in ledger]


def withdraw(native, region, request_id, actor_id, target):
    """Caller identity consistency only; no authentication or multi-writer transaction."""
    field=withdrawal_region(region)
    if any(not isinstance(v,str) or not v for v in (request_id,actor_id)):
        raise ValueError('nonempty request and actor identities required')
    ledger=events(native,region)
    matches=[entry for entry in ledger if canonical(entry)==canonical(target)]
    if len(matches)!=1: raise ValueError('target is not an exact local feedback occurrence')
    target=matches[0]
    if actor_id!=target['event']['actor_id']: raise ValueError('actor does not match feedback origin')
    event=dict(format='memoria.ia-feedback-withdrawal-v1',request_id=request_id,actor_id=actor_id,
               target_address=target['address'],target_event_id=target['event']['event_id'],
               target_receipt_id=target['event']['receipt']['receipt_id'],target_sha256=fingerprint(target))
    controls=withdrawals(native,region)
    projection=feedback_projection(ledger,controls)
    previous=[c for c in controls if c['event']['request_id']==request_id]
    if previous:
        if len(previous)!=1 or canonical(previous[0]['event'])!=canonical(event):
            raise ValueError('withdrawal identity reused with different content')
        return dict(status='EXACT_REPLAY',**previous[0])
    if not next(p['active'] for p in projection if p['event']['event_id']==target['event']['event_id']):
        raise ValueError('feedback occurrence already withdrawn')
    sequence=len(controls)+1; source='withdrawal-request:'+fingerprint(request_id)
    encoded=CODEC+base64.b64encode(canonical(event).encode('utf-8')).decode('ascii')
    status,response=native.call('observe_structural_text',dict(hierarchy_id=field,source_id=source,
                                sequence=sequence,text=encoded,source_kind='user_turn'))
    if status!=0 or response.get('duplicate'): raise RuntimeError('withdrawal persistence failed')
    return dict(status='APPENDED',address=dict(region=field,source_id=source,sequence=sequence),event=event)


def withdrawal_read(native, region, query, *, enabled=False):
    withdrawal_region(region)
    result=gated_read(native,region,query)
    result['format']='memoria.ia-feedback-withdrawal-gate-v1'
    if not enabled: return result
    ledger=events(native,region);controls=withdrawals(native,region)
    projection=feedback_projection(ledger,controls)
    active=[dict(address=p['address'],event=p['event']) for p in projection if p['active']]
    proofs=historical_proofs(collect(native,[region]),active)
    decisions=[];available=[];withheld=[]
    for candidate in result['raw_view']['candidates']:
        binding=receipt(native,region,query,candidate['payload_id'])
        item=continuity_decision(binding,active,current_provenance=witness_provenance(result['raw_view'],candidate),proofs=proofs)
        decisions.append(dict(payload_id=candidate['payload_id'],**item))
        (withheld if item['withheld'] else available).append(candidate)
    result.update(enabled=True,feedback_projection=projection,withdrawal_history=controls,
                  decisions=decisions,available_candidates=available,withheld_candidates=withheld,
                  candidate_filter_used=bool(withheld))
    return result


SCENARIOS=('wrong_veto_withdrawn','correct_veto_withdrawn','other_opposition_remains','support_withdrawn')


def scenario(native,name,seed,renamed):
    rows,region,queries=fixture('partial_overlap' if name=='correct_veto_withdrawn' else 'same_root_two_routes',seed,renamed)
    persist(native,rows)
    query=next(q for q in queries if q['name']=='literal_cue')
    raw=withdrawal_read(native,region,query['text'])['raw_view']
    target=(next(c for c in raw['candidates'] if any(o[1]=='added-map-target' for o in c['origins']))
            if name=='correct_veto_withdrawn' else raw['candidates'][0])
    binding=receipt(native,region,query['text'],target['payload_id'])
    record(native,binding,'opposition-a','caller-a','oppose')
    if name in ('other_opposition_remains','support_withdrawn'):
        record(native,binding,'other-b','caller-b','support' if name=='support_withdrawn' else 'oppose')
    ledger=events(native,region)
    chosen=ledger[-1] if name=='support_withdrawn' else ledger[0]
    controls_before={q['name']:withdrawal_read(native,region,q['text'])['raw_view'] for q in queries if q['name']!='literal_cue'}
    stored=collect(native,[region])
    appended=dict(hierarchy_id=region,source_id='withdrawal-later-context',sequence=max(r['sequence'] for r in stored)+1,
                  text='Observação posterior.',source_kind='user_turn')
    persist(native,[appended]);after_rows=collect(native,[region])
    before=withdrawal_read(native,region,query['text'],enabled=True)
    operation=withdraw(native,region,'withdraw-1',chosen['event']['actor_id'],chosen)
    after=withdrawal_read(native,region,query['text'],enabled=True)
    controls=withdrawals(native,region)
    checks=dict(history_not_erased=events(native,region)==ledger,
                learning_rows_unchanged=collect(native,[region])==after_rows,
                raw_view_unchanged=before['raw_view']==after['raw_view']==raw,
                exact_native_target=operation['event']['target_address']==chosen['address'],
                target_digest=fingerprint(chosen)==operation['event']['target_sha256'],
                single_target_inactivated=sum(not p['active'] for p in after['feedback_projection'])==1,
                others_stay_active=all(p['active'] for p in after['feedback_projection'] if p['event']['event_id']!=chosen['event']['event_id']),
                expected_veto=(bool(after['withheld_candidates'])==(name in ('other_opposition_remains','support_withdrawn'))),
                replay_no_append=withdraw(native,region,'withdraw-1',chosen['event']['actor_id'],chosen)['status']=='EXACT_REPLAY'
                                 and withdrawals(native,region)==controls,
                original_feedback_replay_does_not_reactivate=record(native,binding,chosen['event']['event_id'],chosen['event']['actor_id'],chosen['event']['stance'])['status']=='EXACT_REPLAY'
                                 and withdrawal_read(native,region,query['text'],enabled=True)==after,
                other_query_raw_views_unchanged=all(withdrawal_read(native,region,q['text'])['raw_view']==controls_before[q['name']] for q in queries if q['name']!='literal_cue'),
                disabled_preserves_all=withdrawal_read(native,region,query['text'])['available_candidates']==raw['candidates'],
                unqualified=after['answer'] is None and not after['qualified'] and not after['selection_used'])
    rejections={}
    def reject(label,action):
        try: action()
        except ValueError as error:
            rejections[label]=str(error);checks[label]=withdrawals(native,region)==controls and events(native,region)==ledger
        else: checks[label]=False
    reject('duplicate_target_new_request_rejected',lambda:withdraw(native,region,'withdraw-2',chosen['event']['actor_id'],chosen))
    reject('wrong_actor_rejected',lambda:withdraw(native,region,'withdraw-3','unrelated-actor',chosen))
    altered=json.loads(canonical(chosen));altered['event']['stance']='changed'
    reject('altered_target_rejected',lambda:withdraw(native,region,'withdraw-4',chosen['event']['actor_id'],altered))
    native.reopen()
    checks['cold_full_view_equal']=withdrawal_read(native,region,query['text'],enabled=True)==after
    checks['cold_all_fields_equal']=collect(native,[region])==after_rows and events(native,region)==ledger and withdrawals(native,region)==controls
    return dict(scenario=name,renamed=renamed,raw_rows=stored,appended_row=appended,query=query,
                initial_binding=binding,target=chosen,before_withheld_roots=[c['payload_id'] for c in before['withheld_candidates']],
                after=after,rejections=rejections,checks=checks,
                before_score=score([c['text'] for c in before['available_candidates']],query['expected']),
                after_score=score([c['text'] for c in after['available_candidates']],query['expected']))


def probe(library,seed):
    cases=[]
    for renamed in (False,True):
        for name in SCENARIOS:
            with tempfile.TemporaryDirectory(prefix='memoria-feedback-withdrawal-') as directory:
                native=NativeProbe(library,Path(directory))
                try: cases.append(scenario(native,name,seed,renamed))
                finally: native.close()
    checks={f'{i}:{k}':v for i,c in enumerate(cases) for k,v in c['checks'].items()}
    effects={c['scenario']:dict(before=c['before_score'],after=c['after_score']) for c in cases if not c['renamed']}
    checks['renamed_effect_parity']=all(c['before_score']==effects[c['scenario']]['before'] and c['after_score']==effects[c['scenario']]['after'] for c in cases)
    return dict(format='memoria.ia-feedback-withdrawal-probe-v1',seed=seed,cases=cases,effects=effects,checks=checks,
                integrity_status='PASS' if all(checks.values()) else 'FAIL',integrity_passed=sum(checks.values()),integrity_total=len(checks),
                factual_quality_status='NOT_EVALUATED',general_learning_status='NOT_ESTABLISHED',
                limitation='Append-only exact-event withdrawal, opt-in single-writer lab. Actor identity is caller supplied, not authenticated. Withdrawing valid rejection restores an extra; remaining opposition still vetoes. No erasure, factual validation, route learning or production integration.')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--library',type=Path,required=True)
    parser.add_argument('--seed',type=int,default=20270107)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args();report=probe(args.library,args.seed)
    report['report_content_sha256']=fingerprint(report)
    body=json.dumps(report,ensure_ascii=False,separators=(',',':'))+'\n'
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(body,encoding='utf-8')
    print(body,end='');raise SystemExit(0 if report['integrity_status']=='PASS' else 1)


if __name__=='__main__': main()
