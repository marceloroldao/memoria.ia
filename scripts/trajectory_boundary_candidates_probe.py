#!/usr/bin/env python3
"""Read-only witnessed source cuts without a common source separator."""
import argparse
from dataclasses import asdict,dataclass
from hashlib import blake2b
from itertools import combinations,product
import json

from trajectory_analogy_boundary_probe import extract
from trajectory_analogy_frame_probe import prefix,suffix,occurrences
from trajectory_analogy_two_slot_probe import common_parts
from trajectory_evidence_packet_probe import checked_packet
from trajectory_separator_ablation_probe import evaluate,counts
from trajectory_response_quality_probe import TrajectoryGenerationExperiment


@dataclass(frozen=True)
class BoundaryFrame:
    source_prefix: tuple
    source_suffix: tuple
    target_prefix: tuple
    target_between: tuple
    target_order: tuple
    target_bridge: tuple
    target_suffix: tuple
    internal_anchors: tuple
    witnesses: tuple
    demonstration_alignments: tuple

    @property
    def frame_id(self):
        return blake2b(repr(self).encode(),digest_size=16).hexdigest()

    def head(self,slots):
        a,b=self.target_order
        return self.target_prefix+slots[a]+self.target_between+slots[b]+self.target_bridge


def learn(memory):
    previous,pairs={},set()
    for row in memory.snapshot()['observations']:
        scope=row['hierarchy_id'],row['stream_id']
        if scope in previous and previous[scope]!=row['payload_id']:
            pairs.add((previous[scope],row['payload_id'],row['stream_id']))
        previous[scope]=row['payload_id']
    frames=set()
    for group in combinations(sorted(pairs),3):
        sources=[memory.expand(a) for a,_,_ in group]
        targets=[memory.expand(z) for _,z,_ in group]
        left,right=prefix(sources),suffix(sources)
        if not left or not right:
            continue
        bodies=[extract(s,left,right) for s in sources]
        if any(body is None for body in bodies):
            continue
        choices=[]
        for body,target in zip(bodies,targets):
            cuts=[]
            for position in range(1,len(body)):
                slots=body[:position],body[position:]
                points=[occurrences(slot,target) for slot in slots]
                if any(len(p)!=1 for p in points):
                    continue
                locations=tuple(p[0] for p in points)
                order=(0,1) if locations[0]<locations[1] else (1,0)
                a,b=order
                if locations[a]+len(slots[a])>locations[b]:
                    continue
                head=target[:locations[a]]
                between=target[locations[a]+len(slots[a]):locations[b]]
                if not head:
                    continue
                cuts.append((position,slots,locations,order,head,between,
                             target[locations[b]+len(slots[b]):]))
            choices.append(cuts)
        for alignment in product(*choices):
            if any(len({row[1][i] for row in alignment})!=3 for i in (0,1)):
                continue
            if len({(row[3],row[4],row[5]) for row in alignment})!=1:
                continue
            tails=[row[6] for row in alignment]
            bridge,ending=prefix(tails),suffix(tails)
            if not ending:
                continue
            values=[extract(tail,bridge,ending) for tail in tails]
            if any(value is None for value in values) or len(set(values))!=3:
                continue
            first=alignment[0]
            positions=tuple((len(left)+row[0],row[1],row[2]) for row in alignment)
            frames.add(BoundaryFrame(left,right,first[4],first[5],first[3],bridge,ending,
                                    common_parts(values),group,positions))
    return tuple(sorted(frames,key=lambda f:f.frame_id))


