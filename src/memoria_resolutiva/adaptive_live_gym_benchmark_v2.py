from __future__ import annotations

from dataclasses import dataclass

from .live_cognitive_gym_v2 import LiveCognitiveGymV2
from .live_infinita_adapter_v2 import make_live_request


@dataclass(frozen=True, slots=True)
class AdaptiveGymReport:
    cycles: int
    switch_cycle: int
    confirmed: int
    hypothesis_reductions: int
    total_surprises: int
    unconstrained: int
    reorientations: int
    informative: int
    routine: int
    first_post_switch_surprise: int | None
    first_post_switch_confirmation: int | None
    final_prediction_reason: str
    final_resolved: bool
    final_ambiguous: bool
    episodes: int


def run_adaptive_world_benchmark(
    cycles: int,
    *,
    switch_cycle: int | None = None,
    min_independent_episodes: int = 2,
) -> AdaptiveGymReport:
    """Run a deterministic two-regime world without deleting historical evidence.

    Regime A produces candidate `a` until switch_cycle; regime B produces `b`
    afterwards. Both candidates are always visible to the V2 resolver. This benchmark
    intentionally measures whether the live cognitive state adapts while persistent
    memory retains both historical regimes. It does not inject recency weights.
    """
    if cycles < 4:
        raise ValueError("cycles must be >= 4")
    switch = switch_cycle if switch_cycle is not None else cycles // 2
    if switch < 2 or switch >= cycles:
        raise ValueError("switch_cycle must leave at least two cycles before and after switch")

    gym = LiveCognitiveGymV2(min_independent_episodes=min_independent_episodes)
    confirmed = reductions = surprises = unconstrained = 0
    reorient = informative = routine = 0
    first_surprise = None
    first_confirmation = None
    last = None

    for index in range(cycles):
        request = make_live_request(
            frame_id=f"F{index}",
            state_addresses=("world:anchor", "world:zone"),
            intervention_id=f"I{index}",
            intervention_address="action:step",
            candidates=(
                ("a", ("effect:a",), ("world:anchor", "effect:a")),
                ("b", ("effect:b",), ("world:anchor", "effect:b")),
            ),
            provenance="adaptive-live-gym-v2",
        )
        actual = "a" if index < switch else "b"
        last = gym.step(request, actual_candidate_id=actual, learn=True)

        if last.error.kind == "prediction-confirmed":
            confirmed += 1
            if index >= switch and first_confirmation is None:
                first_confirmation = index
        elif last.error.kind == "hypothesis-reduction":
            reductions += 1
        elif last.error.kind == "total-surprise":
            surprises += 1
            if index >= switch and first_surprise is None:
                first_surprise = index
        elif last.error.kind == "unconstrained-observation":
            unconstrained += 1

        if last.attention.level == "reorient":
            reorient += 1
        elif last.attention.level == "informative":
            informative += 1
        else:
            routine += 1

    assert last is not None
    return AdaptiveGymReport(
        cycles=cycles,
        switch_cycle=switch,
        confirmed=confirmed,
        hypothesis_reductions=reductions,
        total_surprises=surprises,
        unconstrained=unconstrained,
        reorientations=reorient,
        informative=informative,
        routine=routine,
        first_post_switch_surprise=first_surprise,
        first_post_switch_confirmation=first_confirmation,
        final_prediction_reason=last.prediction.reason,
        final_resolved=last.prediction.resolved,
        final_ambiguous=last.prediction.ambiguous,
        episodes=len(gym.memory.snapshot()),
    )
