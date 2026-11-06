"""Bind a received witness response to existing durable review, without learning."""
import re

from trajectory_demonstration_review import validate_offers
from trajectory_region_evidence_probe import fingerprint
from trajectory_witness_requests import propose


PREFIX='witness-response-v1|'
KINDS=('user_turn','assistant_generated')


def current_requests(session,scope,query):
    if not isinstance(query,str) or not query.strip() or len(query)>4000:
        raise ValueError('invalid witness query')
    history=session.execute(dict(op='history',scope=scope))['result']
    return propose(history['entries'],'conversation:feedback-session:'+scope,query)


def offer_identity(request_id,request_sha256,kind,source,target):
    return 'witness-response:'+fingerprint(dict(request_id=request_id,request_sha256=request_sha256,
        source_kind=kind,source_text=source,target_text=target))


def response_origin(offer):
    """Validate this optional provenance convention, leaving ordinary offers unchanged."""
    identity=offer.get('offer_id')
    if not isinstance(identity,str) or not re.fullmatch(r'witness-response:[0-9a-f]{64}',identity):return None
    provenance=offer.get('provenance','')
    if not isinstance(provenance,str) or not provenance.startswith(PREFIX):raise ValueError('invalid witness response provenance')
    fields=provenance.split('|')
    if (len(fields)!=4 or not re.fullmatch(r'witness-request:[0-9a-f]{64}',fields[1])
        or fields[2] not in KINDS or not re.fullmatch(r'[0-9a-f]{64}',fields[3])):
        raise ValueError('invalid witness response provenance')
    validate_offers([offer])
    if len(offer['examples'])!=1:raise ValueError('witness response requires one example')
    example=offer['examples'][0]
    if offer['offer_id']!=offer_identity(fields[1],fields[3],fields[2],example['source_text'],example['target_text']):
        raise ValueError('witness response content disagrees with binding')
    return dict(request_id=fields[1],source_kind=fields[2],request_sha256=fields[3])


def guard_incorporation(offer,kind):
    binding=response_origin(offer)
    if binding and binding['source_kind']=='assistant_generated' and kind!='assistant_generated':
        raise ValueError('Resposta declarada como gerada só pode ser registrada como gerada; não foi autenticada como observação.')


def open_response(session,scope,query,request_id,response_text,source_kind):
    if source_kind not in KINDS:raise ValueError('explicit response source kind required')
    if not isinstance(response_text,str) or not response_text.strip() or len(response_text)>2000:
        raise ValueError('response requires one to 2000 nonempty characters')
    pending=current_requests(session,scope,query)
    matches=[request for request in pending['requests'] if request['request_id']==request_id]
    if len(matches)!=1:raise ValueError('witness request is not current in this scope and query')
    request=matches[0];request_sha256=fingerprint(request)
    offer=dict(offer_id=offer_identity(request_id,request_sha256,source_kind,request['source_text'],response_text),
               provenance=PREFIX+request_id+'|'+source_kind+'|'+request_sha256,
               examples=[dict(source_text=request['source_text'],target_text=response_text)])
    response_origin(offer)
    receipt=session.execute(dict(op='open_review',scope=scope,text=query,offers=[offer]))['result']
    return dict(format='memoria.ia-witness-response-review-v1',request_id=request_id,
                request_sha256=request_sha256,source_kind=source_kind,review_receipt=receipt,
                learning_performed=False,examples_incorporated=False,source_authenticated=False,
                factual_quality_status='NOT_EVALUATED',general_learning_status='NOT_ESTABLISHED')