def packet(memory,query):
    query=tuple(query)
    prior=checked_packet(memory,query)
    frames=learn(memory)
    roots={r['payload_id'] for r in memory.snapshot()['observations']}
    routes={c['payload_id']:dict(c,boundary_matches=()) for c in prior['candidates']}
    cuts=[]
    partial=False
    for frame in frames:
        if frame.internal_anchors:
            continue
        starts=occurrences(frame.source_prefix,query)
        if len(starts)!=1:
            continue
        body=extract(query[starts[0]:],frame.source_prefix,frame.source_suffix)
        if body is None:
            continue
        frame_support=[]
        for position in range(1,len(body)):
            slots=body[:position],body[position:]
            matches=[]
            for root in sorted(roots):
                target=memory.expand(root)
                if any(len(occurrences(slot,target))!=1 for slot in slots):
                    continue
                if extract(target,frame.head(slots),frame.target_suffix) is None:
                    continue
                matches.append(root)
                candidate=routes.setdefault(root,dict(payload_id=root,output=target,
                    frame_ids=(),witnesses=(),alignment_matches=(),evidence_kinds=[],boundary_matches=()))
                candidate['evidence_kinds']=list(candidate['evidence_kinds'])
                if 'UNSEPARATED_COPY_MATCH' not in candidate['evidence_kinds']:
                    candidate['evidence_kinds'].append('UNSEPARATED_COPY_MATCH')
                if frame.frame_id not in candidate['frame_ids']:
                    candidate['frame_ids']+=(frame.frame_id,)
                candidate['witnesses']=tuple(sorted(set(candidate['witnesses'])|set(frame.witnesses)))
                candidate['boundary_matches']+=(dict(frame_id=frame.frame_id,
                    source_position=starts[0]+len(frame.source_prefix)+position,slots=slots),)
            frame_support.append(tuple(matches))
            cuts.append(dict(frame_id=frame.frame_id,source_position=starts[0]+len(frame.source_prefix)+position,
                             slots=slots,candidate_roots=tuple(matches)))
        if len(frame_support)>1 and any(frame_support) and any(not support for support in frame_support):
            partial=True
    candidates=tuple(routes[root] for root in sorted(routes))
    # New copied-root evidence is never promoted to a unique answer here.
    hypothesis=prior['prior_structural_hypothesis'] if len(candidates)==1 and not partial else None
    return dict(format='memoria.ia-unseparated-boundary-packet-v1',query=query,inherited_packet=prior,
        boundary_frames=tuple(asdict(f)|dict(frame_id=f.frame_id) for f in frames),boundary_support=tuple(cuts),
        partial_boundary_support=partial,candidates=candidates,observed_continuations=prior['observed_continuations'],
        prior_structural_hypothesis=hypothesis,inherited_structural_hypothesis=prior['prior_structural_hypothesis'],
        structural_status='CONFLICT' if len(candidates)>1 else 'CANDIDATE' if candidates else 'EMPTY',
        answer=None,qualified=False,authorization_status='UNQUALIFIED_BOUNDARY_EVIDENCE')


def checked_boundary_packet(memory,query):
    before=memory.snapshot(),memory.learning_state(),asdict(memory.generate(query))
    result=packet(memory,query)
    assert result==packet(TrajectoryGenerationExperiment.restore(memory.snapshot()),query)
    assert before==(memory.snapshot(),memory.learning_state(),asdict(memory.generate(query)))
    roots={r['payload_id'] for r in memory.snapshot()['observations']}
    addressed={x for c in result['candidates'] for a,z,_ in c['witnesses'] for x in (a,z)}
    assert addressed|{c['payload_id'] for c in result['candidates']} <= roots
    for frame in result['boundary_frames']:
        for (a,z,_),(position,slots,locations) in zip(frame['witnesses'],frame['demonstration_alignments']):
            source,target=memory.expand(a),memory.expand(z)
            assert source[len(frame['source_prefix']):position]==slots[0]
            assert source[position:len(source)-len(frame['source_suffix'])]==slots[1]
            assert all(target[p:p+len(slot)]==slot for slot,p in zip(slots,locations))
    return result


def probe(seed):
    evaluations=[evaluate(seed,mode,renamed,reader=checked_boundary_packet)
                 for mode in ('explicit','absent','ambiguous') for renamed in (False,True)]
    by_mode={mode:counts([c for ev in evaluations if ev['mode']==mode for s in ev['stages'] for c in s['cases']])
             for mode in ('explicit','absent','ambiguous')}
    complete=counts([c for ev in evaluations for s in ev['stages'] for c in s['cases']])
    return dict(format='memoria.ia-unseparated-boundary-probe-v1',seed=seed,integrity_status='PASS',
        structural_quality_status='PASS' if complete['passed']==complete['cases'] else 'FAIL',
        semantic_quality_status='UNQUALIFIED',counts=complete,by_mode=by_mode,evaluations=evaluations,
        engine_changed=False,prior_selectors_changed=False,native_executed=False)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seed',type=int,default=20261113)
    parser.add_argument('--strict-quality',action='store_true')
    args=parser.parse_args()
    report=probe(args.seed)
    print(json.dumps(report,separators=(',',':')))
    raise SystemExit(1 if args.strict_quality and report['structural_quality_status']!='PASS' else 0)
