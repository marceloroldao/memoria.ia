#!/usr/bin/env python3
"""Measure transfer of taught question forms with the existing attribute reader."""
import argparse
import json
from pathlib import Path
import tempfile

from trajectory_attribute_frame_probe import (
    AttributeFrameReader, NativeProbe, observe, region_rows, score,
)

DOMAINS = {
    'names': {
        'canonical': 'Qual nome do meu {}?',
        'alternative': 'Você lembra o nome do meu {}?',
        'unseen': 'Como se chama meu {}?',
        'training': (
            ('barco', 'Meu barco se chama Coral.', 'Meu barco fica no cais.'),
            ('drone', 'Meu drone se chama Íris.', 'Meu drone fica no hangar.'),
            ('robô', 'Meu robô se chama Bento.', 'Meu robô fica na oficina.'),
        ),
        'facts': (
            'Meu rádio se chama Faísca.', 'Meu rádio fica na bancada.',
            'Meu veleiro se chama Aurora.', 'Meu veleiro se chama Vento.',
            'Meu monitor fica no escritório.',
        ),
        'cases': (
            ('new_entity', 'alternative', 'rádio', ('Meu rádio se chama Faísca.',)),
            ('conflict', 'alternative', 'veleiro', ('Meu veleiro se chama Aurora.', 'Meu veleiro se chama Vento.')),
            ('absent_attribute', 'alternative', 'monitor', ()),
            ('absent_entity', 'alternative', 'projetor', ()),
            ('unseen_form', 'unseen', 'rádio', ('Meu rádio se chama Faísca.',)),
            ('canonical', 'canonical', 'rádio', ('Meu rádio se chama Faísca.',)),
        ),
    },
    'volts': {
        'canonical': 'Quantos volts fornece o {}?',
        'alternative': 'Qual é a tensão em volts do {}?',
        'unseen': 'Que tensão o {} fornece?',
        'training': (
            ('carregador', 'O carregador fornece 5 volts.', 'O carregador fornece 2 amperes.'),
            ('regulador', 'O regulador fornece 12 volts.', 'O regulador fornece 3 amperes.'),
            ('conversor', 'O conversor fornece 30 volts.', 'O conversor fornece 4 amperes.'),
        ),
        'facts': (
            'O adaptador fornece 24 volts.', 'O adaptador fornece 8 amperes.',
            'O inversor fornece 48 volts.', 'O inversor fornece 36 volts.',
            'O módulo fornece 6 amperes.',
        ),
        'cases': (
            ('new_entity', 'alternative', 'adaptador', ('O adaptador fornece 24 volts.',)),
            ('conflict', 'alternative', 'inversor', ('O inversor fornece 48 volts.', 'O inversor fornece 36 volts.')),
            ('absent_attribute', 'alternative', 'módulo', ()),
            ('absent_entity', 'alternative', 'medidor', ()),
            ('unseen_form', 'unseen', 'adaptador', ('O adaptador fornece 24 volts.',)),
            ('canonical', 'canonical', 'adaptador', ('O adaptador fornece 24 volts.',)),
        ),
    },
}

ARMS = ('no_alternative', 'aligned', 'shuffled', 'wrong_attribute', 'mixed_one', 'mixed_all', 'wrong_both')


def fixture(domain, arm):
    region = 'conversation:paraphrase:' + domain
    data = DOMAINS[domain]
    rows = []

    def add(text, kind='user_turn'):
        index = len(rows) + 1
        rows.append(dict(hierarchy_id=region, source_id=f'row-{index}',
                         sequence=index, text=text, source_kind=kind))

    for form in ('canonical', 'alternative'):
        if form == 'alternative' and arm == 'no_alternative':
            continue
        for index, (entity, correct, distractor) in enumerate(data['training']):
            add(data[form].format(entity))
            if arm == 'wrong_both':
                correct = distractor
            elif form == 'alternative':
                if arm == 'shuffled':
                    correct = data['training'][(index + 1) % 3][1]
                if arm == 'wrong_attribute':
                    correct = distractor
            add(correct)
            add('pausa', 'assistant_generated')
            if form == 'alternative' and (arm == 'mixed_all' or (arm == 'mixed_one' and index == 0)):
                add(data[form].format(entity))
                add(distractor)
                add('pausa', 'assistant_generated')
    for fact in data['facts']:
        add(fact)
    return region, rows


def correction_fixture(domain):
    """Replay wrong teaching, then append aligned examples at new addresses."""
    region, initial = fixture(domain, 'wrong_both')
    _, aligned = fixture(domain, 'aligned')
    teaching_count = 2 * len(DOMAINS[domain]['training']) * 3
    additions = [initial[2], *aligned[:teaching_count]]
    appended = [dict(row, source_id=f'row-{index}', sequence=index)
                for index, row in enumerate(additions, start=len(initial) + 1)]
    excluded = [(region, row['source_id'], row['sequence'])
                for row in initial[1:teaching_count:3]]
    return region, initial, appended, excluded


def evaluate(library, *, require_agreement=False, compare_forms=False):
    results = {}
    for arm in ARMS:
        results[arm] = []
        for domain, data in DOMAINS.items():
            region, rows = fixture(domain, arm)
            with tempfile.TemporaryDirectory(prefix='memoria-paraphrase-') as directory:
                native = NativeProbe(library, Path(directory))
                try:
                    for row in rows:
                        observe(native, row)

                    def snapshot():
                        return [dict(row, hierarchy_id=region) for row in region_rows(native, region)]

                    stored = snapshot()
                    if [{key: record[key] for key in rows[0]} for record in stored] != rows:
                        raise RuntimeError('native history differs from fixture')

                    def read(records):
                        reader = AttributeFrameReader(records, region)
                        return [reader.read(data[form].format(entity), require_agreement=require_agreement,
                                            comparison_query=data['canonical'].format(entity)
                                            if compare_forms and form == 'alternative' else None)
                                for _, form, entity, _ in data['cases']]

                    views = read(stored)
                    if snapshot() != stored:
                        raise RuntimeError('queries changed native history')
                    native.reopen()
                    cold = snapshot()
                    if cold != stored or read(cold) != views:
                        raise RuntimeError('cold reopen differs from warm state')
                    by_address = {(region, row['source_id'], row['sequence']): row for row in stored}
                    for (category, _, entity, expected), view in zip(data['cases'], views):
                        if view['query'] in {row['text'] for row in rows}:
                            raise RuntimeError('test query appeared in teaching history')
                        if view['answer'] is not None or view['qualified'] or view['query_recorded']:
                            raise RuntimeError('unexpected qualification or write')
                        for candidate in view['candidates']:
                            for origin in candidate['origins']:
                                record = by_address[tuple(origin)]
                                if record['source_kind'] != 'user_turn' or record['text'] != candidate['text']:
                                    raise RuntimeError('candidate does not preserve raw origin')
                        results[arm].append(dict(domain=domain, category=category, entity=entity,
                            expected=expected, **score(dict(expected=expected), view['candidates']), view=view))
                finally:
                    native.close()
    return results


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--library', type=Path, required=True)
    parser.add_argument('--require-agreement', action='store_true')
    parser.add_argument('--compare-forms', action='store_true')
    args = parser.parse_args()
    print(json.dumps(evaluate(args.library, require_agreement=args.require_agreement,
                              compare_forms=args.compare_forms), ensure_ascii=False, indent=2))
