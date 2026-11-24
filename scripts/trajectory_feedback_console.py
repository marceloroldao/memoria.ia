#!/usr/bin/env python3
"""Portuguese operator console; caller assessments never enter native learning."""
import argparse
import json
import os
from pathlib import Path
from uuid import uuid4

from trajectory_feedback_lab import open_lab, text
from trajectory_feedback_ledger_probe import canonical
from trajectory_question_frame_probe import score
from trajectory_region_evidence_probe import fingerprint


def assessment(query, packet, expected, actor):
    text(query, 'query')
    text(actor, 'actor', 128)
    if (not isinstance(expected, list) or len(expected) > 64
            or any(not isinstance(v, str) or not v.strip() for v in expected)
            or len(set(expected)) != len(expected)
            or sum(len(v) for v in expected) > 4096):
        raise ValueError('Referências devem ser uma lista JSON de textos distintos (até 4096 caracteres).')
    if packet.get('op') != 'query' or packet.get('qualified') or packet.get('answer') is not None:
        raise ValueError('Avaliação exige uma consulta sem qualificação factual.')
    result = packet['result']
    view = result['view']
    for binding in result['receipts']:
        if binding['query'] != query:
            raise ValueError('Recibo pertence a outra consulta.')
    raw = score([c['text'] for c in view['raw_view']['candidates']], expected)
    filtered = score([c['text'] for c in view['available_candidates']], expected)
    raw_errors = raw['false_positive'] + raw['false_negative']
    filtered_errors = filtered['false_positive'] + filtered['false_negative']
    return dict(format='memoria.ia-operator-assessment-v1', query=query, packet=packet,
                expected=expected, actor_id=actor, reference_source='CALLER_SUPPLIED',
                human_participation='NOT_VERIFIED', raw_score=raw, filtered_score=filtered,
                extra_removed=raw['false_positive'] - filtered['false_positive'],
                expected_removed=raw['true_positive'] - filtered['true_positive'],
                effect=('FEWER_ERRORS' if filtered_errors < raw_errors else
                        'MORE_ERRORS' if filtered_errors > raw_errors else 'SAME_ERROR_COUNT'))


class ReviewJournal:
    """Append-only evaluations outside BDR, under the owning laboratory lock.

    Checksums detect accidental alteration, not malicious rewriting or tail deletion.
    A partial final record is rejected, never silently discarded.
    """
    def __init__(self, path):
        self.path = path

    def records(self):
        result = []
        if not self.path.exists():
            return result
        with self.path.open(encoding='utf-8') as source:
            for line in source:
                if not line.endswith('\n'):
                    raise ValueError('Registro de avaliação incompleto; arquivo não foi alterado.')
                item = json.loads(line)
                payload = item['assessment']
                rebuilt = assessment(payload['query'], payload['packet'], payload['expected'], payload['actor_id'])
                if (canonical(payload) != canonical(rebuilt) or item['sequence'] != len(result) + 1
                        or item['previous_sha256'] != (result[-1]['sha256'] if result else None)):
                    raise ValueError('Histórico de avaliações inconsistente.')
                body = {k: v for k, v in item.items() if k != 'sha256'}
                if item['sha256'] != fingerprint(body):
                    raise ValueError('Checksum de avaliação inválido.')
                result.append(item)
        return result

    def append(self, review):
        previous = self.records()
        # Normalize JSON types and recompute rather than trusting supplied scores.
        review = assessment(review['query'], review['packet'], review['expected'], review['actor_id'])
        entry = dict(sequence=len(previous) + 1,
                     previous_sha256=previous[-1]['sha256'] if previous else None,
                     assessment=review)
        entry['sha256'] = fingerprint(entry)
        with self.path.open('a', encoding='utf-8') as target:
            target.write(canonical(entry) + '\n')
            target.flush()
            os.fsync(target.fileno())
        return entry

    def report(self):
        rows = self.records()
        effects = {name: 0 for name in ('FEWER_ERRORS', 'MORE_ERRORS', 'SAME_ERROR_COUNT')}
        totals = {policy: {k: 0 for k in ('true_positive', 'false_positive', 'false_negative')}
                  for policy in ('raw_score', 'filtered_score')}
        for row in rows:
            review = row['assessment']
            effects[review['effect']] += 1
            for policy in totals:
                for key in totals[policy]:
                    totals[policy][key] += review[policy][key]
        return dict(format='memoria.ia-operator-report-v1', assessments=len(rows), effects=effects,
                    totals=totals, last_sha256=rows[-1]['sha256'] if rows else None,
                    human_participation='NOT_VERIFIED', factual_quality_status='NOT_EVALUATED',
                    limitation='Caller-labelled query occurrences, including repeated reviews; '
                    'raw versus filtered on the same saved read, not a longitudinal or human study. '
                    'Labels may be wrong and do not train memory.')


