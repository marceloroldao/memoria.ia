from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from memoria_resolutiva.product_evidence import ProductEvidenceService, attach_evidence_routes


def _client(tmp_path):
    service = ProductEvidenceService.open(
        tmp_path / "evidence",
        backend="sqlite",
        allow_fallback=False,
    )
    app = FastAPI()
    attach_evidence_routes(app, api_key="secret", service=service)
    return service, TestClient(app)


def test_product_evidence_http_ingest_infer_restart_is_deterministic(tmp_path):
    service, client = _client(tmp_path)
    headers = {"X-Memoria-Key": "secret"}

    first = client.post(
        "/api/v1/evidence/relations",
        headers=headers,
        json={
            "subject": "Delta",
            "predicate": "powers",
            "object": "controlador",
            "evidence_id": "e1",
            "source_text": "A fonte Delta alimenta o controlador.",
            "provenance": "sensor-a",
            "origin": "origin-a",
            "confidence": 0.9,
            "namespace": "lab",
            "epoch": 0,
        },
    )
    assert first.status_code == 201
    assert first.json()["persistence"]["backend"] == "sqlite"

    second = client.post(
        "/api/v1/evidence/relations",
        headers=headers,
        json={
            "subject": "controlador",
            "predicate": "belongs_to",
            "object": "Orion",
            "evidence_id": "e2",
            "source_text": "O controlador pertence ao Orion.",
            "provenance": "registry-b",
            "origin": "origin-b",
            "confidence": 0.8,
            "namespace": "lab",
            "epoch": 1,
        },
    )
    assert second.status_code == 201

    request = {
        "source": "Delta",
        "target": "Orion",
        "namespace": "lab",
        "max_hops": 2,
    }
    inferred = client.post("/api/v1/evidence/infer", headers=headers, json=request)
    assert inferred.status_code == 200
    body = inferred.json()
    assert body["inferred"] is True
    assert body["unsupported_claims"] == 0
    assert body["paths"][0]["predicates"] == ["powers", "belongs_to"]
    assert body["paths"][0]["synthesized_claims"] == 0

    restarted = ProductEvidenceService.open(
        tmp_path / "evidence",
        backend="sqlite",
        allow_fallback=False,
    )
    restarted_app = FastAPI()
    attach_evidence_routes(restarted_app, api_key="secret", service=restarted)
    restarted_client = TestClient(restarted_app)
    after_restart = restarted_client.post(
        "/api/v1/evidence/infer",
        headers=headers,
        json=request,
    )
    assert after_restart.status_code == 200
    assert after_restart.json() == body
    assert restarted.receipt is not None
    assert restarted.backend == "sqlite"
    assert service.receipt is not None
    assert restarted.receipt.state_id == service.receipt.state_id


def test_product_evidence_routes_require_admin_key(tmp_path):
    _service, client = _client(tmp_path)
    assert client.get("/api/v1/evidence/health").status_code == 401
    assert client.post(
        "/api/v1/evidence/infer",
        json={"source": "A", "target": "B"},
    ).status_code == 401
