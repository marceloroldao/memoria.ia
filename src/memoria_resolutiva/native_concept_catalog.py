from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json

from .product_identity import MemoryScope
from .semantic_concept_store import PersistentSemanticConceptStore


NATIVE_CONCEPT_CATALOG_SCHEMA = 1


@dataclass(frozen=True, slots=True)
class NativeConceptCatalog:
    schema: int
    namespace: str | None
    concepts: tuple[dict[str, object], ...]
    fingerprint: str

    def payload(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "namespace": self.namespace,
            "concepts": [dict(row) for row in self.concepts],
            "fingerprint": self.fingerprint,
        }


def build_native_concept_catalog(
    store: PersistentSemanticConceptStore,
    scope: MemoryScope,
    *,
    namespace: str | None,
) -> NativeConceptCatalog:
    concepts = store.list_concepts(scope, namespace=namespace)
    rows: list[dict[str, object]] = []
    for concept in concepts:
        rows.append(
            {
                "concept_id": concept.concept_id,
                "namespace": concept.namespace,
                "canonical": concept.normalized_canonical,
                "sense_key": concept.sense_key,
                "aliases": list(concept.aliases),
                "context_cues": list(concept.context_cues),
            }
        )
    rows.sort(key=lambda row: str(row["concept_id"]))
    material = {
        "schema": NATIVE_CONCEPT_CATALOG_SCHEMA,
        "namespace": namespace,
        "concepts": rows,
    }
    encoded = json.dumps(material, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    fingerprint = "sha256:" + hashlib.sha256(encoded).hexdigest()
    return NativeConceptCatalog(
        schema=NATIVE_CONCEPT_CATALOG_SCHEMA,
        namespace=namespace,
        concepts=tuple(rows),
        fingerprint=fingerprint,
    )
