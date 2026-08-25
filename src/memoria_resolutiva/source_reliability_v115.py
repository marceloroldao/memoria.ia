from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from .independent_corroboration_v114 import (
    CorroboratedEdgeV114,
    IndependentCorroborationMemoryV114,
)
from .source_reliability import SourceReliabilityMemory
from .structural_inference_v111 import StructuralPathV111


@dataclass(frozen=True, slots=True)
class ReliabilityAdjudicationV115:
    resolution_id: str
    origin: str
    confirmed: bool
    adjudicator_origins: tuple[str, ...]
    weight: float


@dataclass(frozen=True, slots=True)
class ReliableCorroboratedEdgeV115:
    edge: CorroboratedEdgeV114
    accepted_origins: tuple[str, ...]
    origin_reliabilities: tuple[tuple[str, float], ...]
    reliability_floor: float


@dataclass(frozen=True, slots=True)
class ReliableCorroboratedPathV115:
    path: StructuralPathV111
    confidence: float
    independent_origin_floor: int
    reliability_floor: float
    origins_by_edge: tuple[tuple[str, ...], ...]
    edge_confidences: tuple[float, ...]
    edge_reliabilities: tuple[float, ...]


@dataclass(frozen=True, slots=True)
class ReliabilityInferenceResultV115:
    source: str
    target: str
    paths: tuple[ReliableCorroboratedPathV115, ...]
    inferred: bool
    unsupported_claims: int = 0


