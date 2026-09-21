from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from math import exp
from typing import Any


@dataclass(slots=True)
class _AssociationEdge:
    weight: float = 0.0
    observations: int = 0
    last_tick: int = 0


@dataclass(frozen=True, slots=True)
class StructuralAssociation:
    hierarchy_id: str
    source: int
    target: int
    channel: str
    weight: float
    observations: int
    last_tick: int


class StructuralAssociationField:
    """Non-semantic association dynamics over opaque StructuralEvent symbol IDs.

    The field does not assign names, predicates, facts, grammar classes or truth
    labels. It only accumulates directed structural evidence from observed order.

    The within channel links earlier trail symbols to later nearby symbols.
    The temporal channel links symbols in earlier StructuralEvents to symbols in
    later nearby events. Here distance is causal event lag, not wall-clock time;
    timestamp-aware multimodal layers can supply physical delta-t later.

    Repetition accumulates support. Distance attenuates each contribution.
    Forgetting is lazy exponential decay, evaluated only when an edge is updated
    or queried. No promotion threshold exists in this layer.
    """

    CHANNELS = frozenset({"within", "temporal"})

    def __init__(
        self,
        *,
        max_within_distance: int = 8,
        max_event_lag: int = 4,
        forgetting_rate: float = 0.01,
    ) -> None:
        if max_within_distance < 1:
            raise ValueError("max_within_distance must be >= 1")
        if max_event_lag < 1:
            raise ValueError("max_event_lag must be >= 1")
        if forgetting_rate < 0.0:
            raise ValueError("forgetting_rate must be >= 0")
        self.max_within_distance = int(max_within_distance)
        self.max_event_lag = int(max_event_lag)
        self.forgetting_rate = float(forgetting_rate)
        self.tick = 0
        self._ticks: dict[str, int] = defaultdict(int)
        self._edges: dict[tuple[str, int, int, str], _AssociationEdge] = {}
        self._recent: dict[str, deque[tuple[int, tuple[int, ...]]]] = defaultdict(deque)
        self._seen_observations: set[str] = set()
        self._observation_count = 0

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
    def _hierarchy_id(envelope: dict[str, Any]) -> str:
        provenance = envelope.get("provenance")
        if not isinstance(provenance, dict):
            raise ValueError("structural observation provenance must be an object")
        hierarchy_id = str(provenance.get("hierarchy_id") or "").strip()
        if not hierarchy_id:
            raise ValueError("structural observation hierarchy_id is required")
        return hierarchy_id

    def _decayed(self, edge: _AssociationEdge, tick: int) -> float:
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
        if channel not in self.CHANNELS:
            raise ValueError("unknown association channel")
        if amount <= 0.0:
            return
        key = (hierarchy_id, int(source), int(target), channel)
        current_tick = self._ticks[hierarchy_id]
        edge = self._edges.get(key)
        if edge is None:
            edge = _AssociationEdge(last_tick=current_tick)
            self._edges[key] = edge
        else:
            edge.weight = self._decayed(edge, current_tick)
            edge.last_tick = current_tick
        edge.weight += float(amount)
        edge.observations += 1

    def _trim_recent(self, hierarchy_id: str) -> None:
        recent = self._recent[hierarchy_id]
        current_tick = self._ticks[hierarchy_id]
        while recent and current_tick - recent[0][0] > self.max_event_lag:
            recent.popleft()

    def observe(self, envelope: dict[str, Any]) -> int:
        """Observe one persisted structural envelope and advance causal time once."""
        if envelope.get("semantic_projection") not in {False, None}:
            raise ValueError("StructuralAssociationField accepts raw structural observations only")
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
        current_tick = self._ticks[hierarchy_id]
        self._seen_observations.add(observation_id)
        self._observation_count += 1
        self._trim_recent(hierarchy_id)

        for i, source in enumerate(trail):
            upper = min(len(trail), i + self.max_within_distance + 1)
            for j in range(i + 1, upper):
                target = trail[j]
                self._reinforce(
                    hierarchy_id,
                    source,
                    target,
                    "within",
                    1.0 / float(j - i),
                )

        if trail:
            recent = self._recent[hierarchy_id]
            for previous_tick, previous_trail in recent:
                if not previous_trail:
                    continue
                lag = current_tick - previous_tick
                if lag < 1 or lag > self.max_event_lag:
                    continue
                mass = 1.0 / (
                    float(lag) * float(len(previous_trail)) * float(len(trail))
                )
                for source in previous_trail:
                    for target in trail:
                        self._reinforce(
                            hierarchy_id,
                            source,
                            target,
                            "temporal",
                            mass,
                        )
            recent.append((current_tick, trail))

        return current_tick

    def advance(self, steps: int = 1, *, hierarchy_id: str | None = None) -> int:
        """Advance causal time without inventing observations."""
        if steps < 0:
            raise ValueError("steps must be >= 0")
        amount = int(steps)
        self.tick += amount
        targets = (hierarchy_id,) if hierarchy_id is not None else tuple(self._ticks)
        for target in targets:
            self._ticks[target] += amount
            self._trim_recent(target)
        return self.tick

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
        total = 0.0
        for name in channels:
            edge = self._edges.get((hierarchy_id, int(source), int(target), name))
            if edge is not None:
                total += self._decayed(edge, self._ticks[hierarchy_id])
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
        rows: list[StructuralAssociation] = []
        for (hid, src, target, name), edge in self._edges.items():
            if hid != hierarchy_id or src != int(source):
                continue
            if channel is not None and name != channel:
                continue
            rows.append(
                StructuralAssociation(
                    hid,
                    src,
                    target,
                    name,
                    self._decayed(edge, self._ticks[hierarchy_id]),
                    edge.observations,
                    edge.last_tick,
                )
            )
        rows.sort(
            key=lambda row: (
                -row.weight,
                -row.observations,
                row.channel,
                row.target,
            )
        )
        return tuple(rows[:top_k])


    @property
    def edge_count(self) -> int:
        return len(self._edges)

    @property
    def observation_count(self) -> int:
        return self._observation_count

    @property
    def hierarchy_count(self) -> int:
        return len(self._ticks)

    def export_state(self) -> dict[str, Any]:
        """Export exact derived state without applying additional decay."""
        return {
            "schema": "memoria.ia-structural-association-state-v1",
            "tick": self.tick,
            "hierarchy_ticks": dict(sorted(self._ticks.items())),
            "max_within_distance": self.max_within_distance,
            "max_event_lag": self.max_event_lag,
            "forgetting_rate": self.forgetting_rate,
            "observation_count": self._observation_count,
            "edges": [
                {
                    "hierarchy_id": hierarchy_id,
                    "source": source,
                    "target": target,
                    "channel": channel,
                    "weight": edge.weight,
                    "observations": edge.observations,
                    "last_tick": edge.last_tick,
                }
                for (hierarchy_id, source, target, channel), edge
                in sorted(self._edges.items())
            ],
            "recent": {
                hierarchy_id: [
                    {"tick": tick, "trail": list(trail)}
                    for tick, trail in recent
                ]
                for hierarchy_id, recent in sorted(self._recent.items())
                if recent
            },
        }

    @classmethod
    def from_state(cls, state: dict[str, Any]) -> "StructuralAssociationField":
        if state.get("schema") != "memoria.ia-structural-association-state-v1":
            raise ValueError("unsupported structural association state format")
        field = cls(
            max_within_distance=int(state["max_within_distance"]),
            max_event_lag=int(state["max_event_lag"]),
            forgetting_rate=float(state["forgetting_rate"]),
        )
        field.tick = int(state["tick"])
        if field.tick < 0:
            raise ValueError("structural association tick must be >= 0")
        field._observation_count = int(state.get("observation_count", field.tick))
        if field._observation_count < 0:
            raise ValueError("structural association observation_count must be >= 0")

        ticks = state.get("hierarchy_ticks")
        if not isinstance(ticks, dict):
            raise ValueError("structural association hierarchy_ticks must be an object")
        for hierarchy_id, tick in ticks.items():
            clean = str(hierarchy_id).strip()
            if not clean:
                raise ValueError("structural association hierarchy id must be non-empty")
            value = int(tick)
            if value < 0:
                raise ValueError("structural association hierarchy tick must be >= 0")
            field._ticks[clean] = value

        edges = state.get("edges")
        if not isinstance(edges, list):
            raise ValueError("structural association edges must be a list")
        for row in edges:
            if not isinstance(row, dict):
                raise ValueError("invalid structural association edge")
            hierarchy_id = str(row["hierarchy_id"]).strip()
            source = int(row["source"])
            target = int(row["target"])
            channel = str(row["channel"])
            weight = float(row["weight"])
            observations = int(row["observations"])
            last_tick = int(row["last_tick"])
            if not hierarchy_id or source < 0 or target < 0:
                raise ValueError("invalid structural association edge identity")
            if channel not in cls.CHANNELS:
                raise ValueError("invalid structural association edge channel")
            if weight < 0.0 or observations < 1 or last_tick < 0:
                raise ValueError("invalid structural association edge state")
            if last_tick > field._ticks[hierarchy_id]:
                raise ValueError("structural association edge is ahead of hierarchy clock")
            field._edges[(hierarchy_id, source, target, channel)] = _AssociationEdge(
                weight=weight,
                observations=observations,
                last_tick=last_tick,
            )

        recent = state.get("recent", {})
        if not isinstance(recent, dict):
            raise ValueError("structural association recent state must be an object")
        for hierarchy_id, rows in recent.items():
            clean = str(hierarchy_id).strip()
            if not clean or not isinstance(rows, list):
                raise ValueError("invalid structural association recent lineage")
            restored = field._recent[clean]
            previous_tick = -1
            for row in rows:
                if not isinstance(row, dict):
                    raise ValueError("invalid structural association recent row")
                tick = int(row["tick"])
                trail = tuple(int(item) for item in row["trail"])
                if tick < previous_tick or tick > field._ticks[clean]:
                    raise ValueError("invalid structural association recent tick")
                if any(item < 0 for item in trail):
                    raise ValueError("invalid structural association recent trail")
                restored.append((tick, trail))
                previous_tick = tick
            field._trim_recent(clean)
        return field

    def snapshot(self) -> dict[str, Any]:
        edges = []
        for (hierarchy_id, source, target, channel), edge in sorted(self._edges.items()):
            edges.append(
                {
                    "hierarchy_id": hierarchy_id,
                    "source": source,
                    "target": target,
                    "channel": channel,
                    "weight": self._decayed(edge, self._ticks[hierarchy_id]),
                    "observations": edge.observations,
                    "last_tick": edge.last_tick,
                }
            )
        return {
            "schema": "memoria.ia-structural-association-field-v1",
            "tick": self.tick,
            "hierarchy_ticks": dict(sorted(self._ticks.items())),
            "max_within_distance": self.max_within_distance,
            "max_event_lag": self.max_event_lag,
            "forgetting_rate": self.forgetting_rate,
            "semantic_projection": False,
            "observations": self._observation_count,
            "edges": edges,
        }
