from __future__ import annotations

from collections import Counter, defaultdict, deque
from dataclasses import dataclass
from math import exp, floor, log
from typing import Any

from .structural_association_field import StructuralAssociation


@dataclass(slots=True)
class _ContinuousEdge:
    weight: float = 0.0
    observations: int = 0
    last_tick: int = 0


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
    ) -> None:
        if within_decay <= 0.0:
            raise ValueError("within_decay must be > 0")
        if temporal_decay <= 0.0:
            raise ValueError("temporal_decay must be > 0")
        if forgetting_rate < 0.0:
            raise ValueError("forgetting_rate must be >= 0")
        if not 0.0 < trace_floor < 1.0:
            raise ValueError("trace_floor must be in (0, 1)")
        self.within_decay = float(within_decay)
        self.temporal_decay = float(temporal_decay)
        self.forgetting_rate = float(forgetting_rate)
        self.trace_floor = float(trace_floor)
        self.tick = 0
        self._ticks: dict[str, int] = defaultdict(int)
        self._edges: dict[tuple[str, int, int, str], _ContinuousEdge] = {}
        self._recent: dict[str, deque[tuple[int, tuple[tuple[int, float], ...]]]] = defaultdict(deque)
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
        horizon = self.temporal_horizon
        recent = self._recent[hierarchy_id]
        while recent and now - recent[0][0] > horizon:
            recent.popleft()

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

        self.tick += 1
        self._ticks[hierarchy_id] += 1
        now = self._ticks[hierarchy_id]
        self._seen_observations.add(observation_id)
        self._observation_count += 1
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
            for previous_tick, previous_profile in recent:
                lag = now - previous_tick
                kernel = exp(-self.temporal_decay * float(lag - 1))
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
            recent.append((now, current_profile))
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
            "within_horizon": self.within_horizon,
            "temporal_horizon": self.temporal_horizon,
            "observations": self._observation_count,
            "semantic_projection": False,
            "edges": rows,
        }
