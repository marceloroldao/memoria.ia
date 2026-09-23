from __future__ import annotations

from pathlib import Path

from memoria_resolutiva.persistent_structural_trajectory_v2 import (
    PersistentStructuralTrajectoryRuntimeV2,
)
from memoria_resolutiva.structural_equivalence_v2 import (
    StructuralEquivalenceEngineV2,
)
from memoria_resolutiva.structural_observation import StructuralObservationStore
from memoria_resolutiva.structural_trajectory_v2 import StructuralTrajectoryIndex


def _index(rows, *, hierarchy_id="h"):
    index = StructuralTrajectoryIndex()
    for sequence, (source_id, addresses) in enumerate(rows):
        index.ingest_addresses(
            addresses,
            hierarchy_id=hierarchy_id,
            source_id=source_id,
            sequence=sequence,
        )
    return index


def _event(sequence: int, trail: list[int], source_id: str) -> dict:
    return {
        "version": 1,
        "source_id": source_id,
        "sequence": sequence,
        "byte_offset": sequence * 16,
        "byte_length": 16,
        "trail": trail,
        "relation_ids": [],
        "signature": f"{sequence + 1:016x}",
        "resolution": 2,
    }


def test_repeated_independent_convergence_supports_direct_equivalence():
    index = _index([
        ("L1", [1, 10, 11, 99]),
        ("L2", [2, 10, 11, 99]),
        ("L3", [1, 10, 11, 99]),
        ("L4", [2, 10, 11, 99]),
    ])
    engine = StructuralEquivalenceEngineV2(index)

    candidate = engine.evaluate([1], [2], hierarchy_id="h")

    assert candidate.state == "supported"
    assert candidate.independent_convergence >= 2
    assert candidate.independent_divergence == 0
    assert candidate.shared_terminal_addresses == (99,)


def test_same_lineage_replay_cannot_create_independent_support():
    index = _index([
        ("same", [1, 10, 11, 99]),
        ("same", [2, 10, 11, 99]),
        ("same", [1, 10, 11, 99]),
        ("same", [2, 10, 11, 99]),
    ])
    engine = StructuralEquivalenceEngineV2(index)

    candidate = engine.evaluate([1], [2], hierarchy_id="h")

    assert candidate.state == "insufficient"
    assert candidate.independent_convergence == 0


def test_single_independent_convergence_remains_candidate():
    index = _index([
        ("L1", [1, 10, 11, 99]),
        ("L2", [2, 10, 11, 99]),
    ])
    engine = StructuralEquivalenceEngineV2(index)

    candidate = engine.evaluate([1], [2], hierarchy_id="h")

    assert candidate.state == "candidate"
    assert candidate.independent_convergence == 1


def test_divergent_terminal_evidence_revokes_previous_support():
    index = _index([
        ("L1", [1, 10, 11, 99]),
        ("L2", [2, 10, 11, 99]),
        ("L3", [1, 10, 11, 99]),
        ("L4", [2, 10, 11, 99]),
        ("L5", [1, 10, 11, 70]),
        ("L6", [2, 10, 11, 80]),
        ("L7", [1, 10, 11, 70]),
        ("L8", [2, 10, 11, 80]),
    ])
    engine = StructuralEquivalenceEngineV2(index)

    candidate = engine.evaluate([1], [2], hierarchy_id="h")

    assert candidate.state == "contradicted"
    assert candidate.independent_divergence >= candidate.independent_convergence
    assert candidate.contradicting_witness_ids


def test_shared_terminal_without_required_bridge_never_creates_equivalence():
    index = _index([
        ("L1", [1, 10, 99]),
        ("L2", [2, 20, 99]),
        ("L3", [1, 30, 99]),
        ("L4", [2, 40, 99]),
    ])
    engine = StructuralEquivalenceEngineV2(index, min_bridge_addresses=2)

    candidate = engine.evaluate([1], [2], hierarchy_id="h")

    assert candidate.state == "insufficient"


def test_hyperdense_bridge_fails_closed():
    rows = [
        (f"L{i}", [i + 1, 10, 11, 99])
        for i in range(40)
    ]
    index = _index(rows)
    engine = StructuralEquivalenceEngineV2(
        index,
        max_bucket_signatures=16,
    )

    snapshot = engine.snapshot(hierarchy_id="h")

    assert snapshot.witnesses == ()
    assert snapshot.candidates == ()
    assert snapshot.skipped_hyperdense_bridges == ((10, 11),)


def test_reformulation_returns_supported_direct_neighbors_only_no_transitive_closure():
    index = _index([
        ("A1", [1, 10, 11, 99]),
        ("B1", [2, 10, 11, 99]),
        ("A2", [1, 10, 11, 99]),
        ("B2", [2, 10, 11, 99]),
        ("B3", [2, 20, 21, 88]),
        ("C1", [3, 20, 21, 88]),
        ("B4", [2, 20, 21, 88]),
        ("C2", [3, 20, 21, 88]),
    ])
    engine = StructuralEquivalenceEngineV2(index)

    reformulations = engine.reformulate_addresses([1], hierarchy_id="h")

    assert reformulations[0].direct is True
    assert reformulations[0].addresses == (1,)
    alternatives = {item.addresses for item in reformulations if not item.direct}
    assert (2,) in alternatives
    assert (3,) not in alternatives


