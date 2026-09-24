from __future__ import annotations

from pathlib import Path

import pytest

from memoria_resolutiva.evolving_address_state_v2 import (
    EvolvingAddressStateJournalV2,
    PersistentEvolvingAddressStateJournalV2,
)
from memoria_resolutiva.structural_branch_state_v2 import DynamicStructuralBranchResolverV2
from memoria_resolutiva.structural_trajectory_v2 import StructuralTrajectoryIndex
from memoria_resolutiva.temporal_state_v2 import (
    TemporalStateOperationV2,
    TemporalStateResolverV2,
    temporal_possibilities_from_branch_state,
)


def _journal() -> EvolvingAddressStateJournalV2:
    journal = EvolvingAddressStateJournalV2()
    journal.append(
        42,
        hierarchy_id="h",
        sequence=10,
        payload_addresses=[100, 101],
        trajectory_ids=["t1"],
        provenance_ids=["p1"],
    )
    journal.append(
        42,
        hierarchy_id="h",
        sequence=20,
        payload_addresses=[101, 102],
        trajectory_ids=["t2"],
        provenance_ids=["p2"],
    )
    journal.append(
        42,
        hierarchy_id="h",
        sequence=30,
        payload_addresses=[101, 102, 103],
        trajectory_ids=["t3"],
        provenance_ids=["p3"],
    )
    return journal


def _trajectory_index(rows, *, hierarchy_id="h") -> StructuralTrajectoryIndex:
    index = StructuralTrajectoryIndex()
    for sequence, addresses in enumerate(rows):
        index.ingest_addresses(
            addresses,
            hierarchy_id=hierarchy_id,
            source_id=f"source:{sequence}",
            sequence=sequence,
        )
    return index


def test_current_previous_and_history_are_explicit_read_only_operations():
    journal = _journal()
    resolver = TemporalStateResolverV2(journal)
    before = journal.snapshot()

    current = resolver.resolve(42, hierarchy_id="h", operation=TemporalStateOperationV2.CURRENT)
    previous = resolver.resolve(42, hierarchy_id="h", operation=TemporalStateOperationV2.PREVIOUS)
    history = resolver.resolve(42, hierarchy_id="h", operation=TemporalStateOperationV2.HISTORY)

    assert current.resolved is True
    assert current.revision is not None
    assert current.revision.sequence == 30
    assert current.revision.payload_addresses == (101, 102, 103)

    assert previous.resolved is True
    assert previous.revision is not None
    assert previous.revision.sequence == 20
    assert previous.revision.payload_addresses == (101, 102)

    assert history.resolved is True
    assert tuple(item.sequence for item in history.revisions) == (10, 20, 30)
    assert journal.snapshot() == before


def test_forward_and_reverse_navigate_observed_revisions_only():
    journal = _journal()
    resolver = TemporalStateResolverV2(journal)
    history = journal.history(42, hierarchy_id="h")
    middle = history[1]

    reverse = resolver.resolve(
        42,
        hierarchy_id="h",
        operation=TemporalStateOperationV2.REVERSE,
        anchor_revision_id=middle.revision_id,
    )
    forward = resolver.resolve(
        42,
        hierarchy_id="h",
        operation=TemporalStateOperationV2.FORWARD,
        anchor_revision_id=middle.revision_id,
    )

    assert reverse.resolved is True
    assert reverse.revision == history[0]
    assert forward.resolved is True
    assert forward.revision == history[2]

    at_end = resolver.resolve(
        42,
        hierarchy_id="h",
        operation=TemporalStateOperationV2.FORWARD,
        anchor_revision_id=history[-1].revision_id,
    )
    assert at_end.resolved is False
    assert at_end.reason == "forward-boundary"


def test_change_exposes_ordered_structural_delta_without_domain_predicates():
    journal = _journal()
    resolver = TemporalStateResolverV2(journal)

    result = resolver.resolve(42, hierarchy_id="h", operation=TemporalStateOperationV2.CHANGE)

    assert result.resolved is True
    assert result.change is not None
    assert result.change.retained_addresses == (101, 102)
    assert result.change.removed_addresses == ()
    assert result.change.added_addresses == (103,)
    assert result.change.state_changed is True
    assert result.reason == "observed-state-change"


def test_evidence_reinforcement_does_not_count_as_world_state_change():
    journal = EvolvingAddressStateJournalV2()
    journal.append(
        9,
        hierarchy_id="h",
        sequence=1,
        payload_addresses=[7, 8],
        trajectory_ids=["t1"],
        provenance_ids=["p1"],
    )
    journal.append(
        9,
        hierarchy_id="h",
        sequence=2,
        payload_addresses=[7, 8],
        trajectory_ids=["t1", "t2"],
        provenance_ids=["p1", "p2"],
    )
    resolver = TemporalStateResolverV2(journal)

    result = resolver.resolve(9, hierarchy_id="h", operation=TemporalStateOperationV2.CHANGE)

    assert result.change is not None
    assert result.change.state_changed is False
    assert result.change.evidence_changed is True
    assert result.reason == "observed-state-stable"


