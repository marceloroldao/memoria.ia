from __future__ import annotations

from dataclasses import dataclass

from .intervention_consequence_v2 import InterventionConsequenceMemory
from .live_cognitive_gym_v2 import LiveCognitiveGymV2
from .live_infinita_adapter_v2 import make_live_request, to_world_state_candidates
from .structural_attention_v2 import derive_structural_attention
from .temporal_regime_state_v2 import TemporalRegimeState, constrain_prediction_to_active_regime, observe_regime
from .world_state_candidate_resolution_v2 import resolve_world_state_candidates


@dataclass(frozen=True, slots=True)
class MultiRegimeStressReport:
    cycles: int
    switches_expected: int
    switches_observed: int
    surprises: int
    reorientations: int
    confirmations: int
    final_regime_consequence: tuple[str, ...] | None
    historical_hypotheses: int
    historical_episodes: int


def run_multi_regime_stress(
    *,
    segment_length: int = 20,
    min_contiguous_support: int = 2,
    inject_single_noise: bool = True,
) -> MultiRegimeStressReport:
    """Exercise A -> B -> A continuity while preserving historical alternatives.

    A single B observation may be injected during the first A segment. It must not
    switch the active regime because regime changes require contiguous support.
    The world then genuinely changes to B and later returns to A.
    """
    if segment_length < max(4, min_contiguous_support + 2):
        raise ValueError("segment_length too small for regime qualification")
    if min_contiguous_support < 2:
        raise ValueError("min_contiguous_support must be >= 2")

    memory = InterventionConsequenceMemory()
    regime = TemporalRegimeState.empty()
    sequence = ["a"] * segment_length + ["b"] * segment_length + ["a"] * segment_length
    if inject_single_noise:
        sequence[segment_length // 2] = "b"

    confirmations = surprises = reorientations = 0
    for index, actual_id in enumerate(sequence):
        request = make_live_request(
            frame_id=f"MR{index}",
            state_addresses=("world:anchor", "world:zone"),
            intervention_id=f"MI{index}",
            intervention_address="action:step",
            candidates=(
                ("a", ("effect:a",), ("world:anchor", "effect:a")),
                ("b", ("effect:b",), ("world:anchor", "effect:b")),
            ),
            provenance="multi-regime-stress-v2",
        )
        candidates = to_world_state_candidates(request)
        by_id = {candidate.candidate_id: candidate for candidate in candidates}
        actual = by_id[actual_id]

        historical = resolve_world_state_candidates(
            memory,
            request.state.state_addresses,
            request.intervention.address,
            candidates,
            min_independent_episodes=2,
        )
        effective = constrain_prediction_to_active_regime(historical, regime)
        error = LiveCognitiveGymV2._classify(effective, actual)
        attention = derive_structural_attention(error)
        if error.kind == "prediction-confirmed":
            confirmations += 1
        elif error.kind == "total-surprise":
            surprises += 1
        if attention.level == "reorient":
            reorientations += 1

        regime = observe_regime(
            regime,
            actual,
            min_contiguous_support=min_contiguous_support,
        )
        memory.ingest_episode(
            request.state.state_addresses,
            request.intervention.address,
            actual.consequence_addresses,
            actual.next_state_addresses,
            provenance=request.state.provenance,
        )

    final = regime.active.consequence_addresses if regime.active is not None else None
    historical = memory.resolve(
        ("world:anchor", "world:zone"),
        "action:step",
        min_independent_episodes=2,
    )
    return MultiRegimeStressReport(
        cycles=len(sequence),
        switches_expected=2,
        switches_observed=regime.switches,
        surprises=surprises,
        reorientations=reorientations,
        confirmations=confirmations,
        final_regime_consequence=final,
        historical_hypotheses=len(historical.hypotheses),
        historical_episodes=len(memory.snapshot()),
    )
