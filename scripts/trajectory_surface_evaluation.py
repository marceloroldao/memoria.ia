#!/usr/bin/env python3
"""Observed surface demonstrations and negative controls; no reader normalization."""
import argparse
import copy
import json
from pathlib import Path

from trajectory_region_evidence_probe import fingerprint
from trajectory_transfer_evaluation import DOMAINS, SEEDS, fixture as transfer_fixture, trial


ARMS = ('baseline','repeat_original','one_surface','two_surface','three_surface',
        'known_symbols_only','wrong_map','generated','foreign')
SURFACES = ('uppercase','paraphrase')


def surface_text(text, surface):
    if surface=='uppercase': return text.upper()
    if surface!='paraphrase': raise ValueError('unknown surface')
    # Fixture construction only, not a query adapter: the reader receives the exact text.
    attribute, entity = text.removeprefix('Qual é a ').removesuffix('?').split(' do ')
    return f'Que {attribute} tem o {entity}?'


def fixture(domain,seed,surface,arm):
    if arm not in ARMS or surface not in SURFACES: raise ValueError('unknown condition')
    base = transfer_fixture(domain,seed,'intervention')
    result = copy.deepcopy(base)
    result.update(surface=surface,arm=arm,intervention_start=len(base['rows']),foreign_rows=[])
    originals = base['queries'][:2]
    queries = [dict(q,family='original') for q in originals]
    queries += [dict(q,name=f'{surface}_{i+1}',text=surface_text(q['text'],surface),family='surface',required=True)
                for i,q in enumerate(originals)]
    # Test whether teaching one surface also transfers to the other, without assuming that it should.
    other = next(s for s in SURFACES if s!=surface)
    queries.append(dict(originals[0],name='untaught_surface',text=surface_text(originals[0]['text'],other),
                        family='untaught_surface',required=False))
    queries += [dict(q,text=surface_text(q['text'],surface)) for q in base['queries'] if q['family']=='absence']
    result['queries'] = queries
    # First pair witnesses the fourth symbol. The next two witness the original three.
    pairs = [base['rows'][-3:-1],base['rows'][0:2],base['rows'][3:5]]
    if arm=='known_symbols_only': pairs = [base['rows'][i:i+2] for i in (0,3,6)]
    count = 0 if arm=='baseline' else 1 if arm=='one_surface' else 2 if arm=='two_surface' else 3
    for i,pair in enumerate(pairs[:count]):
        question = pair[0]['text'] if arm=='repeat_original' else surface_text(pair[0]['text'],surface)
        answer = pair[1]['text']
        if arm=='wrong_map' and i==0:
            head, rest = answer.split(' do ')
            used = {c for row in base['rows'] for c in row['text']}
            wrong = next(c for c in 'abcdefghjklmnpqrstuvxyz' if c not in used)
            answer = head+' do '+wrong+rest[1:]
        kind = 'assistant_generated' if arm=='generated' else 'user_turn'
        added = [dict(event_id=f'surface-{i}-q',text=question,source_kind=kind),
                 dict(event_id=f'surface-{i}-a',text=answer,source_kind=kind),
                 dict(event_id=f'surface-{i}-barrier',text='Intervalo observado.',source_kind='assistant_generated')]
        result['foreign_rows' if arm=='foreign' else 'rows'].extend(added)
    assert all(q['text'] not in {r['text'] for r in result['rows']+result['foreign_rows']} for q in queries)
    return result


def summarize(trials):
    checks = {f'{i}:{name}':ok for i,t in enumerate(trials) for name,ok in t['checks'].items()}
    checks.update({f'{i}:diagnostic_trace_matches':all(c['diagnosis']['transform_candidate_set_equal'] for c in t['cases'])
                   for i,t in enumerate(trials)})
    summary = {}
    for arm in ARMS:
        cases = [c for t in trials if t['fixture']['arm']==arm for c in t['cases']]
        summary[arm] = {family:dict(exact=sum(c['score']['exact'] for c in cases if c['query']['family']==family),
                                   total=sum(c['query']['family']==family for c in cases))
                        for family in ('original','surface','untaught_surface','absence')}
    taught = [c for t in trials if t['fixture']['arm']=='three_surface' for c in t['cases']]
    return dict(format='memoria.ia-observed-surface-evaluation-v1',trials=trials,summary=summary,checks=checks,
                integrity_status='PASS' if all(checks.values()) else 'FAIL',
                retrieval_status='PASS_CURATED_SET' if all(c['score']['exact'] for c in taught) else 'EXTRA_OR_MISSING_CONTENT',
                selected_answer_count=sum(c['answer'] is not None for t in trials for c in t['cases']),
                human_evaluation_status='NOT_PERFORMED',general_learning_status='NOT_ESTABLISHED',
                reader_changed=False,normalization_used=False,labels_used_by_session=False,
                limitation='Post-diagnosis interventions on the same two synthetic symbol maps and correlated domains. New source templates are explicitly demonstrated, not understood automatically. Target facts were already observed. Python experimental reader over native persistence; no independent benchmark or factual answer selection.')


def probe(library):
    return summarize([trial(library,fixture(domain,seed,surface,arm),operation='diagnose')
                      for seed in SEEDS for domain in DOMAINS for surface in SURFACES for arm in ARMS])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--library',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--strict-retrieval',action='store_true')
    args=parser.parse_args();report=probe(args.library);report['report_content_sha256']=fingerprint(report)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,ensure_ascii=False,sort_keys=True,separators=(',',':'))+'\n')
    print(json.dumps(dict(integrity_status=report['integrity_status'],retrieval_status=report['retrieval_status'],summary=report['summary'],sha256=report['report_content_sha256'])))
    return 1 if report['integrity_status']!='PASS' or (args.strict_retrieval and report['retrieval_status']!='PASS_CURATED_SET') else 0


if __name__=='__main__': raise SystemExit(main())
