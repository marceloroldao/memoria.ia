from __future__ import annotations

import json
import time
import tracemalloc

from memoria_resolutiva.structural_equivalence_v2 import ConvergenceEvent, StructuralEquivalenceState


def ev(sig: str, region: str, lineage: str, occurrence: str, witness: str, sequence: int) -> ConvergenceEvent:
    return ConvergenceEvent(sig, region, lineage, occurrence, witness, sequence)


def run(size: int) -> dict:
    state = StructuralEquivalenceState()
    tracemalloc.start()
    t0 = time.perf_counter()
    seq = 0

    # Two real paired witnesses support A~B.
    for i in range(2):
        seq += 1
        state.observe(ev("A", "target", f"LA{i}", f"a{i}", f"paired:{i}", seq))
        seq += 1
        state.observe(ev("B", "target", f"LB{i}", f"b{i}", f"paired:{i}", seq))

    # Dense global hub pressure: A and B reach the same hub many times, but
    # never inside the same witness. This must not amplify A~B support.
    for i in range(size):
        seq += 1
        state.observe(ev("A", "hub", f"HA{i}", f"ha{i}", f"hub:a:{i}", seq))
        seq += 1
        state.observe(ev("B", "hub", f"HB{i}", f"hb{i}", f"hub:b:{i}", seq))

    build_ms = (time.perf_counter() - t0) * 1000.0
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    q0 = time.perf_counter()
    before = state.snapshot()
    result = state.evaluate("A", "B")
    lookup_ms = (time.perf_counter() - q0) * 1000.0
    after = state.snapshot()

    # Restart/replay from immutable snapshot.
    restored = StructuralEquivalenceState()
    restored.observe_many(before)
    restarted = restored.evaluate("A", "B")

    return {
        "size": size,
        "event_count": len(before),
        "build_ms": build_ms,
        "peak_python_bytes": peak,
        "lookup_ms": lookup_ms,
        "state": result.state,
        "supporting_witnesses": len(result.supporting_witnesses),
        "contradicting_witnesses": len(result.contradicting_witnesses),
        "hub_false_support": "hub" in result.shared_terminal_regions,
        "query_read_only": before == after,
        "restart_deterministic": restarted == result,
    }


def main() -> None:
    runs = [run(size) for size in (100, 1000, 10000)]
    payload = {
        "schema": "memoria.structural-equivalence-state.v2.benchmark.1",
        "constraints": {
            "semantic_regex": False,
            "domain_vocabulary": False,
            "embeddings": False,
            "neural_networks": False,
            "learned_weights": False,
        },
        "runs": runs,
        "checks": {
            "all_supported": all(item["state"] == "supported" for item in runs),
            "zero_hub_false_support": all(not item["hub_false_support"] for item in runs),
            "all_read_only": all(item["query_read_only"] for item in runs),
            "all_restart_deterministic": all(item["restart_deterministic"] for item in runs),
        },
    }
    print(json.dumps(payload, indent=2))
    if not all(payload["checks"].values()):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
