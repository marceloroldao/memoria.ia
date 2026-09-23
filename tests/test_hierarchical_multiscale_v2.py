from __future__ import annotations

from pathlib import Path

from memoria_resolutiva.hierarchical_composition_v2 import (
    HierarchicalCompositionEngineV2,
)
from memoria_resolutiva.multiscale_resolver_v2 import (
    MultiscaleStructuralResolverV2,
)
from memoria_resolutiva.persistent_structural_trajectory_v2 import (
    PersistentStructuralTrajectoryRuntimeV2,
)
from memoria_resolutiva.structural_density_v2 import StructuralDensityEngineV2
from memoria_resolutiva.structural_observation import StructuralObservationStore
from memoria_resolutiva.structural_trajectory_v2 import StructuralTrajectoryIndex


def _index(rows, *, hierarchy_id="h"):
    index = StructuralTrajectoryIndex()
    for sequence, addresses in enumerate(rows):
        index.ingest_addresses(
            addresses,
            hierarchy_id=hierarchy_id,
            source_id=f"source:{sequence}",
            sequence=sequence,
        )
    return index


def _event(sequence: int, trail: list[int]) -> dict:
    return {
        "version": 1,
        "source_id": f"sensor:{sequence}",
        "sequence": sequence,
        "byte_offset": sequence * 16,
        "byte_length": 16,
        "trail": trail,
        "relation_ids": [],
        "signature": f"{sequence + 1:016x}",
        "resolution": 2,
    }


def test_composition_requires_support_from_distinct_trajectories():
    index = _index([
        [1, 2, 3],
        [1, 2, 4],
    ])
    engine = HierarchicalCompositionEngineV2(
        index,
        max_depth=1,
        min_occurrences=2,
        min_trajectory_count=2,
        min_size=2,
        max_size=2,
    )

    levels = engine.build(hierarchy_id="h")

    assert len(levels) == 1
    pairs = {item.children: item for item in levels[0].compositions}
    assert (1, 2) in pairs
    assert pairs[(1, 2)].trajectory_count == 2
    assert pairs[(1, 2)].occurrences == 2


def test_repeat_inside_one_trajectory_cannot_manufacture_composition():
    index = _index([
        [1, 2, 1, 2],
        [8, 9, 10],
    ])
    engine = HierarchicalCompositionEngineV2(
        index,
        max_depth=1,
        min_occurrences=2,
        min_trajectory_count=2,
        min_size=2,
        max_size=2,
    )

    levels = engine.build(hierarchy_id="h")

    assert levels == ()


def test_hierarchy_isolation_prevents_cross_context_false_recurrence():
    index = StructuralTrajectoryIndex()
    index.ingest_addresses([1, 2, 3], hierarchy_id="left", source_id="l", sequence=0)
    index.ingest_addresses([1, 2, 4], hierarchy_id="right", source_id="r", sequence=0)
    engine = HierarchicalCompositionEngineV2(
        index,
        max_depth=1,
        min_occurrences=2,
        min_trajectory_count=2,
        min_size=2,
        max_size=2,
    )

    assert engine.build(hierarchy_id="left") == ()
    assert engine.build(hierarchy_id="right") == ()


def test_composition_is_derived_and_never_mutates_atomic_trajectories():
    index = _index([
        [1, 2, 3, 4],
        [1, 2, 3, 5],
    ])
    before = index.snapshot()
    engine = HierarchicalCompositionEngineV2(
        index,
        max_depth=2,
        min_size=2,
        max_size=3,
    )

    transformed = engine.transform_addresses((1, 2, 3, 4), hierarchy_id="h")

    assert transformed != (1, 2, 3, 4)
    assert index.snapshot() == before


def test_recursive_hierarchy_can_compose_a_composition_with_an_atomic_address():
    index = _index([
        [1, 2, 3, 4],
        [1, 2, 3, 4],
    ])
    engine = HierarchicalCompositionEngineV2(
        index,
        max_depth=3,
        min_occurrences=2,
        min_trajectory_count=2,
        min_size=2,
        max_size=3,
    )

    levels = engine.build(hierarchy_id="h")

    assert len(levels) >= 2
    assert any(
        any(isinstance(child, str) and child.startswith("hc3:") for child in item.children)
        for item in levels[1].compositions
    )
    metrics = engine.metrics(hierarchy_id="h")
    assert metrics["final_address_count"] < metrics["atomic_address_count"]


def test_multiscale_never_overrides_stronger_atomic_evidence():
    index = _index([
        [1, 2, 3, 9],
        [1, 2, 8],
        [1, 2, 7],
        [1, 2, 6],
    ])
    resolver = MultiscaleStructuralResolverV2(
        index,
        max_depth=2,
        min_occurrences=2,
        min_trajectory_count=2,
        min_size=2,
        max_size=2,
    )

    matches = resolver.resolve_addresses([1, 2, 3], hierarchy_id="h")

    assert matches
    assert matches[0].sequence == 0
    assert matches[0].atomic_evidence.overlap == 3
    assert all(
        matches[0].atomic_evidence.structural_key >= item.atomic_evidence.structural_key
        for item in matches[1:]
    )


def test_unrelated_query_stays_unresolved_even_with_recurrent_compositions():
    index = _index([
        [1, 2, 3],
        [1, 2, 4],
        [1, 2, 5],
    ])
    resolver = MultiscaleStructuralResolverV2(index)

    assert resolver.resolve_addresses([900, 901], hierarchy_id="h") == ()


def test_density_is_observable_but_does_not_enter_multiscale_ranking_key():
    index = _index([
        [1, 99, 2],
        [3, 99, 4],
        [5, 99, 6],
        [7, 99, 8],
    ])
    density = StructuralDensityEngineV2(index)
    profile = density.profile(99, hierarchy_id="h")

    assert profile is not None
    assert profile.trajectory_count == 4
    assert profile.connection_count == 8

    resolver = MultiscaleStructuralResolverV2(index, max_depth=1)
    matches = resolver.resolve_addresses([1, 99], hierarchy_id="h")
    assert matches
    assert matches[0].terminal_density is not None
    # Density is diagnostics in R3: ranking evidence remains purely structural.
    first_key_without_tiebreak = matches[0].multiscale_key[:-1]
    assert all(
        item.multiscale_key[:-1] <= first_key_without_tiebreak
        for item in matches[1:]
    )


def test_hierarchy_rebuild_is_deterministic_after_persistent_cold_reopen(tmp_path: Path):
    observations = StructuralObservationStore(
        tmp_path / "observations",
        backend="sqlite",
        allow_fallback=False,
    )
    for sequence, trail in enumerate(([1, 2, 3, 4], [1, 2, 3, 5])):
        observations.append(
            _event(sequence, list(trail)),
            provenance={"hierarchy_id": "h", "source_kind": "test"},
        )

    first = PersistentStructuralTrajectoryRuntimeV2(
        observations,
        tmp_path / "trajectory",
        backend="sqlite",
        allow_fallback=False,
    )
    first_levels = HierarchicalCompositionEngineV2(first.index).build(hierarchy_id="h")

    restarted = PersistentStructuralTrajectoryRuntimeV2(
        observations,
        tmp_path / "trajectory",
        backend="sqlite",
        allow_fallback=False,
    )
    restarted_levels = HierarchicalCompositionEngineV2(restarted.index).build(hierarchy_id="h")

    assert restarted.replayed_on_open == 0
    assert restarted_levels == first_levels
