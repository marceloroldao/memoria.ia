from __future__ import annotations

from math import exp

import pytest

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


def physical_observation(sequence, trail, t_start, t_end=None, *, clock="clock:main", hierarchy="h1"):
    item = observation(sequence, trail, hierarchy=hierarchy)
    item["temporal"] = {
        "clock_id": clock,
        "t_start": float(t_start),
        "t_end": float(t_start if t_end is None else t_end),
        "unit": "s",
    }
    return item


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


def test_unique_stream_forms_causal_band_not_all_to_all_graph():
    field = ContinuousStructuralAssociationField(
        temporal_decay=0.6,
        within_decay=0.6,
        forgetting_rate=0,
        trace_floor=1e-4,
    )
    observations = 2_000
    for sequence in range(observations):
        field.observe(observation(sequence, [sequence + 1]))

    horizon = field.temporal_horizon
    assert horizon < observations

    # With one never-repeated opaque symbol per event, every edge identity is
    # unique. The field may connect only the causal numerical band still above
    # trace precision, so the exact edge count is linear in stream length,
    # rather than the quadratic all-to-all count.
    expected_edges = (
        observations * horizon
        - (horizon * (horizon + 1)) // 2
    )
    assert field.edge_count == expected_edges



def test_physical_time_weight_depends_on_seconds_not_event_count():
    sparse = ContinuousStructuralAssociationField(
        temporal_decay=0.7,
        within_decay=0.5,
        forgetting_rate=0,
        trace_floor=1e-9,
        temporal_axis="physical",
    )
    sparse.observe(physical_observation(0, [1], 0.0))
    sparse.observe(physical_observation(1, [2], 1.0))
    sparse_weight = sparse.association("h1", 1, 2, channel="temporal")

    dense = ContinuousStructuralAssociationField(
        temporal_decay=0.7,
        within_decay=0.5,
        forgetting_rate=0,
        trace_floor=1e-9,
        temporal_axis="physical",
    )
    dense.observe(physical_observation(0, [1], 0.0))
    for sequence in range(1, 10):
        dense.observe(
            physical_observation(sequence, [1000 + sequence], sequence / 10.0)
        )
    dense.observe(physical_observation(10, [2], 1.0))
    dense_weight = dense.association("h1", 1, 2, channel="temporal")

    expected = exp(-0.7)
    assert abs(sparse_weight - expected) < 1e-12
    assert abs(dense_weight - expected) < 1e-12


def test_physical_time_distinguishes_same_event_lag_with_different_elapsed_time():
    close = ContinuousStructuralAssociationField(
        temporal_decay=1.0,
        within_decay=0.5,
        forgetting_rate=0,
        trace_floor=1e-9,
        temporal_axis="physical",
    )
    far = ContinuousStructuralAssociationField(
        temporal_decay=1.0,
        within_decay=0.5,
        forgetting_rate=0,
        trace_floor=1e-9,
        temporal_axis="physical",
    )

    close.observe(physical_observation(0, [1], 0.0))
    close.observe(physical_observation(1, [2], 0.01))
    far.observe(physical_observation(0, [1], 0.0))
    far.observe(physical_observation(1, [2], 5.0))

    close_weight = close.association("h1", 1, 2, channel="temporal")
    far_weight = far.association("h1", 1, 2, channel="temporal")
    assert close_weight > far_weight > 0.0
    assert abs(close_weight - exp(-0.01)) < 1e-12
    assert abs(far_weight - exp(-5.0)) < 1e-12


def test_physical_time_isolates_clock_domains():
    field = ContinuousStructuralAssociationField(
        temporal_decay=0.5,
        within_decay=0.5,
        forgetting_rate=0,
        trace_floor=1e-9,
        temporal_axis="physical",
    )
    field.observe(physical_observation(0, [1], 0.0, clock="clock:a"))
    field.observe(physical_observation(1, [2], 0.1, clock="clock:b"))

    assert field.association("h1", 1, 2, channel="temporal") == 0.0


def test_physical_time_rejects_out_of_order_without_mutating_state():
    field = ContinuousStructuralAssociationField(
        temporal_decay=0.5,
        within_decay=0.5,
        forgetting_rate=0,
        trace_floor=1e-9,
        temporal_axis="physical",
    )
    field.observe(physical_observation(0, [1], 1.0))
    before = field.snapshot()

    with pytest.raises(ValueError, match="monotonic"):
        field.observe(physical_observation(1, [2], 0.5))

    assert field.snapshot() == before
    assert field.observation_count == 1


def test_physical_history_is_bounded_by_elapsed_seconds_not_sample_count():
    field = ContinuousStructuralAssociationField(
        temporal_decay=1.0,
        within_decay=0.5,
        forgetting_rate=0,
        trace_floor=1e-4,
        temporal_axis="physical",
    )
    step = 0.1
    for sequence in range(2_000):
        field.observe(physical_observation(sequence, [sequence + 1], sequence * step))

    maximum_active = int(field.physical_temporal_horizon_seconds / step) + 2
    assert field.active_history_size("h1", clock_id="clock:main") <= maximum_active
    assert field.active_history_size("h1", clock_id="clock:main") < 200
