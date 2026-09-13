from __future__ import annotations

import json
from time import perf_counter

from memoria_resolutiva.address_trajectory_v2 import AddressTrajectoryMemory
from memoria_resolutiva.multiscale_resolver_v2 import MultiscaleAddressResolver
from memoria_resolutiva.trajectory_frontier_v2 import TrajectoryFrontierResolver
from memoria_resolutiva.trajectory_rollout_v2 import TrajectoryRolloutResolver


# These texts and the plural question intentionally mirror the qualified restart3
# mobile fixture. They are acceptance data, not vocabulary taught to the V2 engine.
USER_EXPERIENCES = (
    "eu tenho um gato que se chama Lotus",
    "ele tem um irmão, que se chama Vibe",
)
PLURAL_QUERY = "qual nome dos meus gatos?"

# Structural controls use the same stored experiences but query address geometry
# directly. They show whether failure on PLURAL_QUERY is a representation/general-
# ization gap rather than loss of the underlying occurrence.
STRUCTURAL_CONTROLS = (
    ("eu tenho um gato que se chama", "lotus"),
    ("ele tem um irmão, que se chama", "vibe"),
)


def surfaces(matches: object) -> list[str | None]:
    return [getattr(item, "surface", None) for item in matches]


def run() -> dict[str, object]:
    memory = AddressTrajectoryMemory()
    for text in USER_EXPERIENCES:
        memory.ingest(text)

    before = memory.snapshot()
    frontier = TrajectoryFrontierResolver(memory)
    multiscale = MultiscaleAddressResolver(memory)
    rollout = TrajectoryRolloutResolver(memory)

    started = perf_counter()
    plural_frontier = frontier.resolve(PLURAL_QUERY, limit=8)
    plural_ms = (perf_counter() - started) * 1000.0
    plural_multiscale = multiscale.resolve(PLURAL_QUERY, limit=8)
    plural_rollout = rollout.resolve(PLURAL_QUERY, max_steps=8, branch_limit=8)

    plural_frontier_surfaces = surfaces(plural_frontier)
    plural_multiscale_terminals = [item.terminal_surface for item in plural_multiscale]
    plural_rollout_surfaces = [
        list(path.continuation_surfaces) for path in plural_rollout.branches
    ]
    plural_contains_lotus = any(
        value == "lotus"
        for value in plural_frontier_surfaces + plural_multiscale_terminals
    ) or any("lotus" in path for path in plural_rollout_surfaces)
    plural_contains_vibe = any(
        value == "vibe"
        for value in plural_frontier_surfaces + plural_multiscale_terminals
    ) or any("vibe" in path for path in plural_rollout_surfaces)

    controls: list[dict[str, object]] = []
    for query, expected in STRUCTURAL_CONTROLS:
        result = frontier.resolve(query, limit=3)
        winner = result[0].surface if result else None
        controls.append(
            {
                "query": query,
                "expected": expected,
                "winner": winner,
                "hit": winner == expected,
                "top": surfaces(result),
            }
        )

    restored = AddressTrajectoryMemory.restore(before)
    restored_frontier = TrajectoryFrontierResolver(restored)
    restart_equal = frontier.resolve(PLURAL_QUERY, limit=8) == restored_frontier.resolve(
        PLURAL_QUERY, limit=8
    )

    # Restart3's frozen acceptance expects Lotus in the persistent collection packet
    # and explicitly excludes Vibe for this exact question. We report compatibility
    # with that observable contract without pretending the V2 output type is the same.
    restart3_observable_compatible = plural_contains_lotus and not plural_contains_vibe

    return {
        "schema": "memoria.v2.restart3-shared-fixture.1",
        "restart3_reference": {
            "sha": "5fa39ea39ce9d09518e8b726f6297bf8db02ef1c",
            "fixture": "native/mobile/tests/restart.c",
            "observable_contract": {
                "query": PLURAL_QUERY,
                "must_contain": "lotus",
                "must_not_contain": "vibe",
                "byte_stable_across_restart": True,
            },
        },
        "v2": {
            "plural_query_ms": plural_ms,
            "plural_frontier_surfaces": plural_frontier_surfaces,
            "plural_multiscale_terminals": plural_multiscale_terminals,
            "plural_rollout_surfaces": plural_rollout_surfaces,
            "plural_contains_lotus": plural_contains_lotus,
            "plural_contains_vibe": plural_contains_vibe,
            "restart3_observable_compatible": restart3_observable_compatible,
            "structural_controls": controls,
            "all_structural_controls_hit": all(item["hit"] for item in controls),
            "query_read_only": memory.snapshot() == before,
            "cold_restart_deterministic": restart_equal,
        },
        "interpretation": {
            "semantic_regex_added": False,
            "domain_vocabulary_added": False,
            "learned_weights_added": False,
            "plural_reformulation_is_expected_to_be_a_hard_generalization_probe": True,
        },
    }


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, indent=2))
