from __future__ import annotations

import json
import tracemalloc
from time import perf_counter

from memoria_resolutiva.address_trajectory_v2 import AddressTrajectoryMemory
from memoria_resolutiva.dynamic_branch_state_v2 import DynamicBranchStateResolver
from memoria_resolutiva.multiscale_resolver_v2 import MultiscaleAddressResolver


SCENARIO_COUNT = 8


def build(size: int) -> tuple[AddressTrajectoryMemory, tuple[tuple[str, str], ...]]:
    """Build a corpus whose recurrent regions deliberately favor wrong continuations.

    Each scenario has one fully matching occurrence:
        anchorN bridgeN keyN -> correctN

    Distractors recurrently expose:
        noiseX bridgeN keyN -> wrongN

    Thus `bridgeN keyN` becomes a high-support composition attached mostly to the
    wrong continuation, while the correct occurrence retains stronger depth-0
    geometry because it also contains `anchorN`. No semantic label is interpreted by
    the engine; these strings are only stable synthetic surfaces for diagnostics.
    """
    memory = AddressTrajectoryMemory()
    queries: list[tuple[str, str]] = []

    for scenario in range(SCENARIO_COUNT):
        memory.ingest(
            f"anchor{scenario} bridge{scenario} key{scenario} correct{scenario}"
        )
        queries.append(
            (f"anchor{scenario} bridge{scenario} key{scenario}", f"correct{scenario}")
        )

    remaining = max(0, size - SCENARIO_COUNT)
    for index in range(remaining):
        scenario = index % SCENARIO_COUNT
        # Recurrent misleading region: the same bridge/key pair repeatedly points
        # elsewhere and should dominate composition support, but not stronger atomic
        # convergence for a query that also contains its unique anchor.
        memory.ingest(
            f"noise{index} bridge{scenario} key{scenario} wrong{scenario}"
        )

    return memory, tuple(queries)


def recovery_overflow_probe(memory: AddressTrajectoryMemory, size: int) -> dict[str, object]:
    # Add a separate modality-neutral hub region to exercise recovery overflow using
    # stable external addresses rather than the text adapter.
    hub_memory = AddressTrajectoryMemory.restore(memory.snapshot())
    branch_limit = 16
    fanout = max(branch_limit + 1, min(size, 256))
    for index in range(fanout):
        hub_memory.ingest_address_stream(
            (f"sensor:source:{index}", "sensor:hub", f"sensor:future:{index}"),
            surfaces=(f"source:{index}", "hub", f"future:{index}"),
            provenance=f"synthetic-sensor:{index}",
        )

    resolver = DynamicBranchStateResolver(hub_memory)
    state = resolver.begin_addresses(("sensor:start",))
    # The unseen start has no active path already; recovery from an observed pair
    # falls back to the hyperdense suffix `sensor:hub` and must fail closed rather
    # than retain an arbitrary bounded subset of futures.
    recovery = resolver.recover_addresses(
        state,
        ("sensor:unseen", "sensor:hub"),
        branch_limit=branch_limit,
        candidate_limit=fanout + 1,
    )
    return {
        "fanout": fanout,
        "recovered": recovery.recovered_any,
        "unresolved": recovery.recovered.exhausted,
        "false_reseed": recovery.recovered_any,
        "active_branch_count": len(recovery.recovered.active),
    }


