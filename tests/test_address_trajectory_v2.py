from memoria_resolutiva.address_trajectory_v2 import AddressTrajectoryMemory


def _seed() -> AddressTrajectoryMemory:
    memory = AddressTrajectoryMemory()
    memory.ingest("meu gato e da cor verde")
    memory.ingest("irmao de meu gato e Lotus")
    memory.ingest("meu carro e da cor azul")
    memory.ingest("irmao de meu amigo e Vibe")
    return memory


def test_ingestion_and_query_share_the_same_decomposition() -> None:
    memory = AddressTrajectoryMemory()
    stored = memory.ingest("irmao de meu gato e Lotus")
    queried = memory.decompose("irmao de meu gato e Lotus")
    assert stored.addresses == tuple(token.address for token in queried)


def test_minimal_corpus_resolves_by_structural_fit_without_semantic_rules() -> None:
    memory = _seed()
    cases = (
        ("qual e irmao do meu gato", "lotus"),
        ("qual a cor do meu gato", "verde"),
        ("qual e irmao do meu amigo", "vibe"),
        ("qual a cor do meu carro", "azul"),
    )
    for query, expected_terminal in cases:
        matches = memory.resolve(query)
        assert matches
        assert matches[0].terminal_surface == expected_terminal


def test_repeated_query_is_read_only() -> None:
    memory = _seed()
    before = memory.snapshot()
    first = memory.resolve("qual e irmao do meu gato")
    second = memory.resolve("qual e irmao do meu gato")
    after = memory.snapshot()
    assert first == second
    assert before == after


def test_cold_restart_preserves_resolution() -> None:
    memory = _seed()
    query = "qual e irmao do meu gato"
    before = memory.resolve(query)
    restored = AddressTrajectoryMemory.restore(memory.snapshot())
    after = restored.resolve(query)
    assert before == after


def test_ambiguity_is_visible_instead_of_hidden_by_a_rule() -> None:
    memory = AddressTrajectoryMemory()
    memory.ingest("meu gato e verde")
    memory.ingest("meu gato e Lotus")
    matches = memory.resolve("qual meu gato", limit=2)
    assert len(matches) == 2
    assert matches[0].overlap == matches[1].overlap
    assert matches[0].ordered_overlap == matches[1].ordered_overlap


def test_growth_does_not_require_weights_or_domain_vocabulary() -> None:
    memory = _seed()
    # Synthetic trajectories add vocabulary and distractors without changing the
    # algorithm or teaching it meanings. The original structural match must remain
    # discoverable.
    for index in range(100):
        memory.ingest(f"objeto{index} possui aspecto{index} valor{index}")
    matches = memory.resolve("qual e irmao do meu gato", limit=3)
    assert matches
    assert matches[0].terminal_surface == "lotus"
