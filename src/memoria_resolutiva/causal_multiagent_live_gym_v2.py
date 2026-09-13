from __future__ import annotations

from dataclasses import dataclass

from .interagent_contrast_v2 import InteragentContrastMemory, InteragentContrastResult
from .multiagent_live_gym_v2 import MultiAgentLiveCognitiveGymV2, MultiAgentObservation, MultiAgentGymStep
from .live_infinita_adapter_v2 import to_world_state_candidates


@dataclass(frozen=True, slots=True)
class InteragentCausalProbe:
    """One explicitly monitored cross-agent intervention/observation contrast.

    This is an adapter-level experimental probe, not a semantic assertion of cause.
    The source intervention is compared against the target's actually observed
    consequence across independent ticks, including ticks where the intervention is
    absent.
    """

    probe_id: str
    source_agent: str
    source_intervention: str
    target_agent: str
    target_observation: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CausalBatchResult:
    tick_id: str
    steps: tuple[MultiAgentGymStep, ...]
    contrasts: tuple[tuple[str, InteragentContrastResult], ...]


class CausalMultiAgentLiveGymV2:
    """Multi-agent gym plus conservative intervention-vs-control evidence.

    All ordinary agent predictions still use the simultaneous two-phase batch in
    MultiAgentLiveCognitiveGymV2. Cross-agent contrast evidence is recorded only after
    the batch prediction phase has completed. A target observation seen on a tick
    where the source intervention is absent becomes a negative control for that probe.
    """

    def __init__(
        self,
        base: MultiAgentLiveCognitiveGymV2 | None = None,
        *,
        min_independent_exposed: int = 2,
        min_independent_controls: int = 1,
    ) -> None:
        if min_independent_exposed < 2:
            raise ValueError("min_independent_exposed must be >= 2")
        if min_independent_controls < 1:
            raise ValueError("min_independent_controls must be >= 1")
        self.base = base if base is not None else MultiAgentLiveCognitiveGymV2()
        self.min_independent_exposed = min_independent_exposed
        self.min_independent_controls = min_independent_controls
        self._contrasts: dict[str, InteragentContrastMemory] = {}

    def _memory_for(self, probe_id: str) -> InteragentContrastMemory:
        memory = self._contrasts.get(probe_id)
        if memory is None:
            memory = InteragentContrastMemory()
            self._contrasts[probe_id] = memory
        return memory

    def step_batch(
        self,
        *,
        tick_id: str,
        observations: tuple[MultiAgentObservation, ...],
        probes: tuple[InteragentCausalProbe, ...],
        learn: bool = True,
    ) -> CausalBatchResult:
        if not tick_id:
            raise ValueError("tick_id must be non-empty")
        if len({probe.probe_id for probe in probes}) != len(probes):
            raise ValueError("probe_id must be unique within a batch")

        # Ordinary prediction/observation handling preserves simultaneous semantics.
        steps = self.base.step_batch(observations, learn=learn)
        by_agent = {item.agent_id: item for item in observations}

        results: list[tuple[str, InteragentContrastResult]] = []
        for probe in sorted(probes, key=lambda item: item.probe_id):
            if not probe.probe_id or not probe.source_agent or not probe.target_agent:
                raise ValueError("probe and agent ids must be non-empty")
            if probe.source_agent == probe.target_agent:
                raise ValueError("interagent probe requires distinct agents")
            if not probe.source_intervention or not probe.target_observation:
                raise ValueError("probe intervention/target must be non-empty")

            source = by_agent.get(probe.source_agent)
            target = by_agent.get(probe.target_agent)
            source_present = (
                source is not None
                and source.request.intervention.address == probe.source_intervention
            )

            # A control/exposure is only informative when the target agent is actually
            # observed in this tick. Missing target data is not interpreted as absence.
            if target is not None:
                candidates = to_world_state_candidates(target.request)
                actual = next(
                    item for item in candidates if item.candidate_id == target.actual_candidate_id
                )
                if actual.consequence_addresses == tuple(probe.target_observation):
                    self._memory_for(probe.probe_id).observe(
                        episode_id=tick_id,
                        source_intervention_present=source_present,
                        target_observation=probe.target_observation,
                    )

            result = self._memory_for(probe.probe_id).resolve(
                target_observation=probe.target_observation,
                min_independent_exposed=self.min_independent_exposed,
                min_independent_controls=self.min_independent_controls,
            )
            results.append((probe.probe_id, result))

        return CausalBatchResult(tick_id, steps, tuple(results))

    def contrast_snapshot(self) -> tuple[tuple[str, tuple], ...]:
        return tuple(
            (probe_id, self._contrasts[probe_id].snapshot())
            for probe_id in sorted(self._contrasts)
        )
