#!/usr/bin/env python3
"""Observed wording and case variants; no normalization or language classifier."""
import argparse
import json
from pathlib import Path
from trajectory_question_frame_probe import fixture as base_fixture, trial, summary

CASES = ('baseline', 'observed_variants', 'two_examples', 'generated_examples',
         'foreign_examples', 'repeated_conflict', 'matching_uppercase_targets',
         'crossed_paraphrase', 'unrelated_twin')


def fixture(case, seed, renamed=False):
    if case not in CASES or renamed:
        raise ValueError('unsupported fixture')
    base = 'repeated_conflict' if case == 'repeated_conflict' else 'three_examples'
    rows, region, queries = base_fixture(base, seed)
    foreign = f'conversation:foreign-{seed}'
    def add(text, source, scope=region, kind='user_turn'):
        rows.append(dict(hierarchy_id=scope, source_id=source,
                         sequence=1 + sum(r['hierarchy_id'] == scope for r in rows),
                         text=text, source_kind=kind))
    subjects = ('barco', 'avião', 'sensor')
    values = ('azul', 'preto', 'cinza')
    # These are fixture observations, never branches in the reader.
    for family in range(3):
        count = 0 if case == 'baseline' else 2 if case == 'two_examples' else 3
        for i in range(count):
            subject = subjects[i]
            question = (f'Que cor tem o {subject}?' if family == 0 else
                        f'QUAL É A COR DO {subject}?' if family == 1 else
                        f'QUAL É A COR DO {subject.upper()}?')
            content = f'A cor do {subject} é {values[i]}.'
            if case == 'matching_uppercase_targets' and family == 2:
                content = f'A COR DO {subject.upper()} É {values[i].upper()}.'
            if case == 'crossed_paraphrase' and family == 0:
                content = f'O nome do {subject} é {("Atlas", "Íris", "Sol")[i]}.'
            scope = foreign if case == 'foreign_examples' else region
            kind = 'assistant_generated' if case == 'generated_examples' else 'user_turn'
            add(question, f'variant-{family}-{i}-question', scope, kind)
            add(content, f'variant-{family}-{i}-content', scope, kind)
            add('Intervalo observado.', f'variant-{family}-{i}-barrier', scope, 'assistant_generated')
    if case == 'matching_uppercase_targets':
        add('A COR DO DRONE É VERDE.', 'uppercase-target')
        add('Intervalo observado.', 'uppercase-target-barrier', kind='assistant_generated')
        next(q for q in queries if q['name'] == 'uppercase')['expected'] = ['A COR DO DRONE É VERDE.']
    color = next(q for q in queries if q['name'] == 'color')['expected']
    queries += [dict(name='uppercase_cue', text='QUAL É A COR DO drone?', expected=list(color)),
                dict(name='unseen_paraphrase', text='Que cor possui o drone?', expected=list(color)),
                dict(name='paraphrase_absent_entity', text='Que cor tem o foguete?', expected=[]),
                dict(name='uppercase_absent_attribute', text='QUAL É A CORRENTE DO drone?', expected=[])]
    if case == 'unrelated_twin':
        for q in queries:
            q['expected'] = []
    if seed % 2 == 0:
        # Evaluator fixture variation only; the reader receives raw observations.
        replacements = {'barco':'carro', 'avião':'radar', 'sensor':'motor',
                        'drone':'robô', 'foguete':'satélite', 'verde':'laranja',
                        'branca':'roxa', 'azul':'rosa', 'preto':'âmbar', 'cinza':'prata'}
        replacements.update({k.upper():v.upper() for k,v in list(replacements.items())})
        def convert(text):
            for source, target in replacements.items():
                text = text.replace(source, target)
            return text
        rows = [dict(r, text=convert(r['text'])) for r in rows]
        queries = [dict(q, text=convert(q['text']), expected=[convert(t) for t in q['expected']]) for q in queries]
    return rows, region, queries


def probe(library, seed):
    trials = [trial(library, case, seed, False, fixture) for case in CASES]
    checks = {f'{i}:{k}': v for i,t in enumerate(trials) for k,v in t['checks'].items()}
    positive, twin = trials[1], trials[-1]
    checks['hidden_reference_same_rows'] = positive['rows'] == twin['rows']
    checks['hidden_reference_same_views'] = [q['frame_view'] for q in positive['queries']] == [q['frame_view'] for q in twin['queries']]
    totals = {}
    for route in ('frame', 'native'):
        scores = [q[route+'_score'] for t in trials for q in t['queries']]
        totals[route] = dict(queries=len(scores), exact_sets=sum(s['exact_set'] for s in scores),
            **{k: sum(s[k] for s in scores) for k in ('true_positive','false_positive','false_negative')})
    return dict(format='memoria.ia-question-variant-probe-v1', seed=seed, cases=trials,
        checks=checks, integrity_status='PASS' if all(checks.values()) else 'FAIL',
        integrity_passed=sum(checks.values()), integrity_total=len(checks), totals=totals,
        retrieval_quality_status='PASS_CURATED_ONLY' if totals['frame']['exact_sets'] == totals['frame']['queries'] else 'FAIL_EXTRA_OR_MISSING_CONTENT',
        hidden_relevance_status='FAIL_INDISTINGUISHABLE_INPUTS', factual_quality_status='NOT_EVALUATED',
        limitation='Literal observed variants; uppercase matching uses separately observed uppercase content. No semantic case equivalence, unseen paraphrase or factual truth guarantee.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--library', type=Path, required=True)
    parser.add_argument('--seed', type=int, default=20261223)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--summary', action='store_true')
    args = parser.parse_args()
    report = probe(args.library, args.seed)
    body = json.dumps(summary(report) if args.summary else report, ensure_ascii=False, indent=2) + '\n'
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(body, encoding='utf-8')
    print(body, end='')
    raise SystemExit(0 if report['integrity_status'] == 'PASS' else 1)


if __name__ == '__main__':
    main()
