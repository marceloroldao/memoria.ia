from memoria_resolutiva.address_trajectory_v2 import AddressTrajectoryMemory
from memoria_resolutiva.trajectory_frontier_v2 import TrajectoryFrontierResolver


def _memory() -> AddressTrajectoryMemory:
    memory = AddressTrajectoryMemory()
    memory.ingest("meu gato e da cor verde")
    memory.ingest("irmao de meu gato e Lotus")
    memory.ingest("meu carro e da cor azul")
    memory.ingest("irmao de meu amigo e Vibe")
    return memory


def test_frontier_finds_unseen_continuation_without_semantic_rules() -> None:
    memory = _memory()
    resolver = TrajectoryFrontierResolver(memory)
    matches = resolver.resolve("qual e irmao do meu gato")
    assert matches
    assert matches[0].surface == "lotus"


def test_frontier_distinguishes_parallel_address_geometries() -> None:
    memory = _memory()
    resolver = TrajectoryFrontierResolver(memory)
    assert resolver.resolve("qual e irmao do meu amigo")[0].surface == "vibe"
    assert resolver.resolve("qual a cor do meu carro")[0].surface == "azul"


def test_query_is_read_only_and_repeatable() -> None:
    memory = _memory()
    resolver = TrajectoryFrontierResolver(memory)
    before = memory.snapshot()
    first = resolver.resolve("qual e irmao do meu gato")
    second = resolver.resolve("qual e irmao do meu gato")
    assert first == second
    assert memory.snapshot() == before


def test_cold_restart_preserves_frontier() -> None:
    memory = _memory()
    query = "qual e irmao do meu gato"
    before = TrajectoryFrontierResolver(memory).resolve(query)
    restored = AddressTrajectoryMemory.restore(memory.snapshot())
    after = TrajectoryFrontierResolver(restored).resolve(query)
    assert before == after


def test_frontier_does_not_require_terminal_answer() -> None:
    memory = AddressTrajectoryMemory()
    memory.ingest("alpha beta resposta gamma delta")
    resolver = TrajectoryFrontierResolver(memory, max_depth=1)
    result = resolver.resolve("alpha beta")
    assert result
    assert result[0].surface == "resposta"
    assert result[0].distance == 1


def test_frontier_is_modality_agnostic() -> None:
    memory = AddressTrajectoryMemory()
    memory.ingest_address_stream(
        ("audio:A", "audio:B", "audio:C", "audio:D"),
        surfaces=("A", "B", "C", "D"),
        provenance="synthetic-audio",
    )
    resolver = TrajectoryFrontierResolver(memory, max_depth=1)
    # Query through the text adapter cannot recreate external addresses, so exercise
    # the generic frontier primitive directly. This verifies the cognitive operation
    # itself is independent of modality.
    trajectory = memory.snapshot()[0]
    candidate = resolver._frontier(
        trajectory,
        ("audio:A", "audio:B"),
        (0,),
    )
    assert candidate is not None
    assert candidate.address == "audio:C"
    assert candidate.surface == "C"
