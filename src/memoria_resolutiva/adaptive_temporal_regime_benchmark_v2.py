from __future__ import annotations

from dataclasses import dataclass

from .intervention_consequence_v2 import InterventionConsequenceMemory
from .live_cognitive_gym_v2 import LiveCognitiveGymV2
from .live_infinita_adapter_v2 import make_live_request, to_world_state_candidates
from .structural_attention_v2 import derive_structural_attention
from .temporal_regime_state_v2 import (
    TemporalRegimeState,
    constrain_prediction_to_active_regime,
    observe_regime,
)
from .world_state_candidate_resolution_v2 import resolve_world_state_candidates


@dataclass(frozen=True, slots=True)
class TemporalRegimeBenchmarkReport:
    cycles: int
    switch_cycle: int
    confirmed: int
    hypothesis_reductions: int
    total_surprises: int
    unconstrained: int
    reorientations: int
    first_post_switch_surprise: int | None
    first_post_switch_confirmation: int | None
    regime_switch_cycle: int | None
    adaptation_latency: int | None
    final_regime_consequence: tuple[str, ...] | None
    regime_switches: int
    historical_episodes: int


def run_temporal_regime_benchmark(
    cycles: int,
    *,
    switch_cycle: int | None = None,
    min_independent_episodes: int = 2,
    min_contiguous_support: int = 2,
) -> TemporalRegimeBenchmarkReport:
    """Run A->B world change with historical memory plus ephemeral active regime.

    Prediction uses persistent structural memory first, then current regime continuity
    to narrow concrete ambiguity.  The actual observation is applied only afterwards,
    and only then can it update the regime and persistent episode history.
    """
    if cycles < 6:
        raise ValueError("cycles must be >= 6")
    switch = switch_cycle if switch_cycle is not None else cycles // 2
    if switch < 3 or switch > cycles - 3:
        raise ValueError("switch_cycle must leave at least three cycles before and after switch")

    memory = InterventionConsequenceMemory()
    regime = TemporalRegimeState.empty()
    confirmed = reductions = surprises = unconstrained = reorientations = 0
    first_surprise = first_confirmation = regime_switch_cycle = None

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
            provenance="adaptive-temporal-regime-v2",
        )
        candidates = to_world_state_candidates(request)
        by_id = {candidate.candidate_id: candidate for candidate in candidates}
        actual_id = "a" if index < switch else "b"
        actual = by_id[actual_id]

        historical_prediction = resolve_world_state_candidates(
            memory,
            request.state.state_addresses,
            request.intervention.address,
            candidates,
            min_independent_episodes=min_independent_episodes,
        )
        prediction = constrain_prediction_to_active_regime(historical_prediction, regime)
        error = LiveCognitiveGymV2._classify(prediction, actual)
        attention = derive_structural_attention(error)

        if error.kind == "prediction-confirmed":
            confirmed += 1
            if index >= switch and first_confirmation is None:
                first_confirmation = index
        elif error.kind == "hypothesis-reduction":
            reductions += 1
        elif error.kind == "total-surprise":
            surprises += 1
            if index >= switch and first_surprise is None:
                first_surprise = index
        elif error.kind == "unconstrained-observation":
            unconstrained += 1

        if attention.level == "reorient":
            reorientations += 1

        previous_switches = regime.switches
        regime = observe_regime(
            regime,
            actual,
            min_contiguous_support=min_contiguous_support,
        )
        if regime.switches > previous_switches and regime_switch_cycle is None:
            regime_switch_cycle = index

        memory.ingest_episode(
            request.state.state_addresses,
            request.intervention.address,
            actual.consequence_addresses,
            actual.next_state_addresses,
            provenance=request.state.provenance,
        )

    final_consequence = regime.active.consequence_addresses if regime.active is not None else None
    latency = None if first_confirmation is None else first_confirmation - switch
    return TemporalRegimeBenchmarkReport(
        cycles=cycles,
        switch_cycle=switch,
        confirmed=confirmed,
        hypothesis_reductions=reductions,
        total_surprises=surprises,
        unconstrained=unconstrained,
        reorientations=reorientations,
        first_post_switch_surprise=first_surprise,
        first_post_switch_confirmation=first_confirmation,
        regime_switch_cycle=regime_switch_cycle,
        adaptation_latency=latency,
        final_regime_consequence=final_consequence,
        regime_switches=regime.switches,
        historical_episodes=len(memory.snapshot()),
    )
