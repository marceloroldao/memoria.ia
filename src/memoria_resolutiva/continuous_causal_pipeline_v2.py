from __future__ import annotations

from dataclasses import dataclass

from .continuous_temporal_causal_buffer_v2 import (
    CausalBufferState,
    append_event,
    candidate_paths_to_latest,
)
from .interagent_contrast_v2 import InteragentContrastMemory, InteragentContrastResult
from .temporal_causal_window_v2 import TemporalCausalEvent, TemporalCausalPath


@dataclass(frozen=True, slots=True)
class ContinuousCausalHypothesis:
    source_address: str
    target_address: str
    mediator_addresses: tuple[str, ...]
    independent_exposed_episodes: tuple[str, ...]
    independent_control_episodes: tuple[str, ...]
    recurrent: bool
    contrast_supported: bool
    supported: bool
    reason: str


class ContinuousCausalPipelineV2:
    """Conservative continuous causal evidence pipeline.

    Candidate temporal paths come from the bounded recent-event buffer. A path shape
    must recur in independent exposed episodes and survive a negative-control gate.
    Historical evidence is preserved; unsupported hypotheses are not deleted or marked
    false. No learned scalar weights or semantic labels are used.
    """

    def __init__(
        self,
        *,
        max_tick_distance: int = 3,
        min_independent_exposed: int = 2,
        min_independent_controls: int = 1,
    ) -> None:
        if min_independent_exposed < 2:
            raise ValueError("min_independent_exposed must be >= 2")
        if min_independent_controls < 1:
            raise ValueError("min_independent_controls must be >= 1")
        self.buffer = CausalBufferState.empty(max_tick_distance=max_tick_distance)
        self.min_independent_exposed = min_independent_exposed
        self.min_independent_controls = min_independent_controls
        self._exposed: dict[tuple[str, tuple[str, ...], str], set[str]] = {}
        self._contrast: dict[tuple[str, str], InteragentContrastMemory] = {}

    @staticmethod
    def _shape(path: TemporalCausalPath) -> tuple[str, tuple[str, ...], str]:
        return (
            path.source.address,
            tuple(item.address for item in path.mediators),
            path.target.address,
        )

    def observe_event(self, event: TemporalCausalEvent) -> tuple[TemporalCausalPath, ...]:
        self.buffer = append_event(self.buffer, event)
        paths = candidate_paths_to_latest(self.buffer)
        for path in paths:
            shape = self._shape(path)
            self._exposed.setdefault(shape, set()).add(path.source.episode_id)
            key = (path.source.address, path.target.address)
            memory = self._contrast.setdefault(key, InteragentContrastMemory())
            memory.observe(
                episode_id=path.source.episode_id,
                source_intervention_present=True,
                target_observation=(path.target.address,),
            )
        return paths

    def observe_negative_control(
        self,
        *,
        episode_id: str,
        source_address: str,
        target_address: str,
    ) -> None:
        if not episode_id or not source_address or not target_address:
            raise ValueError("episode_id, source_address and target_address must be non-empty")
        key = (source_address, target_address)
        memory = self._contrast.setdefault(key, InteragentContrastMemory())
        memory.observe(
            episode_id=episode_id,
            source_intervention_present=False,
            target_observation=(target_address,),
        )

    def resolve(
        self,
        *,
        source_address: str,
        target_address: str,
        mediator_addresses: tuple[str, ...] = (),
    ) -> ContinuousCausalHypothesis:
        shape = (source_address, tuple(mediator_addresses), target_address)
        exposed = tuple(sorted(self._exposed.get(shape, set())))
        recurrent = len(exposed) >= self.min_independent_exposed

        contrast_memory = self._contrast.get((source_address, target_address))
        if contrast_memory is None:
            contrast = InteragentContrastResult(
                target_observation=(target_address,),
                exposed_episodes=(),
                control_episodes=(),
                supported=False,
                discriminative=False,
                reason="insufficient-exposed-support",
            )
        else:
            contrast = contrast_memory.resolve(
                target_observation=(target_address,),
                min_independent_exposed=self.min_independent_exposed,
                min_independent_controls=self.min_independent_controls,
            )

        supported = recurrent and contrast.supported
        if not recurrent:
            reason = "insufficient-independent-path-recurrence"
        elif not contrast.supported:
            reason = contrast.reason
        else:
            reason = "recurrent-bounded-path-with-negative-control-clearance"

        return ContinuousCausalHypothesis(
            source_address=source_address,
            target_address=target_address,
            mediator_addresses=tuple(mediator_addresses),
            independent_exposed_episodes=exposed,
            independent_control_episodes=contrast.control_episodes,
            recurrent=recurrent,
            contrast_supported=contrast.supported,
            supported=supported,
            reason=reason,
        )
