from __future__ import annotations

import json
import os
from pathlib import Path
import statistics
import tempfile
import time

from memoria_resolutiva.topological_bdr_persistence import load_snapshot_bdr, save_snapshot_bdr
from memoria_resolutiva.topological_memory import AddressSpace, TemporalEventStore, TemporalOperator
from memoria_resolutiva.topological_persistence import load_snapshot, save_snapshot


def _disk_bytes(path: Path) -> int:
    if not path.exists():
        return 0
    if path.is_file():
        return path.stat().st_size
    return sum(item.stat().st_size for item in path.rglob("*") if item.is_file())


def _percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * q)))
    return ordered[index]


def _build_fixture(count: int = 240) -> tuple[AddressSpace, TemporalEventStore, list[float]]:
    addresses = AddressSpace()
    store = TemporalEventStore(addresses)
    latencies_ms: list[float] = []
    colors = ("azul", "preta", "branca", "vermelha")
    for i in range(count):
        subject = f"objeto {i % 24}"
        attribute = "cor" if i % 3 else "estado"
        value = colors[(i // 24) % len(colors)] if attribute == "cor" else f"s{i % 7}"
        raw = f"{subject} {attribute} {value} evento {i}."
        started = time.perf_counter_ns()
        ingestion = addresses.ingest_text(raw)
        store.observe_state(subject, attribute, value, raw_memory_address=ingestion.raw_memory_address)
        latencies_ms.append((time.perf_counter_ns() - started) / 1_000_000)
    return addresses, store, latencies_ms


def _query_latencies(store: TemporalEventStore, rounds: int = 120) -> list[float]:
    values: list[float] = []
    for i in range(rounds):
        subject = f"objeto {i % 24}"
        attribute = "cor" if i % 3 else "estado"
        started = time.perf_counter_ns()
        store.resolve(subject, attribute, TemporalOperator.CURRENT)
        values.append((time.perf_counter_ns() - started) / 1_000_000)
    return values


def _latency_summary(values: list[float]) -> dict[str, float]:
    return {
        "mean_ms": statistics.fmean(values) if values else 0.0,
        "p50_ms": _percentile(values, 0.50),
        "p95_ms": _percentile(values, 0.95),
        "max_ms": max(values) if values else 0.0,
    }


def main() -> None:
    library = os.environ.get("BDR_ATOMIC_LIB")
    if not library:
        raise SystemExit("BDR_ATOMIC_LIB is required")

    addresses, store, ingestion_latencies = _build_fixture()
    query_before = _query_latencies(store)
    baseline_metrics = addresses.metrics()

    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        sqlite_path = root / "topology.sqlite3"
        bdr_root = root / "bdr"

        started = time.perf_counter_ns()
        sqlite_stats = save_snapshot(sqlite_path, addresses, store)
        sqlite_save_ms = (time.perf_counter_ns() - started) / 1_000_000
        sqlite_bytes = _disk_bytes(sqlite_path)

        started = time.perf_counter_ns()
        sqlite_addresses, sqlite_store = load_snapshot(sqlite_path)
        sqlite_load_ms = (time.perf_counter_ns() - started) / 1_000_000
        sqlite_query = _query_latencies(sqlite_store)

        started = time.perf_counter_ns()
        bdr_stats = save_snapshot_bdr(bdr_root, library, addresses, store)
        bdr_save_ms = (time.perf_counter_ns() - started) / 1_000_000
        bdr_bytes = _disk_bytes(bdr_root)

        started = time.perf_counter_ns()
        bdr_addresses, bdr_store = load_snapshot_bdr(bdr_root, library)
        bdr_load_ms = (time.perf_counter_ns() - started) / 1_000_000
        bdr_query = _query_latencies(bdr_store)

        current_original = store.resolve("objeto 1", "cor", TemporalOperator.CURRENT)
        current_sqlite = sqlite_store.resolve("objeto 1", "cor", TemporalOperator.CURRENT)
        current_bdr = bdr_store.resolve("objeto 1", "cor", TemporalOperator.CURRENT)
        if not (current_original == current_sqlite == current_bdr):
            raise AssertionError("backend semantic parity failed")
        if sqlite_addresses.metrics() != bdr_addresses.metrics():
            raise AssertionError("backend topology metrics parity failed")

        original_events = store.iter_events()
        original_nodes = addresses.iter_nodes()
        original_raw = addresses.iter_raw_memories()
        original_transitions = store.iter_transitions()
        sqlite_raw = sqlite_addresses.iter_raw_memories()
        bdr_raw = bdr_addresses.iter_raw_memories()
        sqlite_events = sqlite_store.iter_events()
        bdr_events = bdr_store.iter_events()
        sqlite_transitions = sqlite_store.iter_transitions()
        bdr_transitions = bdr_store.iter_transitions()

        report = {
            "fixture": {
                "observations": len(original_events),
                "nodes": len(original_nodes),
                "raw_memories": len(original_raw),
                "transitions": len(original_transitions),
                "node_reuse_ratio": baseline_metrics["node_reuse_ratio"],
                "branching_factor": baseline_metrics["branching_factor"],
                "duplicate_address_count": baseline_metrics["duplicate_address_count"],
            },
            "ingestion": _latency_summary(ingestion_latencies),
            "query_in_memory": _latency_summary(query_before),
            "sqlite_oracle": {
                "save_ms": sqlite_save_ms,
                "load_ms": sqlite_load_ms,
                "disk_bytes": sqlite_bytes,
                "query": _latency_summary(sqlite_query),
                "physical_events": sqlite_stats.events,
            },
            "bdr_atomic": {
                "save_ms": bdr_save_ms,
                "load_ms": bdr_load_ms,
                "disk_bytes": bdr_bytes,
                "query": _latency_summary(bdr_query),
                "physical_records": bdr_stats.physical_records,
                "bdr_sequence": bdr_stats.bdr_sequence,
            },
            "parity": {
                "current_state": True,
                "topology_metrics": True,
                "raw_count": len(sqlite_raw) == len(bdr_raw),
                "event_count": len(sqlite_events) == len(bdr_events),
                "transition_count": len(sqlite_transitions) == len(bdr_transitions),
            },
        }
        print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
