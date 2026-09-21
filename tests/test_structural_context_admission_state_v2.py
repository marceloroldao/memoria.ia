from memoria_resolutiva.structural_context_admission_state_v2 import (
    StructuralContextAdmissionStateMemory,
)
from memoria_resolutiva.structural_context_observation_v2 import (
    StructuralContextObservationMemory,
)
from memoria_resolutiva.structural_context_recall_v2 import (
    recall_active_structural_context,
    recall_structural_context,
)


ANTECEDENTS = ("temporal:pattern:A", "temporal:pattern:X")


def _observe(memory):
    return memory.ingest_observation(
        antecedent_patterns=ANTECEDENTS,
        consequence_pattern="temporal:pattern:P",
        source_candidate_id="hoc_ax_p",
        rho=0.55,
        context_coverage=1.0,
        temporal_stability=1.0,
        context_reliability=1.0,
        lower_order_reliabilities=(0.5, 0.5),
        repetitions=4,
        mean_delay=0.3,
        variance_delay=0.0,
        supporting_slice_ids=("1", "2", "3", "4"),
        supporting_frame_ids=("f1", "f2", "f3", "f4"),
        provenance="test",
    )


def test_admission_state_preserves_history_and_current_snapshot_separately():
    memory = StructuralContextAdmissionStateMemory()

    first = memory.ingest_snapshot(
        antecedent_patterns=ANTECEDENTS,
        active_candidate_ids=("hoc_ax_p",),
        source_epoch_id="phase-1",
        supporting_slice_ids=("1", "2", "3", "4"),
        provenance="test",
    )
    second = memory.ingest_snapshot(
        antecedent_patterns=ANTECEDENTS,
        active_candidate_ids=(),
        source_epoch_id="phase-2",
        supporting_slice_ids=("5", "6", "7", "8"),
        provenance="test",
    )

    assert memory.snapshot() == (first, second)
    assert memory.current(ANTECEDENTS) == second
    assert second.active_candidate_ids == ()


def test_identical_admission_snapshot_is_idempotent():
    memory = StructuralContextAdmissionStateMemory()

    first = memory.ingest_snapshot(
        antecedent_patterns=ANTECEDENTS,
        active_candidate_ids=("hoc_ax_p",),
        source_epoch_id="phase-1",
        supporting_slice_ids=("1", "2"),
    )
    second = memory.ingest_snapshot(
        antecedent_patterns=reversed(ANTECEDENTS),
        active_candidate_ids=("hoc_ax_p",),
        source_epoch_id="phase-1",
        supporting_slice_ids=("2", "1"),
    )

    assert first == second
    assert memory.snapshot() == (first,)


def test_restore_preserves_latest_admission_state():
    memory = StructuralContextAdmissionStateMemory()
    memory.ingest_snapshot(
        antecedent_patterns=ANTECEDENTS,
        active_candidate_ids=("hoc_ax_p",),
        source_epoch_id="phase-1",
    )
    memory.ingest_snapshot(
        antecedent_patterns=ANTECEDENTS,
        active_candidate_ids=(),
        source_epoch_id="phase-2",
    )

    restored = StructuralContextAdmissionStateMemory.restore(memory.snapshot())

    assert restored.snapshot() == memory.snapshot()
    assert restored.current(ANTECEDENTS) == memory.current(ANTECEDENTS)


def test_active_recall_filters_historical_supported_context_after_deactivation():
    observations = StructuralContextObservationMemory()
    admission = StructuralContextAdmissionStateMemory()
    _observe(observations)

    admission.ingest_snapshot(
        antecedent_patterns=ANTECEDENTS,
        active_candidate_ids=("hoc_ax_p",),
        source_epoch_id="phase-1",
    )

    historical = recall_structural_context(observations, ANTECEDENTS)
    active_phase_1 = recall_active_structural_context(
        observations,
        admission,
        ANTECEDENTS,
    )
    assert len(historical.neighbors) == 1
    assert len(active_phase_1.neighbors) == 1

    admission.ingest_snapshot(
        antecedent_patterns=ANTECEDENTS,
        active_candidate_ids=(),
        source_epoch_id="phase-2",
    )

    historical_after = recall_structural_context(observations, ANTECEDENTS)
    active_phase_2 = recall_active_structural_context(
        observations,
        admission,
        ANTECEDENTS,
    )

    assert len(historical_after.neighbors) == 1
    assert active_phase_2.neighbors == ()


