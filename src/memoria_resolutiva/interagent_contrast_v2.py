from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class InteragentContrastObservation:
    episode_id: str
    source_intervention_present: bool
    target_observation: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class InteragentContrastResult:
    target_observation: tuple[str, ...]
    exposed_episodes: tuple[str, ...]
    control_episodes: tuple[str, ...]
    supported: bool
    discriminative: bool
    reason: str


class InteragentContrastMemory:
    """Contrast recurrent cross-agent observations against negative controls.

    The engine never promotes temporal precedence directly to causality.  It records
    episodes where a source intervention was present and episodes where it was absent,
    then asks whether the target observation is recurrent under exposure *and* absent
    from independent negative-control episodes.  No learned weights or probabilities
    are used in this first conservative gate.
    """

    def __init__(self) -> None:
        self._observations: list[InteragentContrastObservation] = []

    def observe(
        self,
        *,
        episode_id: str,
        source_intervention_present: bool,
        target_observation: tuple[str, ...],
    ) -> InteragentContrastObservation:
        if not episode_id:
            raise ValueError("episode_id must be non-empty")
        if not target_observation or any(not item for item in target_observation):
            raise ValueError("target_observation must contain non-empty addresses")
        item = InteragentContrastObservation(
            episode_id=episode_id,
            source_intervention_present=bool(source_intervention_present),
            target_observation=tuple(target_observation),
        )
        self._observations.append(item)
        return item

    def resolve(
        self,
        *,
        target_observation: tuple[str, ...],
        min_independent_exposed: int = 2,
        min_independent_controls: int = 1,
    ) -> InteragentContrastResult:
        if min_independent_exposed < 2:
            raise ValueError("min_independent_exposed must be >= 2")
        if min_independent_controls < 1:
            raise ValueError("min_independent_controls must be >= 1")

        target = tuple(target_observation)
        exposed = sorted({
            item.episode_id for item in self._observations
            if item.source_intervention_present and item.target_observation == target
        })
        controls = sorted({
            item.episode_id for item in self._observations
            if not item.source_intervention_present and item.target_observation == target
        })
        enough_exposed = len(exposed) >= min_independent_exposed
        enough_controls = len(controls) >= min_independent_controls

        if not enough_exposed:
            return InteragentContrastResult(
                target, tuple(exposed), tuple(controls), False, False,
                "insufficient-exposed-support",
            )
        if enough_controls:
            return InteragentContrastResult(
                target, tuple(exposed), tuple(controls), False, False,
                "target-also-occurs-without-intervention",
            )
        return InteragentContrastResult(
            target, tuple(exposed), tuple(controls), True, True,
            "exposure-specific-recurrence",
        )

    def snapshot(self) -> tuple[InteragentContrastObservation, ...]:
        return tuple(self._observations)

    @classmethod
    def restore(
        cls,
        snapshot: tuple[InteragentContrastObservation, ...],
    ) -> "InteragentContrastMemory":
        memory = cls()
        memory._observations = list(snapshot)
        return memory
