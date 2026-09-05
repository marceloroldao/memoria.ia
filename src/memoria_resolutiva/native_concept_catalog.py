from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json

from .product_identity import MemoryScope
from .semantic_concept_store import PersistentSemanticConceptStore


NATIVE_CONCEPT_CATALOG_SCHEMA = 1
NATIVE_CONCEPT_APPLY_SYMBOL = "memoria_mobile_apply_concept_catalog_json"


def _wire_field(value: object) -> str:
    text = "" if value is None else str(value)
    return f"{len(text.encode('utf-8'))}:{text}"


def _wire_row(row: dict[str, object]) -> str:
    aliases = tuple(str(value) for value in row.get("aliases", ()))
    cues = tuple(str(value) for value in row.get("context_cues", ()))
    parts = [
        _wire_field(row.get("concept_id")),
        _wire_field(row.get("namespace")),
        _wire_field(row.get("canonical")),
        _wire_field(row.get("sense_key")),
        f"{len(aliases)}:",
    ]
    parts.extend(_wire_field(value) for value in aliases)
    parts.append(f"{len(cues)}:")
    parts.extend(_wire_field(value) for value in cues)
    return "".join(parts)


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

    def wire_payload(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "namespace": self.namespace or "",
            "fingerprint": self.fingerprint,
            "concept_count": len(self.concepts),
            "rows": [_wire_row(row) for row in self.concepts],
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


def apply_native_concept_catalog(runtime_lease, catalog: NativeConceptCatalog) -> bool:
    supports = getattr(runtime_lease, "supports", None)
    if supports is not None and not supports(NATIVE_CONCEPT_APPLY_SYMBOL):
        raise RuntimeError("native Memoria.ia runtime does not support concept catalog materialization")
    status, response = runtime_lease.call(NATIVE_CONCEPT_APPLY_SYMBOL, catalog.wire_payload())
    if status != 0 or response.get("status") != "OK":
        raise RuntimeError(f"native concept catalog materialization failed: status={status}")
    if response.get("fingerprint") != catalog.fingerprint:
        raise RuntimeError("native concept catalog materialization fingerprint mismatch")
    if int(response.get("concept_count", -1)) != len(catalog.concepts):
        raise RuntimeError("native concept catalog materialization count mismatch")
    return bool(response.get("changed", False))