def test_active_recall_without_current_admission_snapshot_is_empty():
    observations = StructuralContextObservationMemory()
    admission = StructuralContextAdmissionStateMemory()
    _observe(observations)

    active = recall_active_structural_context(
        observations,
        admission,
        ANTECEDENTS,
    )

    assert active.neighbors == ()


def test_active_recall_keeps_only_current_candidate_when_history_has_competitor():
    observations = StructuralContextObservationMemory()
    admission = StructuralContextAdmissionStateMemory()
    _observe(observations)
    observations.ingest_observation(
        antecedent_patterns=ANTECEDENTS,
        consequence_pattern="temporal:pattern:Q",
        source_candidate_id="hoc_ax_q",
        rho=0.55,
        context_coverage=1.0,
        temporal_stability=1.0,
        context_reliability=1.0,
        lower_order_reliabilities=(0.5, 0.5),
        repetitions=4,
        mean_delay=0.3,
        variance_delay=0.0,
        supporting_slice_ids=("5", "6", "7", "8"),
        provenance="test",
    )
    admission.ingest_snapshot(
        antecedent_patterns=ANTECEDENTS,
        active_candidate_ids=("hoc_ax_q",),
        source_epoch_id="phase-2",
    )

    historical = recall_structural_context(observations, ANTECEDENTS)
    active = recall_active_structural_context(
        observations,
        admission,
        ANTECEDENTS,
    )

    assert tuple(x.consequence_pattern for x in historical.neighbors) == (
        "temporal:pattern:P",
        "temporal:pattern:Q",
    )
    assert tuple(x.consequence_pattern for x in active.neighbors) == (
        "temporal:pattern:Q",
    )


def test_multiple_active_candidates_are_normalized_to_explicit_ambiguity():
    memory = StructuralContextAdmissionStateMemory()

    snapshot = memory.ingest_snapshot(
        antecedent_patterns=ANTECEDENTS,
        active_candidate_ids=("hoc_ax_p", "hoc_ax_q"),
        source_epoch_id="transition",
        supporting_slice_ids=("9", "10"),
    )

    assert snapshot.resolution_state == "ambiguous"
    assert snapshot.active_candidate_ids == ()
    assert snapshot.competing_candidate_ids == (
        "hoc_ax_p",
        "hoc_ax_q",
    )


def test_explicit_ambiguous_snapshot_requires_two_competitors_and_no_active_candidate():
    memory = StructuralContextAdmissionStateMemory()

    try:
        memory.ingest_snapshot(
            antecedent_patterns=ANTECEDENTS,
            active_candidate_ids=(),
            source_epoch_id="transition",
            resolution_state="ambiguous",
            competing_candidate_ids=("hoc_ax_p",),
        )
    except ValueError as exc:
        assert "at least two" in str(exc)
    else:
        raise AssertionError("ambiguity must require at least two competing candidates")

    try:
        memory.ingest_snapshot(
            antecedent_patterns=ANTECEDENTS,
            active_candidate_ids=("hoc_ax_p",),
            source_epoch_id="transition",
            resolution_state="ambiguous",
            competing_candidate_ids=("hoc_ax_q", "hoc_ax_r"),
        )
    except ValueError as exc:
        assert "must not activate" in str(exc)
    else:
        raise AssertionError("ambiguous state must not activate a candidate")


def test_explicit_resolution_state_survives_snapshot_restore():
    memory = StructuralContextAdmissionStateMemory()
    first = memory.ingest_snapshot(
        antecedent_patterns=ANTECEDENTS,
        active_candidate_ids=(),
        source_epoch_id="transition",
        resolution_state="ambiguous",
        competing_candidate_ids=("hoc_ax_p", "hoc_ax_q"),
        supporting_slice_ids=("9", "10"),
    )

    restored = StructuralContextAdmissionStateMemory.restore(memory.snapshot())

    assert restored.snapshot() == (first,)
    current = restored.current(ANTECEDENTS)
    assert current is not None
    assert current.resolution_state == "ambiguous"
    assert current.competing_candidate_ids == ("hoc_ax_p", "hoc_ax_q")
