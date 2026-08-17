from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
import tracemalloc
from typing import Callable, Hashable, Iterable

from .baseline_benchmark import ChronologicalMemory, HashMemory
from .memory_lifecycle import MemoryLifecycle


@dataclass(frozen=True, slots=True)
class CapabilityContract:
    basic_current_score: bool
    historical_state: bool
    deactivation_state: bool
    reactivation_history: bool
    layer_depth: bool


@dataclass(frozen=True, slots=True)
class FrontierResult:
    name: str
    events: int
    queries: int
    ingest_latency_us: float
    query_latency_us: float
    peak_bytes: int
    capabilities: CapabilityContract


def capabilities(memory) -> CapabilityContract:
    if isinstance(memory, HashMemory):
        return CapabilityContract(True, False, False, False, False)
    if isinstance(memory, ChronologicalMemory):
        # Raw event history exists, but no explicit lifecycle/depth state is
        # maintained by the baseline implementation.
        return CapabilityContract(True, True, False, False, False)
    if isinstance(memory, MemoryLifecycle):
        return CapabilityContract(True, True, True, True, True)
    raise TypeError(f"unsupported memory type: {type(memory)!r}")


def current_score(memory, key: Hashable) -> float:
    if isinstance(memory, HashMemory):
        return float(memory.data.get(key, 0.0))
    if isinstance(memory, ChronologicalMemory):
        return float(memory.score(key))
    if isinstance(memory, MemoryLifecycle):
        return float(sum(strength for _, strength, active, _ in memory.snapshot(key) if active))
    raise TypeError(f"unsupported memory type: {type(memory)!r}")


def benchmark_frontier(
    name: str,
    factory: Callable[[], object],
    events: Iterable[tuple[Hashable, bool, float]],
    query_keys: Iterable[Hashable],
) -> FrontierResult:
    sequence = list(events)
    queries = list(query_keys)
    memory = factory()

    tracemalloc.start()
    t0 = perf_counter()
    for key, positive, amount in sequence:
        if positive:
            memory.support(key, amount)
        else:
            memory.contradict(key, amount)
    ingest_elapsed = perf_counter() - t0

    q0 = perf_counter()
    for key in queries:
        current_score(memory, key)
    query_elapsed = perf_counter() - q0
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    return FrontierResult(
        name=name,
        events=len(sequence),
        queries=len(queries),
        ingest_latency_us=ingest_elapsed / max(1, len(sequence)) * 1e6,
        query_latency_us=query_elapsed / max(1, len(queries)) * 1e6,
        peak_bytes=peak,
        capabilities=capabilities(memory),
    )
