#!/usr/bin/env python3
"""Observed wording ablation over fresh targets; no normalization or truth selection."""
import argparse
import json
from pathlib import Path
import tempfile

from trajectory_feedback_portuguese_probe import fixtures, score
from trajectory_feedback_session import FeedbackSession
from trajectory_region_evidence_probe import fingerprint


ARMS = ('baseline', 'uppercase', 'paraphrase', 'both')
PARAPHRASES = {'pets': 'Como se chama o {}?', 'cars': 'Que cor tem o {}?',
              'devices': 'Quantos volts fornece o {}?', 'agenda': 'Em que dia será o {}?'}
RESERVED = {'pets': (['hamster', 'peixe', 'cavalo'], ['Lume', 'Dori', 'Trovão'], 'papagaio', 'Zeca'),
            'cars': (['Palio', 'Gol', 'Uno'], ['verde', 'vermelho', 'cinza'], 'Siena', 'amarelo'),
            'devices': (['circuito', 'inversor', 'transistor'], ['3 V', '6 V', '18 V'], 'conversor', '22 V'),
            'agenda': (['seminário', 'treinamento', 'festival'], ['quinta-feira', 'sábado', 'domingo'], 'congresso', 'segunda-feira')}


def corpus(split):
    data = fixtures()
    if split == 'development':
        return data
    if split != 'reserved':
        raise ValueError('unknown split')
    result = []
    for f in data:
        entities, values, target, value = RESERVED[f['scope']]
        old_target = f['queries'][0]['text'].split(' do ')[-1].rstrip('?')
        mapping = {old_target: target}
        for i in range(3):
            old_entity = f['rows'][3*i]['text'].split(' do ')[-1].rstrip('?')
            old_value = f['rows'][3*i+1]['text'].split(' é ')[-1].rstrip('.')
            mapping[old_entity] = entities[i]
            mapping[old_value] = values[i]
        old_value = f['rows'][9]['text'].split(' é ')[-1].rstrip('.')
        mapping[old_value] = value
        def convert(text):
            # Simultaneous literal replacement avoids substring/cascade changes.
            import re
            keys = sorted(mapping, key=len, reverse=True)
            return re.sub('|'.join(re.escape(k) for k in keys), lambda m: mapping[m.group()], text)
        rows = [dict(row, text=convert(row['text'])) for row in f['rows']]
        queries = [dict(q, text=convert(q['text']), expected=[convert(t) for t in q['expected']]) for q in f['queries']]
        # Uppercase cannot be converted using lowercase entity keys.
        queries[2]['text'] = queries[0]['text'].upper()
        result.append(dict(f, rows=rows, queries=queries))
    return result


def additions(fixture, arm):
    rows = []
    for i in range(3):
        question, answer = fixture['rows'][i*3:i*3+2]
        entity = question['text'].split(' do ')[-1].rstrip('?')
        variants = []
        if arm in ('uppercase', 'both'):
            variants.append(('uppercase', question['text'].upper()))
        if arm in ('paraphrase', 'both'):
            variants.append(('paraphrase', PARAPHRASES[fixture['scope']].format(entity)))
        for kind, text in variants:
            prefix = f'variant-{kind}-{i}'
            rows += [dict(event_id=prefix+'-q', text=text),
                     dict(event_id=prefix+'-a', text=answer['text']),
                     dict(event_id=prefix+'-barrier', text='Intervalo observado.', source_kind='assistant_generated')]
    return rows


def evaluate(library, split, arm, fixture):
    scope = fixture['scope']; inputs = fixture['rows'] + additions(fixture, arm)
    with tempfile.TemporaryDirectory(prefix='memoria-observed-variant-') as directory:
        with FeedbackSession(library, directory) as session:
            for row in inputs:
                session.execute(dict(op='observe', scope=scope, **row))
            session.execute(dict(op='observe', scope='foreign', event_id='foreign', text=fixture['foreign']))
            history = session.execute(dict(op='history', scope=scope))
            views = [session.execute(dict(op='query', scope=scope, text=q['text'])) for q in fixture['queries']]
            checks = dict(queries_read_only=session.execute(dict(op='history', scope=scope)) == history,
                          no_feedback_history=not history['result']['feedback_projection'] and not history['result']['withdrawal_history'],
                          repeats_equal=all(session.execute(dict(op='query', scope=scope, text=q['text'])) == v for q, v in zip(fixture['queries'], views)),
                          generated_and_foreign_excluded=all(c['text'] in {r['text'] for r in inputs if r.get('source_kind', 'user_turn') == 'user_turn'}
                              and all(o[0] == 'conversation:feedback-session:'+scope for o in c['origins']) for v in views for c in v['result']['raw_view']['candidates']),
                          unqualified=all(v['answer'] is None and not v['qualified'] and not v['selection_used'] for v in views))
        with FeedbackSession(library, directory) as cold:
            checks['cold_history'] = cold.execute(dict(op='history', scope=scope)) == history
            checks['cold_full_views'] = all(cold.execute(dict(op='query', scope=scope, text=q['text'])) == v for q, v in zip(fixture['queries'], views))
    cases = [dict(query=q, view=v, score=score(v, q['expected'])) for q, v in zip(fixture['queries'], views)]
    return dict(split=split, arm=arm, scope=scope, observations=inputs, cases=cases, checks=checks)


def probe(library, split):
    data = corpus(split)
    trials = [evaluate(library, split, arm, f) for arm in ARMS for f in data]
    checks = {f'{i}:{key}':value for i, trial in enumerate(trials) for key, value in trial['checks'].items()}
    summary = {}
    for arm in ARMS:
        cases = [c for t in trials if t['arm'] == arm for c in t['cases']]
        summary[arm] = {name:dict(queries=sum(c['query']['name'] == name for c in cases),
                                 recovered=sum(c['score']['recovered'] for c in cases if c['query']['name'] == name),
                                 extra=sum(c['score']['extra'] for c in cases if c['query']['name'] == name),
                                 missing=sum(c['score']['missing'] for c in cases if c['query']['name'] == name),
                                 exact=sum(c['score']['exact'] for c in cases if c['query']['name'] == name))
                        for name in (q['name'] for q in data[0]['queries'])}
    return dict(format='memoria.ia-observed-feedback-variants-probe-v1', split=split, trials=trials, summary=summary,
                checks=checks, integrity_status='PASS' if all(checks.values()) else 'FAIL',
                human_evaluation_status='NOT_PERFORMED', general_learning_status='NOT_ESTABLISHED',
                limitation='Explicit observed demonstrations, correlated wording templates and disjoint entity catalogues. No automatic case conversion, semantic paraphrase generalization or factual qualification. Reference scores are evaluator-only.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--library', type=Path, required=True)
    parser.add_argument('--split', choices=('development', 'reserved'), required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(); report = probe(args.library, args.split)
    report['report_content_sha256'] = fingerprint(report)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, sort_keys=True, separators=(',', ':'))+'\n')
    print(json.dumps({k:report[k] for k in ('split', 'integrity_status', 'summary', 'report_content_sha256')}))
    raise SystemExit(0 if report['integrity_status'] == 'PASS' else 1)


if __name__ == '__main__':
    main()
