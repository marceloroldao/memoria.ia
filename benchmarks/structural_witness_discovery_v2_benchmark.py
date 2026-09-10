from __future__ import annotations

import json
import time
import tracemalloc

from memoria_resolutiva.address_trajectory_v2 import AddressTrajectory
from memoria_resolutiva.structural_equivalence_v2 import StructuralEquivalenceState
from memoria_resolutiva.structural_witness_discovery_v2 import (
    TrajectoryOccurrence,
    discover_witnesses,
    events_from_discovered_witnesses,
)


def traj(tid: str, *addresses: str) -> AddressTrajectory:
    return AddressTrajectory(tid, tid, tuple(addresses), tuple(addresses))


def timed_discovery(corpus: tuple[TrajectoryOccurrence, ...]):
    tracemalloc.start()
    t0 = time.perf_counter()
    witnesses = discover_witnesses(corpus)
    elapsed_ms = (time.perf_counter() - t0) * 1000
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return witnesses, elapsed_ms, peak


def run(size: int) -> dict[str, object]:
    true_occurrences = (
        TrajectoryOccurrence(traj("TA1", "a", "p", "q", "z"), "LA1", "OA1"),
        TrajectoryOccurrence(traj("TB1", "b", "p", "q", "z"), "LB1", "OB1"),
        TrajectoryOccurrence(traj("TA2", "a", "p", "q", "z"), "LA2", "OA2"),
        TrajectoryOccurrence(traj("TB2", "b", "p", "q", "z"), "LB2", "OB2"),
    )
    dense = tuple(
        TrajectoryOccurrence(
            traj(f"TH{i}", f"src:{i}", "dense:1", "dense:2", "hub"),
            f"LH{i}",
            f"OH{i}",
        )
        for i in range(size)
    )
    corpus = true_occurrences + dense
    witnesses, build_ms, peak = timed_discovery(corpus)

    true_witnesses = [w for w in witnesses if w.terminal_region_id == "z"]
    dense_witnesses = [w for w in witnesses if w.terminal_region_id == "hub"]

    state = StructuralEquivalenceState()
    state.observe_many(events_from_discovered_witnesses(true_witnesses))
    pair = {(w.left_signature_id, w.right_signature_id) for w in true_witnesses}
    candidate_state = "missing"
    support = 0
    if len(pair) == 1:
        left, right = next(iter(pair))
        candidate = state.evaluate(left, right)
        candidate_state = candidate.state
        support = candidate.independent_convergence

    recurrent = tuple(
        TrajectoryOccurrence(
            traj(
                f"TR{i}",
                "origin:a" if i % 2 == 0 else "origin:b",
                "repeat:1",
                "repeat:2",
                "future:r",
            ),
            f"LR{i}",
            f"OR{i}",
        )
        for i in range(size)
    )
    recurrent_witnesses, recurrent_ms, recurrent_peak = timed_discovery(recurrent)

    return {
        "size": size,
        "occurrence_count": len(corpus),
        "witness_count": len(witnesses),
        "true_witness_count": len(true_witnesses),
        "dense_hub_witness_count": len(dense_witnesses),
        "true_equivalence_state": candidate_state,
        "true_independent_support": support,
        "dense_hub_fail_closed": len(dense_witnesses) == 0,
        "build_ms": build_ms,
        "peak_python_bytes": peak,
        "recurrent_two_origin": {
            "occurrence_count": len(recurrent),
            "witness_count": len(recurrent_witnesses),
            "bounded_to_max_per_pair": len(recurrent_witnesses) <= 8,
            "build_ms": recurrent_ms,
            "peak_python_bytes": recurrent_peak,
        },
    }


def main() -> None:
    runs = [run(size) for size in (100, 1000, 10000)]
    result = {
        "schema": "memoria.structural-witness-discovery.v2.benchmark.2",
        "constraints": {
            "semantic_regex": False,
            "domain_vocabulary": False,
            "embeddings": False,
            "neural_networks": False,
            "learned_weights": False,
            "pairwise_full_scan": False,
        },
        "runs": runs,
        "checks": {
            "all_true_equivalences_supported": all(r["true_equivalence_state"] == "supported" for r in runs),
            "zero_dense_hub_witnesses": all(r["dense_hub_witness_count"] == 0 for r in runs),
            "all_recurrent_pairs_bounded": all(r["recurrent_two_origin"]["bounded_to_max_per_pair"] for r in runs),
        },
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not all(result["checks"].values()):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
