from memoria_resolutiva.polysemy import PolysemyMemory
from memoria_resolutiva.temporal_sense_consolidation_v85 import (
    _support_weight,
    consolidate_temporal_senses,
)


def test_support_weight_is_bounded():
    class Dummy:
        occurrences = 1000
    assert 0.0 <= _support_weight(Dummy(), 1.25) <= 1.0


def test_temporal_consolidation_is_non_destructive():
    m = PolysemyMemory(window=3, split_threshold=0.18)
    rows = [
        "banco aprovou credito para cliente",
        "cliente abriu conta no banco",
        "banco de dados recebeu nova tabela",
        "consulta acessou indice do banco de dados",
    ] * 6
    for row in rows:
        m.observe(row)
    before = len(m.senses("banco"))
    groups = consolidate_temporal_senses(m, "banco", threshold=0.24, saturation=1.25)
    after = len(m.senses("banco"))
    assert before == after
    assert 1 <= len(groups) <= before


def test_repeated_evidence_gets_at_least_as_much_support_as_single_evidence():
    class A:
        occurrences = 1
    class B:
        occurrences = 10
    assert _support_weight(B(), 1.25) >= _support_weight(A(), 1.25)
