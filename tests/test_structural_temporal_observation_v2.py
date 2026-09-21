from memoria_resolutiva.structural_temporal_observation_v2 import (
    StructuralTemporalObservationMemory,
)


def _ingest(
    memory,
    *,
    a="temporal:pattern:10",
    b="temporal:pattern:20",
    orientation="a_before_b",
    candidate="tec_ab",
    slices=("1", "2", "3"),
    frames=("f1", "f2", "f3"),
):
    return memory.ingest_observation(
        pattern_a=a,
        pattern_b=b,
        orientation=orientation,
        source_candidate_id=candidate,
        rho=0.45,
        selectivity=1.2,
        temporal_stability=0.97,
        evidence_score=4.1,
        orientation_confidence=0.96,
        mean_dt=0.2,
        variance_dt=0.001,
        supporting_slice_ids=slices,
        supporting_frame_ids=frames,
        provenance="live.infinita/bit.analyze",
    )


def test_structural_temporal_observation_resolves_one_supported_orientation():
    memory = StructuralTemporalObservationMemory()
    observation = _ingest(memory)

    resolution = memory.resolve(
        "temporal:pattern:10",
        "temporal:pattern:20",
        min_independent_slices=3,
    )

    assert observation.observation_id == "STO1"
    assert resolution.resolved is True
    assert resolution.ambiguous is False
    assert resolution.supported_orientation == "a_before_b"
    assert resolution.reason == "single-supported-orientation"
    assert len(resolution.hypotheses) == 1
    hypothesis = resolution.hypotheses[0]
    assert hypothesis.independent_support == 3
    assert hypothesis.supported is True
    assert hypothesis.supporting_slice_ids == ("1", "2", "3")
    assert hypothesis.supporting_frame_ids == ("f1", "f2", "f3")


def test_exact_replay_is_idempotent_and_does_not_increase_support():
    memory = StructuralTemporalObservationMemory()

    first = _ingest(memory)
    second = _ingest(memory)

    assert first is second
    assert len(memory.snapshot()) == 1

    resolution = memory.resolve(
        "temporal:pattern:10",
        "temporal:pattern:20",
        min_independent_slices=3,
    )
    assert resolution.hypotheses[0].independent_support == 3


def test_overlapping_provenance_counts_union_not_candidate_sum():
    memory = StructuralTemporalObservationMemory()

    _ingest(
        memory,
        candidate="tec_ab_v1",
        slices=("1", "2", "3"),
        frames=("f1", "f2", "f3"),
    )
    _ingest(
        memory,
        candidate="tec_ab_v2",
        slices=("1", "2", "3", "4"),
        frames=("f1", "f2", "f3", "f4"),
    )

    assert len(memory.snapshot()) == 2
    resolution = memory.resolve(
        "temporal:pattern:10",
        "temporal:pattern:20",
        min_independent_slices=4,
    )
    hypothesis = resolution.hypotheses[0]

    assert hypothesis.independent_support == 4
    assert hypothesis.supporting_slice_ids == ("1", "2", "3", "4")
    assert hypothesis.supporting_frame_ids == ("f1", "f2", "f3", "f4")
    assert hypothesis.source_candidate_ids == ("tec_ab_v1", "tec_ab_v2")
    assert resolution.resolved is True


def test_competing_supported_orientations_remain_visible_and_ambiguous():
    memory = StructuralTemporalObservationMemory()

    _ingest(
        memory,
        orientation="a_before_b",
        candidate="tec_forward",
        slices=("1", "2", "3"),
    )
    _ingest(
        memory,
        orientation="b_before_a",
        candidate="tec_backward",
        slices=("4", "5", "6"),
        frames=("f4", "f5", "f6"),
    )

    resolution = memory.resolve(
        "temporal:pattern:10",
        "temporal:pattern:20",
        min_independent_slices=3,
    )

    assert resolution.resolved is False
    assert resolution.ambiguous is True
    assert resolution.supported_orientation is None
    assert resolution.reason == "competing-supported-orientations"
    assert {item.orientation for item in resolution.hypotheses} == {
        "a_before_b",
        "b_before_a",
    }
    assert all(item.supported for item in resolution.hypotheses)


