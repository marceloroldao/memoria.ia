from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Protocol

from .bdr_atomic_bridge import CtypesAtomicBDR
from .topological_memory import (
    AddressSpace,
    RawMemory,
    TemporalEvent,
    TemporalEventStore,
    TopologicalNode,
    Transition,
)


_SCHEMA_VERSION = 1
_ROOT_KEY = "memoria.topology.v1/root"


class AtomicBatchBackend(Protocol):
    def write_batch(self, puts: list[tuple[str, bytes]]) -> int: ...
    def get(self, key: str) -> bytes | None: ...


@dataclass(frozen=True, slots=True)
class BDRPersistenceStats:
    nodes: int
    raw_memories: int
    events: int
    transitions: int
    physical_records: int
    bdr_sequence: int


def _encode_json(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _decode_json(data: bytes | None, key: str) -> object:
    if data is None:
        raise ValueError(f"missing BDR record: {key}")
    try:
        return json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid BDR JSON record: {key}") from exc


def save_snapshot_to_backend(
    backend: AtomicBatchBackend,
    addresses: AddressSpace,
    store: TemporalEventStore,
) -> BDRPersistenceStats:
    """Persist one complete experimental topology as one BDR logical batch."""
    puts: list[tuple[str, bytes]] = []
    node_keys: list[str] = []
    raw_keys: list[str] = []
    event_keys: list[str] = []
    transition_keys: list[str] = []

    for node in addresses.iter_nodes():
        key = f"memoria.topology.v1/node/{node.address}"
        node_keys.append(key)
        puts.append((key, _encode_json({
            "address": node.address,
            "kind": node.kind,
            "canonical_value": node.canonical_value,
            "occurrences": node.occurrences,
            "components": list(node.components),
            "edges_out": sorted(node.edges_out),
        })))

    for raw in addresses.iter_raw_memories():
        key = f"memoria.topology.v1/raw/{raw.address}"
        raw_keys.append(key)
        puts.append((key, _encode_json({"address": raw.address, "text": raw.text})))

    for event in store.iter_events():
        key = f"memoria.topology.v1/event/{event.sequence:020d}"
        event_keys.append(key)
        puts.append((key, _encode_json({
            "event_id": event.event_id,
            "sequence": event.sequence,
            "subject_address": event.subject_address,
            "attribute_address": event.attribute_address,
            "value_address": event.value_address,
            "source": event.source,
            "raw_memory_address": event.raw_memory_address,
            "event_time": event.event_time,
            "ingestion_time": event.ingestion_time,
        })))

    for index, transition in enumerate(store.iter_transitions()):
        key = f"memoria.topology.v1/transition/{index:020d}"
        transition_keys.append(key)
        puts.append((key, _encode_json({
            "subject_address": transition.subject_address,
            "attribute_address": transition.attribute_address,
            "from_value_address": transition.from_value_address,
            "to_value_address": transition.to_value_address,
            "from_sequence": transition.from_sequence,
            "to_sequence": transition.to_sequence,
        })))

    counters = addresses.snapshot_counters()
    manifest = {
        "schema_version": _SCHEMA_VERSION,
        "next_sequence": store.next_sequence,
        "ingestions": counters["ingestions"],
        "new_nodes": counters["new_nodes"],
        "reused_nodes": counters["reused_nodes"],
        "node_keys": node_keys,
        "raw_keys": raw_keys,
        "event_keys": event_keys,
        "transition_keys": transition_keys,
    }
    puts.append((_ROOT_KEY, _encode_json(manifest)))
    sequence = backend.write_batch(puts)
    return BDRPersistenceStats(
        nodes=len(node_keys),
        raw_memories=len(raw_keys),
        events=len(event_keys),
        transitions=len(transition_keys),
        physical_records=len(puts),
        bdr_sequence=sequence,
    )


def load_snapshot_from_backend(backend: AtomicBatchBackend) -> tuple[AddressSpace, TemporalEventStore]:
    manifest_raw = _decode_json(backend.get(_ROOT_KEY), _ROOT_KEY)
    if not isinstance(manifest_raw, dict):
        raise ValueError("invalid BDR topology root manifest")
    manifest = manifest_raw
    if int(manifest.get("schema_version", 0)) != _SCHEMA_VERSION:
        raise ValueError("unsupported BDR topology snapshot schema version")

    nodes: list[TopologicalNode] = []
    for key in manifest.get("node_keys", []):
        record = _decode_json(backend.get(str(key)), str(key))
        if not isinstance(record, dict):
            raise ValueError(f"invalid BDR node record: {key}")
        nodes.append(TopologicalNode(
            address=str(record["address"]),
            kind=str(record["kind"]),
            canonical_value=str(record["canonical_value"]),
            occurrences=int(record["occurrences"]),
            components=tuple(str(item) for item in record.get("components", [])),
            edges_out={str(item) for item in record.get("edges_out", [])},
        ))

    raw_memories: list[RawMemory] = []
    for key in manifest.get("raw_keys", []):
        record = _decode_json(backend.get(str(key)), str(key))
        if not isinstance(record, dict):
            raise ValueError(f"invalid BDR raw-memory record: {key}")
        raw_memories.append(RawMemory(str(record["address"]), str(record["text"])))

    addresses = AddressSpace()
    addresses.restore_snapshot(
        nodes=nodes,
        raw_memories=raw_memories,
        ingestions=int(manifest.get("ingestions", 0)),
        new_nodes=int(manifest.get("new_nodes", len(nodes))),
        reused_nodes=int(manifest.get("reused_nodes", 0)),
    )

    events: list[TemporalEvent] = []
    for key in manifest.get("event_keys", []):
        record = _decode_json(backend.get(str(key)), str(key))
        if not isinstance(record, dict):
            raise ValueError(f"invalid BDR temporal event record: {key}")
        events.append(TemporalEvent(
            event_id=str(record["event_id"]),
            sequence=int(record["sequence"]),
            subject_address=str(record["subject_address"]),
            attribute_address=str(record["attribute_address"]),
            value_address=str(record["value_address"]),
            source=str(record["source"]),
            raw_memory_address=None if record.get("raw_memory_address") is None else str(record["raw_memory_address"]),
            event_time=None if record.get("event_time") is None else str(record["event_time"]),
            ingestion_time=str(record["ingestion_time"]),
        ))

    transitions: list[Transition] = []
    for key in manifest.get("transition_keys", []):
        record = _decode_json(backend.get(str(key)), str(key))
        if not isinstance(record, dict):
            raise ValueError(f"invalid BDR transition record: {key}")
        transitions.append(Transition(
            subject_address=str(record["subject_address"]),
            attribute_address=str(record["attribute_address"]),
            from_value_address=str(record["from_value_address"]),
            to_value_address=str(record["to_value_address"]),
            from_sequence=int(record["from_sequence"]),
            to_sequence=int(record["to_sequence"]),
        ))

    store = TemporalEventStore(addresses)
    store.restore_history(
        events=events,
        transitions=transitions,
        next_sequence=int(manifest.get("next_sequence", 1)),
    )
    return addresses, store


def save_snapshot_bdr(
    root: str | Path,
    library_path: str | Path,
    addresses: AddressSpace,
    store: TemporalEventStore,
) -> BDRPersistenceStats:
    with CtypesAtomicBDR(root, library_path) as backend:
        return save_snapshot_to_backend(backend, addresses, store)


def load_snapshot_bdr(
    root: str | Path,
    library_path: str | Path,
) -> tuple[AddressSpace, TemporalEventStore]:
    with CtypesAtomicBDR(root, library_path) as backend:
        return load_snapshot_from_backend(backend)
