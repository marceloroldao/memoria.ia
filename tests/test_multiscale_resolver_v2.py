from memoria_resolutiva.address_trajectory_v2 import AddressTrajectoryMemory
from memoria_resolutiva.multiscale_resolver_v2 import MultiscaleAddressResolver


def _memory() -> AddressTrajectoryMemory:
    memory = AddressTrajectoryMemory()
    memory.ingest("meu gato dorme aqui")
    memory.ingest("meu gato come aqui")
    memory.ingest("meu gato e Lotus")
    memory.ingest("meu carro dorme fora")
    memory.ingest("meu carro e Jeep")
    return memory


def test_multiscale_resolver_keeps_atomic_and_hierarchical_views() -> None:
    memory = _memory()
    resolver = MultiscaleAddressResolver(memory, max_depth=3)
    views = resolver._views("qual meu gato")
    assert views
    assert views[0][0] == 0
    assert all(depth >= 0 for depth, _ in views)


def test_multiscale_query_remains_read_only() -> None:
    memory = _memory()
    resolver = MultiscaleAddressResolver(memory, max_depth=3)
    before = memory.snapshot()
    resolver.resolve("qual meu gato", limit=5)
    after = memory.snapshot()
    assert before == after


def test_multiscale_resolution_is_deterministic_after_restart() -> None:
    memory = _memory()
    resolver = MultiscaleAddressResolver(memory, max_depth=3)
    before = resolver.resolve("qual meu gato", limit=5)
    restored = AddressTrajectoryMemory.restore(memory.snapshot())
    after = MultiscaleAddressResolver(restored, max_depth=3).resolve("qual meu gato", limit=5)
    assert before == after


def test_recurrent_region_can_support_same_trajectory_at_multiple_depths() -> None:
    memory = _memory()
    resolver = MultiscaleAddressResolver(memory, max_depth=3)
    matches = resolver.resolve("qual meu gato", limit=5)
    assert matches
    assert any(len(match.supporting_depths) >= 2 for match in matches)


def test_unrelated_trajectory_does_not_gain_fake_multiscale_support() -> None:
    memory = _memory()
    resolver = MultiscaleAddressResolver(memory, max_depth=3)
    matches = resolver.resolve("qual meu gato", limit=10)
    by_text = {match.raw_text: match for match in matches}
    assert "meu carro dorme fora" in by_text
    assert len(by_text["meu gato dorme aqui"].supporting_depths) >= len(
        by_text["meu carro dorme fora"].supporting_depths
    )


def test_hierarchy_does_not_need_semantic_domain_rules() -> None:
    memory = AddressTrajectoryMemory()
    memory.ingest_address_stream(("x:A", "x:B", "x:C"), provenance="p1")
    memory.ingest_address_stream(("x:A", "x:B", "x:D"), provenance="p2")
    memory.ingest_address_stream(("x:A", "x:B", "x:E"), provenance="p3")
    resolver = MultiscaleAddressResolver(memory, max_depth=3)
    levels = resolver.hierarchy.build()
    assert levels
    assert any(composition.children[:2] == ("x:A", "x:B") for composition in levels[0].compositions)
