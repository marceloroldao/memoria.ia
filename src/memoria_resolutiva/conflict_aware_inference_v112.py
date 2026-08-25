from __future__ import annotations

from dataclasses import dataclass

from .structural_inference_v111 import StructuralEdgeV111, StructuralInferenceMemoryV111


@dataclass(frozen=True, slots=True)
class QualifiedEdgeV112:
    subject: str
    predicate: str
    object: str
    memory_id: str
    source_text: str
    temporal_status: str
    confidence: float
    admissible: bool


@dataclass(frozen=True, slots=True)
class QualifiedPathV112:
    nodes: tuple[str, ...]
    predicates: tuple[str, ...]
    memory_ids: tuple[str, ...]
    source_texts: tuple[str, ...]
    edge_statuses: tuple[str, ...]
    edge_confidences: tuple[float, ...]
    path_confidence: float
    hops: int
    kind: str = "qualified_evidence_path"
    synthesized_claims: int = 0


@dataclass(frozen=True, slots=True)
class ConflictAwareResultV112:
    source: str
    target: str
    paths: tuple[QualifiedPathV112, ...]
    inferred: bool
    rejected_conflict_edges: int
    rejected_stale_edges: int
    unsupported_claims: int = 0


class ConflictAwareStructuralMemoryV112:
    """Structural inference that rejects conflicted/stale evidence.

    v1.12 keeps the v1.11 source-backed graph, but qualifies every edge against
    the same v1.03 temporal state that owns the convergent frames used by that
    graph. Stable current edges receive confidence 1.0. The current edge of an
    explicit temporal transition receives 0.9. Historical values from a changed
    predicate are stale and inadmissible; conflicted predicates are inadmissible.

    Path confidence is the minimum confidence of its constituent edges. No new
    factual predicate is synthesized from a path.
    """

    def __init__(self, **kwargs) -> None:
        self.structural = StructuralInferenceMemoryV111(**kwargs)

    def observe(self, text: str, *, provenance: str = "conversation", namespace: str | None = None):
        return self.structural.observe(text, provenance=provenance, namespace=namespace)

    def query(self, text: str, *, top_k: int = 3):
        return self.structural.query(text, top_k=top_k)

    def guided_query(self, text: str, *, top_k: int = 3):
        return self.structural.guided_query(text, top_k=top_k)

    def consolidate_abstractions(self):
        return self.structural.consolidate_abstractions()

    def consolidate_relations(self):
        return self.structural.consolidate_relations()

    def consolidate_ontology(self):
        return self.structural.consolidate_ontology()

    @staticmethod
    def _key(value: str) -> str:
        return " ".join(value.strip().split()).casefold()

    def _temporal(self):
        # StructuralInferenceMemoryV111._frames() reads from
        # ...episodic.events_memory.temporal.convergent.  Qualifying edges must
        # therefore consult that exact TemporalSemanticMemoryV103 instance,
        # not the outer TemporalEventMemoryV104 wrapper.
        return (
            self.structural.guided.ontology.relational.abstraction_memory.pattern_memory
            .episodic.events_memory.temporal.convergent
        )

    def qualify_edge(self, edge: StructuralEdgeV111) -> QualifiedEdgeV112:
        state = self._temporal().predicate_state(edge.subject, edge.predicate)
        if state is None:
            return QualifiedEdgeV112(
                edge.subject, edge.predicate, edge.object, edge.memory_id, edge.source_text,
                "unknown", 0.0, False,
            )

        current = {self._key(value) for value in state.current}
        object_key = self._key(edge.object)
        if state.status == "conflict":
            return QualifiedEdgeV112(
                edge.subject, edge.predicate, edge.object, edge.memory_id, edge.source_text,
                "conflict", 0.0, False,
            )
        if state.status == "changed":
            if object_key in current:
                return QualifiedEdgeV112(
                    edge.subject, edge.predicate, edge.object, edge.memory_id, edge.source_text,
                    "current_changed", 0.9, True,
                )
            return QualifiedEdgeV112(
                edge.subject, edge.predicate, edge.object, edge.memory_id, edge.source_text,
                "stale", 0.0, False,
            )
        if object_key in current:
            return QualifiedEdgeV112(
                edge.subject, edge.predicate, edge.object, edge.memory_id, edge.source_text,
                "stable", 1.0, True,
            )
        return QualifiedEdgeV112(
            edge.subject, edge.predicate, edge.object, edge.memory_id, edge.source_text,
            "stale", 0.0, False,
        )

    def qualified_edges(self) -> tuple[QualifiedEdgeV112, ...]:
        return tuple(self.qualify_edge(edge) for edge in self.structural.edges())

    def infer_path(
        self,
        source: str,
        target: str,
        *,
        max_hops: int = 3,
        max_paths: int = 5,
        min_path_confidence: float = 0.5,
    ) -> ConflictAwareResultV112:
        if max_hops < 1:
            raise ValueError("max_hops must be >= 1")
        if max_paths < 1:
            raise ValueError("max_paths must be >= 1")
        if not 0.0 <= min_path_confidence <= 1.0:
            raise ValueError("min_path_confidence must be between 0 and 1")

        qualified = self.qualified_edges()
        rejected_conflict = sum(1 for edge in qualified if edge.temporal_status == "conflict")
        rejected_stale = sum(1 for edge in qualified if edge.temporal_status == "stale")

        adjacency: dict[str, list[QualifiedEdgeV112]] = {}
        canonical: dict[str, str] = {}
        for edge in qualified:
            if not edge.admissible:
                continue
            s, o = self._key(edge.subject), self._key(edge.object)
            adjacency.setdefault(s, []).append(edge)
            canonical.setdefault(s, edge.subject)
            canonical.setdefault(o, edge.object)

        source_key = self._key(source)
        target_key = self._key(target)
        queue = [(source_key, (source,), (), (), (), (), (), 1.0)]
        paths: list[QualifiedPathV112] = []

        while queue and len(paths) < max_paths:
            node, nodes, predicates, memory_ids, source_texts, statuses, confidences, confidence = queue.pop(0)
            if len(predicates) >= max_hops:
                continue
            for edge in sorted(adjacency.get(node, ()), key=lambda e: (self._key(e.object), e.predicate, e.memory_id)):
                nxt = self._key(edge.object)
                if nxt in {self._key(item) for item in nodes}:
                    continue
                new_confidence = min(confidence, edge.confidence)
                if new_confidence < min_path_confidence:
                    continue
                new_nodes = (*nodes, canonical.get(nxt, edge.object))
                new_predicates = (*predicates, edge.predicate)
                new_memory_ids = (*memory_ids, edge.memory_id)
                new_source_texts = (*source_texts, edge.source_text)
                new_statuses = (*statuses, edge.temporal_status)
                new_confidences = (*confidences, edge.confidence)
                if nxt == target_key:
                    paths.append(QualifiedPathV112(
                        nodes=new_nodes,
                        predicates=new_predicates,
                        memory_ids=new_memory_ids,
                        source_texts=new_source_texts,
                        edge_statuses=new_statuses,
                        edge_confidences=new_confidences,
                        path_confidence=new_confidence,
                        hops=len(new_predicates),
                    ))
                    if len(paths) >= max_paths:
                        break
                else:
                    queue.append((nxt, new_nodes, new_predicates, new_memory_ids, new_source_texts, new_statuses, new_confidences, new_confidence))

        paths.sort(key=lambda p: (-p.path_confidence, p.hops, p.memory_ids))
        return ConflictAwareResultV112(
            source=source,
            target=target,
            paths=tuple(paths[:max_paths]),
            inferred=bool(paths),
            rejected_conflict_edges=rejected_conflict,
            rejected_stale_edges=rejected_stale,
            unsupported_claims=0,
        )
