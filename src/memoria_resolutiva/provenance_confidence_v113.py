from __future__ import annotations

from dataclasses import dataclass

from .temporal_structural_inference_v112 import (
    TemporalStructuralEdgeV112,
    TemporalStructuralInferenceMemoryV112,
)
from .structural_inference_v111 import StructuralInferenceResultV111, StructuralPathV111


@dataclass(frozen=True, slots=True)
class ProvenanceStructuralEdgeV113:
    edge: TemporalStructuralEdgeV112
    provenance: str
    confidence: float


@dataclass(frozen=True, slots=True)
class ProvenanceStructuralPathV113:
    path: StructuralPathV111
    confidence: float
    provenances: tuple[str, ...]
    edge_confidences: tuple[float, ...]


@dataclass(frozen=True, slots=True)
class ProvenanceInferenceResultV113:
    source: str
    target: str
    paths: tuple[ProvenanceStructuralPathV113, ...]
    inferred: bool
    unsupported_claims: int = 0


class ProvenanceConfidenceMemoryV113(TemporalStructuralInferenceMemoryV112):
    """v1.12 temporal structural inference plus provenance/confidence gating.

    Each observed memory receives explicit provenance and a confidence in [0, 1].
    Structural traversal may require a minimum edge confidence. A path confidence
    is the minimum confidence of its supporting edges, so a strong path can never
    hide one weak evidential link. No confidence is synthesized from path length.
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._provenance_by_memory: dict[str, str] = {}
        self._confidence_by_memory: dict[str, float] = {}

    def observe(
        self,
        text: str,
        *,
        provenance: str = "conversation",
        confidence: float = 1.0,
        namespace: str | None = None,
        epoch: int | None = None,
    ):
        if not 0.0 <= confidence <= 1.0:
            raise ValueError("confidence must be in [0, 1]")
        observed = super().observe(
            text,
            provenance=provenance,
            namespace=namespace,
            epoch=epoch,
        )
        self._provenance_by_memory[observed.memory_id] = provenance
        self._confidence_by_memory[observed.memory_id] = float(confidence)
        return observed

    def evidence_edges(
        self,
        *,
        namespace: str | None = None,
        epoch: int | None = None,
        min_confidence: float = 0.0,
    ) -> tuple[ProvenanceStructuralEdgeV113, ...]:
        if not 0.0 <= min_confidence <= 1.0:
            raise ValueError("min_confidence must be in [0, 1]")
        out = []
        for edge in super().edges(namespace=namespace, epoch=epoch):
            confidence = self._confidence_by_memory.get(edge.memory_id, 1.0)
            if confidence < min_confidence:
                continue
            out.append(
                ProvenanceStructuralEdgeV113(
                    edge=edge,
                    provenance=self._provenance_by_memory.get(edge.memory_id, "conversation"),
                    confidence=confidence,
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
    ) -> ProvenanceInferenceResultV113:
        if max_hops < 1:
            raise ValueError("max_hops must be >= 1")
        if max_paths < 1:
            raise ValueError("max_paths must be >= 1")
        if not 0.0 <= min_confidence <= 1.0:
            raise ValueError("min_confidence must be in [0, 1]")

        adjacency: dict[str, list[ProvenanceStructuralEdgeV113]] = {}
        canonical: dict[str, str] = {}
        for wrapped in self.evidence_edges(
            namespace=namespace,
            epoch=epoch,
            min_confidence=min_confidence,
        ):
            edge = wrapped.edge
            s, o = self._key(edge.subject), self._key(edge.object)
            adjacency.setdefault(s, []).append(wrapped)
            canonical.setdefault(s, edge.subject)
            canonical.setdefault(o, edge.object)

        source_key = self._key(source)
        target_key = self._key(target)
        queue = [(source_key, (source,), (), (), (), (), ())]
        paths: list[ProvenanceStructuralPathV113] = []
        while queue and len(paths) < max_paths:
            node, nodes, predicates, memory_ids, source_texts, provenances, confidences = queue.pop(0)
            if len(predicates) >= max_hops:
                continue
            for wrapped in sorted(
                adjacency.get(node, ()),
                key=lambda item: (
                    self._key(item.edge.object),
                    item.edge.predicate,
                    -item.confidence,
                    item.edge.memory_id,
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
                new_provenances = (*provenances, wrapped.provenance)
                new_confidences = (*confidences, wrapped.confidence)
                if nxt == target_key:
                    base_path = StructuralPathV111(
                        nodes=new_nodes,
                        predicates=new_predicates,
                        memory_ids=new_memory_ids,
                        source_texts=new_source_texts,
                        hops=len(new_predicates),
                    )
                    paths.append(
                        ProvenanceStructuralPathV113(
                            path=base_path,
                            confidence=min(new_confidences),
                            provenances=new_provenances,
                            edge_confidences=new_confidences,
                        )
                    )
                    if len(paths) >= max_paths:
                        break
                else:
                    queue.append((
                        nxt,
                        new_nodes,
                        new_predicates,
                        new_memory_ids,
                        new_source_texts,
                        new_provenances,
                        new_confidences,
                    ))

        paths.sort(key=lambda item: (-item.confidence, item.path.hops, item.path.nodes))
        return ProvenanceInferenceResultV113(
            source=source,
            target=target,
            paths=tuple(paths),
            inferred=bool(paths),
            unsupported_claims=0,
        )
