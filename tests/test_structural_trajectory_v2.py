from __future__ import annotations

from memoria_resolutiva.structural_observation import StructuralObservationStore
from memoria_resolutiva.structural_trajectory_v2 import StructuralTrajectoryIndex


def test_trajectory_ingest_is_opaque_and_collapses_only_immediate_loops():
    index = StructuralTrajectoryIndex()
    trajectory = index.ingest_addresses(
        [10, 10, 20, 10],
        hierarchy_id="h1",
        source_id="sensor:a",
        sequence=1,
    )
    assert trajectory.addresses == (10, 20, 10)
    assert index.count == 1


def test_trajectory_replay_is_idempotent():
    index = StructuralTrajectoryIndex()
    first = index.ingest_addresses(
        [1, 2, 3],
        hierarchy_id="h1",
        source_id="source",
        sequence=7,
        observation_id="obs:7",
    )
    second = index.ingest_addresses(
        [1, 2, 3],
        hierarchy_id="h1",
        source_id="source",
        sequence=7,
        observation_id="obs:7",
    )
    assert first == second
    assert index.count == 1


def test_resolve_is_read_only_and_preserves_hierarchy_isolation():
    index = StructuralTrajectoryIndex()
    index.ingest_addresses([1, 2, 3], hierarchy_id="h1", source_id="a", sequence=0)
    index.ingest_addresses([1, 2, 9], hierarchy_id="h2", source_id="b", sequence=0)
    before = index.snapshot()

    matches = index.resolve_addresses([1, 2], hierarchy_id="h1")

    assert len(matches) == 1
    assert matches[0].source_id == "a"
    assert matches[0].adjacency_overlap == 1
    assert index.snapshot() == before


def test_frontier_preserves_competing_continuations_instead_of_last_write_wins():
    index = StructuralTrajectoryIndex()
    index.ingest_addresses([1, 2, 3], hierarchy_id="h", source_id="old", sequence=0)
    index.ingest_addresses([1, 2, 4], hierarchy_id="h", source_id="new", sequence=1)
    index.ingest_addresses([1, 2, 4], hierarchy_id="h", source_id="newer", sequence=2)

    result = index.frontier([1, 2], hierarchy_id="h")

    assert result.ambiguous is True
    assert result.resolved is False
    assert result.resolved_address is None
    assert [item.address for item in result.candidates] == [3, 4]
    assert [item.occurrence_count for item in result.candidates] == [1, 2]


def test_reverse_frontier_traverses_the_same_occurrence_backward():
    index = StructuralTrajectoryIndex()
    index.ingest_addresses([7, 8, 9], hierarchy_id="h", source_id="x", sequence=0)

    result = index.frontier([9], hierarchy_id="h", direction="reverse")

    assert result.resolved is True
    assert result.resolved_address == 8


def test_frontier_never_stitches_across_occurrences_through_shared_hub():
    index = StructuralTrajectoryIndex()
    index.ingest_addresses([1, 2], hierarchy_id="h", source_id="a", sequence=0)
    index.ingest_addresses([2, 3], hierarchy_id="h", source_id="b", sequence=1)

    result = index.frontier([1, 2], hierarchy_id="h")

    assert result.resolved is False
    assert result.ambiguous is False
    assert result.candidates == ()


def test_sync_imports_current_v2_structural_observations_without_semantic_projection(tmp_path):
    store = StructuralObservationStore(tmp_path / "observations", backend="sqlite", allow_fallback=False)
    event = {
        "version": 1,
        "source_id": "bit-analyze:capture",
        "sequence": 4,
        "byte_offset": 32,
        "byte_length": 16,
        "trail": [100, 100, 200, 300],
        "relation_ids": [],
        "signature": "0011223344556677",
        "resolution": 2,
    }
    envelope, duplicate = store.append(
        event,
        provenance={"hierarchy_id": "reality:1", "source_kind": "structural"},
    )
    assert duplicate is False
    assert envelope["semantic_projection"] is False

    index = StructuralTrajectoryIndex()
    assert index.sync_observations(store) == 1
    assert index.sync_observations(store) == 0

    trajectory = index.snapshot()[0]
    assert trajectory.hierarchy_id == "reality:1"
    assert trajectory.source_id == "bit-analyze:capture"
    assert trajectory.sequence == 4
    assert trajectory.addresses == (100, 200, 300)
    assert trajectory.observation_id == envelope["observation_id"]