def run_console(lab, journal, actor, scope='principal', *, ask=input, show=print):
    """Prompted UI; errors preserve native state according to the existing lab contract."""
    last = None
    # Refuse corrupted journals before permitting any operator writes.
    journal.records()
    show('Memoria.ia — laboratório local. Candidatas não são respostas factuais.')
    while True:
        try:
            choice = ask('1 Registrar | 2 Consultar | 3 Apoiar | 4 Opor | 5 Retirar | '
                         '6 Histórico | 7 Avaliar consulta | 8 Relatório | 9 Evidências | 0 Sair: ').strip()
            if choice == '0':
                return
            if choice == '1':
                kind = ask('Origem: 1 observação do usuário; 2 conteúdo gerado: ').strip()
                if kind not in ('1', '2'):
                    raise ValueError('Origem inválida.')
                command = dict(op='observe', source_id='console:' + uuid4().hex,
                               text=ask('Texto observado: '),
                               source_kind='user_turn' if kind == '1' else 'assistant_generated')
            elif choice == '2':
                query = ask('Pergunta: ')
                packet = lab.execute(dict(op='query', scope=scope, text=query))
                last = (query, packet)
                withheld = {c['payload_id'] for c in packet['result']['view']['withheld_candidates']}
                for index, binding in enumerate(packet['result']['receipts'], 1):
                    candidate = binding['candidate']
                    state = 'VETADA' if candidate['payload_id'] in withheld else 'DISPONÍVEL'
                    show(f'{index}. [{state}] {candidate["text"]}')
                if not packet['result']['receipts']:
                    show('Nenhuma candidata recuperada.')
                continue
            elif choice in ('3', '4'):
                if last is None:
                    raise ValueError('Faça uma nova consulta antes de dar feedback.')
                index = int(ask('Número da candidata: '))
                bindings = last[1]['result']['receipts']
                if not 1 <= index <= len(bindings):
                    raise ValueError('Número inválido.')
                command = dict(op='feedback', receipt=bindings[index - 1], actor_id=actor,
                               event_id='console-feedback:' + uuid4().hex,
                               stance='support' if choice == '3' else 'oppose')
            elif choice == '5':
                command = dict(op='withdraw', event_id=ask('ID do feedback a retirar: '),
                               request_id='console-withdrawal:' + uuid4().hex, actor_id=actor)
            elif choice == '6':
                command = dict(op='history')
            elif choice == '7':
                if last is None:
                    raise ValueError('Faça uma nova consulta antes de avaliar.')
                expected = json.loads(ask('Conteúdos esperados, lista JSON; [] se nenhum: '))
                entry = journal.append(assessment(*last, expected, actor))
                show(json.dumps(entry['assessment']['raw_score'], ensure_ascii=False))
                show(json.dumps(entry['assessment']['filtered_score'], ensure_ascii=False))
                show('Avaliação salva separadamente; nenhum feedback ou aprendizado foi aplicado.')
                continue
            elif choice == '8':
                show(json.dumps(journal.report(), ensure_ascii=False, indent=2))
                continue
            elif choice == '9':
                if last is None:
                    raise ValueError('Faça uma nova consulta para inspecionar evidências.')
                show(json.dumps(last[1], ensure_ascii=False, indent=2))
                continue
            else:
                raise ValueError('Opção inválida.')
            packet = lab.execute(dict(command, scope=scope))
            if command['op'] != 'history':
                last = None
            result = packet['result']
            if command['op'] == 'feedback':
                show(f'Feedback {result["status"]}: {result["event"]["event_id"]}')
            elif command['op'] == 'withdraw':
                show(f'Retirada {result["status"]}: {result["event"]["target_event_id"]}')
            elif command['op'] == 'observe':
                show(f'Observação {result["status"]}: {result["entry"]["source_id"]}')
            else:
                show(json.dumps(result, ensure_ascii=False, indent=2))
        except EOFError:
            return
        except (ValueError, TypeError, KeyError) as error:
            show('Operação recusada: ' + str(error))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--library', type=Path, required=True)
    parser.add_argument('--data-dir', type=Path, required=True)
    parser.add_argument('--actor', required=True)
    parser.add_argument('--scope', default='principal')
    parser.add_argument('--enable-feedback', action='store_true')
    args = parser.parse_args()
    text(args.actor, 'actor', 128)
    with open_lab(args.library, args.data_dir, enable_feedback=args.enable_feedback) as lab:
        run_console(lab, ReviewJournal(args.data_dir / 'operator-reviews.jsonl'), args.actor, args.scope)


if __name__ == '__main__':
    main()
