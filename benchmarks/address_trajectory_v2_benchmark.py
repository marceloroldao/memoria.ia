from __future__ import annotations

import json
from time import perf_counter

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
        # Distractors deliberately contain no domain teaching. They only grow the
        # address universe and test whether structural discrimination survives.
        memory.ingest(f"objeto{index} possui aspecto{index} valor{index}")
    return memory


def run(size: int) -> dict[str, object]:
    start = perf_counter()
    memory = build(size)
    build_ms = (perf_counter() - start) * 1000.0

    top1 = 0
    query_times: list[float] = []
    cases: list[dict[str, object]] = []
    snapshot_before = memory.snapshot()

    for query, expected in QUERIES:
        q0 = perf_counter()
        matches = memory.resolve(query, limit=3)
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
                "top3": [match.terminal_surface for match in matches],
                "structural": [
                    {
                        "trajectory_id": match.trajectory_id,
                        "overlap": match.overlap,
                        "ordered_overlap": match.ordered_overlap,
                        "adjacency_overlap": match.adjacency_overlap,
                    }
                    for match in matches
                ],
            }
        )

    snapshot_after = memory.snapshot()
    restored = AddressTrajectoryMemory.restore(snapshot_after)
    restart_equal = all(
        memory.resolve(query, limit=3) == restored.resolve(query, limit=3)
        for query, _ in QUERIES
    )

    return {
        "size": size,
        "top1_accuracy": top1 / len(QUERIES),
        "build_ms": build_ms,
        "query_mean_ms": sum(query_times) / len(query_times),
        "query_max_ms": max(query_times),
        "query_read_only": snapshot_before == snapshot_after,
        "cold_restart_deterministic": restart_equal,
        "cases": cases,
    }


def main() -> None:
    report = {
        "schema": "memoria.address-trajectory.v2.benchmark.1",
        "constraints": {
            "semantic_regex": False,
            "domain_vocabulary_in_engine": False,
            "learned_weights": False,
        },
        "runs": [run(size) for size in (100, 1000, 10000)],
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
