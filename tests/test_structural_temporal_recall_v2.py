from memoria_resolutiva.structural_temporal_observation_v2 import (
    StructuralTemporalObservationMemory,
)
from memoria_resolutiva.structural_temporal_recall_v2 import (
    TemporalWorldCandidate,
    recall_structural_temporal_neighbors,
    resolve_temporal_world_candidates,
)


def _observe(
    memory,
    *,
    a="temporal:pattern:A",
    b="temporal:pattern:B",
    orientation="a_before_b",
    candidate_id="tec_ab",
    slices=("1", "2", "3"),
    rho=0.5,
    score=4.0,
):
    return memory.ingest_observation(
        pattern_a=a,
        pattern_b=b,
        orientation=orientation,
        source_candidate_id=candidate_id,
        rho=rho,
        selectivity=1.0,
        temporal_stability=0.95,
        evidence_score=score,
        orientation_confidence=0.95,
        mean_dt=0.2 if orientation != "b_before_a" else -0.2,
        variance_dt=0.001,
        supporting_slice_ids=slices,
        supporting_frame_ids=tuple(f"f{x}" for x in slices),
        provenance="test",
    )


def test_recall_returns_supported_neighbor_relative_to_query_direction():
    memory = StructuralTemporalObservationMemory()
    _observe(memory)

    from_a = recall_structural_temporal_neighbors(memory, "temporal:pattern:A")
    from_b = recall_structural_temporal_neighbors(memory, "temporal:pattern:B")

    assert len(from_a.neighbors) == 1
    assert from_a.neighbors[0].pattern_address == "temporal:pattern:B"
    assert from_a.neighbors[0].relation_to_query == "after_query"
    assert from_a.neighbors[0].hypothesis.independent_support == 3

    assert len(from_b.neighbors) == 1
    assert from_b.neighbors[0].pattern_address == "temporal:pattern:A"
    assert from_b.neighbors[0].relation_to_query == "before_query"


def test_recall_excludes_insufficiently_supported_neighbor():
    memory = StructuralTemporalObservationMemory()
    _observe(memory, slices=("1",))

    recall = recall_structural_temporal_neighbors(
        memory,
        "temporal:pattern:A",
        min_independent_slices=3,
    )

    assert recall.neighbors == ()


def test_single_supported_world_continuation_resolves_without_inventing_other_memory_neighbors():
    memory = StructuralTemporalObservationMemory()
    _observe(memory, b="temporal:pattern:B", candidate_id="tec_ab")
    _observe(
        memory,
        b="temporal:pattern:D",
        candidate_id="tec_ad",
        slices=("4", "5", "6"),
    )

    resolution = resolve_temporal_world_candidates(
        memory,
        "temporal:pattern:A",
        (
            TemporalWorldCandidate("world_b", "temporal:pattern:B"),
            TemporalWorldCandidate("world_c", "temporal:pattern:C"),
        ),
    )

    assert resolution.resolved is True
    assert resolution.ambiguous is False
    assert resolution.resolved_candidate == TemporalWorldCandidate(
        "world_b",
        "temporal:pattern:B",
    )
    assert tuple(item.candidate.candidate_id for item in resolution.matches) == ("world_b",)
    assert "temporal:pattern:D" not in tuple(
        candidate.pattern_address for candidate in resolution.candidates
    )


def test_memory_supported_pattern_absent_from_world_is_not_returned():
    memory = StructuralTemporalObservationMemory()
    _observe(memory, b="temporal:pattern:D", candidate_id="tec_ad")

    resolution = resolve_temporal_world_candidates(
        memory,
        "temporal:pattern:A",
        (
            TemporalWorldCandidate("world_b", "temporal:pattern:B"),
            TemporalWorldCandidate("world_c", "temporal:pattern:C"),
        ),
    )

    assert resolution.resolved is False
    assert resolution.ambiguous is False
    assert resolution.resolved_candidate is None
    assert resolution.matches == ()
    assert resolution.reason == "no-supported-world-continuation"


def test_multiple_supported_world_continuations_preserve_ambiguity_without_ranking():
    memory = StructuralTemporalObservationMemory()
    _observe(
        memory,
        b="temporal:pattern:B",
        candidate_id="tec_ab",
        rho=0.95,
        score=10.0,
    )
    _observe(
        memory,
        b="temporal:pattern:C",
        candidate_id="tec_ac",
        slices=("4", "5", "6"),
        rho=0.41,
        score=3.1,
    )

    resolution = resolve_temporal_world_candidates(
        memory,
        "temporal:pattern:A",
        (
            TemporalWorldCandidate("world_b", "temporal:pattern:B"),
            TemporalWorldCandidate("world_c", "temporal:pattern:C"),
        ),
    )

    assert resolution.resolved is False
    assert resolution.ambiguous is True
    assert resolution.resolved_candidate is None
    assert resolution.reason == "multiple-supported-world-continuations"
    assert tuple(item.candidate.candidate_id for item in resolution.matches) == (
        "world_b",
        "world_c",
    )


def test_reverse_only_relation_does_not_support_future_candidate():
    memory = StructuralTemporalObservationMemory()
    _observe(memory, orientation="b_before_a")

    resolution = resolve_temporal_world_candidates(
        memory,
        "temporal:pattern:A",
        (TemporalWorldCandidate("world_b", "temporal:pattern:B"),),
    )

    assert resolution.matches == ()
    assert resolution.resolved is False
    assert resolution.ambiguous is False
    assert resolution.reason == "no-supported-world-continuation"


