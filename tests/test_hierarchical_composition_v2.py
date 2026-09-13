from memoria_resolutiva.address_trajectory_v2 import AddressTrajectoryMemory
from memoria_resolutiva.hierarchical_composition_v2 import HierarchicalCompositionEngine


def _memory() -> AddressTrajectoryMemory:
    memory = AddressTrajectoryMemory()
    memory.ingest("meu gato dorme aqui")
    memory.ingest("meu gato come aqui")
    memory.ingest("meu gato dorme perto")
    memory.ingest("meu carro dorme aqui")
    return memory


def test_hierarchy_builds_compositions_of_compositions() -> None:
    memory = _memory()
    engine = HierarchicalCompositionEngine(memory, max_depth=3, min_occurrences=2, min_trajectory_count=2)
    levels = engine.build()
    assert levels
    assert levels[0].depth == 1
    if len(levels) > 1:
        level1_addresses = {c.address for c in levels[0].compositions}
        assert any(any(child in level1_addresses for child in c.children) for c in levels[1].compositions)


def test_hierarchy_never_mutates_atomic_memory() -> None:
    memory = _memory()
    before = memory.snapshot()
    engine = HierarchicalCompositionEngine(memory, max_depth=3)
    engine.build()
    after = memory.snapshot()
    assert before == after


def test_hierarchy_is_deterministic_across_restart() -> None:
    memory = _memory()
    first = HierarchicalCompositionEngine(memory, max_depth=3).build()
    restored = AddressTrajectoryMemory.restore(memory.snapshot())
    second = HierarchicalCompositionEngine(restored, max_depth=3).build()
    assert first == second


def test_depth_limit_is_respected() -> None:
    memory = _memory()
    levels = HierarchicalCompositionEngine(memory, max_depth=2).build()
    assert len(levels) <= 2


def test_per_level_cap_prevents_combinatorial_explosion() -> None:
    memory = AddressTrajectoryMemory()
    for index in range(100):
        memory.ingest(f"a{index % 5} b{index % 7} c{index % 11} d{index % 13}")
    engine = HierarchicalCompositionEngine(
        memory,
        max_depth=4,
        min_occurrences=2,
        min_trajectory_count=2,
        max_compositions_per_level=16,
    )
    levels = engine.build()
    assert all(len(level.compositions) <= 16 for level in levels)


def test_single_occurrence_pattern_is_not_promoted() -> None:
    memory = AddressTrajectoryMemory()
    memory.ingest("alpha beta gamma")
    memory.ingest("delta epsilon zeta")
    engine = HierarchicalCompositionEngine(memory, max_depth=3, min_occurrences=2)
    assert engine.build() == ()


def test_transform_text_reduces_or_preserves_address_count() -> None:
    memory = _memory()
    engine = HierarchicalCompositionEngine(memory, max_depth=3)
    atomic = tuple(token.address for token in memory.decompose("meu gato dorme aqui"))
    transformed = engine.transform_text("meu gato dorme aqui")
    assert len(transformed) <= len(atomic)


def test_metrics_report_bounded_growth_and_compression() -> None:
    memory = _memory()
    metrics = HierarchicalCompositionEngine(memory, max_depth=3).metrics()
    assert metrics["levels"] <= 3
    assert metrics["final_address_count"] <= metrics["atomic_address_count"]
    assert metrics["compression_num"] >= 0
