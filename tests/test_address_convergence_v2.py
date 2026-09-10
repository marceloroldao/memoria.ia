from memoria_resolutiva.address_convergence_v2 import AddressConvergenceResolver
from memoria_resolutiva.address_trajectory_v2 import AddressTrajectoryMemory


def _seed() -> AddressTrajectoryMemory:
    memory = AddressTrajectoryMemory()
    memory.ingest("meu gato e da cor verde")
    memory.ingest("irmao de meu gato e Lotus")
    memory.ingest("meu carro e da cor azul")
    memory.ingest("irmao de meu amigo e Vibe")
    return memory


def test_occurrence_trajectory_convergence_finds_expected_terminals() -> None:
    memory = _seed()
    resolver = AddressConvergenceResolver(memory)
    cases = (
        ("qual e irmao do meu gato", "lotus"),
        ("qual a cor do meu gato", "verde"),
        ("qual e irmao do meu amigo", "vibe"),
        ("qual a cor do meu carro", "azul"),
    )
    for query, expected in cases:
        matches = resolver.resolve(query, limit=3)
        assert matches
        assert matches[0].terminal_surface == expected


def test_query_is_read_only_and_repeatable() -> None:
    memory = _seed()
    resolver = AddressConvergenceResolver(memory)
    before = memory.snapshot()
    first = resolver.resolve("qual e irmao do meu gato")
    second = resolver.resolve("qual e irmao do meu gato")
    assert first == second
    assert memory.snapshot() == before


def test_cold_restart_preserves_convergence_ranking() -> None:
    memory = _seed()
    query = "qual a cor do meu carro"
    before = AddressConvergenceResolver(memory).resolve(query)
    restored = AddressTrajectoryMemory.restore(memory.snapshot())
    after = AddressConvergenceResolver(restored).resolve(query)
    assert before == after


def test_common_address_does_not_allow_cross_trajectory_jump() -> None:
    memory = AddressTrajectoryMemory()
    memory.ingest("alfa ponte comum destinoA")
    memory.ingest("beta ponte comum destinoB")
    resolver = AddressConvergenceResolver(memory)

    matches = resolver.resolve("alfa ponte comum", limit=2)
    assert matches[0].terminal_surface == "destinoa"
    assert matches[0].matched_addresses > matches[1].matched_addresses


def test_ambiguity_remains_visible_when_geometry_is_identical() -> None:
    memory = AddressTrajectoryMemory()
    memory.ingest("meu gato e Lotus")
    memory.ingest("meu gato e Vibe")
    resolver = AddressConvergenceResolver(memory)
    matches = resolver.resolve("qual meu gato", limit=2)
    assert len(matches) == 2
    assert matches[0].matched_addresses == matches[1].matched_addresses
    assert matches[0].ordered_matches == matches[1].ordered_matches
    assert matches[0].max_hops_to_terminal == matches[1].max_hops_to_terminal


def test_growth_with_unrelated_trajectories_preserves_result() -> None:
    memory = _seed()
    for index in range(100):
        memory.ingest(f"objeto{index} possui aspecto{index} valor{index}")
    resolver = AddressConvergenceResolver(memory)
    matches = resolver.resolve("qual e irmao do meu gato", limit=3)
    assert matches[0].terminal_surface == "lotus"
