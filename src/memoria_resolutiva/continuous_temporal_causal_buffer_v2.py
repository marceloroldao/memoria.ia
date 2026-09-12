from __future__ import annotations

from dataclasses import dataclass

from .temporal_causal_window_v2 import TemporalCausalEvent, TemporalCausalPath, resolve_temporal_causal_path


@dataclass(frozen=True, slots=True)
class CausalBufferState:
    events: tuple[TemporalCausalEvent, ...]
    max_tick_distance: int

    @classmethod
    def empty(cls, *, max_tick_distance: int = 3) -> "CausalBufferState":
        if max_tick_distance < 1:
            raise ValueError("max_tick_distance must be >= 1")
        return cls((), max_tick_distance)


def append_event(state: CausalBufferState, event: TemporalCausalEvent) -> CausalBufferState:
    if state.events and event.tick < state.events[-1].tick:
        raise ValueError("events must arrive in non-decreasing tick order")
    cutoff = event.tick - state.max_tick_distance
    retained = tuple(item for item in state.events if item.tick >= cutoff)
    return CausalBufferState(retained + (event,), state.max_tick_distance)


def candidate_paths_to_latest(state: CausalBufferState) -> tuple[TemporalCausalPath, ...]:
    if len(state.events) < 2:
        return ()
    target = state.events[-1]
    paths: list[TemporalCausalPath] = []
    for index, source in enumerate(state.events[:-1]):
        mediators = tuple(
            item for item in state.events[index + 1 : -1]
            if source.tick < item.tick < target.tick
        )
        path = resolve_temporal_causal_path(
            source,
            target,
            mediators,
            max_tick_distance=state.max_tick_distance,
        )
        if path.supported:
            paths.append(path)
    paths.sort(key=lambda item: (item.source.tick, item.target.tick, item.source.address, item.target.address))
    return tuple(paths)
