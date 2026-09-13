from __future__ import annotations

import json
from time import perf_counter

from memoria_resolutiva.address_trajectory_v2 import AddressTrajectoryMemory
from memoria_resolutiva.hierarchical_composition_v2 import HierarchicalCompositionEngine


def build(size: int) -> AddressTrajectoryMemory:
    memory = AddressTrajectoryMemory()
    templates = (
        "meu gato dorme aqui",
        "meu gato come aqui",
        "meu gato dorme perto",
        "meu carro fica aqui",
        "meu carro fica perto",
        "irmao de meu gato e Lotus",
        "irmao de meu amigo e Vibe",
        "cor de meu gato e verde",
    )
    for index in range(size):
        base = templates[index % len(templates)]
        memory.ingest(f"{base} contexto{index % 17}")
    return memory


def run(size: int) -> dict[str, object]:
    memory = build(size)
    engine = HierarchicalCompositionEngine(
        memory,
        max_depth=4,
        min_occurrences=2,
        min_trajectory_count=2,
        min_size=2,
        max_size=3,
        max_compositions_per_level=2048,
    )
    before = memory.snapshot()
    t0 = perf_counter()
    levels = engine.build()
    elapsed_ms = (perf_counter() - t0) * 1000.0
    after = memory.snapshot()
    metrics = engine.metrics()

    max_level = max((len(level.compositions) for level in levels), default=0)
    total_compositions = sum(len(level.compositions) for level in levels)
    nested = 0
    previous_addresses: set[str] = set()
    for level in levels:
        if previous_addresses:
            nested += sum(
                1
                for composition in level.compositions
                if any(child in previous_addresses for child in composition.children)
            )
        previous_addresses |= {composition.address for composition in level.compositions}

    return {
        "size": size,
        "build_ms": elapsed_ms,
        "levels": len(levels),
        "total_compositions": total_compositions,
        "max_compositions_in_level": max_level,
        "nested_compositions": nested,
        "atomic_address_count": metrics["atomic_address_count"],
        "final_address_count": metrics["final_address_count"],
        "compression_num": metrics["compression_num"],
        "compression_den": metrics["compression_den"],
        "atomic_memory_immutable": before == after,
    }


def main() -> None:
    print(
        json.dumps(
            {
                "schema": "memoria.hierarchical-composition.v2.benchmark.1",
                "constraints": {
                    "semantic_rules": False,
                    "learned_weights": False,
                    "max_depth": 4,
                    "min_occurrences": 2,
                    "min_trajectory_count": 2,
                    "max_compositions_per_level": 2048,
                },
                "runs": [run(size) for size in (100, 1000, 10000)],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
