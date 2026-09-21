from __future__ import annotations

from math import exp

from memoria_resolutiva.structural_association_continuous import (
    ContinuousStructuralAssociationField,
)


def observation(sequence, trail, *, hierarchy="h1"):
    return {
        "format": "memoria.ia-structural-observation-v1",
        "observation_id": f"obs:{hierarchy}:{sequence}:{trail}",
        "event": {
            "version": 1,
            "source_id": "continuous-test",
            "sequence": sequence,
            "byte_offset": sequence * 16,
            "byte_length": 16,
            "trail": list(trail),
            "relation_ids": [value for value in trail if value >= 256],
            "signature": f"{sequence + 1:016x}",
            "resolution": 2,
        },
        "provenance": {"hierarchy_id": hierarchy},
        "semantic_projection": False,
    }


def _lag_weight(lag):
    field = ContinuousStructuralAssociationField(
        temporal_decay=0.2,
        within_decay=0.2,
        forgetting_rate=0,
        trace_floor=1e-8,
    )
    field.observe(observation(0, [1]))
    for index in range(1, lag):
        field.observe(observation(index, [1000 + index]))
    field.observe(observation(lag, [2]))
    return field.association("h1", 1, 2, channel="temporal")


def test_temporal_influence_has_no_old_four_event_boundary():
    lag_four = _lag_weight(4)
    lag_five = _lag_weight(5)
    lag_ten = _lag_weight(10)

    assert lag_four > lag_five > lag_ten > 0.0
    assert abs((lag_five / lag_four) - exp(-0.2)) < 1e-12


def test_within_event_influence_continues_beyond_old_eight_position_boundary():
    field = ContinuousStructuralAssociationField(
        within_decay=0.2,
        temporal_decay=0.2,
        forgetting_rate=0,
        trace_floor=1e-8,
    )
    trail = [1] + list(range(100, 109)) + [2]
    field.observe(observation(0, trail))

    distant = field.association("h1", 1, 2, channel="within")
    adjacent = field.association("h1", 1, 100, channel="within")
    assert adjacent > distant > 0.0
    assert abs(distant - exp(-0.2 * 9.0)) < 1e-12


def test_repetition_accumulates_continuous_temporal_support():
    field = ContinuousStructuralAssociationField(
        temporal_decay=0.5,
        within_decay=0.5,
        forgetting_rate=0,
        trace_floor=1e-8,
    )
    for sequence, trail in enumerate(([1], [2], [1], [2], [1], [2], [1], [3])):
        field.observe(observation(sequence, trail))

    assert field.association("h1", 1, 2, channel="temporal") > field.association(
        "h1", 1, 3, channel="temporal"
    )


def test_direction_and_hierarchy_are_preserved():
    field = ContinuousStructuralAssociationField(
        temporal_decay=0.5,
        within_decay=0.5,
        forgetting_rate=0,
        trace_floor=1e-8,
    )
    field.observe(observation(0, [7], hierarchy="h1"))
    field.observe(observation(1, [8], hierarchy="h1"))

    assert field.association("h1", 7, 8, channel="temporal") == 1.0
    assert field.association("h1", 8, 7, channel="temporal") == 0.0
    assert field.association("h2", 7, 8, channel="temporal") == 0.0


def test_transport_duplicate_does_not_advance_or_reinforce():
    field = ContinuousStructuralAssociationField(
        temporal_decay=0.5,
        within_decay=0.5,
        forgetting_rate=0,
        trace_floor=1e-8,
    )
    first = observation(0, [9])
    assert field.observe(first) == 1
    assert field.observe(first) == 1
    assert field.observation_count == 1

    field.observe(observation(1, [10]))
    weight = field.association("h1", 9, 10, channel="temporal")
    field.observe(first)
    assert field.association("h1", 9, 10, channel="temporal") == weight
    assert field.observation_count == 2


def test_active_temporal_history_is_bounded_by_numerical_precision_not_fixed_lag():
    field = ContinuousStructuralAssociationField(
        temporal_decay=0.4,
        within_decay=0.4,
        forgetting_rate=0,
        trace_floor=1e-5,
    )
    assert field.temporal_horizon > 4
    for sequence in range(500):
        field.observe(observation(sequence, [sequence + 1]))

    # The deque contains the current event plus all still-contributing past lags.
    assert field.active_history_size("h1") <= field.temporal_horizon + 1
    assert field.active_history_size("h1") > 5


def test_replay_is_deterministic_and_non_semantic():
    stream = [
        observation(0, [1, 2, 300]),
        observation(1, [2, 3, 301]),
        observation(2, [1, 2, 300]),
    ]
    left = ContinuousStructuralAssociationField(
        temporal_decay=0.3,
        within_decay=0.4,
        forgetting_rate=0.02,
        trace_floor=1e-7,
    )
    right = ContinuousStructuralAssociationField(
        temporal_decay=0.3,
        within_decay=0.4,
        forgetting_rate=0.02,
        trace_floor=1e-7,
    )
    for item in stream:
        left.observe(item)
        right.observe(item)

    assert left.snapshot() == right.snapshot()
    snapshot = left.snapshot()
    assert snapshot["semantic_projection"] is False
    assert all(
        "subject" not in row and "predicate" not in row and "object" not in row
        for row in snapshot["edges"]
    )


def test_ten_thousand_event_recurrent_stream_keeps_active_history_bounded():
    field = ContinuousStructuralAssociationField(
        temporal_decay=0.6,
        within_decay=0.6,
        forgetting_rate=0.01,
        trace_floor=1e-4,
    )
    vocabulary = 32
    for sequence in range(10_000):
        field.observe(observation(sequence, [sequence % vocabulary]))

    assert field.observation_count == 10_000
    assert field.active_history_size("h1") <= field.temporal_horizon + 1
    # One-symbol events produce only temporal pairs; the recurring structural
    # universe bounds the possible directed pair identities.
    assert field.edge_count <= vocabulary * vocabulary


def test_recurrent_near_relation_outranks_rotating_distractors():
    field = ContinuousStructuralAssociationField(
        temporal_decay=0.35,
        within_decay=0.35,
        forgetting_rate=0.03,
        trace_floor=1e-8,
    )

    sequence = 0
    distractors = list(range(3, 17))
    for cycle in range(48):
        noise = distractors[cycle % len(distractors)]
        for trail in ([1], [2], [noise]):
            field.observe(observation(sequence, trail))
            sequence += 1

    repeated = field.association("h1", 1, 2, channel="temporal")
    incidental = [
        field.association("h1", 1, distractor, channel="temporal")
        for distractor in distractors
    ]

    assert repeated > max(incidental)
