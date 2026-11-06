"""Append-only snapshot comparison and caller judgement; no causal or truth inference."""
from trajectory_feedback_ledger_probe import canonical
from trajectory_region_evidence_probe import fingerprint
from trajectory_review_decisions import append,history as decision_history,rows


def candidate_delta(before,after):
    left={c['payload_id']:c for c in before};right={c['payload_id']:c for c in after}
    if len(left)!=len(before) or len(right)!=len(after):raise ValueError('duplicate outcome candidate identity')
    return dict(before_count=len(left),after_count=len(right),
                added_ids=sorted(set(right)-set(left)),removed_ids=sorted(set(left)-set(right)),
                retained_ids=sorted(set(left)&set(right)),
                changed_evidence_ids=sorted(k for k in set(left)&set(right) if canonical(left[k])!=canonical(right[k])))


def compare_receipts(before,after):
    left=before['reviewed_result'];right=after['reviewed_result']
    offered=lambda result:[r['offer'] for r in result['example_review']['offers']]
    if before['region']!=after['region'] or before['query']!=after['query'] or canonical(offered(left))!=canonical(offered(right)):
        raise ValueError('outcome snapshots must use the same scope, query and offered set')
    raw=candidate_delta(left['raw_view']['candidates'],right['raw_view']['candidates'])
    available=candidate_delta(left['available_candidates'],right['available_candidates'])
    withheld=candidate_delta(left['withheld_candidates'],right['withheld_candidates'])
    return dict(raw=raw,available=available,withheld=withheld,
                learning_context_changed=before['learning_sha256']!=after['learning_sha256'],
                full_review_changed=canonical(left)!=canonical(right),
                retrieval_change_means_quality_improvement=False,
                causal_attribution='NOT_ESTABLISHED',offer_application_verified=False,
                factual_quality_status='NOT_EVALUATED')


def validate(event,by_decision,by_receipt):
    fields={'format','outcome_id','decision_id','decision_sha256','before_receipt_id','after_receipt_id','actor_id','judgement','reason','comparison'}
    if not isinstance(event,dict) or set(event)!=fields or event.get('format')!='memoria.ia-operator-review-outcome-v1':
        raise ValueError('invalid review outcome fields')
    for key in ('outcome_id','actor_id'):
        if not isinstance(event[key],str) or not event[key].strip() or len(event[key])>128:
            raise ValueError('outcome and actor identities require one to 128 characters')
    if not isinstance(event['reason'],str) or not event['reason'].strip() or len(event['reason'])>2000:
        raise ValueError('outcome reason requires one to 2000 characters')
    if event['judgement'] not in ('helped','unchanged','worsened','uncertain'):
        raise ValueError('unsupported operator outcome judgement')
    if not isinstance(event['decision_id'],str) or event['decision_id'] not in by_decision:
        raise ValueError('decision is not stored in this scope')
    decision=by_decision[event['decision_id']]
    if event['decision_sha256']!=fingerprint(decision) or event['before_receipt_id']!=decision['event']['receipt_id']:
        raise ValueError('outcome does not reference the exact decision')
    if event['actor_id']!=decision['event']['actor_id']:
        raise ValueError('outcome actor does not match caller supplied decision identity')
    if not isinstance(event['after_receipt_id'],str) or event['after_receipt_id'] not in by_receipt:
        raise ValueError('after receipt is not stored in this scope')
    before=by_receipt[event['before_receipt_id']];after=by_receipt[event['after_receipt_id']]
    if after['address']['sequence']<before['address']['sequence']:
        raise ValueError('after receipt precedes the decision review receipt')
    comparison=compare_receipts(before['event'],after['event'])
    if canonical(event['comparison'])!=canonical(comparison):raise ValueError('outcome comparison disagrees with stored receipts')


def history(native,region):
    audit=decision_history(native,region)
    by_receipt={r['event']['receipt_id']:r for r in audit['receipts']}
    by_decision={r['event']['decision_id']:r for r in audit['decisions']}
    outcomes=rows(native,region,'outcomes');identities=set()
    for entry in outcomes:
        event=entry['event'];validate(event,by_decision,by_receipt)
        if event['outcome_id'] in identities or entry['address']['source_id']!='operator-review-outcome:'+fingerprint(event['outcome_id']):
            raise ValueError('invalid or duplicate review outcome history')
        identities.add(event['outcome_id'])
    return dict(receipts=audit['receipts'],decisions=audit['decisions'],outcomes=outcomes,
                learning_performed=False,offers_incorporated=False,operator_judgements_verified=False)


def record(native,region,decision_id,after_receipt_id,outcome_id,actor_id,judgement,reason):
    audit=history(native,region)
    by_receipt={r['event']['receipt_id']:r for r in audit['receipts']}
    by_decision={r['event']['decision_id']:r for r in audit['decisions']}
    if not isinstance(decision_id,str) or decision_id not in by_decision:
        raise ValueError('decision is not stored in this scope')
    if not isinstance(after_receipt_id,str) or after_receipt_id not in by_receipt:
        raise ValueError('after receipt is not stored in this scope')
    decision=by_decision[decision_id];before_id=decision['event']['receipt_id']
    comparison=compare_receipts(by_receipt[before_id]['event'],by_receipt[after_receipt_id]['event'])
    event=dict(format='memoria.ia-operator-review-outcome-v1',outcome_id=outcome_id,decision_id=decision_id,
               decision_sha256=fingerprint(decision),before_receipt_id=before_id,after_receipt_id=after_receipt_id,
               actor_id=actor_id,judgement=judgement,reason=reason,comparison=comparison)
    validate(event,by_decision,by_receipt)
    previous=[r for r in audit['outcomes'] if r['event']['outcome_id']==outcome_id]
    if previous:
        if canonical(previous[0]['event'])!=canonical(event):raise ValueError('outcome identity reused with different content')
        return dict(status='EXACT_REPLAY',**previous[0])
    return append(native,region,'outcomes',event,'operator-review-outcome:'+fingerprint(outcome_id),len(audit['outcomes']))