def run(size: int) -> dict[str, object]:
    tracemalloc.start()
    build_started = perf_counter()
    memory, queries = build(size)
    build_ms = (perf_counter() - build_started) * 1000.0
    _, peak_bytes = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    resolver = MultiscaleAddressResolver(memory, max_depth=4)
    hierarchy_started = perf_counter()
    levels = resolver.hierarchy.build()
    hierarchy_ms = (perf_counter() - hierarchy_started) * 1000.0

    before = memory.snapshot()
    cases: list[dict[str, object]] = []
    atomic_top1 = 0
    multiscale_top1 = 0
    multiscale_top3 = 0
    false_consensus = 0
    ambiguous_top = 0
    query_times: list[float] = []

    for query, expected in queries:
        atomic = memory.resolve(query, limit=3)
        atomic_winner = atomic[0].terminal_surface if atomic else None
        atomic_hit = atomic_winner == expected
        atomic_top1 += int(atomic_hit)

        started = perf_counter()
        matches = resolver.resolve(query, limit=3)
        query_times.append((perf_counter() - started) * 1000.0)
        top = [match.terminal_surface for match in matches]
        winner = top[0] if top else None
        top1_hit = winner == expected
        top3_hit = expected in top
        multiscale_top1 += int(top1_hit)
        multiscale_top3 += int(top3_hit)
        false_consensus += int(atomic_hit and not top1_hit)

        if len(matches) > 1:
            # Ambiguity is structural equality excluding deterministic trajectory ID,
            # which is bookkeeping only and must not be interpreted as cognition.
            left = matches[0].multiscale_key[:-1]
            right = matches[1].multiscale_key[:-1]
            ambiguous_top += int(left == right)

        cases.append(
            {
                "query": query,
                "expected": expected,
                "atomic_winner": atomic_winner,
                "multiscale_winner": winner,
                "top3": top,
                "atomic_hit": atomic_hit,
                "multiscale_top1_hit": top1_hit,
                "multiscale_top3_hit": top3_hit,
                "winner_supporting_depths": list(matches[0].supporting_depths) if matches else [],
                "winner_atomic_overlap": (
                    matches[0].atomic_evidence.overlap
                    if matches and matches[0].atomic_evidence is not None
                    else None
                ),
            }
        )

    restored = AddressTrajectoryMemory.restore(before)
    restart = MultiscaleAddressResolver(restored, max_depth=4)
    restart_equal = all(
        resolver.resolve(query, limit=3) == restart.resolve(query, limit=3)
        for query, _ in queries
    )

    metrics = resolver.hierarchy.metrics()
    recovery = recovery_overflow_probe(memory, size)
    query_count = len(queries)

    return {
        "size": size,
        "trajectory_count": len(memory.snapshot()),
        "build_ms": build_ms,
        "peak_python_bytes": peak_bytes,
        "hierarchy_build_ms": hierarchy_ms,
        "hierarchy_depth": len(levels),
        "composition_count": sum(len(level.compositions) for level in levels),
        "compositions_per_level": [len(level.compositions) for level in levels],
        "atomic_address_count": metrics["atomic_address_count"],
        "final_address_count": metrics["final_address_count"],
        "hop_reduction_num": metrics["compression_num"],
        "hop_reduction_den": metrics["compression_den"],
        "atomic_top1": atomic_top1 / query_count,
        "multiscale_top1": multiscale_top1 / query_count,
        "multiscale_top3": multiscale_top3 / query_count,
        "false_hierarchical_consensus_count": false_consensus,
        "ambiguous_top_count": ambiguous_top,
        "query_mean_ms": sum(query_times) / query_count,
        "query_max_ms": max(query_times),
        "query_read_only": memory.snapshot() == before,
        "cold_restart_deterministic": restart_equal,
        "recovery_overflow": recovery,
        "cases": cases,
    }


def main() -> None:
    runs = [run(size) for size in (100, 1000, 10000)]
    report = {
        "schema": "memoria.address-trajectory.v2.adversarial-corpus.1",
        "constraints": {
            "semantic_regex": False,
            "domain_vocabulary_in_engine": False,
            "intent_enums": False,
            "embeddings": False,
            "neural_networks": False,
            "learned_scalar_weights": False,
        },
        "runs": runs,
        "total_false_hierarchical_consensus": sum(
            item["false_hierarchical_consensus_count"] for item in runs
        ),
        "total_false_reseed": sum(
            int(item["recovery_overflow"]["false_reseed"]) for item in runs
        ),
        "all_read_only": all(item["query_read_only"] for item in runs),
        "all_restart_deterministic": all(
            item["cold_restart_deterministic"] for item in runs
        ),
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
