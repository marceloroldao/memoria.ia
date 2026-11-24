#!/usr/bin/env python3
"""Experimental witnessed, length-preserving symbol substitution in frames.

Learner accepts integer sequences, no vocabulary or character case operations.
Three distinct adjacent root pairs must support each finite substitution map.
"""
import argparse
import copy
from dataclasses import asdict, dataclass
from hashlib import blake2b
from itertools import combinations
import json
from pathlib import Path
from random import Random
from string import ascii_lowercase, digits

from trajectory_analogy_frame_probe import prefix, suffix, middle, occurrences
from trajectory_question_frame_probe import read as raw_read, trial, summary
from trajectory_response_quality_probe import TrajectoryGenerationExperiment


@dataclass(frozen=True)
class TransformFrame:
    source_prefix: tuple
    source_suffix: tuple
    target_prefix: tuple
    target_bridge: tuple
    target_suffix: tuple
    symbol_map: tuple
    witnesses: tuple

    @property
    def frame_id(self):
        return blake2b(repr(self).encode(), digest_size=16).hexdigest()


def learn_frames(memory):
    previous, pairs = {}, set()
    for row in memory.snapshot()['observations']:
        scope = row['hierarchy_id'], row['stream_id']
        if scope in previous and previous[scope] != row['payload_id']:
            pairs.add((previous[scope], row['payload_id'], row['stream_id']))
        previous[scope] = row['payload_id']
    frames = set()
    for group in combinations(sorted(pairs), 3):
        sources = [memory.expand(s) for s, _, _ in group]
        targets = [memory.expand(t) for _, t, _ in group]
        left, right = prefix(sources), suffix(sources)
        if not left or not right:
            continue
        variables = [middle(s, left, right) for s in sources]
        if any(v is None for v in variables) or len(set(variables)) != 3:
            continue
        common_head = prefix(targets)
        for offset in range(1, len(common_head) + 1):
            copies = [t[offset:offset+len(v)] for t,v in zip(targets,variables)]
            if any(len(c) != len(v) for c,v in zip(copies,variables)) or len(set(copies)) != 3:
                continue
            mapping = {}
            consistent = True
            for source, target in zip(variables,copies):
                for a,b in zip(source,target):
                    if a in mapping and mapping[a] != b:
                        consistent = False
                        break
                    mapping[a] = b
                if not consistent:
                    break
            # Finite injective substitutions only. No extrapolation to symbols
            # not witnessed, no identity route, no language-specific policy.
            if not consistent or len(set(mapping.values())) != len(mapping) or all(a == b for a,b in mapping.items()):
                continue
            tails = [t[offset+len(v):] for t,v in zip(targets,variables)]
            bridge, ending = prefix(tails), suffix(tails)
            if not bridge or not ending:
                continue
            values = [middle(t,bridge,ending) for t in tails]
            if any(v is None for v in values) or len(set(values)) != 3:
                continue
            frames.add(TransformFrame(left,right,targets[0][:offset],bridge,ending,
                                      tuple(sorted(mapping.items())),group))
    return tuple(sorted(frames,key=lambda f:f.frame_id))


def recall(memory, query):
    query = tuple(query)
    frames = learn_frames(memory)
    roots = {r['payload_id'] for r in memory.snapshot()['observations']}
    candidates = {}
    for frame in frames:
        starts = occurrences(frame.source_prefix,query)
        if len(starts) != 1:
            continue
        variable = middle(query[starts[0]:],frame.source_prefix,frame.source_suffix)
        mapping = dict(frame.symbol_map)
        if variable is None or any(x not in mapping for x in variable):
            continue
        converted = tuple(mapping[x] for x in variable)
        head = frame.target_prefix + converted + frame.target_bridge
        for root in sorted(roots):
            if middle(memory.expand(root),head,frame.target_suffix) is not None:
                candidates.setdefault(root,[]).append(frame)
    return dict(frames=tuple(asdict(f) | {'frame_id':f.frame_id} for f in frames),
        candidates=tuple(dict(payload_id=root,output=memory.expand(root),
            frame_ids=tuple(f.frame_id for f in routes),
            witnesses=tuple(sorted({w for f in routes for w in f.witnesses})))
            for root,routes in sorted(candidates.items())),
        hypothesis=memory.expand(next(iter(candidates))) if len(candidates)==1 else None,
        reason='UNIQUE_OBSERVED_TRANSFORM_MATCH' if len(candidates)==1 else
               'COMPETING_TRANSFORM_MATCHES' if candidates else 'NO_OBSERVED_TRANSFORM_MATCH')


