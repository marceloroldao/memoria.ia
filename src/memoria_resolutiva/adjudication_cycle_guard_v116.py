from __future__ import annotations

from collections import defaultdict, deque

from .source_reliability_v115 import (
    ReliabilityAdjudicationV115,
    SourceReliabilityCorroborationMemoryV115,
)


class AdjudicationCycleGuardMemoryV116(SourceReliabilityCorroborationMemoryV115):
    """v1.15 plus an acyclic dependency graph for reliability adjudication.

    Every adjudicator-origin -> target-origin relation is recorded as a directed
    dependency. Before reputation is changed, the proposed edges are checked
    transactionally. If adding any edge would make the target already able to
    reach that adjudicator, the adjudication is rejected because it would close
    a direct or indirect trust cycle.

    This prevents mutual or chained reputation bootstrapping such as A -> B and
    B -> A, or A -> B -> C -> A. The guard is structural only: it does not infer
    that an adjudicator is trustworthy merely because it participates in the DAG.
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._adjudication_graph: dict[str, set[str]] = defaultdict(set)

    @staticmethod
    def _path_exists(graph: dict[str, set[str]], source: str, target: str) -> bool:
        if source == target:
            return True
        queue = deque([source])
        seen = {source}
        while queue:
            node = queue.popleft()
            for nxt in graph.get(node, ()):
                if nxt == target:
                    return True
                if nxt in seen:
                    continue
                seen.add(nxt)
                queue.append(nxt)
        return False

    def adjudication_path(self, source_origin: str, target_origin: str) -> tuple[str, ...] | None:
        source_origin = self._clean_identity(source_origin, field="source_origin")
        target_origin = self._clean_identity(target_origin, field="target_origin")
        if source_origin == target_origin:
            return (source_origin,)

        queue = deque([(source_origin, (source_origin,))])
        seen = {source_origin}
        while queue:
            node, path = queue.popleft()
            for nxt in sorted(self._adjudication_graph.get(node, ())):
                new_path = (*path, nxt)
                if nxt == target_origin:
                    return new_path
                if nxt in seen:
                    continue
                seen.add(nxt)
                queue.append((nxt, new_path))
        return None

    def adjudication_dependencies(self) -> dict[str, tuple[str, ...]]:
        return {
            source: tuple(sorted(targets))
            for source, targets in sorted(self._adjudication_graph.items())
            if targets
        }

    def adjudicate_origin(
        self,
        origin: str,
        *,
        resolution_id: str,
        confirmed: bool,
        adjudicator_origins: tuple[str, ...] | list[str],
        weight: float = 1.0,
    ) -> ReliabilityAdjudicationV115:
        target = self._clean_identity(origin, field="origin")
        adjudicators = tuple(
            sorted(
                {
                    self._clean_identity(item, field="adjudicator_origin")
                    for item in adjudicator_origins
                }
            )
        )

        # Preserve v1.15 validation semantics, but reject indirect cycles before
        # super() mutates reputation or consumes the resolution id.
        if target in adjudicators:
            raise ValueError("an origin cannot adjudicate its own reliability")
        for adjudicator in adjudicators:
            if self._path_exists(self._adjudication_graph, target, adjudicator):
                path = self.adjudication_path(target, adjudicator)
                rendered = " -> ".join(path or (target, adjudicator))
                raise ValueError(
                    "adjudication would create a reliability cycle: "
                    f"{rendered} -> {target}"
                )

        record = super().adjudicate_origin(
            target,
            resolution_id=resolution_id,
            confirmed=confirmed,
            adjudicator_origins=adjudicators,
            weight=weight,
        )
        for adjudicator in adjudicators:
            self._adjudication_graph[adjudicator].add(target)
        return record
