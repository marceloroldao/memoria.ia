#!/usr/bin/env python3
"""Localize observed casing transfer; case-sensitive IDs remain separate controls."""
import argparse
import json
from pathlib import Path

from trajectory_feedback_variants_probe import corpus, evaluate
from trajectory_region_evidence_probe import fingerprint


ARMS = ('baseline', 'fixed', 'entity', 'full')


def case_question(text, mode):
    prefix, sep, entity = text.partition(' do ')
    if not sep or not entity.endswith('?'):
        raise ValueError('fixture question must have explicit entity boundary')
    if mode == 'baseline': return text
    if mode == 'fixed': return (prefix+sep).upper()+entity
    if mode == 'entity': return prefix+sep+entity.upper()
    if mode == 'full': return text.upper()
    raise ValueError('unknown case mode')


def diagnostic_fixture(base, arm):
    rows = list(base['rows'])
    training = [base['rows'][3*i]['text'].partition(' do ')[2][:-1] for i in range(3)]
    if arm != 'baseline':
        for i in range(3):
            q, a = base['rows'][3*i:3*i+2]
            rows += [dict(event_id=f'case-{arm}-{i}-q', text=case_question(q['text'], arm)),
                     dict(event_id=f'case-{arm}-{i}-a', text=a['text']),
                     dict(event_id=f'case-{arm}-{i}-barrier', text='Intervalo observado.', source_kind='assistant_generated')]
    original = base['queries'][0]
    queries = [dict(name=mode, text=case_question(original['text'], mode), expected=list(original['expected'])) for mode in ARMS]
    queries += base['queries'][3:]
    target = original['text'].partition(' do ')[2][:-1]
    witnessed = {(c.upper(), c) for entity in training for c in entity if c.upper() != c}
    required = {(c.upper(), c) for c in target if c.upper() != c}
    # This is a fixture-side diagnostic, not a complete proof of learned symbol mapping.
    return dict(base, rows=rows, queries=queries), dict(training_entities=training, target_entity=target,
                observed_case_pairs=sorted(witnessed), required_case_pairs=sorted(required),
                unwitnessed_case_pairs=sorted(required-witnessed), evaluator_only=True)


def sensitive_fixture():
    rows = []
    for i, entity in enumerate(('sensor', 'motor', 'circuito')):
        rows += [dict(event_id=f'demo-{i}-q', text=f'Qual é o código do {entity}?'),
                 dict(event_id=f'demo-{i}-a', text=f'O código do {entity} é {i+1}.'),
                 dict(event_id=f'demo-{i}-barrier', text='Intervalo observado.', source_kind='assistant_generated')]
    for i, (entity, value) in enumerate((('abc', '1'), ('ABC', '2'))):
        rows += [dict(event_id=f'target-{i}', text=f'O código do {entity} é {value}.'),
                 dict(event_id=f'target-{i}-barrier', text='Intervalo observado.', source_kind='assistant_generated')]
    return dict(scope='sensitive', rows=rows, foreign='O código do externo é 3.',
                queries=[dict(name='lower_id', text='Qual é o código do abc?', expected=['O código do abc é 1.']),
                         dict(name='upper_id', text='Qual é o código do ABC?', expected=['O código do ABC é 2.'])])


def probe(library, split):
    trials = []
    for arm in ARMS:
        for base in corpus(split):
            fixture, coverage = diagnostic_fixture(base, arm)
            trial = evaluate(library, split, 'baseline', fixture)
            trial.update(arm=arm, case_pair_diagnostic=coverage)
            trials.append(trial)
        sensitive = sensitive_fixture()
        # Add the same casing demonstrations, without giving either target question.
        rows = list(sensitive['rows'])
        if arm != 'baseline':
            for i in range(3):
                q, a = sensitive['rows'][3*i:3*i+2]
                rows += [dict(event_id=f'case-{arm}-{i}-q', text=case_question(q['text'], arm)),
                         dict(event_id=f'case-{arm}-{i}-a', text=a['text']),
                         dict(event_id=f'case-{arm}-{i}-barrier', text='Intervalo observado.', source_kind='assistant_generated')]
        trial = evaluate(library, split, 'baseline', dict(sensitive, rows=rows))
        trial['arm'] = arm
        trials.append(trial)
    checks = {f'{i}:{key}':value for i,t in enumerate(trials) for key,value in t['checks'].items()}
    summary = {}
    for arm in ARMS:
        cases = [c for t in trials if t['arm'] == arm for c in t['cases']]
        summary[arm] = {name:dict(queries=sum(c['query']['name'] == name for c in cases),
                                 recovered=sum(c['score']['recovered'] for c in cases if c['query']['name'] == name),
                                 extra=sum(c['score']['extra'] for c in cases if c['query']['name'] == name),
                                 missing=sum(c['score']['missing'] for c in cases if c['query']['name'] == name))
                        for name in ('baseline','fixed','entity','full','lower_id','upper_id',
                                     'absent_attribute','absent_entity','generated_only','foreign_only','no_overlap')}
    return dict(format='memoria.ia-feedback-case-localization-probe-v1', split=split,
                trials=trials, checks=checks, summary=summary,
                integrity_status='PASS' if all(checks.values()) else 'FAIL',
                human_evaluation_status='NOT_PERFORMED', general_learning_status='NOT_ESTABLISHED',
                limitation='Curated explicit case demonstrations. Source-boundary and case-pair labels exist only in evaluator. No automatic normalization, case-insensitive identity or factual qualification; partial coverage and extra roots reported separately.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--library', type=Path, required=True)
    parser.add_argument('--split', choices=('development','reserved'), required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(); report = probe(args.library, args.split)
    report['report_content_sha256'] = fingerprint(report)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, sort_keys=True, separators=(',',':'))+'\n')
    print(json.dumps({k:report[k] for k in ('split','integrity_status','summary','report_content_sha256')}))
    raise SystemExit(0 if report['integrity_status'] == 'PASS' else 1)


if __name__ == '__main__': main()