def test_competing_supported_orientations_make_single_world_candidate_contested():
    memory = StructuralTemporalObservationMemory()
    _observe(
        memory,
        orientation="a_before_b",
        candidate_id="tec_forward",
        slices=("1", "2", "3"),
    )
    _observe(
        memory,
        orientation="b_before_a",
        candidate_id="tec_backward",
        slices=("4", "5", "6"),
    )

    recall = recall_structural_temporal_neighbors(memory, "temporal:pattern:A")
    assert {item.relation_to_query for item in recall.neighbors} == {
        "after_query",
        "before_query",
    }

    resolution = resolve_temporal_world_candidates(
        memory,
        "temporal:pattern:A",
        (TemporalWorldCandidate("world_b", "temporal:pattern:B"),),
    )

    assert resolution.resolved is False
    assert resolution.ambiguous is True
    assert resolution.resolved_candidate is None
    assert resolution.reason == "contested-supported-world-continuation"
    assert len(resolution.matches) == 1
    assert resolution.matches[0].contested is True
    assert len(resolution.matches[0].supporting_neighbors) == 1
    assert len(resolution.matches[0].competing_neighbors) == 1


def test_simultaneous_supported_relation_is_recalled_but_not_treated_as_future():
    memory = StructuralTemporalObservationMemory()
    _observe(memory, orientation="simultaneous")

    recall = recall_structural_temporal_neighbors(memory, "temporal:pattern:A")
    assert len(recall.neighbors) == 1
    assert recall.neighbors[0].relation_to_query == "simultaneous"

    resolution = resolve_temporal_world_candidates(
        memory,
        "temporal:pattern:A",
        (TemporalWorldCandidate("world_b", "temporal:pattern:B"),),
    )

    assert resolution.matches == ()
    assert resolution.reason == "no-supported-world-continuation"


def test_resolver_is_read_only_over_structural_temporal_memory():
    memory = StructuralTemporalObservationMemory()
    _observe(memory)
    before = memory.snapshot()

    _ = resolve_temporal_world_candidates(
        memory,
        "temporal:pattern:A",
        (TemporalWorldCandidate("world_b", "temporal:pattern:B"),),
    )

    assert memory.snapshot() == before


def test_duplicate_world_candidate_ids_are_rejected():
    memory = StructuralTemporalObservationMemory()
    _observe(memory)

    try:
        resolve_temporal_world_candidates(
            memory,
            "temporal:pattern:A",
            (
                TemporalWorldCandidate("dup", "temporal:pattern:B"),
                TemporalWorldCandidate("dup", "temporal:pattern:C"),
            ),
        )
    except ValueError as exc:
        assert "unique" in str(exc)
    else:
        raise AssertionError("duplicate world candidate IDs must be rejected")


def test_reinforced_orientation_becomes_active_without_erasing_competitor():
    memory = StructuralTemporalObservationMemory()
    _observe(
        memory,
        orientation="a_before_b",
        candidate_id="tec_forward_initial",
        slices=("1", "2", "3"),
    )
    _observe(
        memory,
        orientation="b_before_a",
        candidate_id="tec_backward",
        slices=("4", "5", "6"),
    )
    _observe(
        memory,
        orientation="a_before_b",
        candidate_id="tec_forward_reinforced",
        slices=("7", "8"),
    )

    recall = recall_structural_temporal_neighbors(memory, "temporal:pattern:A")
    assert len(recall.neighbors) == 2

    by_relation = {item.relation_to_query: item for item in recall.neighbors}
    assert by_relation["after_query"].hypothesis.independent_support == 5
    assert by_relation["after_query"].active_for_resolution is True
    assert by_relation["before_query"].hypothesis.independent_support == 3
    assert by_relation["before_query"].active_for_resolution is False

    resolution = resolve_temporal_world_candidates(
        memory,
        "temporal:pattern:A",
        (TemporalWorldCandidate("world_b", "temporal:pattern:B"),),
    )
    assert resolution.resolved is True
    assert resolution.ambiguous is False
    assert resolution.resolved_candidate == TemporalWorldCandidate(
        "world_b",
        "temporal:pattern:B",
    )
    assert resolution.matches[0].contested is False


def test_reinforced_reverse_orientation_blocks_future_without_erasing_forward_history():
    memory = StructuralTemporalObservationMemory()
    _observe(
        memory,
        orientation="a_before_b",
        candidate_id="tec_forward",
        slices=("1", "2", "3"),
    )
    _observe(
        memory,
        orientation="b_before_a",
        candidate_id="tec_backward_initial",
        slices=("4", "5", "6"),
    )
    _observe(
        memory,
        orientation="b_before_a",
        candidate_id="tec_backward_reinforced",
        slices=("7", "8"),
    )

    recall = recall_structural_temporal_neighbors(memory, "temporal:pattern:A")
    by_relation = {item.relation_to_query: item for item in recall.neighbors}
    assert by_relation["after_query"].active_for_resolution is False
    assert by_relation["before_query"].active_for_resolution is True

    resolution = resolve_temporal_world_candidates(
        memory,
        "temporal:pattern:A",
        (TemporalWorldCandidate("world_b", "temporal:pattern:B"),),
    )
    assert resolution.resolved is False
    assert resolution.ambiguous is False
    assert resolution.matches == ()
    assert resolution.reason == "no-supported-world-continuation"
