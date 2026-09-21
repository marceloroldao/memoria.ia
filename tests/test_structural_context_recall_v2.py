from memoria_resolutiva.structural_context_observation_v2 import (
    StructuralContextObservationMemory,
)
from memoria_resolutiva.structural_context_recall_v2 import (
    recall_structural_context,
)


def _observe(
    memory,
    *,
    antecedents=("temporal:pattern:A", "temporal:pattern:C"),
    consequence="temporal:pattern:P",
    candidate_id="hoc_ac_p",
    slices=("1", "2", "3", "4"),
):
    return memory.ingest_observation(
        antecedent_patterns=antecedents,
        consequence_pattern=consequence,
        source_candidate_id=candidate_id,
        rho=0.52,
        context_coverage=1.0,
        temporal_stability=1.0,
        context_reliability=1.0,
        lower_order_reliabilities=(0.5, 0.5),
        repetitions=len(slices),
        mean_delay=0.3,
        variance_delay=0.0,
        supporting_slice_ids=slices,
        supporting_frame_ids=tuple(f"f{x}" for x in slices),
        provenance="test",
    )


def test_context_recall_returns_supported_consequence_for_exact_pair():
    memory = StructuralContextObservationMemory()
    _observe(memory)

    recall = recall_structural_context(
        memory,
        ("temporal:pattern:A", "temporal:pattern:C"),
    )

    assert recall.antecedent_patterns == (
        "temporal:pattern:A",
        "temporal:pattern:C",
    )
    assert len(recall.neighbors) == 1
    assert recall.neighbors[0].consequence_pattern == "temporal:pattern:P"
    assert recall.neighbors[0].hypothesis.independent_support == 4


def test_context_recall_is_order_invariant_for_antecedent_pair():
    memory = StructuralContextObservationMemory()
    _observe(memory)

    forward = recall_structural_context(
        memory,
        ("temporal:pattern:A", "temporal:pattern:C"),
    )
    reversed_query = recall_structural_context(
        memory,
        ("temporal:pattern:C", "temporal:pattern:A"),
    )

    assert forward == reversed_query


def test_context_recall_excludes_insufficient_support():
    memory = StructuralContextObservationMemory()
    _observe(memory, slices=("1",))

    recall = recall_structural_context(
        memory,
        ("temporal:pattern:A", "temporal:pattern:C"),
        min_independent_slices=3,
    )

    assert recall.neighbors == ()


def test_multiple_supported_consequences_remain_visible_without_metric_ranking():
    memory = StructuralContextObservationMemory()
    _observe(
        memory,
        consequence="temporal:pattern:P",
        candidate_id="hoc_ac_p",
        slices=("1", "2", "3", "4"),
    )
    _observe(
        memory,
        consequence="temporal:pattern:Q",
        candidate_id="hoc_ac_q",
        slices=("5", "6", "7", "8"),
    )

    recall = recall_structural_context(
        memory,
        ("temporal:pattern:A", "temporal:pattern:C"),
    )

    assert tuple(item.consequence_pattern for item in recall.neighbors) == (
        "temporal:pattern:P",
        "temporal:pattern:Q",
    )
    assert all(item.hypothesis.supported for item in recall.neighbors)


def test_different_context_pair_does_not_leak_into_query():
    memory = StructuralContextObservationMemory()
    _observe(memory)
    _observe(
        memory,
        antecedents=("temporal:pattern:A", "temporal:pattern:D"),
        consequence="temporal:pattern:Q",
        candidate_id="hoc_ad_q",
        slices=("5", "6", "7", "8"),
    )

    recall = recall_structural_context(
        memory,
        ("temporal:pattern:A", "temporal:pattern:C"),
    )

    assert tuple(item.consequence_pattern for item in recall.neighbors) == (
        "temporal:pattern:P",
    )


def test_single_pattern_query_is_rejected_instead_of_guessing_context():
    memory = StructuralContextObservationMemory()
    _observe(memory)

    try:
        recall_structural_context(
            memory,
            ("temporal:pattern:A",),
        )
    except ValueError as exc:
        assert "exactly two" in str(exc)
    else:
        raise AssertionError("single-pattern context recall must be rejected")


def test_context_recall_is_read_only():
    memory = StructuralContextObservationMemory()
    _observe(memory)
    before = memory.snapshot()

    _ = recall_structural_context(
        memory,
        ("temporal:pattern:A", "temporal:pattern:C"),
    )

    assert memory.snapshot() == before
