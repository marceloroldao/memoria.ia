from memoria_resolutiva.structural_context_observation_v2 import (
    StructuralContextObservationMemory,
)


def _ingest(
    memory,
    *,
    antecedents=("temporal:pattern:A", "temporal:pattern:C"),
    consequence="temporal:pattern:P",
    candidate_id="hoc_ac_p",
    slices=("1", "2", "3", "4"),
    frames=("f1", "f2", "f3", "f4"),
    lower=(0.5, 0.5),
):
    return memory.ingest_observation(
        antecedent_patterns=antecedents,
        consequence_pattern=consequence,
        source_candidate_id=candidate_id,
        rho=0.52,
        context_coverage=1.0,
        temporal_stability=1.0,
        context_reliability=1.0,
        lower_order_reliabilities=lower,
        repetitions=len(slices),
        mean_delay=0.3,
        variance_delay=0.0,
        supporting_slice_ids=slices,
        supporting_frame_ids=frames,
        provenance="live.infinita/bit.analyze",
    )


def test_context_observation_preserves_two_opaque_antecedents_without_synthetic_pattern():
    memory = StructuralContextObservationMemory()
    observation = _ingest(memory)

    assert observation.antecedent_patterns == (
        "temporal:pattern:A",
        "temporal:pattern:C",
    )
    assert observation.consequence_pattern == "temporal:pattern:P"
    assert not hasattr(observation, "context_pattern")
    assert not hasattr(observation, "combined_pattern")


def test_reversed_antecedent_input_is_canonicalized_with_metric_alignment():
    memory = StructuralContextObservationMemory()
    observation = _ingest(
        memory,
        antecedents=("temporal:pattern:C", "temporal:pattern:A"),
        lower=(0.4, 0.6),
    )

    assert observation.antecedent_patterns == (
        "temporal:pattern:A",
        "temporal:pattern:C",
    )
    assert observation.lower_order_reliabilities == (0.6, 0.4)


def test_identical_context_observation_is_idempotent():
    memory = StructuralContextObservationMemory()

    first = _ingest(memory)
    second = _ingest(memory)

    assert first == second
    assert memory.snapshot() == (first,)


def test_independent_slice_support_controls_context_resolution():
    memory = StructuralContextObservationMemory()
    _ingest(memory, slices=("1",), frames=("f1",))

    unresolved = memory.resolve(
        ("temporal:pattern:A", "temporal:pattern:C"),
        "temporal:pattern:P",
        min_independent_slices=3,
    )
    assert unresolved is not None
    assert unresolved.independent_support == 1
    assert unresolved.supported is False

    _ingest(
        memory,
        candidate_id="hoc_ac_p_more",
        slices=("2", "3"),
        frames=("f2", "f3"),
    )
    resolved = memory.resolve(
        ("temporal:pattern:C", "temporal:pattern:A"),
        "temporal:pattern:P",
        min_independent_slices=3,
    )
    assert resolved is not None
    assert resolved.independent_support == 3
    assert resolved.supported is True


def test_updated_metrics_with_same_slice_provenance_do_not_inflate_support():
    memory = StructuralContextObservationMemory()
    _ingest(memory)

    memory.ingest_observation(
        antecedent_patterns=("temporal:pattern:A", "temporal:pattern:C"),
        consequence_pattern="temporal:pattern:P",
        source_candidate_id="hoc_ac_p_updated",
        rho=0.61,
        context_coverage=1.0,
        temporal_stability=0.98,
        context_reliability=0.98,
        lower_order_reliabilities=(0.5, 0.5),
        repetitions=4,
        mean_delay=0.31,
        variance_delay=0.001,
        supporting_slice_ids=("1", "2", "3", "4"),
        supporting_frame_ids=("f1", "f2", "f3", "f4"),
        provenance="live.infinita/bit.analyze",
    )

    assert len(memory.snapshot()) == 2
    resolved = memory.resolve(
        ("temporal:pattern:A", "temporal:pattern:C"),
        "temporal:pattern:P",
    )
    assert resolved is not None
    assert resolved.independent_support == 4


def test_snapshot_restore_preserves_context_observations():
    memory = StructuralContextObservationMemory()
    _ingest(memory)

    snapshot = memory.snapshot()
    restored = StructuralContextObservationMemory.restore(snapshot)

    assert restored.snapshot() == snapshot
    assert restored.resolve(
        ("temporal:pattern:A", "temporal:pattern:C"),
        "temporal:pattern:P",
    ) == memory.resolve(
        ("temporal:pattern:A", "temporal:pattern:C"),
        "temporal:pattern:P",
    )


def test_invalid_context_does_not_create_observation():
    memory = StructuralContextObservationMemory()

    for antecedents, consequence in (
        (("A",), "P"),
        (("A", "A"), "P"),
        (("A", "C"), "A"),
    ):
        try:
            _ingest(
                memory,
                antecedents=antecedents,
                consequence=consequence,
            )
        except ValueError:
            pass
        else:
            raise AssertionError("invalid structural context must be rejected")

    assert memory.snapshot() == ()
