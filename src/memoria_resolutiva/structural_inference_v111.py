from __future__ import annotations

from dataclasses import dataclass

from .ontology_guided_retrieval_v110 import OntologyGuidedMemoryV110


@dataclass(frozen=True, slots=True)
class StructuralEdgeV111:
    subject: str
    predicate: str
    object: str
    memory_id: str
    source_text: str


@dataclass(frozen=True, slots=True)
class StructuralPathV111:
    nodes: tuple[str, ...]
    predicates: tuple[str, ...]
    memory_ids: tuple[str, ...]
    source_texts: tuple[str, ...]
    hops: int
    kind: str = "evidence_path"
    synthesized_claims: int = 0


@dataclass(frozen=True, slots=True)
class StructuralInferenceResultV111:
    source: str
    target: str
    paths: tuple[StructuralPathV111, ...]
    inferred: bool
    unsupported_claims: int = 0


class StructuralInferenceMemoryV111:
    """Conservative graph navigation over source-backed semantic relations.

    v1.11 does not synthesize a new predicate from a multi-hop path. It may only
    return an ``evidence_path`` whose every edge exists in an original semantic
    frame with a source memory id and source text. This allows structural
    navigation such as Delta --powers--> controlador --belongs_to--> Orion
    without claiming that Delta itself ``belongs_to`` Orion or that any edge is
    causal, taxonomic, or universally true.
    """

    def __init__(self, **kwargs) -> None:
        self.guided = OntologyGuidedMemoryV110(**kwargs)

    def observe(self, text: str, *, provenance: str = "conversation", namespace: str | None = None):
        return self.guided.observe(text, provenance=provenance, namespace=namespace)

    def query(self, text: str, *, top_k: int = 3):
        return self.guided.query(text, top_k=top_k)

    def guided_query(self, text: str, *, top_k: int = 3):
        return self.guided.guided_query(text, top_k=top_k)

    def consolidate_abstractions(self):
        return self.guided.consolidate_abstractions()

    def consolidate_relations(self):
        return self.guided.consolidate_relations()

    def consolidate_ontology(self):
        return self.guided.consolidate_ontology()

    def _frames(self):
        convergent = (
            self.guided.ontology.relational.abstraction_memory.pattern_memory
            .episodic.events_memory.temporal.convergent
        )
        return tuple(convergent._frames.values())

    @staticmethod
    def _key(value: str) -> str:
        return " ".join(value.strip().split()).casefold()

    def edges(self) -> tuple[StructuralEdgeV111, ...]:
        out: list[StructuralEdgeV111] = []
        seen: set[tuple[str, str, str, str]] = set()
        for frame in self._frames():
            for relation in frame.relations:
                key = (
                    self._key(relation.subject),
                    relation.predicate,
                    self._key(relation.object),
                    frame.memory_id,
                )
                if key in seen:
                    continue
                seen.add(key)
                out.append(
                    StructuralEdgeV111(
                        subject=relation.subject,
                        predicate=relation.predicate,
                        object=relation.object,
                        memory_id=frame.memory_id,
                        source_text=frame.source_text,
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
    ) -> StructuralInferenceResultV111:
        if max_hops < 1:
            raise ValueError("max_hops must be >= 1")
        if max_paths < 1:
            raise ValueError("max_paths must be >= 1")

        source_key = self._key(source)
        target_key = self._key(target)
        adjacency: dict[str, list[StructuralEdgeV111]] = {}
        canonical: dict[str, str] = {}
        for edge in self.edges():
            s, o = self._key(edge.subject), self._key(edge.object)
            adjacency.setdefault(s, []).append(edge)
            canonical.setdefault(s, edge.subject)
            canonical.setdefault(o, edge.object)

        queue: list[tuple[str, tuple[str, ...], tuple[str, ...], tuple[str, ...], tuple[str, ...]]] = [
            (source_key, (source,), (), (), ())
        ]
        paths: list[StructuralPathV111] = []
        while queue and len(paths) < max_paths:
            node, nodes, predicates, memory_ids, source_texts = queue.pop(0)
            if len(predicates) >= max_hops:
                continue
            for edge in sorted(
                adjacency.get(node, ()),
                key=lambda e: (self._key(e.object), e.predicate, e.memory_id),
            ):
                nxt = self._key(edge.object)
                if nxt in {self._key(item) for item in nodes}:
                    continue
                new_nodes = (*nodes, canonical.get(nxt, edge.object))
                new_predicates = (*predicates, edge.predicate)
                new_memory_ids = (*memory_ids, edge.memory_id)
                new_source_texts = (*source_texts, edge.source_text)
                if nxt == target_key:
                    paths.append(
                        StructuralPathV111(
                            nodes=new_nodes,
                            predicates=new_predicates,
                            memory_ids=new_memory_ids,
                            source_texts=new_source_texts,
                            hops=len(new_predicates),
                        )
                    )
                    if len(paths) >= max_paths:
                        break
                else:
                    queue.append((nxt, new_nodes, new_predicates, new_memory_ids, new_source_texts))

        return StructuralInferenceResultV111(
            source=source,
            target=target,
            paths=tuple(paths),
            inferred=bool(paths),
            unsupported_claims=0,
        )
