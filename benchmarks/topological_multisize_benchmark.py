from __future__ import annotations

import json
import os
from pathlib import Path
import statistics
import tempfile
import time

from memoria_resolutiva.topological_bdr_persistence import load_snapshot_bdr, save_snapshot_bdr
from memoria_resolutiva.topological_memory import AddressSpace, TemporalEventStore, TemporalOperator
from memoria_resolutiva.topological_metrics import measure_activation
from memoria_resolutiva.topological_persistence import load_snapshot, save_snapshot


SIZES = (24, 240, 1200)


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


def _latency_summary(values: list[float]) -> dict[str, float]:
    return {
        "mean_ms": statistics.fmean(values) if values else 0.0,
        "p50_ms": _percentile(values, 0.50),
        "p95_ms": _percentile(values, 0.95),
        "max_ms": max(values) if values else 0.0,
    }


def _build_fixture(count: int) -> tuple[AddressSpace, TemporalEventStore, list[float]]:
    addresses = AddressSpace()
    store = TemporalEventStore(addresses)
    latencies_ms: list[float] = []
    colors = ("azul", "preta", "branca", "vermelha")
    states = ("ligado", "espera", "ativo", "inativo")

    for i in range(count):
        subject = f"objeto {i % 24}"
        attribute = "cor" if i % 3 else "estado"
        value = colors[(i // 24) % len(colors)] if attribute == "cor" else states[(i // 24) % len(states)]
        rare = " xqz91" if i == 0 else ""
        raw = f"registro de {subject} com {attribute} de {value} evento {i}{rare}."
        started = time.perf_counter_ns()
        ingestion = addresses.ingest_text(raw)
        store.observe_state(subject, attribute, value, raw_memory_address=ingestion.raw_memory_address)
        latencies_ms.append((time.perf_counter_ns() - started) / 1_000_000)
    return addresses, store, latencies_ms


def _query_latencies(store: TemporalEventStore, rounds: int) -> list[float]:
    values: list[float] = []
    for i in range(rounds):
        subject = f"objeto {i % 24}"
        attribute = "cor" if i % 3 else "estado"
        started = time.perf_counter_ns()
        store.resolve(subject, attribute, TemporalOperator.CURRENT)
        values.append((time.perf_counter_ns() - started) / 1_000_000)
    return values


def _activation(addresses: AddressSpace, word: str) -> dict[str, object]:
    node = addresses.resolve("word", word)
    if node is None:
        return {"present": False}
    profile = measure_activation(addresses, node, max_depth=2, max_candidates=64, direction="in")
    return {
        "present": True,
        "occurrences": node.occurrences,
        "degree": node.density,
        "candidate_count": profile.candidate_count,
        "truncated": profile.truncated,
        "max_candidates": profile.max_candidates,
    }


def _run_size(count: int, library: str, root: Path) -> dict[str, object]:
    addresses, store, ingestion = _build_fixture(count)
    query_rounds = min(240, max(60, count))
    query_before = _query_latencies(store, query_rounds)
    metrics = addresses.metrics()

    sqlite_path = root / f"sqlite-{count}.sqlite3"
    bdr_root = root / f"bdr-{count}"

    started = time.perf_counter_ns()
    sqlite_stats = save_snapshot(sqlite_path, addresses, store)
    sqlite_save_ms = (time.perf_counter_ns() - started) / 1_000_000
    sqlite_bytes = _disk_bytes(sqlite_path)

    started = time.perf_counter_ns()
    sqlite_addresses, sqlite_store = load_snapshot(sqlite_path)
    sqlite_load_ms = (time.perf_counter_ns() - started) / 1_000_000
    sqlite_query = _query_latencies(sqlite_store, query_rounds)

    started = time.perf_counter_ns()
    bdr_stats = save_snapshot_bdr(bdr_root, library, addresses, store)
    bdr_save_ms = (time.perf_counter_ns() - started) / 1_000_000
    bdr_bytes = _disk_bytes(bdr_root)

    started = time.perf_counter_ns()
    bdr_addresses, bdr_store = load_snapshot_bdr(bdr_root, library)
    bdr_load_ms = (time.perf_counter_ns() - started) / 1_000_000
    bdr_query = _query_latencies(bdr_store, query_rounds)

    original_current = store.resolve("objeto 1", "cor", TemporalOperator.CURRENT)
    sqlite_current = sqlite_store.resolve("objeto 1", "cor", TemporalOperator.CURRENT)
    bdr_current = bdr_store.resolve("objeto 1", "cor", TemporalOperator.CURRENT)
    if not (original_current == sqlite_current == bdr_current):
        raise AssertionError(f"semantic parity failed at size {count}")
    if sqlite_addresses.metrics() != bdr_addresses.metrics():
        raise AssertionError(f"topology metrics parity failed at size {count}")

    return {
        "observations": count,
        "nodes": len(addresses.iter_nodes()),
        "raw_memories": len(addresses.iter_raw_memories()),
        "transitions": len(store.iter_transitions()),
        "node_reuse_ratio": metrics["node_reuse_ratio"],
        "branching_factor": metrics["branching_factor"],
        "duplicate_address_count": metrics["duplicate_address_count"],
        "ingestion": _latency_summary(ingestion),
        "query_in_memory": _latency_summary(query_before),
        "activation": {
            "dense_hub_de": _activation(addresses, "de"),
            "rare_xqz91": _activation(addresses, "xqz91"),
        },
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
            "raw_count": len(sqlite_addresses.iter_raw_memories()) == len(bdr_addresses.iter_raw_memories()),
            "event_count": len(sqlite_store.iter_events()) == len(bdr_store.iter_events()),
            "transition_count": len(sqlite_store.iter_transitions()) == len(bdr_store.iter_transitions()),
        },
    }


def main() -> None:
    library = os.environ.get("BDR_ATOMIC_LIB")
    if not library:
        raise SystemExit("BDR_ATOMIC_LIB is required")

    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        samples = [_run_size(size, library, root) for size in SIZES]

    report = {
        "benchmark": "topological_multisize_v1",
        "sizes": list(SIZES),
        "policy": {
            "performance_thresholds": False,
            "semantic_parity_required": True,
            "negative_results_must_be_recorded": True,
        },
        "samples": samples,
    }
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
