from __future__ import annotations

from memoria_resolutiva.structural_association_continuous import (
    ContinuousStructuralAssociationField,
)
from memoria_resolutiva.structural_attractor_v2 import StructuralAttractorResolverV2
from memoria_resolutiva.structural_trajectory_v2 import StructuralTrajectoryIndex


def _index(rows, *, hierarchy_id="h"):
    index = StructuralTrajectoryIndex()
    for sequence, addresses in enumerate(rows):
        index.ingest_addresses(
            addresses,
            hierarchy_id=hierarchy_id,
            source_id=f"source:{sequence}",
            sequence=sequence,
        )
    return index


def _envelope(sequence: int, trail: list[int], *, hierarchy_id: str = "h") -> dict:
    return {
        "observation_id": f"obs:{hierarchy_id}:{sequence}",
        "semantic_projection": False,
        "provenance": {"hierarchy_id": hierarchy_id},
        "event": {
            "trail": trail,
        },
    }


def _continuous_field(rows, *, hierarchy_id="h", forgetting_rate=0.0):
    field = ContinuousStructuralAssociationField(
        within_decay=0.35,
        temporal_decay=0.35,
        forgetting_rate=forgetting_rate,
    )
    for sequence, trail in enumerate(rows):
        field.observe(_envelope(sequence, list(trail), hierarchy_id=hierarchy_id))
    return field


def _candidate(result, address):
    return next(item for item in result.candidates if item.address == address)


def test_recurrence_can_form_a_unique_attractor_without_weighted_score():
    rows = [
        [1, 2, 3],
        [1, 2, 4],
        [1, 2, 4],
    ]
    index = _index(rows)
    resolver = StructuralAttractorResolverV2(index)

    result = resolver.resolve_addresses([1, 2], hierarchy_id="h")

    assert result.resolved is True
    assert result.resolved_address == 4
    assert result.pareto_frontier == (4,)
    c4 = _candidate(result, 4)
    c3 = _candidate(result, 3)
    assert c4.evidence.trajectory_support == 2
    assert c3.evidence.trajectory_support == 1
    # Extra hierarchical compression can make the stronger recurrent candidate
    # visible at fewer derived depths. Depth is therefore diagnostic, not strength.
    assert c3.evidence.supporting_depth_count > c4.evidence.supporting_depth_count
    assert 4 in c3.dominated_by


def test_equal_structural_evidence_stays_ambiguous():
    index = _index([
        [1, 2, 3],
        [1, 2, 4],
    ])
    resolver = StructuralAttractorResolverV2(index)

    result = resolver.resolve_addresses([1, 2], hierarchy_id="h")

    assert result.resolved is False
    assert result.ambiguous is True
    assert result.pareto_frontier == (3, 4)
    assert result.reason == "crossed-or-equal-attractor-evidence"


def test_current_continuous_field_can_break_a_structural_tie_by_accumulated_decay():
    rows = [
        [1, 2, 3],
        [1, 2, 3],
        [1, 2, 4],
        [1, 2, 4],
    ]
    index = _index(rows)
    field = _continuous_field(rows, forgetting_rate=0.55)
    resolver = StructuralAttractorResolverV2(
        index,
        association_field=field,
    )

    before_field = field.snapshot()
    before_index = index.snapshot()
    result = resolver.resolve_addresses([1, 2], hierarchy_id="h")

    c3 = _candidate(result, 3)
    c4 = _candidate(result, 4)
    assert c3.evidence.trajectory_support == c4.evidence.trajectory_support == 2
    assert c4.evidence.within.total_mass > c3.evidence.within.total_mass
    assert c4.evidence.temporal.total_mass >= c3.evidence.temporal.total_mass
    assert result.resolved is True
    assert result.resolved_address == 4
    assert field.snapshot() == before_field
    assert index.snapshot() == before_index


