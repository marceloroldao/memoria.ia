#!/usr/bin/env python3
"""Curated Portuguese session evaluation. Scripted feedback, not human validation."""
import argparse
import json
from pathlib import Path
import tempfile

from trajectory_feedback_session import FeedbackSession
from trajectory_region_evidence_probe import fingerprint


def fixtures():
    domains = [
        ('pets', ['gato', 'cachorro', 'pássaro'], ['Alt', 'Bolt', 'Piu'], 'coelho', 'Nino',
         'Qual é o nome do {}?', 'O nome do {} é {}.', 'Como se chama o coelho?', 'Qual é a idade do coelho?'),
        ('cars', ['Corsa', 'Jetta', 'Kombi'], ['prata', 'preto', 'branca'], 'Fiesta', 'azul',
         'Qual é a cor do {}?', 'A cor do {} é {}.', 'Que cor tem o Fiesta?', 'Qual é o ano do Fiesta?'),
        ('devices', ['sensor', 'robô', 'motor'], ['5 V', '9 V', '24 V'], 'carregador', '12 V',
         'Qual é a tensão do {}?', 'A tensão do {} é {}.', 'Quantos volts fornece o carregador?', 'Qual é a corrente do carregador?'),
        ('agenda', ['curso', 'encontro', 'passeio'], ['segunda-feira', 'terça-feira', 'quarta-feira'], 'evento', 'sexta-feira',
         'Qual é o dia do {}?', 'O dia do {} é {}.', 'Em que dia será o evento?', 'Qual é o horário do evento?'),
    ]
    result = []
    for scope, entities, values, target, value, question, statement, paraphrase, absent in domains:
        rows = []
        for i, (entity, item) in enumerate(zip(entities, values)):
            rows += [dict(event_id=f'demo-{i}-q', text=question.format(entity)),
                     dict(event_id=f'demo-{i}-a', text=statement.format(entity, item)),
                     dict(event_id=f'demo-{i}-barrier', text='Intervalo observado.', source_kind='assistant_generated')]
        fact = statement.format(target, value)
        conflict = statement.format(target, 'desconhecido')
        rows += [dict(event_id='target', text=fact),
                 dict(event_id='barrier', text='Intervalo observado.', source_kind='assistant_generated'),
                 dict(event_id='conflict', text=conflict),
                 dict(event_id='conflict-barrier', text='Intervalo observado.', source_kind='assistant_generated'),
                 dict(event_id='generated', text=statement.format('objeto gerado', 'inventado'), source_kind='assistant_generated')]
        queries = [dict(name='covered_conflict', text=question.format(target), expected=[fact, conflict]),
                   dict(name='paraphrase', text=paraphrase, expected=[fact, conflict]),
                   dict(name='uppercase', text=question.format(target).upper(), expected=[fact, conflict]),
                   dict(name='absent_attribute', text=absent, expected=[]),
                   dict(name='absent_entity', text=question.format('objeto ausente'), expected=[]),
                   dict(name='generated_only', text=question.format('objeto gerado'), expected=[]),
                   dict(name='foreign_only', text=question.format('objeto estrangeiro'), expected=[]),
                   dict(name='no_overlap', text='zzzzzzz', expected=[])]
        result.append(dict(scope=scope, rows=rows, queries=queries,
                           foreign=statement.format('objeto estrangeiro', 'fora')))
    return result


def score(view, expected):
    observed = {c['text'] for c in view['result']['available_candidates']}
    expected = set(expected)
    return dict(exact=observed == expected, recovered=len(observed & expected),
                extra=len(observed-expected), missing=len(expected-observed))


