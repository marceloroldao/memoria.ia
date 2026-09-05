from __future__ import annotations

from memoria_resolutiva.native_concept_catalog import build_native_concept_catalog
from memoria_resolutiva.product_identity import MemoryScope, OrganizationIdentity
from memoria_resolutiva.product_service import EnterpriseMemoryService
from memoria_resolutiva.semantic_concept_store import PersistentSemanticConceptStore


def test_native_concept_catalog_is_deterministic_and_namespace_scoped():
    memory = EnterpriseMemoryService(OrganizationIdentity("org-a", "Org A"))
    store = PersistentSemanticConceptStore(memory)
    scope = MemoryScope("org-a")

    store.register_concept(
        scope,
        "voltage",
        aliases=("ddp", "diferença de potencial"),
        namespace="semantic",
        concept_id="concept:voltage",
    )
    store.register_concept(
        scope,
        "financial bank",
        aliases=("bank",),
        context_cues=("loan", "credit"),
        namespace="semantic",
        sense_key="finance",
        concept_id="concept:bank-finance",
    )
    store.register_concept(
        scope,
        "temperature",
        aliases=("temperatura",),
        namespace="sensors",
        concept_id="concept:temperature",
    )

    first = build_native_concept_catalog(store, scope, namespace="semantic")
    second = build_native_concept_catalog(store, scope, namespace="semantic")

    assert first == second
    assert first.schema == 1
    assert [row["concept_id"] for row in first.concepts] == ["concept:bank-finance", "concept:voltage"]
    assert all(row["namespace"] == "semantic" for row in first.concepts)
    assert first.fingerprint.startswith("sha256:")

    sensors = build_native_concept_catalog(store, scope, namespace="sensors")
    assert [row["concept_id"] for row in sensors.concepts] == ["concept:temperature"]
    assert sensors.fingerprint != first.fingerprint


def test_native_concept_catalog_fingerprint_changes_after_authoritative_update():
    memory = EnterpriseMemoryService(OrganizationIdentity("org-a"))
    store = PersistentSemanticConceptStore(memory)
    scope = MemoryScope("org-a")

    store.register_concept(
        scope,
        "voltage",
        aliases=("ddp",),
        namespace="semantic",
        concept_id="concept:voltage",
    )
    before = build_native_concept_catalog(store, scope, namespace="semantic")

    store.register_concept(
        scope,
        "voltage",
        aliases=("diferença de potencial",),
        namespace="semantic",
        concept_id="concept:voltage",
    )
    after = build_native_concept_catalog(store, scope, namespace="semantic")

    assert after.fingerprint != before.fingerprint
    assert after.concepts[0]["aliases"] == ["voltage", "ddp", "diferenca de potencial"]
