from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass

from .evidence_core import EvidenceCore, EvidenceEdge
from .product_identity import MemoryScope
from .semantic_concept_store import PersistentSemanticConceptStore
from .semantic_concepts import normalize_concept_surface


@dataclass(frozen=True, slots=True)
class ConceptEndpoint:
    surface: str
    key: str
    concept_id: str | None
    sense_key: str | None
    status: str


@dataclass(frozen=True, slots=True)
class ConceptBoundRelation:
    evidence_id: str
    subject: ConceptEndpoint
    predicate: str
    object: ConceptEndpoint
    source_text: str
    namespace: str | None
    epoch: int
    confidence: float


@dataclass(frozen=True, slots=True)
class ConceptRelationLookup:
    status: str
    relations: tuple[ConceptBoundRelation, ...]
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class ConceptRelationPath:
    nodes: tuple[ConceptEndpoint, ...]
    predicates: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    source_texts: tuple[str, ...]
    confidence: float
    hops: int


@dataclass(frozen=True, slots=True)
class ConceptRelationPathResult:
    status: str
    paths: tuple[ConceptRelationPath, ...]
    reason: str | None = None


class ConceptRelationView:
    """Read-only concept projection over active EvidenceCore relations.

    Evidence rows remain authoritative and unchanged. This view derives a stable
    endpoint key for each subject/object: explicit semantic concept identity when
    an unambiguous concept exists, otherwise the normalized lexical surface.
    Contextual sense selection may use only explicit persisted context cues.
    """

    def __init__(
        self,
        evidence: EvidenceCore,
        concepts: PersistentSemanticConceptStore,
        *,
        scope: MemoryScope,
        concept_namespace: str | None = None,
    ) -> None:
        self.evidence = evidence
        self.concepts = concepts
        self.scope = scope
        self.concept_namespace = concept_namespace

    def _endpoint(self, surface: str, *, context: str) -> ConceptEndpoint:
        resolution = self.concepts.resolve_with_context(
            self.scope,
            surface,
            context,
            namespace=self.concept_namespace,
        )
        if resolution.status == "HIT" and resolution.concept_id is not None:
            concept = self.concepts.get(
                self.scope,
                resolution.concept_id,
                namespace=self.concept_namespace,
            )
            if concept is not None:
                return ConceptEndpoint(
                    surface=surface,
                    key=f"concept:{concept.concept_id}",
                    concept_id=concept.concept_id,
                    sense_key=concept.sense_key,
                    status="CONCEPT",
                )
        normalized = normalize_concept_surface(surface)
        reason = resolution.reason or "lexical"
        return ConceptEndpoint(
            surface=surface,
            key=f"surface:{normalized}",
            concept_id=None,
            sense_key=None,
            status="AMBIGUOUS" if reason in {"ambiguous", "ambiguous_context"} else "LEXICAL",
        )

    def bind_edge(self, edge: EvidenceEdge) -> ConceptBoundRelation:
        return ConceptBoundRelation(
            evidence_id=edge.evidence_id,
            subject=self._endpoint(edge.subject, context=edge.source_text),
            predicate=edge.predicate,
            object=self._endpoint(edge.object, context=edge.source_text),
            source_text=edge.source_text,
            namespace=edge.namespace,
            epoch=edge.epoch,
            confidence=edge.confidence,
        )

    def active_relations(self, *, namespace: str | None = None) -> tuple[ConceptBoundRelation, ...]:
        rows = []
        for edge in self.evidence.active_edges(namespace=namespace):
            if edge.predicate == "conversation_text" or edge.predicate.startswith("provenance_"):
                continue
            rows.append(self.bind_edge(edge))
        return tuple(rows)

    def _query_endpoint(self, surface: str, *, context: str) -> ConceptEndpoint:
        return self._endpoint(surface, context=context)

    def find(
        self,
        *,
        subject: str | None = None,
        predicate: str | None = None,
        object: str | None = None,
        namespace: str | None = None,
        context: str | None = None,
    ) -> ConceptRelationLookup:
        if subject is None and predicate is None and object is None:
            raise ValueError("at least one relation selector is required")
        query_context = context or " ".join(value for value in (subject, predicate, object) if value)

        subject_endpoint = self._query_endpoint(subject, context=query_context) if subject is not None else None
        object_endpoint = self._query_endpoint(object, context=query_context) if object is not None else None
        for endpoint in (subject_endpoint, object_endpoint):
            if endpoint is not None and endpoint.status == "AMBIGUOUS":
                return ConceptRelationLookup("UNRESOLVED", (), "ambiguous_concept")

        matches = []
        for relation in self.active_relations(namespace=namespace):
            if predicate is not None and relation.predicate != predicate:
                continue
            if subject_endpoint is not None and relation.subject.key != subject_endpoint.key:
                continue
            if object_endpoint is not None and relation.object.key != object_endpoint.key:
                continue
            matches.append(relation)
        if not matches:
            return ConceptRelationLookup("UNRESOLVED", (), "no_match")
        matches.sort(key=lambda row: (-row.epoch, row.evidence_id))
        return ConceptRelationLookup("HIT", tuple(matches), None)

    def infer_path(
        self,
        source: str,
        target: str,
        *,
        namespace: str | None = None,
        context: str | None = None,
        max_hops: int = 3,
        max_paths: int = 5,
        min_confidence: float = 0.0,
    ) -> ConceptRelationPathResult:
        """Traverse active relations by concept identity without changing evidence.

        Two lexical surfaces connect only when they project to the exact same
        explicit concept ID (or the same normalized lexical surface when neither
        side has a registered concept). Ambiguous endpoints fail closed.
        """
        if max_hops < 1 or max_paths < 1:
            raise ValueError("max_hops and max_paths must be >= 1")
        if not 0.0 <= min_confidence <= 1.0:
            raise ValueError("min_confidence must be in [0, 1]")
        query_context = context or f"{source} {target}"
        source_endpoint = self._query_endpoint(source, context=query_context)
        target_endpoint = self._query_endpoint(target, context=query_context)
        if source_endpoint.status == "AMBIGUOUS" or target_endpoint.status == "AMBIGUOUS":
            return ConceptRelationPathResult("UNRESOLVED", (), "ambiguous_concept")

        adjacency: dict[str, list[ConceptBoundRelation]] = defaultdict(list)
        endpoint_by_key: dict[str, ConceptEndpoint] = {
            source_endpoint.key: source_endpoint,
            target_endpoint.key: target_endpoint,
        }
        for relation in self.active_relations(namespace=namespace):
            if relation.confidence < min_confidence:
                continue
            if relation.subject.status == "AMBIGUOUS" or relation.object.status == "AMBIGUOUS":
                continue
            adjacency[relation.subject.key].append(relation)
            endpoint_by_key.setdefault(relation.subject.key, relation.subject)
            endpoint_by_key.setdefault(relation.object.key, relation.object)
        for rows in adjacency.values():
            rows.sort(key=lambda row: (row.object.key, row.predicate, row.evidence_id))

        queue = deque([
            (
                source_endpoint.key,
                (source_endpoint,),
                (),
                (),
                (),
                (),
                frozenset({source_endpoint.key}),
            )
        ])
        paths: list[ConceptRelationPath] = []
        while queue and len(paths) < max_paths:
            node_key, nodes, predicates, evidence_ids, source_texts, confidences, seen = queue.popleft()
            if len(predicates) >= max_hops:
                continue
            for relation in adjacency.get(node_key, ()):
                next_key = relation.object.key
                if next_key in seen:
                    continue
                next_endpoint = endpoint_by_key[next_key]
                next_nodes = (*nodes, next_endpoint)
                next_predicates = (*predicates, relation.predicate)
                next_evidence_ids = (*evidence_ids, relation.evidence_id)
                next_source_texts = (*source_texts, relation.source_text)
                next_confidences = (*confidences, relation.confidence)
                if next_key == target_endpoint.key:
                    paths.append(
                        ConceptRelationPath(
                            nodes=next_nodes,
                            predicates=next_predicates,
                            evidence_ids=next_evidence_ids,
                            source_texts=next_source_texts,
                            confidence=min(next_confidences),
                            hops=len(next_predicates),
                        )
                    )
                else:
                    queue.append(
                        (
                            next_key,
                            next_nodes,
                            next_predicates,
                            next_evidence_ids,
                            next_source_texts,
                            next_confidences,
                            seen | {next_key},
                        )
                    )
        if not paths:
            return ConceptRelationPathResult("UNRESOLVED", (), "no_path")
        paths.sort(key=lambda path: (-path.confidence, path.hops, path.evidence_ids))
        return ConceptRelationPathResult("HIT", tuple(paths[:max_paths]), None)
