#!/usr/bin/env python3
"""Read-only transform admission trace plus explicit observation interventions."""
import argparse
import json
from pathlib import Path

from trajectory_transform_trace_core import trace_transform
from trajectory_feedback_case_probe import diagnostic_fixture
from trajectory_feedback_variants_probe import corpus, evaluate
from trajectory_region_evidence_probe import fingerprint


ARMS = ('baseline', 'irrelevant', 'targeted', 'contrast')


def fixture_for(name, arm):
    split, scope = ('development', 'cars') if name == 'identity_pair' else ('reserved', 'devices')
    base = next(f for f in corpus(split) if f['scope'] == scope)
    fixture, exposure = diagnostic_fixture(base, 'entity')
    if arm != 'baseline':
        if arm == 'irrelevant':
            added = [dict(event_id='isolated-context', text='Observação isolada sem demonstração.')]
        else:
            question = 'Qual é a cor do FORTE?' if name == 'identity_pair' else 'Qual é a tensão do ADAPTADOR?'
            answer = ('A cor do Forte é verde.' if arm == 'targeted' else 'A cor do forte é verde.') if name == 'identity_pair' else (
                      'A tensão do adaptador é desconhecido.' if arm == 'targeted' else 'A tensão do adaptador é 18 V.')
            added = [dict(event_id='intervention-q', text=question),
                     dict(event_id='intervention-a', text=answer),
                     dict(event_id='intervention-barrier', text='Intervalo observado.', source_kind='assistant_generated')]
        fixture = dict(fixture, rows=fixture['rows']+added)
    return split, fixture, exposure


def probe(library):
    trials = []; checks = {}
    for name in ('identity_pair','value_suffix'):
        for arm in ARMS:
            split, fixture, exposure = fixture_for(name, arm)
            trial = evaluate(library, split, 'baseline', fixture)
            trial.update(experiment=name, arm=arm, prior_case_pair_diagnostic=exposure)
            query_case = next(c for c in trial['cases'] if c['query']['name'] == 'entity')
            before = fingerprint(query_case['view'])
            trace = trace_transform(query_case['view'], trial['observations'], query_case['query']['text'])
            trial['transform_trace'] = trace
            trial['checks'].update(trace_candidates_equal=trace['candidate_set_equal'],
                                  trace_read_only=fingerprint(query_case['view']) == before,
                                  references_absent_from_observation_schema=all(set(r) <= {'event_id','text','source_kind'} for r in trial['observations']))
            checks.update({f'{name}:{arm}:{k}':v for k,v in trial['checks'].items()})
            trials.append(trial)
    summary = {name:{t['arm']:dict(score=next(c['score'] for c in t['cases'] if c['query']['name']=='entity'),
                                  trace_status_counts=t['transform_trace']['status_counts']) for t in trials if t['experiment']==name}
               for name in ('identity_pair','value_suffix')}
    return dict(format='memoria.ia-entity-transform-intervention-probe-v1', trials=trials, checks=checks, summary=summary,
                integrity_status='PASS' if all(checks.values()) else 'FAIL',
                human_evaluation_status='NOT_PERFORMED', general_learning_status='NOT_ESTABLISHED',
                limitation='Post-diagnosis targeted interventions on two known failures, with negative contrasts. No held-out accuracy estimate or change to learner/reader. Added demonstrations are scripted observations, not autonomous learning from inferred output.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--library',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args(); report = probe(args.library)
    report['report_content_sha256'] = fingerprint(report)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,ensure_ascii=False,sort_keys=True,separators=(',',':'))+'\n')
    print(json.dumps({k:report[k] for k in ('integrity_status','summary','report_content_sha256')}))
    raise SystemExit(0 if report['integrity_status']=='PASS' else 1)


if __name__=='__main__': main()
