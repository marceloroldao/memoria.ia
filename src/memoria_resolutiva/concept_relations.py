from __future__ import annotations

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
