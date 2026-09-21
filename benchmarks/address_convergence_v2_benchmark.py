from __future__ import annotations

import json
from time import perf_counter

from memoria_resolutiva.address_convergence_v2 import AddressConvergenceResolver
from memoria_resolutiva.address_trajectory_v2 import AddressTrajectoryMemory


QUERIES = (
    ("qual e irmao do meu gato", "lotus"),
    ("qual a cor do meu gato", "verde"),
    ("qual e irmao do meu amigo", "vibe"),
    ("qual a cor do meu carro", "azul"),
)


def build(size: int) -> AddressTrajectoryMemory:
    memory = AddressTrajectoryMemory()
    memory.ingest("meu gato e da cor verde")
    memory.ingest("irmao de meu gato e Lotus")
    memory.ingest("meu carro e da cor azul")
    memory.ingest("irmao de meu amigo e Vibe")
    for index in range(max(0, size - 4)):
        memory.ingest(f"objeto{index} possui aspecto{index} valor{index}")
    return memory


def run(size: int) -> dict[str, object]:
    memory = build(size)
    resolver = AddressConvergenceResolver(memory)
    before = memory.snapshot()
    cases: list[dict[str, object]] = []
    times: list[float] = []
    hits = 0

    for query, expected in QUERIES:
        started = perf_counter()
        matches = resolver.resolve(query, limit=3)
        times.append((perf_counter() - started) * 1000.0)
        winner = matches[0].terminal_surface if matches else None
        hit = winner == expected
        hits += int(hit)
        cases.append({
            "query": query,
            "expected": expected,
            "winner": winner,
            "hit": hit,
            "top3": [match.terminal_surface for match in matches],
            "routes": [
                {
                    "trajectory_id": match.trajectory_id,
                    "matched_addresses": match.matched_addresses,
                    "ordered_matches": match.ordered_matches,
                    "max_hops_to_terminal": match.max_hops_to_terminal,
                    "sum_hops_to_terminal": match.sum_hops_to_terminal,
                    "route_hops": list(match.route_hops),
                }
                for match in matches
            ],
        })

    restored = AddressTrajectoryMemory.restore(memory.snapshot())
    restart_resolver = AddressConvergenceResolver(restored)
    restart_equal = all(
        resolver.resolve(query, limit=3) == restart_resolver.resolve(query, limit=3)
        for query, _ in QUERIES
    )

    return {
        "size": size,
        "top1_accuracy": hits / len(QUERIES),
        "query_mean_ms": sum(times) / len(times),
        "query_max_ms": max(times),
        "query_read_only": before == memory.snapshot(),
        "cold_restart_deterministic": restart_equal,
        "cases": cases,
    }


def main() -> None:
    print(json.dumps({
        "schema": "memoria.address-convergence.v2.benchmark.1",
        "constraints": {
            "semantic_regex": False,
            "domain_vocabulary_in_engine": False,
            "learned_weights": False,
            "cross_trajectory_jump": False,
        },
        "runs": [run(size) for size in (100, 1000, 10000)],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