class SourceReliabilityCorroborationMemoryV115(IndependentCorroborationMemoryV114):
    """v1.14 plus externally adjudicated historical reliability by evidence origin.

    Reliability is deliberately separate from explicit observation confidence and
    independent-origin corroboration. It is never learned automatically from the
    memory's own inferences. An origin changes reputation only through an explicit
    adjudication that names at least one different adjudicator origin.

    ``resolution_id`` is globally unique inside the memory instance so replaying
    the same adjudication cannot stack reputation. The inherited Beta posterior
    starts unseen origins at 0.5; Wilson lower bound remains available for more
    conservative gates. No source probabilities are fused into observation
    confidence.
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._origin_reliability = SourceReliabilityMemory()
        self._adjudications: list[ReliabilityAdjudicationV115] = []
        self._resolution_ids: set[str] = set()

    @staticmethod
    def _clean_identity(value: str, *, field: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError(f"{field} must be non-empty")
        return cleaned

    def adjudicate_origin(
        self,
        origin: str,
        *,
        resolution_id: str,
        confirmed: bool,
        adjudicator_origins: tuple[str, ...] | list[str],
        weight: float = 1.0,
    ) -> ReliabilityAdjudicationV115:
        origin = self._clean_identity(origin, field="origin")
        resolution_id = self._clean_identity(resolution_id, field="resolution_id")
        if resolution_id in self._resolution_ids:
            raise ValueError("resolution_id has already been applied")
        if weight <= 0:
            raise ValueError("weight must be positive")

        adjudicators = tuple(
            sorted(
                {
                    self._clean_identity(item, field="adjudicator_origin")
                    for item in adjudicator_origins
                }
            )
        )
        if not adjudicators:
            raise ValueError("at least one independent adjudicator origin is required")
        if origin in adjudicators:
            raise ValueError("an origin cannot adjudicate its own reliability")

        if confirmed:
            self._origin_reliability.confirm(origin, weight=weight)
        else:
            self._origin_reliability.contradict(origin, weight=weight)

        record = ReliabilityAdjudicationV115(
            resolution_id=resolution_id,
            origin=origin,
            confirmed=bool(confirmed),
            adjudicator_origins=adjudicators,
            weight=float(weight),
        )
        self._resolution_ids.add(resolution_id)
        self._adjudications.append(record)
        return record

    def origin_reliability(self, origin: str, *, metric: str = "posterior") -> float:
        origin = self._clean_identity(origin, field="origin")
        if metric == "posterior":
            return self._origin_reliability.reliability(origin)
        if metric == "wilson":
            return self._origin_reliability.wilson_lower(origin)
        raise ValueError("metric must be 'posterior' or 'wilson'")

    def origin_evidence_count(self, origin: str) -> float:
        origin = self._clean_identity(origin, field="origin")
        return self._origin_reliability.evidence_count(origin)

    def reliability_snapshot(self) -> dict[str, dict[str, float]]:
        return self._origin_reliability.snapshot()

    def adjudications(self) -> tuple[ReliabilityAdjudicationV115, ...]:
        return tuple(self._adjudications)

    def reliable_edges(
        self,
        *,
        namespace: str | None = None,
        epoch: int | None = None,
        min_confidence: float = 0.0,
        min_independent_origins: int = 1,
        min_origin_reliability: float | None = None,
        reliability_metric: str = "posterior",
    ) -> tuple[ReliableCorroboratedEdgeV115, ...]:
        if min_origin_reliability is not None and not 0.0 <= min_origin_reliability <= 1.0:
            raise ValueError("min_origin_reliability must be in [0, 1]")
        if reliability_metric not in {"posterior", "wilson"}:
            raise ValueError("reliability_metric must be 'posterior' or 'wilson'")

        baseline_edges = super().corroborated_edges(
            namespace=namespace,
            epoch=epoch,
            min_confidence=min_confidence,
            min_independent_origins=1,
        )
        out: list[ReliableCorroboratedEdgeV115] = []
        for wrapped in baseline_edges:
            accepted: list[tuple[str, float]] = []
            for origin in wrapped.independent_origins:
                reliability = self.origin_reliability(origin, metric=reliability_metric)
                if min_origin_reliability is not None and reliability < min_origin_reliability:
                    continue
                accepted.append((origin, reliability))

            if len(accepted) < min_independent_origins:
                continue
            accepted.sort(key=lambda pair: pair[0])
            out.append(
                ReliableCorroboratedEdgeV115(
                    edge=wrapped,
                    accepted_origins=tuple(origin for origin, _ in accepted),
                    origin_reliabilities=tuple(accepted),
                    reliability_floor=min(score for _, score in accepted),
                )
            )
        return tuple(out)

    def infer_path(
        self,
        source: str,
        target: str,
        *,
        max_hops: int = 3,
        max_paths: int = 5,
        namespace: str | None = None,
        epoch: int | None = None,
        min_confidence: float = 0.0,
        min_independent_origins: int = 1,
        min_origin_reliability: float | None = None,
        reliability_metric: str = "posterior",
    ) -> ReliabilityInferenceResultV115:
        if max_hops < 1:
            raise ValueError("max_hops must be >= 1")
        if max_paths < 1:
            raise ValueError("max_paths must be >= 1")
        if min_independent_origins < 1:
            raise ValueError("min_independent_origins must be >= 1")

        adjacency: dict[str, list[ReliableCorroboratedEdgeV115]] = defaultdict(list)
        canonical: dict[str, str] = {}
        for wrapped in self.reliable_edges(
            namespace=namespace,
            epoch=epoch,
            min_confidence=min_confidence,
            min_independent_origins=min_independent_origins,
            min_origin_reliability=min_origin_reliability,
            reliability_metric=reliability_metric,
        ):
            edge = wrapped.edge.edge
            s, o = self._key(edge.subject), self._key(edge.object)
            adjacency[s].append(wrapped)
            canonical.setdefault(s, edge.subject)
            canonical.setdefault(o, edge.object)

        source_key = self._key(source)
        target_key = self._key(target)
        queue = [(source_key, (source,), (), (), (), ())]
        paths: list[ReliableCorroboratedPathV115] = []
        while queue and len(paths) < max_paths:
            node, nodes, predicates, memory_ids, source_texts, edge_wrappers = queue.pop(0)
            if len(predicates) >= max_hops:
                continue
            for wrapped in sorted(
                adjacency.get(node, ()),
                key=lambda item: (
                    -len(item.accepted_origins),
                    -item.reliability_floor,
                    -item.edge.best_confidence,
                    self._key(item.edge.edge.object),
                    item.edge.edge.predicate,
                ),
            ):
                edge = wrapped.edge.edge
                nxt = self._key(edge.object)
                if nxt in {self._key(item) for item in nodes}:
                    continue
                new_nodes = (*nodes, canonical.get(nxt, edge.object))
                new_predicates = (*predicates, edge.predicate)
                new_memory_ids = (*memory_ids, edge.memory_id)
                new_source_texts = (*source_texts, edge.source_text)
                new_wrappers = (*edge_wrappers, wrapped)
                if nxt == target_key:
                    base_path = StructuralPathV111(
                        nodes=new_nodes,
                        predicates=new_predicates,
                        memory_ids=new_memory_ids,
                        source_texts=new_source_texts,
                        hops=len(new_predicates),
                    )
                    paths.append(
                        ReliableCorroboratedPathV115(
                            path=base_path,
                            confidence=min(item.edge.best_confidence for item in new_wrappers),
                            independent_origin_floor=min(
                                len(item.accepted_origins) for item in new_wrappers
                            ),
                            reliability_floor=min(
                                item.reliability_floor for item in new_wrappers
                            ),
                            origins_by_edge=tuple(item.accepted_origins for item in new_wrappers),
                            edge_confidences=tuple(
                                item.edge.best_confidence for item in new_wrappers
                            ),
                            edge_reliabilities=tuple(
                                item.reliability_floor for item in new_wrappers
                            ),
                        )
                    )
                else:
                    queue.append(
                        (
                            nxt,
                            new_nodes,
                            new_predicates,
                            new_memory_ids,
                            new_source_texts,
                            new_wrappers,
                        )
                    )

        paths.sort(
            key=lambda item: (
                -item.independent_origin_floor,
                -item.reliability_floor,
                -item.confidence,
                item.path.hops,
                item.path.nodes,
            )
        )
        return ReliabilityInferenceResultV115(
            source=source,
            target=target,
            paths=tuple(paths[:max_paths]),
            inferred=bool(paths),
            unsupported_claims=0,
        )
