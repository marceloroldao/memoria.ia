from __future__ import annotations

from dataclasses import dataclass
from typing import Hashable


@dataclass(frozen=True, slots=True)
class Edge:
    source: Hashable
    relation: Hashable
    target: Hashable
    confidence: float
    provenance: str | None = None


@dataclass(frozen=True, slots=True)
class InferencePath:
    nodes: tuple[Hashable, ...]
    edges: tuple[Edge, ...]
    confidence: float


class InferenceChain:
    """Compose graph relations into auditable multi-step hypotheses.

    Confidence is multiplicative with an optional hop penalty, so longer chains
    cannot become more confident than their weakest evidence by mere composition.
    """

    def __init__(self, hop_penalty: float = 0.95, max_depth: int = 4):
        if not 0 < hop_penalty <= 1:
            raise ValueError("hop_penalty must be in (0,1]")
        self.hop_penalty = hop_penalty
        self.max_depth = max_depth
        self._out: dict[Hashable, list[Edge]] = {}

    def add(self, source: Hashable, relation: Hashable, target: Hashable, confidence: float, provenance: str | None = None) -> None:
        if not 0 <= confidence <= 1:
            raise ValueError("confidence must be in [0,1]")
        self._out.setdefault(source, []).append(Edge(source, relation, target, confidence, provenance))

    def infer(self, source: Hashable, target: Hashable) -> list[InferencePath]:
        results: list[InferencePath] = []

        def dfs(node: Hashable, nodes: list[Hashable], edges: list[Edge], conf: float) -> None:
            if len(edges) >= self.max_depth:
                return
            for edge in self._out.get(node, []):
                if edge.target in nodes:
                    continue
                new_edges = edges + [edge]
                new_nodes = nodes + [edge.target]
                hop_factor = 1.0 if not edges else self.hop_penalty
                new_conf = conf * edge.confidence * hop_factor
                if edge.target == target:
                    results.append(InferencePath(tuple(new_nodes), tuple(new_edges), new_conf))
                dfs(edge.target, new_nodes, new_edges, new_conf)

        dfs(source, [source], [], 1.0)
        return sorted(results, key=lambda p: p.confidence, reverse=True)
