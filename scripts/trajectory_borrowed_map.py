"""Opt-in read-only hypotheses borrowing a map across two witnessed source examples.

Not used by FeedbackSession or the standard reader. Unwitnessed pairs in the new
source form remain assumptions, even when they were witnessed in a donor frame.
"""
from itertools import combinations

from trajectory_analogy_frame_probe import prefix, suffix, middle, occurrences
from trajectory_native_evidence_join_probe import adapt_regions
from trajectory_region_evidence_probe import fingerprint
from trajectory_symbol_transform_probe import learn_frames


def read(rows, region, query):
    memory, origins = adapt_regions([row for row in rows if row['hierarchy_id']==region])
    before = memory.snapshot(), memory.learning_state()
    previous, pairs = {}, set()
    for row in memory.snapshot()['observations']:
        scope = row['hierarchy_id'],row['stream_id']
        if scope in previous and previous[scope]!=row['payload_id']:
            pairs.add((previous[scope],row['payload_id'],row['stream_id']))
        previous[scope] = row['payload_id']
    roots = sorted(origins); symbols = tuple(map(ord,query)); candidates = {}
    for donor in learn_frames(memory):
        mapping = dict(donor.symbol_map)
        for anchors in combinations(sorted(pairs),2):
            sources = [memory.expand(s) for s,_,_ in anchors]
            left,right = prefix(sources),suffix(sources)
            if not left or not right or (left,right)==(donor.source_prefix,donor.source_suffix): continue
            variables = [middle(s,left,right) for s in sources]
            if any(v is None for v in variables) or len(set(variables))!=2: continue
            if any(x not in mapping for v in variables for x in v): continue
            if any(middle(memory.expand(t),donor.target_prefix+tuple(mapping[x] for x in v)+donor.target_bridge,
                          donor.target_suffix) is None for (_,t,_),v in zip(anchors,variables)): continue
            # A witnessed pair in this source form can contradict the donor.
            # Do not bypass that evidence by picking only two agreeable anchors.
            contradicted = False
            for source,target,_ in pairs:
                v = middle(memory.expand(source),left,right)
                if v is not None and all(x in mapping for x in v):
                    expected_head = donor.target_prefix+tuple(mapping[x] for x in v)+donor.target_bridge
                    if middle(memory.expand(target),expected_head,donor.target_suffix) is None:
                        contradicted = True;break
            if contradicted: continue
            starts = occurrences(left,symbols)
            if len(starts)!=1: continue
            variable = middle(symbols[starts[0]:],left,right)
            if variable is None or any(x not in mapping for x in variable): continue
            witnessed = {x for v in variables for x in v}
            borrowed = sorted(set(variable)-witnessed)
            if not borrowed: continue
            head = donor.target_prefix+tuple(mapping[x] for x in variable)+donor.target_bridge
            route = dict(donor_frame_id=donor.frame_id,
                         donor_witnesses=[dict(source_origins=origins[s],target_origins=origins[t]) for s,t,_ in donor.witnesses],
                         new_form_witnesses=[dict(source_origins=origins[s],target_origins=origins[t]) for s,t,_ in anchors],
                         source_prefix=''.join(map(chr,left)),source_suffix=''.join(map(chr,right)),
                         borrowed_pairs=[dict(source=chr(x),target=chr(mapping[x])) for x in borrowed],
                         epistemic_status='UNWITNESSED_IN_NEW_SOURCE_FORM')
            route['route_id'] = fingerprint(route)
            for root in roots:
                if middle(memory.expand(root),head,donor.target_suffix) is not None:
                    entry = candidates.setdefault(root,dict(text=''.join(map(chr,memory.expand(root))),
                                                            payload_id=root,origins=origins[root],routes={}))
                    entry['routes'][route['route_id']] = route
    if before!=(memory.snapshot(),memory.learning_state()): raise RuntimeError('borrowed-map read changed memory')
    return dict(format='memoria.ia-borrowed-map-hypotheses-v1',
                hypotheses=[dict(entry,routes=[entry['routes'][key] for key in sorted(entry['routes'])]) for _,entry in sorted(candidates.items())],
                answer=None,qualified=False,selection_used=False,learning_performed=False,
                factual_quality_status='NOT_EVALUATED',general_learning_status='NOT_ESTABLISHED',
                epistemic_status='UNWITNESSED_PAIRS_BORROWED_FROM_OTHER_SOURCE_FORM')
