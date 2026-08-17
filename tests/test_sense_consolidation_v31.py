from memoria_resolutiva.polysemy import PolysemyMemory
from memoria_resolutiva.sense_consolidation import consolidate_senses, resolve_group

FINANCE = [
    "banco aprovou credito cliente",
    "banco concedeu emprestimo cliente",
    "cliente abriu conta banco",
    "banco cobrou juros financiamento",
    "banco recebeu deposito cliente",
]
DATA = [
    "banco armazenou dados sistema",
    "banco recebeu registros aplicacao",
    "consulta acessou banco dados",
    "servidor gravou informacao banco",
    "banco possui tabelas registros",
]


def build():
    m = PolysemyMemory(window=3, split_threshold=0.18)
    for sentence in FINANCE + DATA:
        m.observe(sentence)
    return m


def test_consolidation_is_non_destructive():
    m = build()
    before = [(s.sense_id, s.occurrences, dict(s.contexts)) for s in m.senses("banco")]
    consolidate_senses(m, "banco")
    after = [(s.sense_id, s.occurrences, dict(s.contexts)) for s in m.senses("banco")]
    assert before == after


def test_consolidation_does_not_increase_fragmentation():
    m = build()
    groups = consolidate_senses(m, "banco")
    assert 1 <= len(groups) <= len(m.senses("banco"))


def test_macro_resolution_can_preserve_domain_separation():
    m = build()
    groups = consolidate_senses(m, "banco")
    finance_id, finance_score = resolve_group(groups, {"credito", "cliente", "emprestimo", "conta", "juros"})
    data_id, data_score = resolve_group(groups, {"dados", "registros", "servidor", "tabelas", "consulta"})
    assert finance_id is not None and data_id is not None
    assert finance_score > 0 and data_score > 0
    # This is the key safety property: consolidation must not force known
    # finance/data contexts into one macro-sense.
    assert finance_id != data_id
