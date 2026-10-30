#!/usr/bin/env python3
"""Fresh finite-map catalogues; retain conflicting routes without factual selection."""
import argparse
import json
from pathlib import Path

from trajectory_entity_transform_trace import trace_transform
from trajectory_feedback_case_probe import sensitive_fixture
from trajectory_feedback_variants_probe import evaluate
from trajectory_region_evidence_probe import fingerprint


ARMS = ('baseline','irrelevant','intervention','contrast')
EXPERIMENTS = ('unseen_symbol','unseen_identity','conflicting_map','value_boundary')
CATALOGUES = {
    'frequency': dict(attribute='frequência', units='Hz', training=('ABC','BCD','CDA'),
                      target='DAC', unseen='QAC', identity='ZAC', teaching='QBC', identity_teaching='ZBC',
                      absent='DDAC', generated='ACD', foreign='BDA', conflict_source='D', conflict_target='x'),
    'level': dict(attribute='nível', units='dB', training=('LM','MN','NL'),
                  target='LN', unseen='UN', identity='VN', teaching='UM', identity_teaching='VM',
                  absent='LLN', generated='ML', foreign='NM', conflict_source='L', conflict_target='z'),
}


def fixture_for(catalogue, experiment, arm):
    if catalogue not in CATALOGUES or experiment not in EXPERIMENTS or arm not in ARMS:
        raise ValueError('unknown catalogue, experiment or arm')
    spec = CATALOGUES[catalogue]; attribute = spec['attribute']; units = spec['units']
    question = lambda entity: f'Qual é a {attribute} do {entity}?'
    statement = lambda entity,value: f'A {attribute} do {entity} é {value}.'
    mapping = {c:c.lower() for entity in spec['training'] for c in entity}
    def convert(entity, extra=None):
        table = mapping | (extra or {})
        return ''.join(table[c] for c in entity)
    rows = []
    def add(text, event_id, kind='user_turn'):
        rows.append(dict(text=text,event_id=event_id,source_kind=kind))
    def demonstrate(entity, value, event_id, extra=None):
        add(question(entity),event_id+'-q')
        add(statement(convert(entity,extra),value),event_id+'-a')
        add('Intervalo observado.',event_id+'-barrier','assistant_generated')
    for i, entity in enumerate(spec['training']):
        demonstrate(entity,f'{10*(i+1)} {units}',f'base-{i}')
    if experiment == 'unseen_symbol':
        target = spec['unseen']; new = target[0]; desired_map = {new:new.lower()}
    elif experiment == 'unseen_identity':
        target = spec['identity']; new = target[0]; desired_map = {new:new}
    else:
        target = spec['target']; desired_map = {}
    expected = [statement(convert(target,desired_map),f'40 {units}')]
    add(expected[0],'target')
    add('Intervalo observado.','target-barrier','assistant_generated')
    if experiment == 'conflicting_map':
        alternative = {spec['conflict_source']:spec['conflict_target']}
        expected.append(statement(convert(target,alternative),f'60 {units}'))
        add(expected[-1],'alternate-target')
        add('Intervalo observado.','alternate-barrier','assistant_generated')
    if experiment == 'value_boundary':
        expected.append(statement(convert(target),'sem leitura'))
        add(expected[-1],'different-ending-target')
        add('Intervalo observado.','different-ending-barrier','assistant_generated')
    add(statement(convert(spec['generated']),f'70 {units}'),'generated-target','assistant_generated')
    prefix_length = len(rows)
    if arm == 'irrelevant':
        add('Observação isolada sem demonstração.','irrelevant')
    elif arm in ('intervention','contrast'):
        if experiment in ('unseen_symbol','unseen_identity'):
            entity = spec['teaching'] if experiment == 'unseen_symbol' else spec['identity_teaching']
            extra = desired_map if arm == 'intervention' else {new:('x' if catalogue=='frequency' else 'z')}
            if experiment == 'unseen_identity' and arm == 'contrast': extra = {new:new.lower()}
            demonstrate(entity,f'50 {units}','additional',extra)
        elif experiment == 'conflicting_map':
            alternative = {spec['conflict_source']:spec['conflict_target']} if arm == 'intervention' else {}
            for i, entity in enumerate(spec['training']):
                demonstrate(entity,f'{10*(i+1)} {units}',f'additional-{i}',alternative)
        else:
            # A new entity made only of witnessed symbols, without the query target.
            entity = spec['training'][0]+spec['training'][1]
            demonstrate(entity,'sem leitura' if arm=='intervention' else f'50 {units}','additional')
    queries = [dict(name='primary',text=question(target),expected=expected),
               dict(name='absent_attribute',text=f'Qual é a idade do {target}?',expected=[]),
               dict(name='absent_entity',text=question(spec['absent']),expected=[]),
               dict(name='generated_only',text=question(spec['generated']),expected=[]),
               dict(name='foreign_only',text=question(spec['foreign']),expected=[]),
               dict(name='no_overlap',text='zzzzzzz',expected=[])]
    return dict(scope=catalogue+'_'+experiment,rows=rows,queries=queries,
                foreign=statement(convert(spec['foreign']),f'80 {units}'), intervention_start=prefix_length)


def probe(library):
    trials = []; checks = {}
    for catalogue in CATALOGUES:
        for experiment in EXPERIMENTS:
            for arm in ARMS:
                fixture = fixture_for(catalogue,experiment,arm)
                trial = evaluate(library,catalogue,'baseline',fixture)
                trial.update(arm=arm,experiment=experiment,intervention_start=fixture['intervention_start'])
                case = trial['cases'][0]; before = fingerprint(case['view'])
                trial['transform_trace'] = trace_transform(case['view'],trial['observations'],case['query']['text'])
                trial['checks'].update(trace_candidates_equal=trial['transform_trace']['candidate_set_equal'],
                                      trace_read_only=fingerprint(case['view'])==before,
                                      unqualified_conflict=not case['view']['qualified'] and case['view']['answer'] is None)
                trials.append(trial)
        trial = evaluate(library,catalogue,'baseline',sensitive_fixture())
        trial.update(experiment='sensitive_ids',arm='control')
        trials.append(trial)
    for i, trial in enumerate(trials):
        checks.update({f'{i}:{k}':v for k,v in trial['checks'].items()})
    summary = {catalogue:{experiment:{t['arm']:t['cases'][0]['score'] for t in trials
                        if t['split']==catalogue and t['experiment']==experiment}
                       for experiment in EXPERIMENTS} for catalogue in CATALOGUES}
    return dict(format='memoria.ia-fresh-transform-catalogue-probe-v1',trials=trials,summary=summary,checks=checks,
                integrity_status='PASS' if all(checks.values()) else 'FAIL',
                human_evaluation_status='NOT_PERFORMED',general_learning_status='NOT_ESTABLISHED',
                limitation='Two new curated finite-map catalogues designed after earlier diagnoses, with correlated templates and scripted interventions. Conflicting maps expose alternative hypotheses, not resolved truth. No independent accuracy estimate, automatic normalization or learner change.')


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
