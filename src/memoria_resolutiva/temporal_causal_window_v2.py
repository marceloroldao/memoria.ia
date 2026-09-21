from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TemporalCausalEvent:
    tick: int
    episode_id: str
    agent_id: str
    address: str
    kind: str  # intervention | observation | mediator


@dataclass(frozen=True, slots=True)
class TemporalCausalPath:
    source: TemporalCausalEvent
    mediators: tuple[TemporalCausalEvent, ...]
    target: TemporalCausalEvent
    distance: int
    within_window: bool
    mediated: bool
    supported: bool
    reason: str


def evaluate_temporal_causal_path(
    source: TemporalCausalEvent,
    target: TemporalCausalEvent,
    *,
    mediators: tuple[TemporalCausalEvent, ...] = (),
    max_tick_distance: int = 3,
    require_mediator_for_multistep: bool = True,
) -> TemporalCausalPath:
    if max_tick_distance < 1:
        raise ValueError("max_tick_distance must be >= 1")
    if source.kind != "intervention":
        raise ValueError("source must be an intervention")
    if target.kind != "observation":
        raise ValueError("target must be an observation")
    if target.tick <= source.tick:
        return TemporalCausalPath(source, (), target, target.tick - source.tick, False, False, False, "non-forward-time")

    distance = target.tick - source.tick
    if distance > max_tick_distance:
        return TemporalCausalPath(source, (), target, distance, False, False, False, "outside-temporal-window")

    ordered = tuple(sorted(mediators, key=lambda item: (item.tick, item.agent_id, item.address)))
    valid = tuple(item for item in ordered if source.tick < item.tick < target.tick)
    mediated = bool(valid)
    if require_mediator_for_multistep and distance > 1 and not mediated:
        return TemporalCausalPath(source, (), target, distance, True, False, False, "missing-observable-mediator")

    return TemporalCausalPath(source, valid, target, distance, True, mediated, True, "bounded-mediated-path")