def test_contradicted_equivalence_is_not_used_for_reformulation():
    index = _index([
        ("L1", [1, 10, 11, 99]),
        ("L2", [2, 10, 11, 99]),
        ("L3", [1, 10, 11, 99]),
        ("L4", [2, 10, 11, 99]),
        ("L5", [1, 10, 11, 70]),
        ("L6", [2, 10, 11, 80]),
        ("L7", [1, 10, 11, 70]),
        ("L8", [2, 10, 11, 80]),
    ])
    engine = StructuralEquivalenceEngineV2(index)

    reformulations = engine.reformulate_addresses([1], hierarchy_id="h")

    assert tuple(item.addresses for item in reformulations) == ((1,),)


def test_hierarchy_isolation_prevents_cross_world_equivalence():
    index = StructuralTrajectoryIndex()
    index.ingest_addresses([1, 10, 11, 99], hierarchy_id="left", source_id="L1", sequence=0)
    index.ingest_addresses([2, 10, 11, 99], hierarchy_id="right", source_id="L2", sequence=0)
    index.ingest_addresses([1, 10, 11, 99], hierarchy_id="left", source_id="L3", sequence=1)
    index.ingest_addresses([2, 10, 11, 99], hierarchy_id="right", source_id="L4", sequence=1)
    engine = StructuralEquivalenceEngineV2(index)

    assert engine.evaluate([1], [2], hierarchy_id="left").state == "insufficient"
    assert engine.evaluate([1], [2], hierarchy_id="right").state == "insufficient"


def test_equivalence_query_is_read_only():
    index = _index([
        ("L1", [1, 10, 11, 99]),
        ("L2", [2, 10, 11, 99]),
        ("L3", [1, 10, 11, 99]),
        ("L4", [2, 10, 11, 99]),
    ])
    engine = StructuralEquivalenceEngineV2(index)
    before = index.snapshot()

    assert engine.evaluate([1], [2], hierarchy_id="h").state == "supported"
    assert engine.reformulate_addresses([1], hierarchy_id="h")

    assert index.snapshot() == before


def test_discovery_is_deterministic_under_input_order():
    rows = [
        ("L1", [1, 10, 11, 99]),
        ("L2", [2, 10, 11, 99]),
        ("L3", [1, 10, 11, 99]),
        ("L4", [2, 10, 11, 99]),
    ]
    forward = StructuralEquivalenceEngineV2(_index(rows)).snapshot(hierarchy_id="h")
    reverse = StructuralEquivalenceEngineV2(_index(tuple(reversed(rows)))).snapshot(hierarchy_id="h")

    assert forward.signatures == reverse.signatures
    assert forward.candidates == reverse.candidates
    assert {
        (
            witness.left_signature_id,
            witness.right_signature_id,
            witness.bridge_addresses,
            witness.left_terminal_address,
            witness.right_terminal_address,
            witness.left_lineage_id,
            witness.right_lineage_id,
        )
        for witness in forward.witnesses
    } == {
        (
            witness.left_signature_id,
            witness.right_signature_id,
            witness.bridge_addresses,
            witness.left_terminal_address,
            witness.right_terminal_address,
            witness.left_lineage_id,
            witness.right_lineage_id,
        )
        for witness in reverse.witnesses
    }


def test_equivalence_rebuild_is_deterministic_after_cold_reopen(tmp_path: Path):
    observations = StructuralObservationStore(
        tmp_path / "observations",
        backend="sqlite",
        allow_fallback=False,
    )
    rows = (
        ("L1", [1, 10, 11, 99]),
        ("L2", [2, 10, 11, 99]),
        ("L3", [1, 10, 11, 99]),
        ("L4", [2, 10, 11, 99]),
    )
    for sequence, (source_id, trail) in enumerate(rows):
        observations.append(
            _event(sequence, trail, source_id),
            provenance={"hierarchy_id": "h", "source_kind": "test"},
        )

    first = PersistentStructuralTrajectoryRuntimeV2(
        observations,
        tmp_path / "trajectory",
        backend="sqlite",
        allow_fallback=False,
    )
    first_snapshot = StructuralEquivalenceEngineV2(first.index).snapshot(hierarchy_id="h")

    restarted = PersistentStructuralTrajectoryRuntimeV2(
        observations,
        tmp_path / "trajectory",
        backend="sqlite",
        allow_fallback=False,
    )
    restarted_snapshot = StructuralEquivalenceEngineV2(restarted.index).snapshot(hierarchy_id="h")

    assert restarted.replayed_on_open == 0
    assert restarted_snapshot == first_snapshot
