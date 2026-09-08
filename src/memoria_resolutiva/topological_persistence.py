from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sqlite3

from .topological_memory import (
    AddressSpace,
    RawMemory,
    TemporalEvent,
    TemporalEventStore,
    TopologicalNode,
    Transition,
)


_SCHEMA_VERSION = 1


@dataclass(frozen=True, slots=True)
class PersistenceStats:
    nodes: int
    raw_memories: int
    events: int
    transitions: int


def _connect(path: str | Path) -> sqlite3.Connection:
    connection = sqlite3.connect(str(path))
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def _ensure_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS topology_meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS topology_nodes (
            address TEXT PRIMARY KEY,
            kind TEXT NOT NULL,
            canonical_value TEXT NOT NULL,
            occurrences INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS topology_components (
            parent_address TEXT NOT NULL,
            position INTEGER NOT NULL,
            child_address TEXT NOT NULL,
            PRIMARY KEY (parent_address, position)
        );
        CREATE TABLE IF NOT EXISTS topology_edges (
            parent_address TEXT NOT NULL,
            child_address TEXT NOT NULL,
            PRIMARY KEY (parent_address, child_address)
        );
        CREATE TABLE IF NOT EXISTS topology_raw (
            address TEXT PRIMARY KEY,
            text TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS temporal_events (
            event_id TEXT PRIMARY KEY,
            sequence INTEGER NOT NULL UNIQUE,
            subject_address TEXT NOT NULL,
            attribute_address TEXT NOT NULL,
            value_address TEXT NOT NULL,
            source TEXT NOT NULL,
            raw_memory_address TEXT,
            event_time TEXT,
            ingestion_time TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS temporal_transitions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject_address TEXT NOT NULL,
            attribute_address TEXT NOT NULL,
            from_value_address TEXT NOT NULL,
            to_value_address TEXT NOT NULL,
            from_sequence INTEGER NOT NULL,
            to_sequence INTEGER NOT NULL
        );
        """
    )


def save_snapshot(
    path: str | Path,
    addresses: AddressSpace,
    store: TemporalEventStore,
) -> PersistenceStats:
    """Persist one complete experimental topology + temporal snapshot atomically.

    This adapter is intentionally separate from RC7/EvidenceCore/BDR persistence.
    It serializes the current experimental in-memory structures without changing
    their runtime semantics.
    """
    with _connect(path) as connection:
        _ensure_schema(connection)
        connection.executescript(
            """
            DELETE FROM temporal_transitions;
            DELETE FROM temporal_events;
            DELETE FROM topology_raw;
            DELETE FROM topology_edges;
            DELETE FROM topology_components;
            DELETE FROM topology_nodes;
            DELETE FROM topology_meta;
            """
        )
        meta = {
            "schema_version": str(_SCHEMA_VERSION),
            "next_sequence": str(store._next_sequence),
            "ingestions": str(addresses._ingestions),
            "new_nodes": str(addresses._new_nodes),
            "reused_nodes": str(addresses._reused_nodes),
        }
        connection.executemany(
            "INSERT INTO topology_meta(key, value) VALUES (?, ?)",
            sorted(meta.items()),
        )

        for node in sorted(addresses._nodes.values(), key=lambda item: item.address):
            connection.execute(
                "INSERT INTO topology_nodes(address, kind, canonical_value, occurrences) VALUES (?, ?, ?, ?)",
                (node.address, node.kind, node.canonical_value, node.occurrences),
            )
            connection.executemany(
                "INSERT INTO topology_components(parent_address, position, child_address) VALUES (?, ?, ?)",
                ((node.address, position, child) for position, child in enumerate(node.components)),
            )
            connection.executemany(
                "INSERT INTO topology_edges(parent_address, child_address) VALUES (?, ?)",
                ((node.address, child) for child in sorted(node.edges_out)),
            )

        connection.executemany(
            "INSERT INTO topology_raw(address, text) VALUES (?, ?)",
            ((raw.address, raw.text) for raw in sorted(addresses._raw.values(), key=lambda item: item.address)),
        )

        connection.executemany(
            """
            INSERT INTO temporal_events(
                event_id, sequence, subject_address, attribute_address, value_address,
                source, raw_memory_address, event_time, ingestion_time
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                (
                    event.event_id,
                    event.sequence,
                    event.subject_address,
                    event.attribute_address,
                    event.value_address,
                    event.source,
                    event.raw_memory_address,
                    event.event_time,
                    event.ingestion_time,
                )
                for event in sorted(store._events, key=lambda item: item.sequence)
            ),
        )
        connection.executemany(
            """
            INSERT INTO temporal_transitions(
                subject_address, attribute_address, from_value_address, to_value_address,
                from_sequence, to_sequence
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                (
                    transition.subject_address,
                    transition.attribute_address,
                    transition.from_value_address,
                    transition.to_value_address,
                    transition.from_sequence,
                    transition.to_sequence,
                )
                for transition in store._transitions
            ),
        )

    return PersistenceStats(
        nodes=len(addresses._nodes),
        raw_memories=len(addresses._raw),
        events=len(store._events),
        transitions=len(store._transitions),
    )


def load_snapshot(path: str | Path) -> tuple[AddressSpace, TemporalEventStore]:
    addresses = AddressSpace()
    store = TemporalEventStore(addresses)
    with _connect(path) as connection:
        _ensure_schema(connection)
        meta = dict(connection.execute("SELECT key, value FROM topology_meta"))
        if not meta:
            raise ValueError("topological snapshot is empty")
        if int(meta.get("schema_version", "0")) != _SCHEMA_VERSION:
            raise ValueError("unsupported topological snapshot schema version")

        for address, kind, canonical_value, occurrences in connection.execute(
            "SELECT address, kind, canonical_value, occurrences FROM topology_nodes ORDER BY address"
        ):
            addresses._nodes[address] = TopologicalNode(
                address=address,
                kind=kind,
                canonical_value=canonical_value,
                occurrences=int(occurrences),
            )

        components: dict[str, list[str]] = {}
        for parent, _position, child in connection.execute(
            "SELECT parent_address, position, child_address FROM topology_components ORDER BY parent_address, position"
        ):
            components.setdefault(parent, []).append(child)
        for parent, children in components.items():
            node = addresses._nodes.get(parent)
            if node is None:
                raise ValueError(f"snapshot references unknown component parent: {parent}")
            node.components = tuple(children)

        for parent, child in connection.execute(
            "SELECT parent_address, child_address FROM topology_edges ORDER BY parent_address, child_address"
        ):
            parent_node = addresses._nodes.get(parent)
            child_node = addresses._nodes.get(child)
            if parent_node is None or child_node is None:
                raise ValueError("snapshot edge references unknown node")
            parent_node.edges_out.add(child)
            child_node.edges_in.add(parent)

        for address, text in connection.execute("SELECT address, text FROM topology_raw ORDER BY address"):
            addresses._raw[address] = RawMemory(address, text)

        addresses._ingestions = int(meta.get("ingestions", "0"))
        addresses._new_nodes = int(meta.get("new_nodes", str(len(addresses._nodes))))
        addresses._reused_nodes = int(meta.get("reused_nodes", "0"))

        store._events = [
            TemporalEvent(
                event_id=event_id,
                sequence=int(sequence),
                subject_address=subject,
                attribute_address=attribute,
                value_address=value,
                source=source,
                raw_memory_address=raw_address,
                event_time=event_time,
                ingestion_time=ingestion_time,
            )
            for (
                event_id,
                sequence,
                subject,
                attribute,
                value,
                source,
                raw_address,
                event_time,
                ingestion_time,
            ) in connection.execute(
                """
                SELECT event_id, sequence, subject_address, attribute_address, value_address,
                       source, raw_memory_address, event_time, ingestion_time
                FROM temporal_events ORDER BY sequence
                """
            )
        ]
        store._transitions = [
            Transition(
                subject_address=subject,
                attribute_address=attribute,
                from_value_address=from_value,
                to_value_address=to_value,
                from_sequence=int(from_sequence),
                to_sequence=int(to_sequence),
            )
            for subject, attribute, from_value, to_value, from_sequence, to_sequence in connection.execute(
                """
                SELECT subject_address, attribute_address, from_value_address, to_value_address,
                       from_sequence, to_sequence
                FROM temporal_transitions ORDER BY id
                """
            )
        ]
        store._next_sequence = int(meta.get("next_sequence", "1"))

    return addresses, store
