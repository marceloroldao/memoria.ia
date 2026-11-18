#!/usr/bin/env python3
"""Evaluate spelling variation on a fixed set of new synthetic questions."""

import json

from trajectory_attribute_frame_probe import AttributeFrameReader, fixture, score


# References are used only for scoring, after the reader has returned candidates.
QUESTIONS = (
    ('pets', 'case', 'QUAL NOME DO MEU CACHORRO?', ('Meu cachorro se chama Bolt.',)),
    ('pets', 'case', 'onde MEU GATO dorme?', ('Meu gato dorme no sofá.',)),
    ('cars', 'case', 'QUAL A COR DA MINHA KOMBI?', ('Minha Kombi é preta.',)),
    ('cars', 'case', 'qual a cor do meu CORSA?', ('Meu Corsa é prata.', 'Meu Corsa é branco.')),
    ('home', 'case', 'Qual a COR da minha PORTA?', ('Minha porta é branca.',)),
    ('agenda', 'case', 'EM QUE DIA ESTÁ MARCADA MINHA VIAGEM?', ('Minha viagem está marcada para sexta-feira.',)),
    ('devices', 'case', 'quantos GRAUS indica o SENSOR?', ('O sensor indica 23 graus.',)),
    ('devices', 'case', 'QUANTOS VOLTS FORNECE A FONTE?', ('A fonte fornece 12 volts.',)),
    ('pets', 'paraphrase', 'Você lembra o nome do meu cachorro?', ('Meu cachorro se chama Bolt.',)),
    ('pets', 'paraphrase', 'Em que lugar meu gato costuma dormir?', ('Meu gato dorme no sofá.',)),
    ('cars', 'paraphrase', 'De qual cor é minha Kombi?', ('Minha Kombi é preta.',)),
    ('home', 'paraphrase', 'Minha porta tem qual cor?', ('Minha porta é branca.',)),
    ('agenda', 'paraphrase', 'Em qual dia vai acontecer minha viagem?', ('Minha viagem está marcada para sexta-feira.',)),
    ('devices', 'paraphrase', 'Qual é a tensão em volts da fonte?', ('A fonte fornece 12 volts.',)),
    ('devices', 'surface_edit', 'Quantos volt fornece a fonte?', ('A fonte fornece 12 volts.',)),
    ('pets', 'surface_edit', 'Qual o nome do meu cachorro?', ('Meu cachorro se chama Bolt.',)),
    ('pets', 'absent', 'QUAL NOME DO MEU HAMSTER?', ()),
    ('pets', 'absent', 'ONDE MEU CACHORRO DORME?', ()),
    ('pets', 'absent', 'QUAL A IDADE DO MEU GATO?', ()),
    ('devices', 'absent', 'QUANTOS VOLTS FORNECE A BATERIA?', ()),
    ('devices', 'absent', 'QUANTOS AMPERES FORNECE A FONTE?', ()),
    ('agenda', 'absent', 'A QUE HORAS MINHA VIAGEM COMEÇA?', ()),
    ('home', 'absent', 'QUAL A COR DA MINHA JANELA?', ()),
    ('cars', 'absent', 'QUAL A POTÊNCIA DO MEU CORSA?', ()),
)


def evaluate():
    rows, earlier = fixture()
    readers = {scope: AttributeFrameReader(rows, 'conversation:attribute:' + scope)
               for scope in {question[0] for question in QUESTIONS}}
    earlier_queries = {(entry['scope'], entry['query']) for entry in earlier}
    observed = {(row['hierarchy_id'], row['text']) for row in rows}
    results = []
    for scope, category, question, expected in QUESTIONS:
        reader = readers[scope]
        if (scope, question) in earlier_queries or (reader.region, question) in observed:
            raise RuntimeError('evaluation question already used')
        result = dict(scope=scope, category=category, query=question, expected=expected)
        for mode, casefold in (('exact', False), ('unicode_casefold', True)):
            view = reader.read(question, casefold=casefold)
            result[mode] = score(result, view['candidates']) | dict(
                candidates=[dict(text=c['text'], origins=c['origins']) for c in view['candidates']],
                reason=view['reason'])
        results.append(result)
    return results


if __name__ == '__main__':
    print(json.dumps(evaluate(), ensure_ascii=False, indent=2))