def checked_read(memory, query):
    before = memory.snapshot(), memory.learning_state(), asdict(memory.generate(query))
    result = recall(memory,query)
    cold = TrajectoryGenerationExperiment.restore(memory.snapshot())
    if result != recall(cold,query) or before != (memory.snapshot(), memory.learning_state(), asdict(memory.generate(query))):
        raise RuntimeError('transform read mutated memory or lost cold parity')
    return result


def read(rows, region, query):
    return raw_read(rows,region,query,reader=checked_read)


CASES = ('no_examples','observed_map','two_examples','repeated_one_example',
         'generated_examples','foreign_examples','repeated_conflict',
         'wrong_map','competing_maps','unrelated_twin')


def fixture(case, seed, renamed=False):
    if case not in CASES:
        raise ValueError('unknown case')
    region, foreign = f'conversation:transform-{seed}', f'conversation:outside-{seed}'
    rows=[]
    def add(text,source,scope=region,kind='user_turn'):
        rows.append(dict(hierarchy_id=scope,source_id=source,
            sequence=1+sum(r['hierarchy_id']==scope for r in rows),text=text,source_kind=kind))
    subjects = ('dardo','nervo','odre') if seed % 2 else ('nardo','vereda','ordem')
    values = ('azul','preto','cinza') if seed % 2 else ('rosa','âmbar','prata')
    entity, color = ('drone','verde') if seed % 2 else ('morena','laranja')
    # Fixture-only alternate finite relation; learner never sees this function.
    alternate = lambda text: text.replace('d','b').replace('n','l')
    count = 0 if case=='no_examples' else 2 if case=='two_examples' else 3
    for route in range(2 if case=='competing_maps' else 1):
        for i in range(count):
            j=0 if case=='repeated_one_example' else i
            scope=foreign if case=='foreign_examples' else region
            kind='assistant_generated' if case=='generated_examples' else 'user_turn'
            target=alternate(subjects[j]) if case=='wrong_map' or route else subjects[j]
            add(f'QUAL É A COR DO {subjects[j].upper()}?',f'train-{route}-{i}-q',scope,kind)
            add(f'A cor do {target} é {values[j]}.',f'train-{route}-{i}-a',scope,kind)
            add('Intervalo observado.',f'train-{route}-{i}-barrier',scope,'assistant_generated')
    fact=f'A cor do {entity} é {color}.'
    rival=f'A cor do {entity} é branca.'
    wrong=f'A cor do {alternate(entity)} é {color}.'
    targets=[fact, f'O nome do {entity} é Nova.', 'A cor do gato é preta.']
    if case in ('wrong_map','competing_maps'):
        targets.append(wrong)
    for i,text in enumerate(targets):
        add(text,f'isolated-{i}')
        add('Intervalo observado.',f'isolated-{i}-barrier',kind='assistant_generated')
    if case=='repeated_conflict':
        for i in range(20):
            add(fact if i else rival,f'conflict-{i}')
            add('Intervalo observado.',f'conflict-{i}-barrier',kind='assistant_generated')
    expected=[fact]
    if case=='repeated_conflict': expected.append(rival)
    if case=='competing_maps': expected.append(wrong)
    queries=[dict(name='covered',text=f'QUAL É A COR DO {entity.upper()}?',expected=expected),
             dict(name='new_prefix',text=f'Lembre: QUAL É A COR DO {entity.upper()}?',expected=expected),
             dict(name='unknown_symbols',text='QUAL É A COR DO GATO?',expected=['A cor do gato é preta.']),
             dict(name='absent_entity',text='QUAL É A COR DO NORDE?',expected=[]),
             dict(name='untrained_relation',text=f'QUAL É O NOME DO {entity.upper()}?',expected=[targets[1]]),
             dict(name='absent_attribute',text=f'QUAL É A IDADE DO {entity.upper()}?',expected=[]),
             dict(name='untrained_lowercase',text=f'Qual é a cor do {entity}?',expected=expected),
             dict(name='unseen_paraphrase',text=f'Que cor possui o {entity}?',expected=expected),
             dict(name='two_cues',text=f'QUAL É A COR DO {entity.upper()}? QUAL É A COR DO NORDE?',expected=[])]
    if case=='unrelated_twin':
        for q in queries: q['expected']=[]
    if renamed:
        symbols=sorted({c for r in rows for c in r['text']} | {c for q in queries for c in q['text']})
        alphabet=list(ascii_lowercase+digits+''.join(chr(i) for i in range(0xe0,0x100) if i!=0xf7))
        if len(symbols)>len(alphabet): raise ValueError('alphabet exhausted')
        Random(seed).shuffle(alphabet)
        mapping=dict(zip(symbols,alphabet))
        convert=lambda text: ''.join(mapping[c] for c in text)
        rows=[dict(r,text=convert(r['text'])) for r in rows]
        queries=[dict(q,text=convert(q['text']),expected=[convert(t) for t in q['expected']]) for q in queries]
    return rows,region,queries


