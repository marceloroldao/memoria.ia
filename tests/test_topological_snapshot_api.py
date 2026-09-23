from __future__ import annotations

import pytest

from memoria_resolutiva.topological_memory import (
    AddressSpace,
    RawMemory,
    TemporalEvent,
    TemporalEventStore,
    TopologicalNode,
    Transition,
)


def test_public_snapshot_round_trip_preserves_catalog_and_history():
    addresses = AddressSpace()
    store = TemporalEventStore(addresses)
    raw = addresses.ingest_text("Minha camisa é azul.")
    store.observe_state("minha camisa", "cor", "azul", sequence=12, raw_memory_address=raw.raw_memory_address)

    restored_addresses = AddressSpace()
    counters = addresses.snapshot_counters()
    restored_addresses.restore_snapshot(
        nodes=addresses.iter_nodes(),
        raw_memories=addresses.iter_raw_memories(),
        ingestions=counters["ingestions"],
        new_nodes=counters["new_nodes"],
        reused_nodes=counters["reused_nodes"],
    )
    restored_store = TemporalEventStore(restored_addresses)
    restored_store.restore_history(
        events=store.iter_events(),
        transitions=store.iter_transitions(),
        next_sequence=store.next_sequence,
    )

    assert restored_addresses.metrics() == addresses.metrics()
    assert restored_addresses.iter_raw_memories() == addresses.iter_raw_memories()
    assert restored_store.iter_events() == store.iter_events()
    assert restored_store.next_sequence == 13


def test_restore_rejects_duplicate_node_addresses():
    node = TopologicalNode("mt1:duplicate", "value", "x", occurrences=1)
    addresses = AddressSpace()
    with pytest.raises(ValueError, match="duplicate restored node address"):
        addresses.restore_snapshot(
            nodes=(node, node),
            raw_memories=(),
            ingestions=0,
            new_nodes=1,
            reused_nodes=0,
        )


def test_restore_rejects_unknown_component_or_edge():
    component_parent = TopologicalNode(
        "mt1:parent",
        "word",
        "parent",
        occurrences=1,
        components=("mt1:missing",),
    )
    addresses = AddressSpace()
    with pytest.raises(ValueError, match="component references unknown node"):
        addresses.restore_snapshot(
            nodes=(component_parent,),
            raw_memories=(),
            ingestions=0,
            new_nodes=1,
            reused_nodes=0,
        )

    edge_parent = TopologicalNode(
        "mt1:parent2",
        "word",
        "parent2",
        occurrences=1,
        edges_out={"mt1:missing2"},
    )
    addresses = AddressSpace()
    with pytest.raises(ValueError, match="edge references unknown node"):
        addresses.restore_snapshot(
            nodes=(edge_parent,),
            raw_memories=(),
            ingestions=0,
            new_nodes=1,
            reused_nodes=0,
        )


def _restorable_slot() -> tuple[AddressSpace, str, str, str, str]:
    addresses = AddressSpace()
    raw = addresses.ingest_text("objeto cor azul")
    store = TemporalEventStore(addresses)
    event = store.observe_state("objeto", "cor", "azul", sequence=3, raw_memory_address=raw.raw_memory_address)
    return addresses, event.subject_address, event.attribute_address, event.value_address, raw.raw_memory_address


def test_restore_history_rejects_duplicate_sequences():
    addresses, subject, attribute, value, raw_address = _restorable_slot()
    event_a = TemporalEvent("E3", 3, subject, attribute, value, "USER_CONFIRMED", raw_address, None, "t1")
    event_b = TemporalEvent("E3b", 3, subject, attribute, value, "USER_CONFIRMED", raw_address, None, "t2")
    store = TemporalEventStore(addresses)
    with pytest.raises(ValueError, match="duplicate temporal sequence"):
        store.restore_history(events=(event_a, event_b), transitions=(), next_sequence=4)


def test_restore_history_rejects_unknown_transition_sequence_and_backward_next_sequence():
    addresses, subject, attribute, value, raw_address = _restorable_slot()
    event = TemporalEvent("E3", 3, subject, attribute, value, "USER_CONFIRMED", raw_address, None, "t1")
    bad_transition = Transition(subject, attribute, value, value, 3, 9)
    store = TemporalEventStore(addresses)
    with pytest.raises(ValueError, match="unknown event sequence"):
        store.restore_history(events=(event,), transitions=(bad_transition,), next_sequence=10)

    store = TemporalEventStore(addresses)
    with pytest.raises(ValueError, match="move temporal time backward"):
        store.restore_history(events=(event,), transitions=(), next_sequence=3)


def test_restore_history_rejects_unknown_raw_reference():
    addresses, subject, attribute, value, _raw_address = _restorable_slot()
    event = TemporalEvent("E3", 3, subject, attribute, value, "USER_CONFIRMED", "raw1:missing", None, "t1")
    store = TemporalEventStore(addresses)
    with pytest.raises(ValueError, match="unknown raw memory"):
        store.restore_history(events=(event,), transitions=(), next_sequence=4)
