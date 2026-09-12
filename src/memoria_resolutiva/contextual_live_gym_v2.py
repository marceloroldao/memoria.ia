from __future__ import annotations

from dataclasses import dataclass

from .contextual_temporal_regime_v2 import (
    ContextualRegimeKey,
    ContextualTemporalRegimes,
    contextual_regime_key,
    observe_contextual_regime,
)
from .intervention_consequence_v2 import InterventionConsequenceMemory
from .live_cognitive_gym_v2 import LiveCognitiveGymV2
from .live_infinita_adapter_v2 import LiveWorldStateRequest, to_world_state_candidates
from .prediction_error_v2 import StructuralPredictionError
from .structural_attention_v2 import StructuralAttention, derive_structural_attention
from .temporal_regime_state_v2 import TemporalRegimeState, constrain_prediction_to_active_regime
from .world_state_candidate_resolution_v2 import WorldStateCandidateResolution, resolve_world_state_candidates


@dataclass(frozen=True, slots=True)
class ContextualLiveGymStep:
    context_key: ContextualRegimeKey
    prior_regime: TemporalRegimeState
    current_regime: TemporalRegimeState
    base_prediction: WorldStateCandidateResolution
    effective_prediction: WorldStateCandidateResolution
    actual_candidate_id: str
    error: StructuralPredictionError
    attention: StructuralAttention
    learned_episode_id: str | None


class ContextualLiveCognitiveGymV2:
    """Continuous V2 gym with independent active continuity per structural context.

    Persistent intervention/consequence memory remains global and historical.  The
    ephemeral contextual regime collection only narrows structurally compatible
    candidates for the current state topology + intervention role.  Observations in
    one context never advance or challenge another context's continuity state.
    """

    def __init__(
        self,
        memory: InterventionConsequenceMemory | None = None,
        *,
        min_independent_episodes: int = 2,
        min_contiguous_support: int = 2,
        regimes: ContextualTemporalRegimes | None = None,
    ) -> None:
        if min_contiguous_support < 2:
            raise ValueError("min_contiguous_support must be >= 2")
        self.memory = memory if memory is not None else InterventionConsequenceMemory()
        self.min_independent_episodes = min_independent_episodes
        self.min_contiguous_support = min_contiguous_support
        self.regimes = regimes if regimes is not None else ContextualTemporalRegimes.empty()

    def step(
        self,
        request: LiveWorldStateRequest,
        *,
        actual_candidate_id: str,
        learn: bool = True,
    ) -> ContextualLiveGymStep:
        candidates = to_world_state_candidates(request)
        by_id = {candidate.candidate_id: candidate for candidate in candidates}
        if actual_candidate_id not in by_id:
            raise ValueError("actual_candidate_id must name a candidate supplied by the world")

        key = contextual_regime_key(
            request.state.state_addresses,
            request.intervention.address,
        )
        prior_regime = self.regimes.get(key)
        base_prediction = resolve_world_state_candidates(
            self.memory,
            request.state.state_addresses,
            request.intervention.address,
            candidates,
            min_independent_episodes=self.min_independent_episodes,
        )
        effective = constrain_prediction_to_active_regime(base_prediction, prior_regime)
        actual = by_id[actual_candidate_id]
        error = LiveCognitiveGymV2._classify(effective, actual)
        attention = derive_structural_attention(error)

        # Observation updates only this structural context after prediction.
        self.regimes = observe_contextual_regime(
            self.regimes,
            request.state.state_addresses,
            request.intervention.address,
            actual,
            min_contiguous_support=self.min_contiguous_support,
        )
        current_regime = self.regimes.get(key)

        learned_episode_id: str | None = None
        if learn:
            episode = self.memory.ingest_episode(
                request.state.state_addresses,
                request.intervention.address,
                actual.consequence_addresses,
                actual.next_state_addresses,
                provenance=request.state.provenance,
            )
            learned_episode_id = episode.episode_id

        return ContextualLiveGymStep(
            context_key=key,
            prior_regime=prior_regime,
            current_regime=current_regime,
            base_prediction=base_prediction,
            effective_prediction=effective,
            actual_candidate_id=actual_candidate_id,
            error=error,
            attention=attention,
            learned_episode_id=learned_episode_id,
        )