def test_unsupported_competitor_does_not_delete_supported_history():
    memory = StructuralTemporalObservationMemory()

    _ingest(
        memory,
        orientation="a_before_b",
        candidate="tec_forward",
        slices=("1", "2", "3"),
    )
    _ingest(
        memory,
        orientation="b_before_a",
        candidate="tec_backward_one_shot",
        slices=("4",),
        frames=("f4",),
    )

    resolution = memory.resolve(
        "temporal:pattern:10",
        "temporal:pattern:20",
        min_independent_slices=3,
    )

    assert resolution.resolved is True
    assert resolution.supported_orientation == "a_before_b"
    assert len(resolution.hypotheses) == 2
    backward = next(
        item for item in resolution.hypotheses
        if item.orientation == "b_before_a"
    )
    assert backward.independent_support == 1
    assert backward.supported is False


def test_reversed_input_pair_is_canonicalized_without_changing_temporal_meaning():
    memory = StructuralTemporalObservationMemory()

    observation = _ingest(
        memory,
        a="temporal:pattern:20",
        b="temporal:pattern:10",
        orientation="a_before_b",
    )

    assert observation.pattern_a == "temporal:pattern:10"
    assert observation.pattern_b == "temporal:pattern:20"
    assert observation.orientation == "b_before_a"

    resolution = memory.resolve(
        "temporal:pattern:20",
        "temporal:pattern:10",
        min_independent_slices=3,
    )
    assert resolution.supported_orientation == "b_before_a"


def test_metrics_are_preserved_for_audit_but_not_used_as_support_count():
    memory = StructuralTemporalObservationMemory()
    observation = _ingest(memory, slices=("slice-x",), frames=("frame-x",))

    assert observation.rho == 0.45
    assert observation.selectivity == 1.2
    assert observation.temporal_stability == 0.97
    assert observation.evidence_score == 4.1
    assert observation.orientation_confidence == 0.96
    assert observation.mean_dt == 0.2
    assert observation.variance_dt == 0.001
    assert observation.provenance == "live.infinita/bit.analyze"

    resolution = memory.resolve(
        "temporal:pattern:10",
        "temporal:pattern:20",
        min_independent_slices=3,
    )
    assert resolution.resolved is False
    assert resolution.reason == "insufficient-supported-orientation"
    assert resolution.hypotheses[0].independent_support == 1


def test_snapshot_restore_preserves_observational_history_and_resolution():
    memory = StructuralTemporalObservationMemory()
    _ingest(memory, candidate="tec_forward", slices=("1", "2", "3"))
    _ingest(
        memory,
        orientation="b_before_a",
        candidate="tec_backward",
        slices=("4", "5"),
        frames=("f4", "f5"),
    )

    snapshot = memory.snapshot()
    restored = StructuralTemporalObservationMemory.restore(snapshot)

    assert restored.snapshot() == snapshot
    assert restored.resolve(
        "temporal:pattern:10",
        "temporal:pattern:20",
        min_independent_slices=3,
    ) == memory.resolve(
        "temporal:pattern:10",
        "temporal:pattern:20",
        min_independent_slices=3,
    )


def test_invalid_observation_does_not_create_semantic_or_causal_shortcuts():
    memory = StructuralTemporalObservationMemory()

    try:
        memory.ingest_observation(
            pattern_a="temporal:pattern:10",
            pattern_b="temporal:pattern:10",
            orientation="a_before_b",
            source_candidate_id="tec_invalid",
            rho=0.5,
            selectivity=1.0,
            temporal_stability=1.0,
            evidence_score=3.0,
            orientation_confidence=1.0,
            mean_dt=0.2,
            variance_dt=0.0,
            supporting_slice_ids=("1",),
        )
    except ValueError as exc:
        assert "distinct patterns" in str(exc)
    else:
        raise AssertionError("same-pattern temporal relation must be rejected")

    assert memory.snapshot() == ()
