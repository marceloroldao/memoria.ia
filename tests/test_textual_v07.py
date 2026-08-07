from memoria_resolutiva.textual import TextContextMemory, tokenize


def test_tokenize_is_deterministic():
    assert tokenize("Fibra óptica, TESTE!") == ["fibra", "óptica", "teste"]


def test_natural_language_hidden_pair_ranks_first():
    memory = TextContextMemory(radius=3)
    for sentence in [
        "o carro percorreu a estrada durante a viagem",
        "o motorista estacionou o carro perto da garagem",
        "o automovel percorreu a estrada durante a viagem",
        "o motorista estacionou o automovel perto da garagem",
        "a estrela emite luz observada pelo telescopio",
        "o astro possui temperatura elevada e grande massa",
    ]:
        memory.observe_sentence(sentence)

    candidates = ["automovel", "estrela", "astro"]
    ranked = sorted(
        ((c, memory.associator.similarity("carro", c)) for c in candidates),
        key=lambda item: item[1],
        reverse=True,
    )
    assert ranked[0][0] == "automovel"


def test_ambiguity_probe_reports_multiple_alternatives():
    memory = TextContextMemory(radius=3)
    for sentence in [
        "o banco aprovou credito para a empresa",
        "o banco recebeu deposito durante a manha",
        "o banco de dados manteve registros persistentes",
        "o banco de dados recuperou informacoes antigas",
    ]:
        memory.observe_sentence(sentence)

    probe = memory.ambiguity_probe("banco", top_k=5)
    assert len(probe.alternatives) >= 2
    assert 0.0 <= probe.normalized_entropy <= 1.0
