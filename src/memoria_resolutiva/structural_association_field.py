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
    later nearby events.

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
        self._edges: dict[tuple[str, int, int, str], _AssociationEdge] = {}
        self._recent: dict[str, deque[tuple[int, tuple[int, ...]]]] = defaultdict(deque)

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
        if source == target or amount <= 0.0:
            return
        key = (hierarchy_id, int(source), int(target), channel)
        edge = self._edges.get(key)
        if edge is None:
            edge = _AssociationEdge(last_tick=self.tick)
            self._edges[key] = edge
        else:
            edge.weight = self._decayed(edge, self.tick)
            edge.last_tick = self.tick
        edge.weight += float(amount)
        edge.observations += 1

    def _trim_recent(self, hierarchy_id: str) -> None:
        recent = self._recent[hierarchy_id]
        while recent and self.tick - recent[0][0] > self.max_event_lag:
            recent.popleft()

    def observe(self, envelope: dict[str, Any]) -> int:
        """Observe one persisted structural envelope and advance causal time once."""
        if envelope.get("semantic_projection") not in {False, None}:
            raise ValueError("StructuralAssociationField accepts raw structural observations only")
        event = envelope.get("event")
        if not isinstance(event, dict):
            raise ValueError("structural observation event must be an object")
        hierarchy_id = self._hierarchy_id(envelope)
        trail = self._trail(event)

        self.tick += 1
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
                lag = self.tick - previous_tick
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
            recent.append((self.tick, trail))

        return self.tick

    def advance(self, steps: int = 1) -> int:
        """Advance causal time without inventing observations."""
        if steps < 0:
            raise ValueError("steps must be >= 0")
        self.tick += int(steps)
        for hierarchy_id in tuple(self._recent):
            self._trim_recent(hierarchy_id)
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
                total += self._decayed(edge, self.tick)
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
                    self._decayed(edge, self.tick),
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

    def snapshot(self) -> dict[str, Any]:
        edges = []
        for (hierarchy_id, source, target, channel), edge in sorted(self._edges.items()):
            edges.append(
                {
                    "hierarchy_id": hierarchy_id,
                    "source": source,
                    "target": target,
                    "channel": channel,
                    "weight": self._decayed(edge, self.tick),
                    "observations": edge.observations,
                    "last_tick": edge.last_tick,
                }
            )
        return {
            "schema": "memoria.ia-structural-association-field-v1",
            "tick": self.tick,
            "max_within_distance": self.max_within_distance,
            "max_event_lag": self.max_event_lag,
            "forgetting_rate": self.forgetting_rate,
            "semantic_projection": False,
            "edges": edges,
        }
