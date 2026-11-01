"""Append-only operator review receipts and decisions, outside the learning region."""
import base64
import json

from trajectory_feedback_ledger_probe import canonical
from trajectory_region_evidence_probe import fingerprint
from trajectory_window_consistency_probe import window_snapshot


CODEC='operator-review-json-utf8-base64-v1:'
MAX_RECEIPT_BYTES=262144
MAX_RECORDS=128


def field(region,kind):
    if not isinstance(region,str) or not region.startswith('conversation:feedback-session:'):
        raise ValueError('invalid operator review learning region')
    return 'operator-review-'+kind+':'+fingerprint(region)


def rows(native,region,kind):
    result=[]
    for row in window_snapshot(native,field(region,kind))['rows']:
        if not row['text'].startswith(CODEC):raise ValueError('unknown operator review codec')
        try:
            event=json.loads(base64.b64decode(row['text'][len(CODEC):],validate=True).decode('utf-8'))
        except (ValueError,UnicodeError) as error:
            raise ValueError('invalid operator review control') from error
        result.append(dict(address=dict(region=row['hierarchy_id'],source_id=row['source_id'],sequence=row['sequence']),event=event))
    if len(result)>MAX_RECORDS:raise ValueError('operator review history exceeds laboratory limit')
    return result


def receipts(native,region):
    stored=rows(native,region,'receipts'); identities=set()
    for entry in stored:
        event=entry['event']
        if not isinstance(event,dict):raise ValueError('invalid review receipt')
        body={k:v for k,v in event.items() if k!='receipt_id'}
        identity=event.get('receipt_id')
        if (set(body)!={'format','region','query','learning_sha256','reviewed_result'}
            or body.get('format')!='memoria.ia-operator-review-receipt-v1' or body.get('region')!=region
            or identity!=fingerprint(body) or identity in identities
            or entry['address']['source_id']!='operator-review-receipt:'+identity):
            raise ValueError('invalid or duplicate review receipt history')
        identities.add(identity)
    return stored


def append(native,region,kind,event,source_id,count):
    if count>=MAX_RECORDS:raise ValueError('operator review record limit reached')
    encoded=canonical(event).encode('utf-8')
    if len(encoded)>MAX_RECEIPT_BYTES:raise ValueError('operator review record exceeds 256 KiB; reduce reviewed history or offers')
    address=dict(region=field(region,kind),source_id=source_id,sequence=count+1)
    status,response=native.call('observe_structural_text',dict(hierarchy_id=address['region'],source_id=source_id,
                                sequence=address['sequence'],text=CODEC+base64.b64encode(encoded).decode('ascii'),source_kind='user_turn'))
    if status!=0 or response.get('duplicate'):raise RuntimeError('operator review persistence failed')
    return dict(status='APPENDED',address=address,event=event)


def open_review(native,region,query,learning_sha256,reviewed_result):
    body=dict(format='memoria.ia-operator-review-receipt-v1',region=region,query=query,
              learning_sha256=learning_sha256,reviewed_result=reviewed_result)
    event=dict(body,receipt_id=fingerprint(body))
    stored=history(native,region)['receipts']
    previous=[entry for entry in stored if entry['event']['receipt_id']==event['receipt_id']]
    if previous:
        if canonical(previous[0]['event'])!=canonical(event):raise ValueError('review receipt content conflict')
        return dict(status='EXACT_REPLAY',**previous[0])
    return append(native,region,'receipts',event,'operator-review-receipt:'+event['receipt_id'],len(stored))


def validate_decision(event,by_receipt):
    if not isinstance(event,dict) or set(event)!={'format','decision_id','receipt_id','actor_id','choice','offer_id','reason'}:
        raise ValueError('invalid operator decision fields')
    if event['format']!='memoria.ia-operator-review-decision-v1':raise ValueError('invalid operator decision format')
    for key in ('decision_id','actor_id'):
        if not isinstance(event[key],str) or not event[key].strip() or len(event[key])>128:
            raise ValueError('operator and decision identities require one to 128 characters')
    if not isinstance(event['reason'],str) or not event['reason'].strip() or len(event['reason'])>2000:
        raise ValueError('decision reason requires one to 2000 characters')
    if not isinstance(event['receipt_id'],str) or event['receipt_id'] not in by_receipt:
        raise ValueError('review receipt is not stored in this scope')
    choices=('select','defer','reject_all')
    if event['choice'] not in choices:raise ValueError('unsupported operator choice')
    offered={r['offer']['offer_id'] for r in by_receipt[event['receipt_id']]['event']['reviewed_result']['example_review']['offers']}
    if event['choice']=='select':
        if not isinstance(event['offer_id'],str) or event['offer_id'] not in offered:
            raise ValueError('selected offer is not in the exact reviewed set')
    elif event['offer_id'] is not None:
        raise ValueError('defer and reject_all require a null offer_id')


def history(native,region):
    stored=receipts(native,region);by_receipt={entry['event']['receipt_id']:entry for entry in stored}
    decisions=rows(native,region,'decisions');identities=set()
    for entry in decisions:
        event=entry['event'];validate_decision(event,by_receipt)
        if event['decision_id'] in identities or entry['address']['source_id']!='operator-review-decision:'+fingerprint(event['decision_id']):
            raise ValueError('invalid or duplicate operator decision history')
        identities.add(event['decision_id'])
    return dict(receipts=stored,decisions=decisions,learning_performed=False,
                offers_incorporated=False,decision_identities_authenticated=False)


def record_decision(native,region,receipt_id,decision_id,actor_id,choice,offer_id,reason,current_review):
    stored=history(native,region)
    by_receipt={entry['event']['receipt_id']:entry for entry in stored['receipts']}
    event=dict(format='memoria.ia-operator-review-decision-v1',decision_id=decision_id,receipt_id=receipt_id,
               actor_id=actor_id,choice=choice,offer_id=offer_id,reason=reason)
    validate_decision(event,by_receipt)
    previous=[entry for entry in stored['decisions'] if entry['event']['decision_id']==decision_id]
    if previous:
        if canonical(previous[0]['event'])!=canonical(event):raise ValueError('decision identity reused with different content')
        return dict(status='EXACT_REPLAY',**previous[0])
    binding=by_receipt[receipt_id]['event']
    offers=[entry['offer'] for entry in binding['reviewed_result']['example_review']['offers']]
    reviewed,learning_sha256=current_review(binding['query'],offers)
    if canonical(reviewed)!=canonical(binding['reviewed_result']) or learning_sha256!=binding['learning_sha256']:
        raise ValueError('stale review receipt; open a new review before a new decision')
    return append(native,region,'decisions',event,'operator-review-decision:'+fingerprint(decision_id),len(stored['decisions']))
