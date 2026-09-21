from __future__ import annotations

import json
import time
import tracemalloc

from memoria_resolutiva.address_trajectory_v2 import AddressTrajectory
from memoria_resolutiva.structural_role_abstraction_v2 import build_role_profile, compare_structural_roles
from memoria_resolutiva.structural_witness_discovery_v2 import TrajectoryOccurrence


def traj(tid: str, *addresses: str) -> AddressTrajectory:
    return AddressTrajectory(tid, tid, tuple(addresses), tuple(addresses))


def make_matching(prefix: str, focus: str, size: int) -> tuple[TrajectoryOccurrence, ...]:
    return tuple(
        TrajectoryOccurrence(
            traj(f"{prefix}T{i}", f"{prefix}p{i}", focus, f"{prefix}s{i}", f"{prefix}t{i}"),
            f"{prefix}L{i}",
            f"{prefix}O{i}",
        )
        for i in range(size)
    )


def make_crossed(prefix: str, focus: str, width: int) -> tuple[TrajectoryOccurrence, ...]:
    out = []
    seq = 0
    for i in range(width):
        for j in range(width):
            out.append(
                TrajectoryOccurrence(
                    traj(f"{prefix}T{seq}", f"{prefix}p{i}", focus, f"{prefix}s{j}", f"{prefix}t{seq}"),
                    f"{prefix}L{seq}",
                    f"{prefix}O{seq}",
                )
            )
            seq += 1
    return tuple(out)


def run(size: int) -> dict[str, object]:
    train = make_matching("tr", "focus:train", size)
    heldout = make_matching("ho", "focus:heldout", size)
    train_addresses = {a for o in train for a in o.trajectory.addresses}
    heldout_addresses = {a for o in heldout for a in o.trajectory.addresses}

    tracemalloc.start()
    t0 = time.perf_counter()
    train_profile = build_role_profile(train, "focus:train", max_neighbor_diversity=size + 1)
    heldout_profile = build_role_profile(heldout, "focus:heldout", max_neighbor_diversity=size + 1)
    match = compare_structural_roles(train_profile, heldout_profile)
    exact_ms = (time.perf_counter() - t0) * 1000
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    # Deceptive corpus: equal focus position and equal predecessor/successor counts,
    # but a different predecessor->successor incidence geometry.
    width = min(size, 32)
    deceptive_left = make_matching("dl", "focus:left", width)
    deceptive_right = make_crossed("dr", "focus:right", width)
    left_profile = build_role_profile(deceptive_left, "focus:left", max_neighbor_diversity=64)
    right_profile = build_role_profile(deceptive_right, "focus:right", max_neighbor_diversity=64)
    deceptive_match = compare_structural_roles(left_profile, right_profile)

    # Hyperdense neighborhoods remain fail-closed under the default bound.
    dense = make_matching("dn", "focus:dense", max(64, min(size, 256)))
    dense_profile = build_role_profile(dense, "focus:dense", max_neighbor_diversity=32)

    return {
        "size": size,
        "train_occurrences": len(train),
        "heldout_occurrences": len(heldout),
        "address_spaces_disjoint": train_addresses.isdisjoint(heldout_addresses),
        "exact_transfer_supported": match.supported,
        "exact_transfer_reason": match.reason,
        "role_ids_equal": train_profile.role_id == heldout_profile.role_id,
        "exact_build_and_compare_ms": exact_ms,
        "peak_python_bytes": peak,
        "deceptive_equal_pred_diversity": left_profile.predecessor_diversity == right_profile.predecessor_diversity,
        "deceptive_equal_succ_diversity": left_profile.successor_diversity == right_profile.successor_diversity,
        "deceptive_transfer_blocked": not deceptive_match.supported,
        "deceptive_reason": deceptive_match.reason,
        "dense_fail_closed": not dense_profile.discriminative,
    }


def main() -> None:
    runs = [run(size) for size in (100, 1000, 10000)]
    result = {
        "schema": "memoria.structural-role-abstraction.v2.benchmark.1",
        "constraints": {
            "semantic_regex": False,
            "domain_vocabulary": False,
            "embeddings": False,
            "neural_networks": False,
            "learned_weights": False,
            "literal_address_identity_required": False,
        },
        "runs": runs,
        "checks": {
            "all_disjoint": all(r["address_spaces_disjoint"] for r in runs),
            "all_exact_transfer_supported": all(r["exact_transfer_supported"] for r in runs),
            "all_deceptive_transfer_blocked": all(r["deceptive_transfer_blocked"] for r in runs),
            "all_dense_fail_closed": all(r["dense_fail_closed"] for r in runs),
        },
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not all(result["checks"].values()):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
