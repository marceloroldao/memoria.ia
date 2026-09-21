from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class InterventionEpisode:
    """One observed state -> intervention -> consequence episode.

    The adapter supplies stable addresses only. The engine does not interpret the
    meaning of state, action, or consequence; it only preserves their causal order.
    """

    episode_id: str
    state_addresses: tuple[str, ...]
    intervention_address: str
    consequence_addresses: tuple[str, ...]
    next_state_addresses: tuple[str, ...]
    provenance: str = ""


@dataclass(frozen=True, slots=True)
class ConsequenceHypothesis:
    consequence_addresses: tuple[str, ...]
    next_state_addresses: tuple[str, ...]
    supporting_episode_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class InterventionResolution:
    state_addresses: tuple[str, ...]
    intervention_address: str
    hypotheses: tuple[ConsequenceHypothesis, ...]
    resolved: bool
    ambiguous: bool
    reason: str


class InterventionConsequenceMemory:
    """Read-only resolver over explicitly delimited causal episodes.

    This layer does not claim philosophical causation. It records an intervention
    boundary supplied by an external world adapter and asks what consequences were
    observed after the same state+intervention configuration in independent episodes.
    """

    def __init__(self) -> None:
        self._episodes: list[InterventionEpisode] = []
        self._next_id = 1

    @staticmethod
    def _collapse(addresses: tuple[str, ...]) -> tuple[str, ...]:
        output: list[str] = []
        current: str | None = None
        for address in addresses:
            if not address:
                raise ValueError("addresses must be non-empty")
            if address == current:
                continue
            output.append(address)
            current = address
        return tuple(output)

    def ingest_episode(
        self,
        state_addresses: tuple[str, ...],
        intervention_address: str,
        consequence_addresses: tuple[str, ...],
        next_state_addresses: tuple[str, ...],
        *,
        provenance: str = "",
    ) -> InterventionEpisode:
        if not intervention_address:
            raise ValueError("intervention_address must be non-empty")
        state = self._collapse(state_addresses)
        consequence = self._collapse(consequence_addresses)
        next_state = self._collapse(next_state_addresses)
        if not state:
            raise ValueError("state_addresses must be non-empty")
        if not consequence:
            raise ValueError("consequence_addresses must be non-empty")
        if not next_state:
            raise ValueError("next_state_addresses must be non-empty")

        episode = InterventionEpisode(
            episode_id=f"IC{self._next_id}",
            state_addresses=state,
            intervention_address=intervention_address,
            consequence_addresses=consequence,
            next_state_addresses=next_state,
            provenance=provenance,
        )
        self._next_id += 1
        self._episodes.append(episode)
        return episode

    def snapshot(self) -> tuple[InterventionEpisode, ...]:
        return tuple(self._episodes)

    @classmethod
    def restore(cls, episodes: tuple[InterventionEpisode, ...]) -> "InterventionConsequenceMemory":
        memory = cls()
        memory._episodes = list(episodes)
        max_id = 0
        for episode in episodes:
            if episode.episode_id.startswith("IC"):
                try:
                    max_id = max(max_id, int(episode.episode_id[2:]))
                except ValueError:
                    pass
        memory._next_id = max_id + 1
        return memory

    def resolve(
        self,
        state_addresses: tuple[str, ...],
        intervention_address: str,
        *,
        min_independent_episodes: int = 2,
    ) -> InterventionResolution:
        if min_independent_episodes < 1:
            raise ValueError("min_independent_episodes must be >= 1")
        state = self._collapse(state_addresses)
        if not state or not intervention_address:
            return InterventionResolution(state, intervention_address, (), False, False, "invalid-query")

        grouped: dict[tuple[tuple[str, ...], tuple[str, ...]], list[str]] = {}
        for episode in self._episodes:
            if episode.state_addresses != state:
                continue
            if episode.intervention_address != intervention_address:
                continue
            key = (episode.consequence_addresses, episode.next_state_addresses)
            grouped.setdefault(key, []).append(episode.episode_id)

        hypotheses: list[ConsequenceHypothesis] = []
        for (consequence, next_state), episode_ids in grouped.items():
            independent = tuple(sorted(set(episode_ids)))
            if len(independent) < min_independent_episodes:
                continue
            hypotheses.append(
                ConsequenceHypothesis(
                    consequence_addresses=consequence,
                    next_state_addresses=next_state,
                    supporting_episode_ids=independent,
                )
            )

        hypotheses.sort(
            key=lambda item: (
                item.consequence_addresses,
                item.next_state_addresses,
                item.supporting_episode_ids,
            )
        )
        visible = tuple(hypotheses)
        if not visible:
            reason = "insufficient-supported-consequence"
        elif len(visible) == 1:
            reason = "single-supported-consequence"
        else:
            reason = "competing-supported-consequences"

        return InterventionResolution(
            state_addresses=state,
            intervention_address=intervention_address,
            hypotheses=visible,
            resolved=len(visible) == 1,
            ambiguous=len(visible) > 1,
            reason=reason,
        )
