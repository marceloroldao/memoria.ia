from __future__ import annotations

from pathlib import Path

import pytest

from memoria_resolutiva.bdr_store import native_bdr_available
from memoria_resolutiva.evolving_address_state_v2 import (
    EvolvingAddressStateJournalV2,
    PersistentEvolvingAddressStateJournalV2,
)


def test_stable_address_keeps_append_only_revision_history():
    journal = EvolvingAddressStateJournalV2()

    first = journal.append(
        42,
        hierarchy_id="world",
        sequence=10,
        payload_addresses=[100, 101],
        trajectory_ids=["t1"],
        provenance_ids=["obs1"],
    )
    second = journal.append(
        42,
        hierarchy_id="world",
        sequence=20,
        payload_addresses=[200],
        trajectory_ids=["t2"],
        provenance_ids=["obs2"],
    )

    assert first.address == second.address == 42
    assert first.predecessor_revision_id is None
    assert second.predecessor_revision_id == first.revision_id
    assert journal.current_revision(42, hierarchy_id="world") == second
    assert journal.history(42, hierarchy_id="world") == (first, second)
    assert journal.previous_revision(second.revision_id) == first
    assert journal.next_revision(first.revision_id) == second


def test_current_revision_is_navigation_not_destructive_truth():
    journal = EvolvingAddressStateJournalV2()
    old = journal.append(
        7,
        hierarchy_id="context",
        sequence=1,
        payload_addresses=[11],
        provenance_ids=["old-evidence"],
    )
    new = journal.append(
        7,
        hierarchy_id="context",
        sequence=2,
        payload_addresses=[12],
        provenance_ids=["new-evidence"],
    )

    assert journal.current_revision(7, hierarchy_id="context") == new
    assert old in journal.history(7, hierarchy_id="context")
    assert new in journal.history(7, hierarchy_id="context")
    assert journal.revision_count == 2


def test_exact_revision_replay_is_idempotent_but_same_sequence_conflict_is_rejected():
    journal = EvolvingAddressStateJournalV2()
    first = journal.append(
        9,
        hierarchy_id="h",
        sequence=3,
        payload_addresses=[1, 2],
        trajectory_ids=["t"],
        provenance_ids=["p"],
    )
    replay = journal.append(
        9,
        hierarchy_id="h",
        sequence=3,
        payload_addresses=[1, 2],
        trajectory_ids=["t"],
        provenance_ids=["p"],
    )
    assert replay == first
    assert journal.revision_count == 1

    with pytest.raises(ValueError, match="same address sequence"):
        journal.append(
            9,
            hierarchy_id="h",
            sequence=3,
            payload_addresses=[99],
            trajectory_ids=["t"],
            provenance_ids=["p"],
        )


def test_address_state_isolated_by_hierarchy():
    journal = EvolvingAddressStateJournalV2()
    left = journal.append(5, hierarchy_id="left", sequence=1, payload_addresses=[10])
    right = journal.append(5, hierarchy_id="right", sequence=1, payload_addresses=[20])

    assert journal.current_revision(5, hierarchy_id="left") == left
    assert journal.current_revision(5, hierarchy_id="right") == right
    assert left.revision_id != right.revision_id


def test_persistent_address_state_survives_cold_reopen(tmp_path: Path):
    root = tmp_path / "address-state"
    first = PersistentEvolvingAddressStateJournalV2(
        root,
        backend="sqlite",
        allow_fallback=False,
    )
    r1 = first.append(
        1234,
        hierarchy_id="window:alpha",
        sequence=100,
        payload_addresses=[10, 20],
        trajectory_ids=["trajectory:a"],
        provenance_ids=["observation:a"],
    )
    r2 = first.append(
        1234,
        hierarchy_id="window:alpha",
        sequence=101,
        payload_addresses=[20, 30],
        trajectory_ids=["trajectory:b"],
        provenance_ids=["observation:b"],
    )

    restarted = PersistentEvolvingAddressStateJournalV2(
        root,
        backend="sqlite",
        allow_fallback=False,
    )
    assert restarted.backend == "sqlite"
    assert restarted.history(1234, hierarchy_id="window:alpha") == (r1, r2)
    assert restarted.current_revision(1234, hierarchy_id="window:alpha") == r2
    assert restarted.previous_revision(r2.revision_id) == r1
    assert restarted.next_revision(r1.revision_id) == r2


def test_persistent_exact_replay_does_not_append_second_index_row(tmp_path: Path):
    root = tmp_path / "address-state"
    state = PersistentEvolvingAddressStateJournalV2(
        root,
        backend="sqlite",
        allow_fallback=False,
    )
    first = state.append(
        77,
        hierarchy_id="h",
        sequence=1,
        payload_addresses=[8],
        provenance_ids=["obs"],
    )
    size_before = state.index_path.read_bytes()

    replay = state.append(
        77,
        hierarchy_id="h",
        sequence=1,
        payload_addresses=[8],
        provenance_ids=["obs"],
    )

    assert replay == first
    assert state.index_path.read_bytes() == size_before


@pytest.mark.skipif(not native_bdr_available(), reason="native BDR extension not built")
def test_evolving_address_state_cold_reopen_on_native_bdr(tmp_path: Path):
    root = tmp_path / "address-state-bdr"
    first = PersistentEvolvingAddressStateJournalV2(
        root,
        backend="bdr",
        allow_fallback=False,
    )
    revision = first.append(
        500,
        hierarchy_id="robot",
        sequence=1,
        payload_addresses=[501, 502],
        trajectory_ids=["trajectory:robot"],
        provenance_ids=["sensor:1"],
    )
    assert first.backend == "bdr"

    restarted = PersistentEvolvingAddressStateJournalV2(
        root,
        backend="bdr",
        allow_fallback=False,
    )
    assert restarted.current_revision(500, hierarchy_id="robot") == revision
