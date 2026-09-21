from __future__ import annotations

from memoria_resolutiva.structural_association_field import StructuralAssociationField


def observation(trail, *, hierarchy="h1", source="capture", sequence=0):
    return {
        "format": "memoria.ia-structural-observation-v1",
        "observation_id": f"obs:{hierarchy}:{source}:{sequence}:{trail}",
        "event": {
            "version": 1,
            "source_id": source,
            "sequence": sequence,
            "byte_offset": sequence * 16,
            "byte_length": 16,
            "trail": list(trail),
            "relation_ids": [item for item in trail if item >= 256],
            "signature": f"{sequence + 1:016x}",
            "resolution": 2,
        },
        "provenance": {"hierarchy_id": hierarchy},
        "semantic_projection": False,
    }


def test_within_event_order_is_directional_without_invented_reverse_edge():
    field = StructuralAssociationField(
        max_within_distance=4,
        max_event_lag=1,
        forgetting_rate=0,
    )
    field.observe(observation([10, 20, 30]))
    assert field.association("h1", 10, 20, channel="within") == 1.0
    assert field.association("h1", 10, 30, channel="within") == 0.5
    assert field.association("h1", 20, 10, channel="within") == 0.0


def test_temporal_direction_follows_observed_event_order():
    field = StructuralAssociationField(max_event_lag=1, forgetting_rate=0)
    field.observe(observation([1], sequence=0))
    field.observe(observation([2], sequence=1))
    assert field.association("h1", 1, 2, channel="temporal") == 1.0
    assert field.association("h1", 2, 1, channel="temporal") == 0.0


def test_repetition_accumulates_more_evidence_than_single_occurrence():
    field = StructuralAssociationField(max_event_lag=1, forgetting_rate=0)
    sequence = [[1], [2], [1], [2], [1], [2], [1], [3]]
    for index, trail in enumerate(sequence):
        field.observe(observation(trail, sequence=index))
    assert field.association(
        "h1",
        1,
        2,
        channel="temporal",
    ) > field.association("h1", 1, 3, channel="temporal")


def test_forgetting_reduces_weight_without_deleting_history():
    field = StructuralAssociationField(max_event_lag=1, forgetting_rate=0.2)
    field.observe(observation([1], sequence=0))
    field.observe(observation([2], sequence=1))
    initial = field.association("h1", 1, 2, channel="temporal")
    field.advance(10)
    faded = field.association("h1", 1, 2, channel="temporal")
    assert 0.0 < faded < initial
    row = field.strongest("h1", 1, channel="temporal")[0]
    assert row.observations == 1


def test_hierarchy_lineages_do_not_share_symbol_meaning():
    field = StructuralAssociationField(max_event_lag=1, forgetting_rate=0)
    field.observe(observation([7], hierarchy="h1", sequence=0))
    field.observe(observation([8], hierarchy="h1", sequence=1))
    assert field.association("h1", 7, 8, channel="temporal") == 1.0
    assert field.association("h2", 7, 8, channel="temporal") == 0.0


def test_replay_is_deterministic_and_snapshot_remains_non_semantic():
    stream = [
        observation([1, 2, 300], sequence=0),
        observation([2, 3, 301], sequence=1),
        observation([1, 2, 300], sequence=2),
    ]
    left = StructuralAssociationField(
        max_within_distance=3,
        max_event_lag=2,
        forgetting_rate=0.03,
    )
    right = StructuralAssociationField(
        max_within_distance=3,
        max_event_lag=2,
        forgetting_rate=0.03,
    )
    for row in stream:
        left.observe(row)
        right.observe(row)
    assert left.snapshot() == right.snapshot()
    snapshot = left.snapshot()
    assert snapshot["semantic_projection"] is False
    assert all(
        "predicate" not in edge
        and "subject" not in edge
        and "object" not in edge
        for edge in snapshot["edges"]
    )