def test_change_preserves_reordering_as_structural_change():
    journal = EvolvingAddressStateJournalV2()
    journal.append(5, hierarchy_id="h", sequence=1, payload_addresses=[1, 2])
    journal.append(5, hierarchy_id="h", sequence=2, payload_addresses=[2, 1])
    resolver = TemporalStateResolverV2(journal)

    result = resolver.resolve(5, hierarchy_id="h", operation="change")

    assert result.change is not None
    assert result.change.state_changed is True
    assert len(result.change.retained_addresses) == 1
    assert len(result.change.removed_addresses) == 1
    assert len(result.change.added_addresses) == 1


def test_first_revision_has_no_previous_or_change_answer():
    journal = EvolvingAddressStateJournalV2()
    journal.append(1, hierarchy_id="h", sequence=1, payload_addresses=[10])
    resolver = TemporalStateResolverV2(journal)

    previous = resolver.resolve(1, hierarchy_id="h", operation="previous")
    change = resolver.resolve(1, hierarchy_id="h", operation="change")

    assert previous.resolved is False
    assert previous.reason == "no-previous-revision"
    assert change.resolved is False
    assert change.change is None
    assert change.reason == "no-previous-revision-for-change"


def test_missing_history_is_unresolved_not_ambiguous():
    resolver = TemporalStateResolverV2(EvolvingAddressStateJournalV2())

    result = resolver.resolve(404, hierarchy_id="h", operation="current")

    assert result.resolved is False
    assert result.ambiguous is False
    assert result.reason == "no-state-history"


def test_anchor_must_belong_to_requested_stable_address():
    journal = _journal()
    other = journal.append(99, hierarchy_id="h", sequence=1, payload_addresses=[1])
    resolver = TemporalStateResolverV2(journal)

    with pytest.raises(LookupError, match="anchor revision"):
        resolver.resolve(
            42,
            hierarchy_id="h",
            operation="reverse",
            anchor_revision_id=other.revision_id,
        )


def test_persistent_temporal_state_survives_cold_reopen(tmp_path: Path):
    root = tmp_path / "state"
    first = PersistentEvolvingAddressStateJournalV2(
        root,
        backend="sqlite",
        allow_fallback=False,
    )
    first.append(
        77,
        hierarchy_id="h",
        sequence=10,
        payload_addresses=[1, 2],
        trajectory_ids=["t1"],
        provenance_ids=["p1"],
    )
    first.append(
        77,
        hierarchy_id="h",
        sequence=20,
        payload_addresses=[2, 3],
        trajectory_ids=["t2"],
        provenance_ids=["p2"],
    )
    first_result = TemporalStateResolverV2(first).resolve(
        77,
        hierarchy_id="h",
        operation="change",
    )

    restarted = PersistentEvolvingAddressStateJournalV2(
        root,
        backend="sqlite",
        allow_fallback=False,
    )
    restarted_result = TemporalStateResolverV2(restarted).resolve(
        77,
        hierarchy_id="h",
        operation="change",
    )

    assert restarted_result == first_result
    assert restarted_result.change is not None
    assert restarted_result.change.removed_addresses == (1,)
    assert restarted_result.change.added_addresses == (3,)


def test_competing_r4_branches_remain_possible_futures_not_observed_history():
    index = _trajectory_index([
        [1, 2, 3],
        [1, 2, 4],
    ])
    dynamic = DynamicStructuralBranchResolverV2(index)
    branch_state = dynamic.begin_addresses([1, 2], hierarchy_id="h")

    journal = EvolvingAddressStateJournalV2()
    journal.append(500, hierarchy_id="h", sequence=1, payload_addresses=[1, 2])
    before = journal.snapshot()

    possibilities = temporal_possibilities_from_branch_state(branch_state)

    assert possibilities.resolved is False
    assert possibilities.ambiguous is True
    assert {(item.kind, item.address) for item in possibilities.outcomes} == {
        ("next-address", 3),
        ("next-address", 4),
    }
    assert journal.snapshot() == before


def test_terminal_and_continuing_r4_outcomes_remain_temporally_ambiguous():
    index = _trajectory_index([
        [1, 2],
        [1, 2, 3],
    ])
    state = DynamicStructuralBranchResolverV2(index).begin_addresses(
        [1, 2],
        hierarchy_id="h",
    )

    possibilities = temporal_possibilities_from_branch_state(state)

    assert possibilities.ambiguous is True
    assert possibilities.resolved is False
    assert {(item.kind, item.address) for item in possibilities.outcomes} == {
        ("next-address", 3),
        ("terminal", None),
    }


def test_single_branch_future_is_resolved_but_not_admitted_as_history():
    index = _trajectory_index([[1, 2, 3]])
    state = DynamicStructuralBranchResolverV2(index).begin_addresses(
        [1, 2],
        hierarchy_id="h",
    )

    possibilities = temporal_possibilities_from_branch_state(state)

    assert possibilities.resolved is True
    assert possibilities.ambiguous is False
    assert possibilities.resolved_outcome is not None
    assert possibilities.resolved_outcome.address == 3
    assert possibilities.reason == "single-next-address"


def test_temporal_core_contains_no_language_mapping():
    assert {item.value for item in TemporalStateOperationV2} == {
        "current",
        "previous",
        "history",
        "change",
        "forward",
        "reverse",
    }
