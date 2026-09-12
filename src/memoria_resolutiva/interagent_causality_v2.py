from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class InteragentOccurrence:
    episode_id: str
    source_agent: str
    source_intervention: str
    target_agent: str
    target_observation: tuple[str, ...]
    provenance: str


@dataclass(frozen=True, slots=True)
class InteragentRelation:
    source_intervention: str
    target_observation: tuple[str, ...]
    independent_episodes: tuple[str, ...]
    supported: bool
    reason: str


class InteragentCausalMemory:
    """Conservative cross-agent recurrence store.

    Temporal co-occurrence is stored as evidence, not asserted as causality. A relation
    becomes *supported* only after the same intervention->observation pattern appears
    in enough independent episodes. Historical alternatives are preserved.
    """

    def __init__(self) -> None:
        self._occurrences: list[InteragentOccurrence] = []

    def observe(
        self,
        *,
        episode_id: str,
        source_agent: str,
        source_intervention: str,
        target_agent: str,
        target_observation: tuple[str, ...],
        provenance: str = "live.infinita",
    ) -> InteragentOccurrence:
        if not episode_id or not source_agent or not target_agent or not source_intervention:
            raise ValueError("episode, agents and intervention must be non-empty")
        if source_agent == target_agent:
            raise ValueError("interagent occurrence requires distinct agents")
        if not target_observation or any(not item for item in target_observation):
            raise ValueError("target_observation must contain non-empty addresses")

        occurrence = InteragentOccurrence(
            episode_id=episode_id,
            source_agent=source_agent,
            source_intervention=source_intervention,
            target_agent=target_agent,
            target_observation=tuple(target_observation),
            provenance=provenance,
        )
        self._occurrences.append(occurrence)
        return occurrence

    def resolve(
        self,
        *,
        source_intervention: str,
        target_observation: tuple[str, ...],
        min_independent_episodes: int = 2,
    ) -> InteragentRelation:
        if min_independent_episodes < 2:
            raise ValueError("min_independent_episodes must be >= 2")

        episode_ids = sorted(
            {
                item.episode_id
                for item in self._occurrences
                if item.source_intervention == source_intervention
                and item.target_observation == tuple(target_observation)
            }
        )
        supported = len(episode_ids) >= min_independent_episodes
        return InteragentRelation(
            source_intervention=source_intervention,
            target_observation=tuple(target_observation),
            independent_episodes=tuple(episode_ids),
            supported=supported,
            reason=("recurrent-cross-agent-pattern" if supported else "insufficient-independent-support"),
        )

    def snapshot(self) -> tuple[InteragentOccurrence, ...]:
        return tuple(self._occurrences)

    @classmethod
    def restore(cls, snapshot: tuple[InteragentOccurrence, ...]) -> "InteragentCausalMemory":
        memory = cls()
        memory._occurrences = list(snapshot)
        return memory
