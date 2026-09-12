from __future__ import annotations

import json
from time import perf_counter

from memoria_resolutiva.address_trajectory_v2 import AddressTrajectoryMemory
from memoria_resolutiva.multiscale_resolver_v2 import MultiscaleAddressResolver


QUERIES = (
    ("qual meu gato", "lotus"),
    ("qual meu carro", "jeep"),
)


def build(size: int) -> AddressTrajectoryMemory:
    memory = AddressTrajectoryMemory()
    memory.ingest("meu gato dorme aqui")
    memory.ingest("meu gato come aqui")
    memory.ingest("meu gato e Lotus")
    memory.ingest("meu carro anda fora")
    memory.ingest("meu carro e Jeep")
    for index in range(max(0, size - 5)):
        prefix = f"grupo{index % 50}"
        memory.ingest(f"{prefix} objeto{index} estado{index % 17}")
    return memory


def run(size: int) -> dict[str, object]:
    memory = build(size)
    resolver = MultiscaleAddressResolver(memory, max_depth=3)

    t0 = perf_counter()
    levels = resolver.hierarchy.build()
    hierarchy_ms = (perf_counter() - t0) * 1000.0

    cases: list[dict[str, object]] = []
    top1 = 0
    query_times: list[float] = []
    before = memory.snapshot()

    for query, expected in QUERIES:
        q0 = perf_counter()
        matches = resolver.resolve(query, limit=5)
        query_times.append((perf_counter() - q0) * 1000.0)
        winner = matches[0].terminal_surface if matches else None
        hit = winner == expected
        top1 += int(hit)
        cases.append(
            {
                "query": query,
                "expected": expected,
                "winner": winner,
                "hit": hit,
                "top5": [match.terminal_surface for match in matches],
                "supporting_depths": [list(match.supporting_depths) for match in matches],
                "evidence_counts": [len(match.scale_evidence) for match in matches],
            }
        )

    after = memory.snapshot()
    restored = AddressTrajectoryMemory.restore(after)
    restart = MultiscaleAddressResolver(restored, max_depth=3)
    restart_equal = all(
        resolver.resolve(query, limit=5) == restart.resolve(query, limit=5)
        for query, _ in QUERIES
    )

    return {
        "size": size,
        "levels": len(levels),
        "compositions_per_level": [len(level.compositions) for level in levels],
        "hierarchy_build_ms": hierarchy_ms,
        "query_mean_ms": sum(query_times) / len(query_times),
        "query_max_ms": max(query_times),
        "top1_accuracy": top1 / len(QUERIES),
        "query_read_only": before == after,
        "cold_restart_deterministic": restart_equal,
        "cases": cases,
    }


def main() -> None:
    report = {
        "schema": "memoria.multiscale-resolver.v2.benchmark.1",
        "constraints": {
            "semantic_regex": False,
            "domain_vocabulary_in_engine": False,
            "learned_weights": False,
            "fixed_semantic_level": False,
        },
        "runs": [run(size) for size in (100, 1000, 10000)],
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
