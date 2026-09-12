from __future__ import annotations

import json
from time import perf_counter
from tracemalloc import start as trace_start, get_traced_memory, stop as trace_stop

from memoria_resolutiva.address_trajectory_v2 import AddressTrajectoryMemory
from memoria_resolutiva.dynamic_branch_state_v2 import DynamicBranchStateResolver


SIZES = (100, 1000, 10000)


def build(size: int) -> AddressTrajectoryMemory:
    memory = AddressTrajectoryMemory()
    # Stable recovery targets and a deliberately dense hub family.
    memory.ingest("origin start expected")
    memory.ingest("recover alpha beta")
    memory.ingest("recover alpha gamma")
    for index in range(max(0, size - 3)):
        memory.ingest(f"region{index} hub branch{index}")
    return memory


def _addr(memory: AddressTrajectoryMemory, text: str) -> str:
    return memory.decompose(text)[0].address


def run(size: int) -> dict[str, object]:
    trace_start()
    t0 = perf_counter()
    memory = build(size)
    build_ms = (perf_counter() - t0) * 1000.0
    _, peak_bytes = get_traced_memory()
    trace_stop()

    resolver = DynamicBranchStateResolver(memory)
    before = memory.snapshot()

    initial = resolver.begin("origin start")
    unexpected = _addr(memory, "recover")
    exhausted = resolver.observe_address(initial, unexpected)

    t1 = perf_counter()
    recovery = resolver.recover_text(exhausted, "recover alpha")
    recovery_ms = (perf_counter() - t1) * 1000.0

    branch_surfaces = sorted(
        tuple(surface for surface in branch.remaining_surfaces if surface is not None)
        for branch in recovery.recovered.active
    )
    expected_branches = [("beta",), ("gamma",)]

    # Hub-induced false reseed probe: a two-address observed configuration must
    # recover only its exact occurrence, not every trajectory containing hub.
    target = f"region{max(0, size // 2)}"
    false_probe_state = resolver.begin("origin start")
    false_probe_state = resolver.observe_address(false_probe_state, _addr(memory, target))
    false_t0 = perf_counter()
    false_probe = resolver.recover_text(false_probe_state, f"{target} hub")
    false_reseed_ms = (perf_counter() - false_t0) * 1000.0
    false_targets = {
        surface
        for branch in false_probe.recovered.active
        for surface in branch.remaining_surfaces
        if surface is not None
    }
    expected_target = f"branch{max(0, size // 2)}"
    hub_induced_errors = sorted(false_targets - {expected_target})

    restored = AddressTrajectoryMemory.restore(before)
    restored_resolver = DynamicBranchStateResolver(restored)
    restored_initial = restored_resolver.begin("origin start")
    restored_exhausted = restored_resolver.observe_address(
        restored_initial,
        _addr(restored, "recover"),
    )
    restored_recovery = restored_resolver.recover_text(restored_exhausted, "recover alpha")

    return {
        "size": size,
        "build_ms": build_ms,
        "peak_python_bytes": peak_bytes,
        "trajectory_count": len(memory.snapshot()),
        "exhaustion": exhausted.exhausted,
        "recovered": recovery.recovered_any,
        "recovery_ms": recovery_ms,
        "branch_count": len(recovery.recovered.active),
        "branch_surfaces": branch_surfaces,
        "branch_survival_correct": branch_surfaces == expected_branches,
        "ambiguous_after_recovery": recovery.recovered.ambiguous,
        "query_read_only": memory.snapshot() == before,
        "cold_restart_deterministic": recovery == restored_recovery,
        "false_reseed_ms": false_reseed_ms,
        "hub_induced_recovery_errors": hub_induced_errors,
        "hub_induced_recovery_error_count": len(hub_induced_errors),
    }


def main() -> None:
    runs = [run(size) for size in SIZES]
    print(json.dumps({
        "schema": "memoria.recovery-after-exhaustion.v2.benchmark.1",
        "constraints": {
            "semantic_regex": False,
            "domain_vocabulary_in_engine": False,
            "learned_weights": False,
            "persistent_mutation_during_recovery": False,
            "cross_occurrence_stitching": False,
        },
        "runs": runs,
        "all_branch_survival_correct": all(run["branch_survival_correct"] for run in runs),
        "all_restart_deterministic": all(run["cold_restart_deterministic"] for run in runs),
        "total_hub_induced_recovery_errors": sum(run["hub_induced_recovery_error_count"] for run in runs),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
