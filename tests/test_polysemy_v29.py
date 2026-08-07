from memoria_resolutiva.polysemy import PolysemyMemory


def trained_memory():
    m = PolysemyMemory(window=3, split_threshold=0.18)
    finance = [
        "banco aprovou credito cliente",
        "banco concedeu emprestimo cliente",
        "cliente abriu conta banco",
        "banco cobrou juros financiamento",
        "banco recebeu deposito cliente",
    ]
    data = [
        "banco armazenou dados sistema",
        "banco recebeu registros aplicacao",
        "consulta acessou banco dados",
        "servidor gravou informacao banco",
        "banco possui tabelas registros",
    ]
    for sentence in finance + data:
        m.observe(sentence)
    return m


def test_polysemous_word_splits_into_multiple_senses():
    m = trained_memory()
    assert len(m.senses("banco")) >= 2


def test_finance_and_data_contexts_resolve_to_different_senses():
    m = trained_memory()
    finance_id, finance_score = m.resolve("banco", {"credito", "cliente", "emprestimo", "conta"})
    data_id, data_score = m.resolve("banco", {"dados", "registros", "servidor", "tabelas"})
    assert finance_id is not None and data_id is not None
    assert finance_id != data_id
    assert finance_score > 0
    assert data_score > 0


def test_new_sense_is_added_online_without_replaying_old_sentences():
    m = PolysemyMemory(window=2, split_threshold=0.15)
    for sentence in ["banco aprovou credito", "cliente abriu conta banco", "banco concedeu emprestimo"]:
        m.observe(sentence)
    before = len(m.senses("banco"))
    for sentence in ["banco armazena dados", "servidor consulta banco", "banco possui registros"]:
        m.observe(sentence)
    after = len(m.senses("banco"))
    assert after > before


def test_unknown_word_has_no_resolved_sense():
    m = trained_memory()
    assert m.resolve("inexistente", {"dados"}) == (None, 0.0)
