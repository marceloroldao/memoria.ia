from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from .provenance_confidence_v113 import ProvenanceConfidenceMemoryV113
from .structural_inference_v111 import StructuralPathV111
from .temporal_structural_inference_v112 import (
    TemporalStructuralEdgeV112,
    TemporalStructuralInferenceMemoryV112,
    _SINGLE_VALUE_PREDICATES,
)


@dataclass(frozen=True, slots=True)
class CorroborationObservationV114:
    subject: str
    predicate: str
    object: str
    memory_id: str
    provenance: str
    origin: str
    confidence: float
    namespace: str | None
    epoch: int


@dataclass(frozen=True, slots=True)
class CorroboratedEdgeV114:
    edge: TemporalStructuralEdgeV112
    independent_origins: tuple[str, ...]
    origin_confidences: tuple[tuple[str, float], ...]
    provenances: tuple[str, ...]
    best_confidence: float


@dataclass(frozen=True, slots=True)
class CorroboratedPathV114:
    path: StructuralPathV111
    confidence: float
    independent_origin_floor: int
    origins_by_edge: tuple[tuple[str, ...], ...]
    edge_confidences: tuple[float, ...]


@dataclass(frozen=True, slots=True)
class CorroborationInferenceResultV114:
    source: str
    target: str
    paths: tuple[CorroboratedPathV114, ...]
    inferred: bool
    unsupported_claims: int = 0


class IndependentCorroborationMemoryV114(ProvenanceConfidenceMemoryV113):
    """v1.13 plus conservative corroboration by independent evidence origin.

    Confidence and independence stay separate. Repeating or copying evidence from
    one origin never increases the independent-origin count; only the strongest
    explicit confidence from that origin is retained for a logical edge. No
    probability is synthesized by combining sources.

    ``origin`` identifies the underlying evidence family. When omitted, it
    defaults to ``provenance``. This lets several channels that copy one original
    report share one origin and therefore count only once.
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._corroboration_observations: list[CorroborationObservationV114] = []

    def observe(
        self,
        text: str,
        *,
        provenance: str = "conversation",
        origin: str | None = None,
        confidence: float = 1.0,
        namespace: str | None = None,
        epoch: int | None = None,
    ):
        used_epoch = self._next_epoch_by_namespace[namespace] if epoch is None else epoch
        observed = super().observe(
            text,
            provenance=provenance,
            confidence=confidence,
            namespace=namespace,
            epoch=epoch,
        )
        frame = self._frame_for_memory(observed.memory_id, namespace=namespace)
        if frame is not None:
            evidence_origin = provenance if origin is None else origin
            for relation in frame.relations:
                self._corroboration_observations.append(
                    CorroborationObservationV114(
                        subject=relation.subject,
                        predicate=relation.predicate,
                        object=relation.object,
                        memory_id=observed.memory_id,
                        provenance=provenance,
                        origin=evidence_origin,
                        confidence=float(confidence),
                        namespace=namespace,
                        epoch=used_epoch,
                    )
                )
        return observed

    def _logical_key(self, subject: str, predicate: str, object_: str) -> tuple[str, str, str]:
        return self._key(subject), predicate, self._key(object_)

    def corroborated_edges(
        self,
        *,
        namespace: str | None = None,
        epoch: int | None = None,
        min_confidence: float = 0.0,
        min_independent_origins: int = 1,
    ) -> tuple[CorroboratedEdgeV114, ...]:
        if not 0.0 <= min_confidence <= 1.0:
            raise ValueError("min_confidence must be in [0, 1]")
        if min_independent_origins < 1:
            raise ValueError("min_independent_origins must be >= 1")

        active = TemporalStructuralInferenceMemoryV112.edges(
            self, namespace=namespace, epoch=epoch
        )
        grouped_edges: dict[tuple[str, str, str], list[TemporalStructuralEdgeV112]] = defaultdict(list)
        for edge in active:
            grouped_edges[self._logical_key(edge.subject, edge.predicate, edge.object)].append(edge)

        out: list[CorroboratedEdgeV114] = []
        for key, edge_group in grouped_edges.items():
            representative = max(edge_group, key=lambda e: (e.epoch, e.memory_id))
            supports = [
                item
                for item in self._corroboration_observations
                if item.namespace == namespace
                and self._logical_key(item.subject, item.predicate, item.object) == key
                and (epoch is None or item.epoch <= epoch)
            ]
            if representative.predicate in _SINGLE_VALUE_PREDICATES:
                supports = [item for item in supports if item.epoch == representative.epoch]

            by_origin: dict[str, list[CorroborationObservationV114]] = defaultdict(list)
            for item in supports:
                by_origin[item.origin].append(item)

            origin_confidences: list[tuple[str, float]] = []
            provenances: set[str] = set()
            for evidence_origin, items in by_origin.items():
                strongest = max(item.confidence for item in items)
                if strongest < min_confidence:
                    continue
                origin_confidences.append((evidence_origin, strongest))
                provenances.update(item.provenance for item in items if item.confidence >= min_confidence)

            origin_confidences.sort(key=lambda pair: pair[0])
            if len(origin_confidences) < min_independent_origins:
                continue
            out.append(
                CorroboratedEdgeV114(
                    edge=representative,
                    independent_origins=tuple(origin for origin, _ in origin_confidences),
                    origin_confidences=tuple(origin_confidences),
                    provenances=tuple(sorted(provenances)),
                    best_confidence=max(score for _, score in origin_confidences),
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
    ) -> CorroborationInferenceResultV114:
        if max_hops < 1:
            raise ValueError("max_hops must be >= 1")
        if max_paths < 1:
            raise ValueError("max_paths must be >= 1")

        adjacency: dict[str, list[CorroboratedEdgeV114]] = defaultdict(list)
        canonical: dict[str, str] = {}
        for wrapped in self.corroborated_edges(
            namespace=namespace,
            epoch=epoch,
            min_confidence=min_confidence,
            min_independent_origins=min_independent_origins,
        ):
            edge = wrapped.edge
            s, o = self._key(edge.subject), self._key(edge.object)
            adjacency[s].append(wrapped)
            canonical.setdefault(s, edge.subject)
            canonical.setdefault(o, edge.object)

        source_key = self._key(source)
        target_key = self._key(target)
        queue = [(source_key, (source,), (), (), (), ())]
        paths: list[CorroboratedPathV114] = []
        while queue and len(paths) < max_paths:
            node, nodes, predicates, memory_ids, source_texts, edge_wrappers = queue.pop(0)
            if len(predicates) >= max_hops:
                continue
            for wrapped in sorted(
                adjacency.get(node, ()),
                key=lambda item: (
                    -len(item.independent_origins),
                    -item.best_confidence,
                    self._key(item.edge.object),
                    item.edge.predicate,
                ),
            ):
                edge = wrapped.edge
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
                        CorroboratedPathV114(
                            path=base_path,
                            confidence=min(item.best_confidence for item in new_wrappers),
                            independent_origin_floor=min(
                                len(item.independent_origins) for item in new_wrappers
                            ),
                            origins_by_edge=tuple(item.independent_origins for item in new_wrappers),
                            edge_confidences=tuple(item.best_confidence for item in new_wrappers),
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
                -item.confidence,
                item.path.hops,
                item.path.nodes,
            )
        )
        return CorroborationInferenceResultV114(
            source=source,
            target=target,
            paths=tuple(paths[:max_paths]),
            inferred=bool(paths),
            unsupported_claims=0,
        )
