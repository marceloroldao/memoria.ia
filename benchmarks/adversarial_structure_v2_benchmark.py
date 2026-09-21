from __future__ import annotations

import json
from time import perf_counter

from memoria_resolutiva.address_trajectory_v2 import AddressTrajectoryMemory
from memoria_resolutiva.dynamic_branch_state_v2 import DynamicBranchStateResolver
from memoria_resolutiva.multiscale_resolver_v2 import MultiscaleMatch, ScaleEvidence


def evidence(depth: int, overlap: int, ordered: int) -> ScaleEvidence:
    return ScaleEvidence(
        depth=depth,
        query_addresses=("q1", "q2", "q3"),
        trajectory_addresses=("t1", "t2", "t3", "t4"),
        overlap=overlap,
        ordered_overlap=ordered,
        max_hops_to_terminal=1,
        sum_hops_to_terminal=1,
    )


def false_hierarchical_consensus_probe() -> dict[str, object]:
    strong = MultiscaleMatch(
        trajectory_id="AT-strong",
        raw_text="",
        terminal_surface="correct",
        scale_evidence=(evidence(0, 3, 3),),
        supporting_depths=(0,),
    )
    derived = MultiscaleMatch(
        trajectory_id="AT-derived",
        raw_text="",
        terminal_surface="wrong",
        scale_evidence=(
            evidence(0, 2, 2),
            evidence(1, 2, 2),
            evidence(2, 2, 2),
        ),
        supporting_depths=(0, 1, 2),
    )
    ordered = sorted((strong, derived), key=lambda item: item.multiscale_key, reverse=True)
    return {
        "winner": ordered[0].terminal_surface,
        "false_consensus": ordered[0].terminal_surface != "correct",
        "strong_atomic_overlap": strong.atomic_evidence.overlap if strong.atomic_evidence else None,
        "derived_atomic_overlap": derived.atomic_evidence.overlap if derived.atomic_evidence else None,
        "derived_depth_count": len(derived.supporting_depths),
    }


def dense_hub_probe(size: int, branch_limit: int = 16) -> dict[str, object]:
    memory = AddressTrajectoryMemory()
    memory.ingest("start expected")
    for index in range(size):
        memory.ingest(f"source{index} hub future{index}")

    resolver = DynamicBranchStateResolver(memory)
    state = resolver.begin("start")
    unexpected = memory.decompose("unseen")[0].address
    state = resolver.observe_address(state, unexpected)

    before = memory.snapshot()
    started = perf_counter()
    recovery = resolver.recover_text(
        state,
        "unseen hub",
        branch_limit=branch_limit,
        candidate_limit=max(64, size + 1),
    )
    elapsed_ms = (perf_counter() - started) * 1000.0

    restored = AddressTrajectoryMemory.restore(before)
    restored_resolver = DynamicBranchStateResolver(restored)
    restored_state = restored_resolver.begin("start")
    restored_state = restored_resolver.observe_address(restored_state, unexpected)
    repeated = restored_resolver.recover_text(
        restored_state,
        "unseen hub",
        branch_limit=branch_limit,
        candidate_limit=max(64, size + 1),
    )

    return {
        "hub_trajectory_count": size,
        "branch_limit": branch_limit,
        "recovered": recovery.recovered_any,
        "active_branch_count": len(recovery.recovered.active),
        "fail_closed": recovery.recovered.exhausted and not recovery.recovered_any,
        "false_reseed": recovery.recovered_any,
        "read_only": memory.snapshot() == before,
        "restart_deterministic": recovery == repeated,
        "recovery_ms": elapsed_ms,
    }


def main() -> None:
    hierarchy = false_hierarchical_consensus_probe()
    hubs = [dense_hub_probe(size) for size in (100, 1000, 10000)]
    report = {
        "schema": "memoria.address-trajectory.v2.adversarial.1",
        "constraints": {
            "semantic_regex": False,
            "domain_vocabulary_in_engine": False,
            "learned_weights": False,
            "persistent_mutation_during_recovery": False,
        },
        "false_hierarchical_consensus": hierarchy,
        "dense_hub_recovery": hubs,
        "all_hub_reseeds_fail_closed": all(item["fail_closed"] for item in hubs),
        "total_false_reseeds": sum(int(item["false_reseed"]) for item in hubs),
        "all_restart_deterministic": all(item["restart_deterministic"] for item in hubs),
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