def test_crossed_recurrence_and_decayed_field_evidence_must_remain_ambiguous():
    rows = [
        [1, 2, 3],
        [1, 2, 3],
        [1, 2, 3],
        [1, 2, 4],
        [1, 2, 4],
    ]
    index = _index(rows)
    field = _continuous_field(rows, forgetting_rate=1.25)
    resolver = StructuralAttractorResolverV2(
        index,
        association_field=field,
    )

    result = resolver.resolve_addresses([1, 2], hierarchy_id="h")

    c3 = _candidate(result, 3)
    c4 = _candidate(result, 4)
    assert c3.evidence.trajectory_support > c4.evidence.trajectory_support
    assert c4.evidence.within.total_mass > c3.evidence.within.total_mass
    assert result.resolved is False
    assert result.ambiguous is True
    assert set(result.pareto_frontier) == {3, 4}


def test_density_is_diagnostic_and_cannot_choose_an_attractor():
    index = _index([
        [1, 2, 3],
        [1, 2, 4],
        [90, 3, 91],
        [92, 3, 93],
        [94, 3, 95],
    ])
    resolver = StructuralAttractorResolverV2(index)

    result = resolver.resolve_addresses([1, 2], hierarchy_id="h")

    c3 = _candidate(result, 3)
    c4 = _candidate(result, 4)
    assert c3.density is not None
    assert c4.density is not None
    assert c3.density.trajectory_count > c4.density.trajectory_count
    assert c3.evidence == c4.evidence
    assert result.resolved is False
    assert result.ambiguous is True


def test_terminal_outcome_cannot_be_numerically_fabricated_into_forward_score():
    index = _index([
        [1, 2],
        [1, 2, 3],
        [1, 2, 3],
    ])
    resolver = StructuralAttractorResolverV2(index)

    result = resolver.resolve_addresses([1, 2], hierarchy_id="h")

    assert result.resolved is False
    assert result.ambiguous is True
    assert result.resolved_address is None
    assert result.terminal is False
    assert result.terminal_trajectory_ids
    assert result.reason == "terminal-competes-with-forward-attractor"


def test_terminal_only_region_is_reported_without_inventing_next_address():
    index = _index([[1, 2]])
    resolver = StructuralAttractorResolverV2(index)

    result = resolver.resolve_addresses([1, 2], hierarchy_id="h")

    assert result.resolved is False
    assert result.ambiguous is False
    assert result.terminal is True
    assert result.resolved_address is None
    assert result.candidates == ()
    assert result.reason == "terminal-attractor-region"


def test_attractor_resolution_respects_hierarchy_isolation():
    index = StructuralTrajectoryIndex()
    index.ingest_addresses([1, 2, 3], hierarchy_id="left", source_id="l1", sequence=0)
    index.ingest_addresses([1, 2, 3], hierarchy_id="left", source_id="l2", sequence=1)
    index.ingest_addresses([1, 2, 4], hierarchy_id="right", source_id="r1", sequence=0)
    index.ingest_addresses([1, 2, 4], hierarchy_id="right", source_id="r2", sequence=1)
    resolver = StructuralAttractorResolverV2(index)

    left = resolver.resolve_addresses([1, 2], hierarchy_id="left")
    right = resolver.resolve_addresses([1, 2], hierarchy_id="right")

    assert left.resolved_address == 3
    assert right.resolved_address == 4


def test_unrelated_query_remains_without_attractor_candidate():
    index = _index([
        [1, 2, 3],
        [1, 2, 4],
    ])
    resolver = StructuralAttractorResolverV2(index)

    result = resolver.resolve_addresses([900, 901], hierarchy_id="h")

    assert result.resolved is False
    assert result.ambiguous is False
    assert result.candidates == ()
    assert result.reason == "no-attractor-candidate"


def test_attractor_fails_closed_when_frontier_is_bounded_out():
    index = _index([
        [1, 2, 3],
        [1, 2, 4],
        [1, 2, 5],
    ])
    resolver = StructuralAttractorResolverV2(index)

    result = resolver.resolve_addresses(
        [1, 2],
        hierarchy_id="h",
        candidate_limit=2,
    )

    assert result.resolved is False
    assert result.ambiguous is True
    assert result.bounded_out is True
    assert result.candidates == ()
    assert result.reason == "candidate-limit-exceeded"
