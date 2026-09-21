from __future__ import annotations

from collections import Counter, defaultdict, deque
from dataclasses import dataclass
from math import exp, floor, isfinite, log
from typing import Any

from .structural_association_field import StructuralAssociation


@dataclass(slots=True)
class _ContinuousEdge:
    weight: float = 0.0
    observations: int = 0
    last_tick: int = 0


@dataclass(frozen=True, slots=True)
class _TemporalCoordinate:
    clock_id: str
    t_start: float
    t_end: float

    @property
    def center(self) -> float:
        return (self.t_start + self.t_end) * 0.5


class ContinuousStructuralAssociationField:
    """Experimental non-semantic field with continuous spatial/temporal kernels.

    There is no conceptual maximum distance or event lag. Contributions decay
    exponentially with distance. A numerical trace_floor only determines when
    an already negligible contribution can be omitted for bounded runtime;
    changing that floor changes approximation precision, not semantic meaning.
    """

    CHANNELS = frozenset({"within", "temporal"})

    def __init__(
        self,
        *,
        within_decay: float = 0.35,
        temporal_decay: float = 0.35,
        forgetting_rate: float = 0.01,
        trace_floor: float = 1e-6,
        physical_time_decay: float | None = None,
        max_physical_history_events: int = 4096,
    ) -> None:
        if within_decay <= 0.0:
            raise ValueError("within_decay must be > 0")
        if temporal_decay <= 0.0:
            raise ValueError("temporal_decay must be > 0")
        if forgetting_rate < 0.0:
            raise ValueError("forgetting_rate must be >= 0")
        if not 0.0 < trace_floor < 1.0:
            raise ValueError("trace_floor must be in (0, 1)")
        if physical_time_decay is not None and physical_time_decay <= 0.0:
            raise ValueError("physical_time_decay must be > 0 when enabled")
        if max_physical_history_events < 1:
            raise ValueError("max_physical_history_events must be >= 1")
        self.within_decay = float(within_decay)
        self.temporal_decay = float(temporal_decay)
        self.forgetting_rate = float(forgetting_rate)
        self.trace_floor = float(trace_floor)
        self.physical_time_decay = (
            None if physical_time_decay is None else float(physical_time_decay)
        )
        self.max_physical_history_events = int(max_physical_history_events)
        self.tick = 0
        self._ticks: dict[str, int] = defaultdict(int)
        self._edges: dict[tuple[str, int, int, str], _ContinuousEdge] = {}
        self._recent: dict[
            str,
            deque[
                tuple[
                    int,
                    tuple[tuple[int, float], ...],
                    _TemporalCoordinate | None,
                ]
            ],
        ] = defaultdict(deque)
        self._latest_temporal: dict[tuple[str, str], _TemporalCoordinate] = {}
        self._seen_observations: set[str] = set()
        self._observation_count = 0

    @staticmethod
    def _numerical_horizon(decay: float, floor_value: float) -> int:
        return max(1, 1 + int(floor(-log(floor_value) / decay)))

    @property
    def within_horizon(self) -> int:
        return self._numerical_horizon(self.within_decay, self.trace_floor)

    @property
    def temporal_horizon(self) -> int:
        return self._numerical_horizon(self.temporal_decay, self.trace_floor)

    @property
    def physical_horizon_seconds(self) -> float | None:
        if self.physical_time_decay is None:
            return None
        return -log(self.trace_floor) / self.physical_time_decay

    @property
    def edge_count(self) -> int:
        return len(self._edges)

    @property
    def observation_count(self) -> int:
        return self._observation_count

    def active_history_size(self, hierarchy_id: str) -> int:
        return len(self._recent.get(hierarchy_id, ()))

    @staticmethod
    def _hierarchy_id(envelope: dict[str, Any]) -> str:
        provenance = envelope.get("provenance")
        if not isinstance(provenance, dict):
            raise ValueError("structural observation provenance must be an object")
        value = str(provenance.get("hierarchy_id") or "").strip()
        if not value:
            raise ValueError("structural observation hierarchy_id is required")
        return value

    @staticmethod
    def _trail(event: dict[str, Any]) -> tuple[int, ...]:
        raw = event.get("trail")
        if not isinstance(raw, (list, tuple)):
            raise ValueError("StructuralEvent trail must be a list")
        trail = tuple(int(item) for item in raw)
        if any(item < 0 for item in trail):
            raise ValueError("StructuralEvent trail ids must be >= 0")
        return trail

    @staticmethod
    def _profile(trail: tuple[int, ...]) -> tuple[tuple[int, float], ...]:
        if not trail:
            return ()
        counts = Counter(trail)
        total = float(len(trail))
        return tuple(sorted((symbol, count / total) for symbol, count in counts.items()))

    @staticmethod
    def _temporal_coordinate(envelope: dict[str, Any]) -> _TemporalCoordinate | None:
        provenance = envelope.get("provenance")
        if not isinstance(provenance, dict):
            return None
        raw = provenance.get("temporal")
        if raw is None:
            return None
        if not isinstance(raw, dict):
            raise ValueError("structural observation temporal provenance must be an object")
        if str(raw.get("unit") or "") != "s":
            raise ValueError("structural observation temporal unit must be 's'")
        clock_id = str(raw.get("clock_id") or "").strip()
        if not clock_id:
            raise ValueError("structural observation temporal clock_id is required")
        try:
            t_start = float(raw["t_start"])
            t_end = float(raw["t_end"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(
                "structural observation temporal t_start/t_end must be finite seconds"
            ) from exc
        if not isfinite(t_start) or not isfinite(t_end):
            raise ValueError(
                "structural observation temporal t_start/t_end must be finite seconds"
            )
        if t_end < t_start:
            raise ValueError("structural observation temporal interval is inverted")
        return _TemporalCoordinate(clock_id=clock_id, t_start=t_start, t_end=t_end)

    @staticmethod
    def _physical_interval_distance(
        left: _TemporalCoordinate,
        right: _TemporalCoordinate,
    ) -> float:
        if left.t_end >= right.t_start and right.t_end >= left.t_start:
            return 0.0
        return min(
            abs(right.t_start - left.t_end),
            abs(left.t_start - right.t_end),
        )

    def _validate_physical_temporal_input(
        self,
        hierarchy_id: str,
        temporal: _TemporalCoordinate | None,
    ) -> None:
        if temporal is None or self.physical_time_decay is None:
            return
        key = (hierarchy_id, temporal.clock_id)
        latest = self._latest_temporal.get(key)
        if latest is not None and temporal.center < latest.center:
            raise ValueError(
                "physical temporal observations must be non-decreasing within a clock"
            )

        horizon = self.physical_horizon_seconds
        assert horizon is not None
        active_same_clock = sum(
            1
            for _tick, _profile, previous in self._recent.get(hierarchy_id, ())
            if previous is not None
            and previous.clock_id == temporal.clock_id
            and self._physical_interval_distance(temporal, previous) <= horizon
        )
        if active_same_clock >= self.max_physical_history_events:
            raise RuntimeError(
                "physical temporal history saturation: aggregate upstream into "
                "RealitySlices or reduce temporal resolution"
            )

    def _temporal_kernel(
        self,
        *,
        current_tick: int,
        previous_tick: int,
        current_temporal: _TemporalCoordinate | None,
        previous_temporal: _TemporalCoordinate | None,
    ) -> float:
        if (
            self.physical_time_decay is not None
            and current_temporal is not None
            and previous_temporal is not None
        ):
            if current_temporal.clock_id != previous_temporal.clock_id:
                return 0.0
            delta = self._physical_interval_distance(
                current_temporal,
                previous_temporal,
            )
            return exp(-self.physical_time_decay * delta)

        lag = current_tick - previous_tick
        return exp(-self.temporal_decay * float(lag - 1))

    def _edge_value(self, edge: _ContinuousEdge, tick: int) -> float:
        age = max(0, tick - edge.last_tick)
        if age == 0 or self.forgetting_rate == 0.0:
            return edge.weight
        return edge.weight * exp(-self.forgetting_rate * age)

    def _reinforce(
        self,
        hierarchy_id: str,
        source: int,
        target: int,
        channel: str,
        amount: float,
    ) -> None:
        if amount <= 0.0:
            return
        key = (hierarchy_id, int(source), int(target), channel)
        now = self._ticks[hierarchy_id]
        edge = self._edges.get(key)
        if edge is None:
            edge = _ContinuousEdge(last_tick=now)
            self._edges[key] = edge
        else:
            edge.weight = self._edge_value(edge, now)
            edge.last_tick = now
        edge.weight += float(amount)
        edge.observations += 1

    def _trim_history(self, hierarchy_id: str) -> None:
        now = self._ticks[hierarchy_id]
        causal_horizon = self.temporal_horizon
        physical_horizon = self.physical_horizon_seconds
        recent = self._recent[hierarchy_id]
        if not recent:
            return

        kept = deque()
        for tick, profile, temporal in recent:
            causal_alive = now - tick <= causal_horizon
            physical_alive = False
            if physical_horizon is not None and temporal is not None:
                latest = self._latest_temporal.get((hierarchy_id, temporal.clock_id))
                if latest is not None:
                    physical_alive = (
                        self._physical_interval_distance(latest, temporal)
                        <= physical_horizon
                    )
            if causal_alive or physical_alive:
                kept.append((tick, profile, temporal))
        self._recent[hierarchy_id] = kept

    def observe(self, envelope: dict[str, Any]) -> int:
        if envelope.get("semantic_projection") not in {False, None}:
            raise ValueError("continuous structural field accepts raw observations only")
        observation_id = str(envelope.get("observation_id") or "").strip()
        if not observation_id:
            raise ValueError("structural observation observation_id is required")
        hierarchy_id = self._hierarchy_id(envelope)
        if observation_id in self._seen_observations:
            return self._ticks[hierarchy_id]
        event = envelope.get("event")
        if not isinstance(event, dict):
            raise ValueError("structural observation event must be an object")
        trail = self._trail(event)
        temporal = self._temporal_coordinate(envelope)
        self._validate_physical_temporal_input(hierarchy_id, temporal)

        self.tick += 1
        self._ticks[hierarchy_id] += 1
        now = self._ticks[hierarchy_id]
        self._seen_observations.add(observation_id)
        self._observation_count += 1
        if temporal is not None and self.physical_time_decay is not None:
            self._latest_temporal[(hierarchy_id, temporal.clock_id)] = temporal
        self._trim_history(hierarchy_id)

        horizon = self.within_horizon
        for i, source in enumerate(trail):
            upper = min(len(trail), i + horizon + 1)
            for j in range(i + 1, upper):
                distance = j - i
                kernel = exp(-self.within_decay * float(distance - 1))
                if kernel < self.trace_floor:
                    break
                self._reinforce(hierarchy_id, source, trail[j], "within", kernel)

        current_profile = self._profile(trail)
        if current_profile:
            recent = self._recent[hierarchy_id]
            for previous_tick, previous_profile, previous_temporal in recent:
                kernel = self._temporal_kernel(
                    current_tick=now,
                    previous_tick=previous_tick,
                    current_temporal=temporal,
                    previous_temporal=previous_temporal,
                )
                if kernel < self.trace_floor:
                    continue
                for source, source_mass in previous_profile:
                    for target, target_mass in current_profile:
                        self._reinforce(
                            hierarchy_id,
                            source,
                            target,
                            "temporal",
                            kernel * source_mass * target_mass,
                        )
            recent.append((now, current_profile, temporal))
            self._trim_history(hierarchy_id)

        return now

    def association(
        self,
        hierarchy_id: str,
        source: int,
        target: int,
        *,
        channel: str | None = None,
    ) -> float:
        if channel is not None and channel not in self.CHANNELS:
            raise ValueError("unknown association channel")
        channels = (channel,) if channel is not None else tuple(sorted(self.CHANNELS))
        now = self._ticks[hierarchy_id]
        total = 0.0
        for name in channels:
            edge = self._edges.get((hierarchy_id, int(source), int(target), name))
            if edge is not None:
                total += self._edge_value(edge, now)
        return total

    def strongest(
        self,
        hierarchy_id: str,
        source: int,
        *,
        channel: str | None = None,
        top_k: int = 10,
    ) -> tuple[StructuralAssociation, ...]:
        if top_k < 1:
            raise ValueError("top_k must be >= 1")
        if channel is not None and channel not in self.CHANNELS:
            raise ValueError("unknown association channel")
        now = self._ticks[hierarchy_id]
        rows: list[StructuralAssociation] = []
        for (hid, src, target, name), edge in self._edges.items():
            if hid != hierarchy_id or src != int(source):
                continue
            if channel is not None and channel != name:
                continue
            rows.append(
                StructuralAssociation(
                    hierarchy_id=hid,
                    source=src,
                    target=target,
                    channel=name,
                    weight=self._edge_value(edge, now),
                    observations=edge.observations,
                    last_tick=edge.last_tick,
                )
            )
        rows.sort(key=lambda row: (-row.weight, -row.observations, row.channel, row.target))
        return tuple(rows[:top_k])

    def snapshot(self) -> dict[str, Any]:
        rows = []
        for (hierarchy_id, source, target, channel), edge in sorted(self._edges.items()):
            rows.append(
                {
                    "hierarchy_id": hierarchy_id,
                    "source": source,
                    "target": target,
                    "channel": channel,
                    "weight": self._edge_value(edge, self._ticks[hierarchy_id]),
                    "observations": edge.observations,
                    "last_tick": edge.last_tick,
                }
            )
        return {
            "schema": "memoria.ia-continuous-structural-association-field-v1",
            "tick": self.tick,
            "hierarchy_ticks": dict(sorted(self._ticks.items())),
            "within_decay": self.within_decay,
            "temporal_decay": self.temporal_decay,
            "forgetting_rate": self.forgetting_rate,
            "trace_floor": self.trace_floor,
            "physical_time_decay": self.physical_time_decay,
            "physical_horizon_seconds": self.physical_horizon_seconds,
            "max_physical_history_events": self.max_physical_history_events,
            "within_horizon": self.within_horizon,
            "temporal_horizon": self.temporal_horizon,
            "observations": self._observation_count,
            "semantic_projection": False,
            "edges": rows,
        }
