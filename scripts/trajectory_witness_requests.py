"""Read-only proposals for witnessing pairs borrowed into a new source form.

Constructed source examples are requests, not observations or expected answers.
This module neither dispatches requests nor accepts responses into memory.
"""
from trajectory_analogy_frame_probe import middle
from trajectory_borrowed_map import read as borrowed_read
from trajectory_native_evidence_join_probe import adapt_regions
from trajectory_region_evidence_probe import fingerprint
from trajectory_symbol_transform_probe import learn_frames


def propose(rows, region, query):
    local=[row for row in rows if row['hierarchy_id']==region]
    memory,origins=adapt_regions(local)
    before=memory.snapshot(),memory.learning_state()
    frames={frame.frame_id:frame for frame in learn_frames(memory)}
    hypotheses=borrowed_read(rows,region,query)
    observed={row['text'] for row in local if row['source_kind'] in ('user_turn','user_assertion')}
    proposed={}
    for hypothesis in hypotheses['hypotheses']:
        for route in hypothesis['routes']:
            donor=frames[route['donor_frame_id']]
            required={ord(pair['source']) for pair in route['borrowed_pairs']}
            for source,_,_ in donor.witnesses:
                variable=middle(memory.expand(source),donor.source_prefix,donor.source_suffix)
                covered=sorted(required.intersection(variable or ()))
                if not covered:continue
                example=route['source_prefix']+''.join(map(chr,variable))+route['source_suffix']
                if example==query or example in observed:continue
                identity=fingerprint(dict(region=region,source_text=example,symbols=covered))
                item=proposed.setdefault(identity,dict(request_id='witness-request:'+identity,
                    kind='OBSERVE_SOURCE_TARGET_PAIR',source_text=example,
                    source_kind='constructed_request',unwitnessed_source_symbols=[chr(x) for x in covered],
                    donor_question_origins=[],supporting_route_ids=[]))
                for origin in origins[source]:
                    if origin not in item['donor_question_origins']:item['donor_question_origins'].append(origin)
                if route['route_id'] not in item['supporting_route_ids']:item['supporting_route_ids'].append(route['route_id'])
    requests=[]
    for _,item in sorted(proposed.items()):
        item['donor_question_origins']=sorted(item['donor_question_origins'])
        item['supporting_route_ids']=sorted(item['supporting_route_ids']);requests.append(item)
    if before!=(memory.snapshot(),memory.learning_state()):raise RuntimeError('witness proposal changed memory')
    return dict(format='memoria.ia-witness-requests-v1',region=region,query=query,requests=requests,
                request_dispatched=False,observations_recorded=False,learning_performed=False,
                answer=None,qualified=False,selection_used=False,
                factual_quality_status='NOT_EVALUATED',general_learning_status='NOT_ESTABLISHED',
                limitation='A proposed source example covers an unwitnessed symbol; no answer is supplied and no information gain or truthful response is guaranteed.')