def probe(library, seed):
    trials=[trial(library,c,seed,r,fixture,read) for r in (False,True) for c in CASES]
    checks={f'{i}:{k}':v for i,t in enumerate(trials) for k,v in t['checks'].items()}
    for i,c in enumerate(CASES):
        checks['rename:'+c]=[q['frame_score'] for q in trials[i]['queries']]==[q['frame_score'] for q in trials[i+len(CASES)]['queries']]
    for offset in (0,len(CASES)):
        positive,twin=trials[offset+1],trials[offset+CASES.index('unrelated_twin')]
        checks[f'twin_rows:{offset}']=positive['rows']==twin['rows']
        checks[f'twin_views:{offset}']=[q['frame_view'] for q in positive['queries']]==[q['frame_view'] for q in twin['queries']]
    totals={}
    for route in ('frame','native'):
        scores=[q[route+'_score'] for t in trials for q in t['queries']]
        totals[route]=dict(queries=len(scores),exact_sets=sum(s['exact_set'] for s in scores),
            **{k:sum(s[k] for s in scores) for k in ('true_positive','false_positive','false_negative')})
    return dict(format='memoria.ia-symbol-transform-probe-v1',seed=seed,cases=trials,
        checks=checks,integrity_status='PASS' if all(checks.values()) else 'FAIL',
        integrity_passed=sum(checks.values()),integrity_total=len(checks),totals=totals,
        retrieval_quality_status='PASS_CURATED_ONLY' if totals['frame']['exact_sets']==totals['frame']['queries'] else 'FAIL_EXTRA_OR_MISSING_CONTENT',
        hidden_relevance_status='FAIL_INDISTINGUISHABLE_INPUTS',factual_quality_status='NOT_EVALUATED',
        limitation='Observed finite injective length-preserving symbol substitutions, correlated templates and renaming; no Unicode case rule or unknown-symbol extrapolation; no factual qualification.')


def report_summary(report):
    compact = summary(report)
    # These small maps are the central new evidence: keep their complete
    # symbol correspondences, boundaries and demonstration witnesses visible.
    for source, target in zip(report["cases"], compact["cases"]):
        target["transform_frames"] = copy.deepcopy(source["frames"])
    return compact


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--library',type=Path,required=True)
    parser.add_argument('--seed',type=int,default=20261225)
    parser.add_argument('--output',type=Path)
    parser.add_argument('--summary',action='store_true')
    args=parser.parse_args();report=probe(args.library,args.seed)
    body=json.dumps(report_summary(report) if args.summary else report,ensure_ascii=False,indent=2)+'\n'
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(body,encoding='utf-8')
    print(body,end='')
    raise SystemExit(0 if report['integrity_status']=='PASS' else 1)


if __name__=='__main__': main()