def probe(library):
    cases = []; checks = {}
    for fixture in fixtures():
        scope = fixture['scope']
        with tempfile.TemporaryDirectory(prefix='memoria-portuguese-feedback-') as directory:
            with FeedbackSession(library, directory) as session:
                for row in fixture['rows']:
                    session.execute(dict(op='observe', scope=scope, **row))
                session.execute(dict(op='observe', scope='foreign', event_id='foreign', text=fixture['foreign']))
                history = session.execute(dict(op='history', scope=scope))
                views = [session.execute(dict(op='query', scope=scope, text=q['text'])) for q in fixture['queries']]
                checks[scope+':queries_read_only'] = session.execute(dict(op='history', scope=scope)) == history
                checks[scope+':repeated_full_views'] = all(session.execute(dict(op='query', scope=scope, text=q['text'])) == v
                                                         for q, v in zip(fixture['queries'], views))
                for query, view in zip(fixture['queries'], views):
                    candidates = view['result']['raw_view']['candidates']
                    accepted = {r['text'] for r in fixture['rows'] if r.get('source_kind', 'user_turn') == 'user_turn'}
                    checks[scope+':observed:'+query['name']] = all(c['text'] in accepted and all(o[0] == 'conversation:feedback-session:'+scope for o in c['origins']) for c in candidates)
                    checks[scope+':unqualified:'+query['name']] = view['answer'] is None and not view['qualified'] and not view['selection_used']
                    cases.append(dict(scope=scope, query=query, view=view, score=score(view, query['expected'])))
                # The operator target is selected by returned order, never by reference correctness.
                initial = views[0]; cycle = dict(status='NO_CANDIDATE_FOR_FEEDBACK')
                if initial['result']['receipts']:
                    binding = initial['result']['receipts'][0]
                    saved = session.execute(dict(op='feedback', scope=scope, receipt=binding,
                                                 event_id='operator-opposition', actor_id='scripted-operator', stance='oppose'))['result']
                    target = {k: saved[k] for k in ('address', 'event')}
                    opposed = session.execute(dict(op='query', scope=scope, text=fixture['queries'][0]['text']))
                    session.execute(dict(op='withdraw', scope=scope, target=target,
                                         request_id='operator-withdrawal', actor_id='scripted-operator'))
                    restored = session.execute(dict(op='query', scope=scope, text=fixture['queries'][0]['text']))
                    checks[scope+':raw_preserved'] = initial['result']['raw_view'] == opposed['result']['raw_view'] == restored['result']['raw_view']
                    checks[scope+':only_one_suspended'] = len(opposed['result']['withheld_candidates']) == 1
                    checks[scope+':withdrawal_restores_set'] = restored['result']['available_candidates'] == initial['result']['available_candidates']
                    cycle = dict(status='SCRIPTED_CYCLE_EXECUTED', target=target,
                                 before=score(initial, fixture['queries'][0]['expected']),
                                 opposed=score(opposed, fixture['queries'][0]['expected']),
                                 restored=score(restored, fixture['queries'][0]['expected']))
                final_views = [session.execute(dict(op='query', scope=scope, text=q['text'])) for q in fixture['queries']]
                final_history = session.execute(dict(op='history', scope=scope))
            with FeedbackSession(library, directory) as cold:
                checks[scope+':cold_history'] = cold.execute(dict(op='history', scope=scope)) == final_history
                checks[scope+':cold_full_views'] = all(cold.execute(dict(op='query', scope=scope, text=q['text'])) == v
                                                    for q, v in zip(fixture['queries'], final_views))
            for case in cases:
                if case['scope'] == scope:
                    case['feedback_cycle'] = cycle
    totals = dict(queries=len(cases), exact=sum(c['score']['exact'] for c in cases),
                  recovered=sum(c['score']['recovered'] for c in cases), extra=sum(c['score']['extra'] for c in cases),
                  missing=sum(c['score']['missing'] for c in cases))
    return dict(format='memoria.ia-portuguese-feedback-session-probe-v1', cases=cases, checks=checks, totals=totals,
                integrity_status='PASS' if all(checks.values()) else 'FAIL',
                retrieval_status='PASS_CURATED_SET' if totals['exact'] == totals['queries'] else 'EXTRA_OR_MISSING_CONTENT',
                human_evaluation_status='NOT_PERFORMED', general_learning_status='NOT_ESTABLISHED',
                limitation='Curated correlated templates and scripted operator feedback; not human evaluation, independent benchmark or factual validation.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--library', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = probe(args.library)
    report['report_content_sha256'] = fingerprint(report)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, sort_keys=True, separators=(',', ':'))+'\n')
    print(json.dumps({k: report[k] for k in ('totals', 'integrity_status', 'retrieval_status', 'human_evaluation_status', 'report_content_sha256')}))
    raise SystemExit(0 if report['integrity_status'] == 'PASS' else 1)


if __name__ == '__main__':
    main()
