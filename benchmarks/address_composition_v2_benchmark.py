from __future__ import annotations

import json
from time import perf_counter

from memoria_resolutiva.address_trajectory_v2 import AddressTrajectoryMemory
from memoria_resolutiva.address_convergence_v2 import AddressConvergenceResolver
from memoria_resolutiva.address_composition_v2 import AddressCompositionEngine
from memoria_resolutiva.composed_convergence_v2 import ComposedAddressConvergenceResolver


QUERIES = (
    ("qual e irmao de meu gato", "lotus"),
    ("qual a cor do meu gato", "verde"),
)


def build(size: int) -> AddressTrajectoryMemory:
    memory = AddressTrajectoryMemory()
    seeds = (
        "meu gato dorme aqui",
        "meu gato come agora",
        "meu gato e da cor verde",
        "irmao de meu gato e Lotus",
        "meu carro e da cor azul",
        "irmao de meu amigo e Vibe",
    )
    for text in seeds:
        memory.ingest(text)
    for index in range(max(0, size - len(seeds))):
        group = index % 20
        memory.ingest(f"grupo{group} objeto{index} estado{group} valor{index}")
    return memory


def run(size: int) -> dict[str, object]:
    memory = build(size)
    atomic = AddressConvergenceResolver(memory)
    composition_engine = AddressCompositionEngine(
        memory,
        min_size=2,
        max_size=4,
        min_occurrences=2,
    )
    composed = ComposedAddressConvergenceResolver(
        memory,
        composition_engine=composition_engine,
    )

    t0 = perf_counter()
    catalogue = composition_engine.discover()
    discovery_ms = (perf_counter() - t0) * 1000.0

    cases: list[dict[str, object]] = []
    atomic_hits = 0
    composed_hits = 0

    for query, expected in QUERIES:
        a0 = perf_counter()
        a = atomic.resolve(query, limit=3)
        atomic_ms = (perf_counter() - a0) * 1000.0

        c0 = perf_counter()
        c = composed.resolve(query, limit=3)
        composed_ms = (perf_counter() - c0) * 1000.0

        atomic_winner = a[0].terminal_surface if a else None
        composed_winner = c[0].terminal_surface if c else None
        atomic_hits += int(atomic_winner == expected)
        composed_hits += int(composed_winner == expected)

        cases.append(
            {
                "query": query,
                "expected": expected,
                "atomic_winner": atomic_winner,
                "composed_winner": composed_winner,
                "atomic_ms": atomic_ms,
                "composed_ms": composed_ms,
                "atomic_max_hops": a[0].max_hops_to_terminal if a else None,
                "atomic_sum_hops": a[0].sum_hops_to_terminal if a else None,
                "composed_max_hops": c[0].max_hops_to_terminal if c else None,
                "composed_sum_hops": c[0].sum_hops_to_terminal if c else None,
                "composed_atomic_length": c[0].atomic_length if c else None,
                "composed_view_length": c[0].composed_length if c else None,
            }
        )

    return {
        "size": size,
        "composition_count": len(catalogue),
        "composition_discovery_ms": discovery_ms,
        "atomic_accuracy": atomic_hits / len(QUERIES),
        "composed_accuracy": composed_hits / len(QUERIES),
        "cases": cases,
    }


def main() -> None:
    report = {
        "schema": "memoria.address-composition.v2.benchmark.1",
        "constraints": {
            "semantic_regex": False,
            "domain_vocabulary_in_engine": False,
            "learned_weights": False,
            "atomic_memory_mutation": False,
        },
        "runs": [run(size) for size in (100, 1000, 10000)],
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
