from __future__ import annotations

import hashlib

from .product_identity import MemoryScope
from .product_service import EnterpriseMemoryService
from .semantic_concepts import (
    ConceptResolution,
    SemanticConcept,
    SemanticConceptIndex,
    normalize_concept_surface,
)


def _namespace_key(namespace: str | None) -> str:
    value = " ".join(str(namespace or "").split()).strip()
    return value or "__global__"


def _alias_key(normalized_alias: str) -> str:
    return hashlib.sha256(normalized_alias.encode("utf-8")).hexdigest()[:24]


class PersistentSemanticConceptStore:
    """Persist explicit concept identities through EnterpriseMemoryService.

    Concept metadata and alias indexes live on dedicated product-memory routes,
    so they survive the existing save/load boundary without becoming factual
    EvidenceCore edges. Alias collisions are preserved as multiple concept IDs.
    """

    def __init__(self, memory: EnterpriseMemoryService) -> None:
        self.memory = memory

    @staticmethod
    def _concept_route(namespace: str | None, concept_id: str) -> tuple[str, ...]:
        return ("semantic-concepts", _namespace_key(namespace), "concept", concept_id)

    @staticmethod
    def _alias_route(namespace: str | None, normalized_alias: str) -> tuple[str, ...]:
        return (
            "semantic-concepts",
            _namespace_key(namespace),
            "alias",
            _alias_key(normalized_alias),
        )

    def _existing_concept(
        self,
        scope: MemoryScope,
        *,
        namespace: str | None,
        concept_id: str,
    ) -> SemanticConcept | None:
        record = self.memory.recall(scope, self._concept_route(namespace, concept_id))
        if record is None or not isinstance(record.payload, dict):
            return None
        payload = record.payload
        if payload.get("kind") != "semantic_concept":
            raise ValueError("semantic concept route contains an incompatible payload")
        return SemanticConcept(
            concept_id=str(payload["concept_id"]),
            canonical_name=str(payload["canonical_name"]),
            normalized_canonical=str(payload["normalized_canonical"]),
            namespace=namespace,
            sense_key=(str(payload["sense_key"]) if payload.get("sense_key") else None),
            aliases=tuple(str(value) for value in payload.get("aliases", ())),
        )

    def register_concept(
        self,
        scope: MemoryScope,
        canonical_name: str,
        *,
        aliases: tuple[str, ...] | list[str] = (),
        namespace: str | None = None,
        sense_key: str | None = None,
        concept_id: str | None = None,
    ) -> SemanticConcept:
        probe = SemanticConceptIndex().register_concept(
            canonical_name,
            aliases=aliases,
            namespace=namespace,
            sense_key=sense_key,
            concept_id=concept_id,
        )
        existing = self._existing_concept(
            scope,
            namespace=namespace,
            concept_id=probe.concept_id,
        )

        index = SemanticConceptIndex()
        if existing is not None:
            index.register_concept(
                existing.canonical_name,
                aliases=existing.aliases,
                namespace=namespace,
                sense_key=existing.sense_key,
                concept_id=existing.concept_id,
            )
        concept = index.register_concept(
            canonical_name,
            aliases=aliases,
            namespace=namespace,
            sense_key=sense_key,
            concept_id=probe.concept_id,
        )

        concept_payload = {
            "kind": "semantic_concept",
            "concept_id": concept.concept_id,
            "canonical_name": concept.canonical_name,
            "normalized_canonical": concept.normalized_canonical,
            "sense_key": concept.sense_key,
            "aliases": list(concept.aliases),
        }
        concept_route = self._concept_route(namespace, concept.concept_id)
        if existing is None:
            self.memory.remember(
                scope,
                f"semantic-concept:{concept.concept_id}",
                concept_payload,
                concept_route,
                modality="semantic",
                provenance="semantic-concept",
            )
        elif concept.aliases != existing.aliases:
            self.memory.update(
                scope,
                concept_route,
                concept_payload,
                modality="semantic",
                provenance="semantic-concept",
            )

        for normalized_alias in concept.aliases:
            route = self._alias_route(namespace, normalized_alias)
            record = self.memory.recall(scope, route)
            if record is None:
                ids = [concept.concept_id]
                payload = {
                    "kind": "semantic_concept_alias",
                    "normalized_alias": normalized_alias,
                    "concept_ids": ids,
                }
                self.memory.remember(
                    scope,
                    f"semantic-alias:{_namespace_key(namespace)}:{_alias_key(normalized_alias)}",
                    payload,
                    route,
                    modality="semantic",
                    provenance="semantic-concept",
                )
                continue
            if not isinstance(record.payload, dict) or record.payload.get("kind") != "semantic_concept_alias":
                raise ValueError("semantic alias route contains an incompatible payload")
            if str(record.payload.get("normalized_alias") or "") != normalized_alias:
                raise ValueError("semantic alias route hash collision detected")
            ids = sorted({str(value) for value in record.payload.get("concept_ids", ())} | {concept.concept_id})
            if ids != list(record.payload.get("concept_ids", ())):
                self.memory.update(
                    scope,
                    route,
                    {
                        "kind": "semantic_concept_alias",
                        "normalized_alias": normalized_alias,
                        "concept_ids": ids,
                    },
                    modality="semantic",
                    provenance="semantic-concept",
                )
        return concept

    def resolve(
        self,
        scope: MemoryScope,
        surface: str,
        *,
        namespace: str | None = None,
    ) -> ConceptResolution:
        normalized = normalize_concept_surface(surface)
        if not normalized:
            return ConceptResolution("UNRESOLVED", None, (), normalized, "empty")
        record = self.memory.recall(scope, self._alias_route(namespace, normalized))
        if record is None:
            return ConceptResolution("UNRESOLVED", None, (), normalized, "unknown")
        if not isinstance(record.payload, dict) or record.payload.get("kind") != "semantic_concept_alias":
            raise ValueError("semantic alias route contains an incompatible payload")
        if str(record.payload.get("normalized_alias") or "") != normalized:
            raise ValueError("semantic alias route hash collision detected")
        candidates = tuple(sorted(str(value) for value in record.payload.get("concept_ids", ())))
        if not candidates:
            return ConceptResolution("UNRESOLVED", None, (), normalized, "unknown")
        if len(candidates) > 1:
            return ConceptResolution("UNRESOLVED", None, candidates, normalized, "ambiguous")
        concept = self._existing_concept(scope, namespace=namespace, concept_id=candidates[0])
        if concept is None:
            return ConceptResolution("UNRESOLVED", None, candidates, normalized, "missing_concept")
        return ConceptResolution("HIT", concept.concept_id, candidates, normalized, None)

    def get(
        self,
        scope: MemoryScope,
        concept_id: str,
        *,
        namespace: str | None = None,
    ) -> SemanticConcept | None:
        return self._existing_concept(scope, namespace=namespace, concept_id=concept_id)
