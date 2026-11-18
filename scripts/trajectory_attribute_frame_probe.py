#!/usr/bin/env python3
"""Scoped, source-addressed reading of existing learned frames; never factual selection.

Demonstration wording and evaluator labels live in the fixture, not in the reader.
This opt-in probe does not change the cognitive core or the MVP query endpoint.
"""
import argparse
import copy
from dataclasses import asdict
import gzip
import json
from pathlib import Path
import tempfile

from mobile_personal_proof_gate import region_rows
from mobile_region_replay import NativeProbe
from trajectory_analogy_frame_probe import learn_frames, middle, occurrences
from trajectory_inferred_relation_probe import FIELDS
from trajectory_native_bridge_probe import USER_KINDS, address
from trajectory_native_evidence_join_probe import adapt_regions
from trajectory_region_evidence_probe import fingerprint
from trajectory_region_reply_probe import observe
from trajectory_response_quality_probe import encode


class AttributeFrameReader:
    """Immutable local projection of at most 64 rows / 4096 raw characters.

    Reuses learn_frames without adding attribute names, question classification,
    label access, a ranking threshold, or an observed-query requirement.
    """
    def __init__(self, rows, region):
        if not isinstance(region,str) or not region.strip():
            raise ValueError('explicit nonempty region required')
        self.region=region
        local=[{key:r[key] for key in FIELDS} for r in rows if r['hierarchy_id']==region]
        if len(local)>64 or sum(len(r['text']) for r in local)>4096:
            raise ValueError('frame projection limited to 64 rows and 4096 characters')
        self.memory,self.origins=adapt_regions(local)
        self.frames=learn_frames(self.memory)
        self.observation_sha256=fingerprint(local)
        previous={};self.pair_origins={}
        for row in self.memory.snapshot()['observations']:
            stream=row['stream_id'];root=row['payload_id']
            origin=address(local[int(row['observation_id'].split(':')[1])])
            if stream in previous:
                source,source_origin=previous[stream]
                if source!=root:
                    self.pair_origins.setdefault((source,root,stream),[]).append(
                        dict(source_origin=source_origin,target_origin=origin))
            previous[stream]=root,origin

    def read(self,query,*,casefold=False,require_agreement=False):
        if not isinstance(query,str) or not query or len(query)>4096:
            raise ValueError('raw query requires 1..4096 characters')
        def for_matching(symbols):
            if not casefold:
                return symbols
            return encode(''.join(map(chr,symbols)).casefold(),'unicode')

        symbols=for_matching(encode(query,'unicode'))
        before=self.memory.snapshot(),self.memory.learning_state()
        candidates={}
        matched_frames = set()
        supported_frames = set()
        roots={root:for_matching(self.memory.expand(root)) for root in sorted(self.origins)}
        for frame in self.frames:
            # Unlike a substring cue, the whole question must fit the frame.
            source_prefix=for_matching(frame.source_prefix)
            if occurrences(source_prefix,symbols)!=(0,):
                continue
            variable=middle(symbols,source_prefix,for_matching(frame.source_suffix))
            if variable is None:
                continue
            if require_agreement:
                frame_id = frame.frame_id
                matched_frames.add(frame_id)
            head=for_matching(frame.target_prefix)+variable+for_matching(frame.target_bridge)
            target_suffix=for_matching(frame.target_suffix)
            for root,matching_symbols in roots.items():
                if middle(matching_symbols,head,target_suffix) is None:
                    continue
                candidates.setdefault(root,[]).append(frame)
                if require_agreement:
                    supported_frames.add(frame_id)
        result=[]
        for root,frames in sorted(candidates.items()):
            witnesses=[]
            for source,target,stream in sorted({w for f in frames for w in f.witnesses}):
                witnesses.append(dict(source_payload_id=source,target_payload_id=target,stream_id=stream,
                    occurrences=self.pair_origins[source,target,stream]))
            result.append(dict(payload_id=root,text=''.join(map(chr,self.memory.expand(root))),
                origins=self.origins[root],frame_ids=[f.frame_id for f in frames],witnesses=witnesses,
                evidence_kind='LEARNED_FRAME_CANDIDATE',support_is_factual_confidence=False))
        if before!=(self.memory.snapshot(),self.memory.learning_state()):
            raise RuntimeError('frame query changed projected memory')
        view=dict(format='memoria.ia-attribute-frame-view-v1',region=self.region,query=query,
            observation_sha256=self.observation_sha256,
            learned_frames=[asdict(f)|dict(frame_id=f.frame_id) for f in self.frames],candidates=result,
            proposal_payload_id=result[0]['payload_id'] if len(result)==1 else None,
            reason='UNIQUE_FRAME_CANDIDATE' if len(result)==1 else
                   'COMPETING_FRAME_CANDIDATES' if result else 'NO_SUPPORTED_FRAME_CANDIDATE',
            absence_proven=False,answer=None,qualified=False,selected_target=None,selection_used=False,
            query_recorded=False,factual_quality_status='NOT_EVALUATED')
        if casefold:
            view['matching_mode']='unicode_casefold'
        if require_agreement:
            unsupported = sorted(matched_frames - supported_frames)
            view['frame_agreement'] = dict(matched_frame_ids=sorted(matched_frames),
                                           unsupported_frame_ids=unsupported)
            if view['proposal_payload_id'] is not None and unsupported:
                view['proposal_payload_id'] = None
                view['reason'] = 'UNSUPPORTED_MATCHING_FRAMES'
        return copy.deepcopy(view)


