from __future__ import annotations

import json
import time
import tracemalloc

from memoria_resolutiva.address_trajectory_v2 import AddressTrajectory
from memoria_resolutiva.structural_relation_abstraction_v2 import build_relation_profile, compare_structural_relations
from memoria_resolutiva.structural_witness_discovery_v2 import TrajectoryOccurrence


def traj(tid: str, *addresses: str) -> AddressTrajectory:
    return AddressTrajectory(tid, tid, tuple(addresses), tuple(addresses))


def make_relation(prefix: str, size: int, *, divergent_deep_future: bool = False):
    out = []
    for i in range(size):
        deep = f"{prefix}end{i}" if divergent_deep_future else f"{prefix}end"
        out.append(
            TrajectoryOccurrence(
                traj(
                    f"{prefix}T{i}",
                    f"{prefix}pre{i}",
                    f"{prefix}left",
                    f"{prefix}bridge",
                    f"{prefix}right",
                    f"{prefix}shared",
                    deep,
                ),
                f"{prefix}L{i}",
                f"{prefix}O{i}",
            )
        )
    return tuple(out)


def run(size: int) -> dict[str, object]:
    train = make_relation("tr", size)
    held = make_relation("ho", size)
    deceptive = make_relation("dv", size, divergent_deep_future=True)

    tracemalloc.start()
    t0 = time.perf_counter()
    train_profile = build_relation_profile(
        train,
        ("trleft", "trbridge", "trright"),
        max_neighbor_diversity=size + 1,
        max_continuation_depth=2,
    )
    held_profile = build_relation_profile(
        held,
        ("holeft", "hobridge", "horight"),
        max_neighbor_diversity=size + 1,
        max_continuation_depth=2,
    )
    positive = compare_structural_relations(train_profile, held_profile)
    elapsed_ms = (time.perf_counter() - t0) * 1000
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    deceptive_profile = build_relation_profile(
        deceptive,
        ("dvleft", "dvbridge", "dvright"),
        max_neighbor_diversity=size + 1,
        max_continuation_depth=2,
    )
    deceptive_match = compare_structural_relations(train_profile, deceptive_profile)

    train_addresses = {a for o in train for a in o.trajectory.addresses}
    held_addresses = {a for o in held for a in o.trajectory.addresses}

    return {
        "size": size,
        "address_spaces_disjoint": train_addresses.isdisjoint(held_addresses),
        "positive_transfer_supported": positive.supported,
        "positive_reason": positive.reason,
        "deceptive_transfer_blocked": not deceptive_match.supported,
        "deceptive_reason": deceptive_match.reason,
        "train_future_diversity": train_profile.continuation_diversity_by_depth,
        "deceptive_future_diversity": deceptive_profile.continuation_diversity_by_depth,
        "build_and_compare_ms": elapsed_ms,
        "peak_python_bytes": peak,
    }


def main() -> None:
    runs = [run(size) for size in (100, 1000, 10000)]
    result = {
        "schema": "memoria.structural-relation-abstraction.v2.benchmark.1",
        "constraints": {
            "semantic_regex": False,
            "domain_vocabulary": False,
            "embeddings": False,
            "neural_networks": False,
            "learned_weights": False,
        },
        "runs": runs,
        "checks": {
            "all_disjoint": all(r["address_spaces_disjoint"] for r in runs),
            "all_positive_transfer_supported": all(r["positive_transfer_supported"] for r in runs),
            "all_deceptive_transfer_blocked": all(r["deceptive_transfer_blocked"] for r in runs),
        },
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not all(result["checks"].values()):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
