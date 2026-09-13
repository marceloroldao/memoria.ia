from __future__ import annotations

from dataclasses import dataclass

from .intervention_consequence_v2 import InterventionConsequenceMemory
from .live_infinita_adapter_v2 import LiveWorldStateRequest, to_world_state_candidates
from .prediction_error_v2 import StructuralPredictionError
from .structural_attention_v2 import StructuralAttention, derive_structural_attention
from .world_state_candidate_resolution_v2 import (
    WorldStateCandidate,
    WorldStateCandidateResolution,
    resolve_world_state_candidates,
)


@dataclass(frozen=True, slots=True)
class LiveGymStep:
    frame_id: str
    intervention_id: str
    prediction: WorldStateCandidateResolution
    actual_candidate_id: str
    error: StructuralPredictionError
    attention: StructuralAttention
    learned_episode_id: str | None


class LiveCognitiveGymV2:
    """Minimal continuous synthetic gym for the Live.Infinita bridge.

    One step is deliberately ordered as:

        world frame -> structural prediction -> actual consequence -> prediction
        error -> attention -> optional episode ingestion

    The current observation is never ingested before prediction, preventing future
    leakage. The gym is transport-agnostic and consumes the same request contract
    intended for Godot/WebSocket integration.
    """

    def __init__(
        self,
        memory: InterventionConsequenceMemory | None = None,
        *,
        min_independent_episodes: int = 2,
    ) -> None:
        if min_independent_episodes < 1:
            raise ValueError("min_independent_episodes must be >= 1")
        self.memory = memory if memory is not None else InterventionConsequenceMemory()
        self.min_independent_episodes = min_independent_episodes

    def step(
        self,
        request: LiveWorldStateRequest,
        *,
        actual_candidate_id: str,
        learn: bool = True,
    ) -> LiveGymStep:
        candidates = to_world_state_candidates(request)
        by_id = {candidate.candidate_id: candidate for candidate in candidates}
        if actual_candidate_id not in by_id:
            raise ValueError("actual_candidate_id must name a candidate supplied by the world")

        prediction = resolve_world_state_candidates(
            self.memory,
            request.state.state_addresses,
            request.intervention.address,
            candidates,
            min_independent_episodes=self.min_independent_episodes,
        )
        actual = by_id[actual_candidate_id]
        error = self._classify(prediction, actual)
        attention = derive_structural_attention(error)

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

        return LiveGymStep(
            frame_id=request.state.frame_id,
            intervention_id=request.intervention.intervention_id,
            prediction=prediction,
            actual_candidate_id=actual_candidate_id,
            error=error,
            attention=attention,
            learned_episode_id=learned_episode_id,
        )

    @staticmethod
    def _classify(
        prediction: WorldStateCandidateResolution,
        actual: WorldStateCandidate,
    ) -> StructuralPredictionError:
        predicted = len(prediction.matches)
        observation_depth = max(1, len(actual.consequence_addresses))

        if predicted == 0:
            return StructuralPredictionError(
                kind="unconstrained-observation",
                predicted_branches=0,
                surviving_branches=0,
                eliminated_branches=0,
                observation_depth=observation_depth,
                surprising=False,
            )

        matched_ids = {match.candidate.candidate_id for match in prediction.matches}
        if actual.candidate_id not in matched_ids:
            return StructuralPredictionError(
                kind="total-surprise",
                predicted_branches=predicted,
                surviving_branches=0,
                eliminated_branches=predicted,
                observation_depth=observation_depth,
                surprising=True,
            )

        if predicted == 1:
            return StructuralPredictionError(
                kind="prediction-confirmed",
                predicted_branches=1,
                surviving_branches=1,
                eliminated_branches=0,
                observation_depth=observation_depth,
                surprising=False,
            )

        return StructuralPredictionError(
            kind="hypothesis-reduction",
            predicted_branches=predicted,
            surviving_branches=1,
            eliminated_branches=predicted - 1,
            observation_depth=observation_depth,
            surprising=False,
        )
