from fastapi import FastAPI
from fastapi.testclient import TestClient

from memoria_resolutiva.concept_relations import ConceptRelationView
from memoria_resolutiva.evidence_core import EvidenceCore
from memoria_resolutiva.product_concept_relations import (
    ProductConceptRelationService,
    attach_concept_relation_routes,
)
from memoria_resolutiva.product_identity import MemoryScope, OrganizationIdentity
from memoria_resolutiva.product_service import EnterpriseMemoryService
from memoria_resolutiva.semantic_concept_store import PersistentSemanticConceptStore


def _scope():
    return MemoryScope("org-a", application_id="app", user_id="user", agent_id="agent")


def _client():
    memory = EnterpriseMemoryService(OrganizationIdentity("org-a", "Org A"))
    concepts = PersistentSemanticConceptStore(memory)
    concepts.register_concept(
        _scope(),
        "voltage",
        aliases=("DDP", "diferença de potencial"),
        namespace="electronics",
    )
    evidence = EvidenceCore()
    evidence.observe_relation(
        "charger",
        "has_property",
        "diferença de potencial",
        evidence_id="e1",
        source_text="charger has diferença de potencial",
        namespace="session",
        confidence=0.95,
    )
    evidence.observe_relation(
        "voltage",
        "has_value",
        "34V",
        evidence_id="e2",
        source_text="voltage has value 34V",
        namespace="session",
        confidence=0.92,
    )
    view = ConceptRelationView(
        evidence,
        concepts,
        scope=_scope(),
        concept_namespace="electronics",
    )
    app = FastAPI()
    attach_concept_relation_routes(
        app,
        api_key="secret",
        service=ProductConceptRelationService(view),
    )
    return TestClient(app)


def test_concept_relation_routes_require_credentials():
    client = _client()

    response = client.get("/api/v1/semantic/relations/health")

    assert response.status_code == 401


def test_health_declares_read_only_concept_traversal():
    client = _client()

    response = client.get(
        "/api/v1/semantic/relations/health",
        headers={"X-Memoria-Key": "secret"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["capability"] == "concept-relation-traversal-v1"
    assert payload["read_only"] is True
    assert payload["concept_namespace"] == "electronics"


def test_http_infer_returns_auditable_concept_path():
    client = _client()

    response = client.post(
        "/api/v1/semantic/relations/infer",
        headers={"X-Memoria-Key": "secret"},
        json={
            "source": "charger",
            "target": "34V",
            "namespace": "session",
            "max_hops": 3,
            "min_confidence": 0.9,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "HIT"
    assert payload["reason"] is None
    assert payload["paths"][0]["evidence_ids"] == ["e1", "e2"]
    assert payload["paths"][0]["predicates"] == ["has_property", "has_value"]
    assert payload["paths"][0]["hops"] == 2
    assert payload["paths"][0]["confidence"] == 0.92
    bridge = payload["paths"][0]["nodes"][1]
    assert bridge["status"] == "CONCEPT"
    assert bridge["concept_id"] is not None


def test_http_infer_unresolved_is_explicit_not_an_error():
    client = _client()

    response = client.post(
        "/api/v1/semantic/relations/infer",
        headers={"X-Memoria-Key": "secret"},
        json={
            "source": "unknown",
            "target": "34V",
            "namespace": "session",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "UNRESOLVED"
    assert payload["reason"] == "no_path"
    assert payload["paths"] == []


def test_http_request_bounds_are_validated_before_traversal():
    client = _client()

    response = client.post(
        "/api/v1/semantic/relations/infer",
        headers={"X-Memoria-Key": "secret"},
        json={
            "source": "charger",
            "target": "34V",
            "max_hops": 0,
        },
    )

    assert response.status_code == 422
