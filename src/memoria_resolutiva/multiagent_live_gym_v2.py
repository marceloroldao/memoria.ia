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
class MultiAgentObservation:
    """One agent-local observation/intervention inside a shared world tick.

    `agent_id` is an adapter-provided stable address/namespace. The V2 core assigns no
    semantic meaning to it; it is used only to prevent one agent's ephemeral cognitive
    continuity from overwriting another agent's state.
    """

    agent_id: str
    request: LiveWorldStateRequest
    actual_candidate_id: str


@dataclass(frozen=True, slots=True)
class AgentContextualRegimes:
    entries: tuple[tuple[str, ContextualTemporalRegimes], ...]

    @classmethod
    def empty(cls) -> "AgentContextualRegimes":
        return cls(())

    def get(self, agent_id: str) -> ContextualTemporalRegimes:
        for stored_id, regimes in self.entries:
            if stored_id == agent_id:
                return regimes
        return ContextualTemporalRegimes.empty()

    def with_regimes(
        self,
        agent_id: str,
        regimes: ContextualTemporalRegimes,
    ) -> "AgentContextualRegimes":
        updated = [(stored_id, stored) for stored_id, stored in self.entries if stored_id != agent_id]
        updated.append((agent_id, regimes))
        updated.sort(key=lambda item: item[0])
        return AgentContextualRegimes(tuple(updated))


@dataclass(frozen=True, slots=True)
class MultiAgentGymStep:
    agent_id: str
    context_key: ContextualRegimeKey
    prior_regime: TemporalRegimeState
    current_regime: TemporalRegimeState
    base_prediction: WorldStateCandidateResolution
    effective_prediction: WorldStateCandidateResolution
    actual_candidate_id: str
    error: StructuralPredictionError
    attention: StructuralAttention
    learned_episode_id: str | None


class MultiAgentLiveCognitiveGymV2:
    """Shared historical memory with agent-local contextual cognitive continuity.

    A batch represents one simultaneous world tick. All predictions are computed
    before any current-tick episode is ingested, so agent ordering cannot create a
    false causal path or allow later agents to learn from earlier agents in the same
    tick. Historical memory is shared; ephemeral regimes are namespaced per agent and
    structural context.
    """

    def __init__(
        self,
        memory: InterventionConsequenceMemory | None = None,
        *,
        min_independent_episodes: int = 2,
        min_contiguous_support: int = 2,
        agent_regimes: AgentContextualRegimes | None = None,
    ) -> None:
        if min_independent_episodes < 1:
            raise ValueError("min_independent_episodes must be >= 1")
        if min_contiguous_support < 2:
            raise ValueError("min_contiguous_support must be >= 2")
        self.memory = memory if memory is not None else InterventionConsequenceMemory()
        self.min_independent_episodes = min_independent_episodes
        self.min_contiguous_support = min_contiguous_support
        self.agent_regimes = agent_regimes if agent_regimes is not None else AgentContextualRegimes.empty()

    def step_batch(
        self,
        observations: tuple[MultiAgentObservation, ...],
        *,
        learn: bool = True,
    ) -> tuple[MultiAgentGymStep, ...]:
        if not observations:
            return ()
        agent_ids = [item.agent_id for item in observations]
        if any(not agent_id for agent_id in agent_ids):
            raise ValueError("agent_id must be non-empty")
        if len(set(agent_ids)) != len(agent_ids):
            raise ValueError("one observation per agent is allowed in a simultaneous batch")

        # Stable order makes output and state deterministic while preserving simultaneity:
        # no episode is ingested until every prediction has been computed.
        ordered = tuple(sorted(observations, key=lambda item: item.agent_id))
        pending: list[tuple[MultiAgentObservation, object, ContextualRegimeKey, TemporalRegimeState,
                            WorldStateCandidateResolution, WorldStateCandidateResolution,
                            StructuralPredictionError, StructuralAttention, ContextualTemporalRegimes]] = []

        for item in ordered:
            candidates = to_world_state_candidates(item.request)
            by_id = {candidate.candidate_id: candidate for candidate in candidates}
            if item.actual_candidate_id not in by_id:
                raise ValueError("actual_candidate_id must name a candidate supplied by the world")

            key = contextual_regime_key(
                item.request.state.state_addresses,
                item.request.intervention.address,
            )
            regimes = self.agent_regimes.get(item.agent_id)
            prior_regime = regimes.get(key)
            base_prediction = resolve_world_state_candidates(
                self.memory,
                item.request.state.state_addresses,
                item.request.intervention.address,
                candidates,
                min_independent_episodes=self.min_independent_episodes,
            )
            effective = constrain_prediction_to_active_regime(base_prediction, prior_regime)
            actual = by_id[item.actual_candidate_id]
            error = LiveCognitiveGymV2._classify(effective, actual)
            attention = derive_structural_attention(error)
            next_regimes = observe_contextual_regime(
                regimes,
                item.request.state.state_addresses,
                item.request.intervention.address,
                actual,
                min_contiguous_support=self.min_contiguous_support,
            )
            pending.append(
                (
                    item,
                    actual,
                    key,
                    prior_regime,
                    base_prediction,
                    effective,
                    error,
                    attention,
                    next_regimes,
                )
            )

        # Commit ephemeral agent-local states only after all predictions are complete.
        next_agent_regimes = self.agent_regimes
        for item, _actual, _key, _prior, _base, _effective, _error, _attention, next_regimes in pending:
            next_agent_regimes = next_agent_regimes.with_regimes(item.agent_id, next_regimes)
        self.agent_regimes = next_agent_regimes

        # Persistent historical learning is also second-phase to prevent intra-tick leakage.
        learned_ids: dict[str, str | None] = {item.agent_id: None for item in ordered}
        if learn:
            for item, actual, _key, _prior, _base, _effective, _error, _attention, _next_regimes in pending:
                episode = self.memory.ingest_episode(
                    item.request.state.state_addresses,
                    item.request.intervention.address,
                    actual.consequence_addresses,
                    actual.next_state_addresses,
                    provenance=item.request.state.provenance,
                )
                learned_ids[item.agent_id] = episode.episode_id

        result = []
        for item, _actual, key, prior, base, effective, error, attention, next_regimes in pending:
            result.append(
                MultiAgentGymStep(
                    agent_id=item.agent_id,
                    context_key=key,
                    prior_regime=prior,
                    current_regime=next_regimes.get(key),
                    base_prediction=base,
                    effective_prediction=effective,
                    actual_candidate_id=item.actual_candidate_id,
                    error=error,
                    attention=attention,
                    learned_episode_id=learned_ids[item.agent_id],
                )
            )
        return tuple(result)
