from __future__ import annotations

from dataclasses import dataclass

from .intervention_consequence_v2 import InterventionConsequenceMemory
from .live_cognitive_gym_v2 import LiveCognitiveGymV2, LiveGymStep
from .live_infinita_adapter_v2 import LiveWorldStateRequest, to_world_state_candidates
from .prediction_error_v2 import StructuralPredictionError
from .structural_attention_v2 import StructuralAttention, derive_structural_attention
from .temporal_regime_v2 import (
    TemporalRegimeState,
    TemporalRegimeUpdate,
    initial_temporal_regime,
    observe_temporal_regime,
)
from .world_state_candidate_resolution_v2 import (
    WorldStateCandidate,
    WorldStateCandidateMatch,
    WorldStateCandidateResolution,
    resolve_world_state_candidates,
)


@dataclass(frozen=True, slots=True)
class RegimeAwareGymStep:
    base_prediction: WorldStateCandidateResolution
    effective_prediction: WorldStateCandidateResolution
    actual_candidate_id: str
    error: StructuralPredictionError
    attention: StructuralAttention
    regime_update: TemporalRegimeUpdate
    learned_episode_id: str | None


class RegimeAwareLiveCognitiveGymV2:
    """Live gym with explicit separation between history and active continuity.

    Persistent structural memory may retain several historically supported futures.
    TemporalRegimeState is ephemeral and can select one currently continuous concrete
    candidate among structurally equivalent alternatives. Selection never deletes or
    downweights the historical alternatives.
    """

    def __init__(
        self,
        memory: InterventionConsequenceMemory | None = None,
        *,
        min_independent_episodes: int = 2,
        min_contiguous_support: int = 2,
        regime: TemporalRegimeState | None = None,
    ) -> None:
        if min_contiguous_support < 1:
            raise ValueError("min_contiguous_support must be >= 1")
        self.base = LiveCognitiveGymV2(
            memory=memory,
            min_independent_episodes=min_independent_episodes,
        )
        self.min_contiguous_support = min_contiguous_support
        self.regime = regime if regime is not None else initial_temporal_regime()

    @property
    def memory(self) -> InterventionConsequenceMemory:
        return self.base.memory

    @staticmethod
    def _select_active(
        prediction: WorldStateCandidateResolution,
        active_key: str | None,
    ) -> WorldStateCandidateResolution:
        if not active_key or not prediction.matches:
            return prediction

        selected = tuple(
            match for match in prediction.matches if match.candidate.candidate_id == active_key
        )
        if len(selected) != 1:
            return prediction

        match = selected[0]
        return WorldStateCandidateResolution(
            structural=prediction.structural,
            matches=(match,),
            resolved_candidate=match.candidate,
            resolved=True,
            ambiguous=False,
            reason="active-temporal-regime",
        )

    def step(
        self,
        request: LiveWorldStateRequest,
        *,
        actual_candidate_id: str,
        learn: bool = True,
    ) -> RegimeAwareGymStep:
        candidates = to_world_state_candidates(request)
        by_id = {candidate.candidate_id: candidate for candidate in candidates}
        if actual_candidate_id not in by_id:
            raise ValueError("actual_candidate_id must name a candidate supplied by the world")

        base_prediction = resolve_world_state_candidates(
            self.memory,
            request.state.state_addresses,
            request.intervention.address,
            candidates,
            min_independent_episodes=self.base.min_independent_episodes,
        )
        effective = self._select_active(base_prediction, self.regime.active_key)
        actual = by_id[actual_candidate_id]
        error = LiveCognitiveGymV2._classify(effective, actual)
        attention = derive_structural_attention(error)

        regime_update = observe_temporal_regime(
            self.regime,
            actual_candidate_id,
            min_contiguous_support=self.min_contiguous_support,
        )
        self.regime = regime_update.current

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

        return RegimeAwareGymStep(
            base_prediction=base_prediction,
            effective_prediction=effective,
            actual_candidate_id=actual_candidate_id,
            error=error,
            attention=attention,
            regime_update=regime_update,
            learned_episode_id=learned_episode_id,
        )