def demonstrations():
    """Public synthetic teaching examples; no target-case answer is included."""
    subjects=('barco','avião','drone')
    templates=[
        ('pets','Qual nome do meu {}?','Meu {} se chama {}.',('Vela','Nuvem','Pico')),
        ('pets','Onde meu {} dorme?','Meu {} dorme {}.',('na garagem','no hangar','na base')),
        ('cars','Qual a cor do meu {}?','Meu {} é {}.',('verde','vermelho','roxo')),
        ('cars','Qual a cor da minha {}?','Minha {} é {}.',('verde','vermelha','roxa')),
        ('home','Qual a cor da minha {}?','Minha {} é {}.',('verde','vermelha','roxa')),
        ('agenda','Em que dia está marcada minha {}?','Minha {} está marcada para {}.',('segunda','quarta','sábado')),
        ('agenda','A que horas minha {} começa?','Minha {} começa às {}.',('8h','9h','10h')),
        ('devices','Quantos graus indica o {}?','O {} indica {} graus.',('11','32','45')),
        ('devices','Quantos volts fornece a {}?','A {} fornece {} volts.',('24','36','48')),
        ('devices','Como está o {}?','O {} está {}.',('ligado','parado','ativo')),
    ]
    return [dict(scope=scope,question=q.format(subject),content=a.format(subject,value))
            for scope,q,a,values in templates for subject,value in zip(subjects,values)]


def fixture(with_demonstrations=True):
    from trajectory_local_mvp_variation_gate import fixture as retrieval_fixture
    entries,specs=retrieval_fixture()
    rows=[];sequence={}
    def add(scope,text,kind='user_turn'):
        region='conversation:attribute:'+scope
        sequence[region]=sequence.get(region,0)+1
        rows.append(dict(hierarchy_id=region,source_id='row-'+str(len(rows)),sequence=sequence[region],
                         text=text,source_kind=kind))
    for entry in entries: add(entry['scope'],entry['text'],entry['source_kind'])
    if with_demonstrations:
        for scope in sorted({d['scope'] for d in demonstrations()}): add(scope,'pausa','assistant_generated')
        for demo in demonstrations():
            add(demo['scope'],demo['question']);add(demo['scope'],demo['content'])
            add(demo['scope'],'pausa','assistant_generated')
    return rows,specs


def score(spec,candidates):
    expected=set(spec['expected']);returned={c['text'] for c in candidates}
    return dict(exact_set=expected==returned,true_positive=len(expected&returned),
        false_positive=len(returned-expected),false_negative=len(expected-returned),
        extra=sorted(returned-expected),missing=sorted(expected-returned))


def totals(cases,route):
    return dict(cases=len(cases),**{k:sum(c[route][k] for c in cases)
        for k in ('exact_set','true_positive','false_positive','false_negative')})


def gate(library):
    stages=[];checks={}
    for taught in (False,True):
        rows,specs=fixture(taught);scopes=sorted({r['hierarchy_id'] for r in rows}|
            {'conversation:attribute:'+s['scope'] for s in specs})
        with tempfile.TemporaryDirectory(prefix='memoria-attribute-') as directory:
            native=NativeProbe(library,Path(directory))
            try:
                for row in rows: observe(native,row)
                def collect():
                    return [dict(r,hierarchy_id=s) for s in scopes for r in region_rows(native,s)]
                stored=collect();readers={s:AttributeFrameReader(stored,s) for s in scopes}
                views=[];cases=[]
                for spec in specs:
                    region='conversation:attribute:'+spec['scope'];view=readers[region].read(spec['query'])
                    views.append(view)
                    status,recall=native.call('resolve_structural_text',dict(hierarchy_id=region,query=spec['query'],top_k=16))
                    if status not in (0,2): raise RuntimeError('native baseline query failed')
                    accepted=[r for r in stored if r['hierarchy_id']==region and r['source_kind'] in USER_KINDS]
                    texts={r['text'] for r in accepted if r['text']==spec['query']}|{
                        c['source_text'] for c in recall.get('contexts',[]) if any(r['text']==c['source_text'] for r in accepted)}
                    baseline=[dict(text=t) for t in sorted(texts)]
                    cases.append(dict(**spec,frame=score(spec,view['candidates']),baseline=score(spec,baseline),
                        view=view,baseline_candidates=baseline))
                prefix='taught_' if taught else 'untaught_'
                checks[prefix+'native_history_unchanged']=stored==collect()
                checks[prefix+'repeat_full_parity']=views==[readers['conversation:attribute:'+s['scope']].read(s['query']) for s in specs]
                checks[prefix+'unqualified']=all(v['answer'] is None and v['qualified'] is False and not v['query_recorded'] for v in views)
                checks[prefix+'no_query_inserted']=all(spec['query'] not in {
                    r['text'] for r in stored if r['hierarchy_id']=='conversation:attribute:'+spec['scope'] and r['source_kind'] in USER_KINDS}
                    for spec in specs if spec['category']!='exact_content')
                indexed={address(r):r for r in stored}
                checks[prefix+'origins_local_observed_users']=all(
                    tuple(o) in indexed and indexed[tuple(o)]['hierarchy_id']==v['region'] and
                    indexed[tuple(o)]['source_kind'] in USER_KINDS and indexed[tuple(o)]['text']==c['text']
                    for v in views for c in v['candidates'] for o in c['origins'])
                native.reopen();cold=collect()
                cold_readers={s:AttributeFrameReader(cold,s) for s in scopes}
                checks[prefix+'cold_full_parity']=views==[cold_readers['conversation:attribute:'+s['scope']].read(s['query']) for s in specs]
                checks[prefix+'cold_history_equal']=cold==stored
                stages.append(dict(with_demonstrations=taught,cases=cases,rows=stored,
                    frame_totals=totals(cases,'frame'),baseline_totals=totals(cases,'baseline')))
            finally: native.close()
    if not all(checks.values()): raise RuntimeError('failed integrity: '+str([k for k,v in checks.items() if not v]))
    final=stages[-1]['frame_totals']
    return dict(format='memoria.ia-attribute-frame-probe-v1',stages=stages,checks=checks,
        integrity_status='PASS',integrity_passed=sum(checks.values()),integrity_total=len(checks),
        retrieval_quality_status='PASS' if final['exact_set']==final['cases'] else 'FAIL_EXTRA_OR_MISSING_CONTENT',
        factual_quality_status='NOT_EVALUATED',engine_changed=False,native_executed=True,
        answer=None,qualified=False,limitation='Curated teaching examples and fixed wording; no blind semantic generalization or proof of absence.')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--library',type=Path,required=True)
    parser.add_argument('--output',type=Path)
    parser.add_argument('--strict-quality',action='store_true')
    args=parser.parse_args();report=gate(args.library)
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        raw=(json.dumps(report,ensure_ascii=False,sort_keys=True,indent=2)+'\n').encode('utf-8')
        args.output.write_bytes(gzip.compress(raw,mtime=0) if args.output.suffix=='.gz' else raw)
    print(json.dumps(dict(integrity_status=report['integrity_status'],integrity_passed=report['integrity_passed'],
        retrieval_quality_status=report['retrieval_quality_status'],stages=[{k:v for k,v in s.items() if k not in ('cases','rows')} for s in report['stages']],
        full_report_sha256=fingerprint(report)),ensure_ascii=False,sort_keys=True))
    return int(args.strict_quality and report['retrieval_quality_status']!='PASS')


if __name__=='__main__': raise SystemExit(main())
