from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from memoria_resolutiva.product_structural import (
    ProductStructuralObservationService,
    attach_structural_observation_routes,
)


def _event():
    return {
        "version": 1,
        "source_id": "web:deployment-smoke",
        "sequence": 7,
        "byte_offset": 112,
        "byte_length": 16,
        "trail": [65, 66, 300, 301],
        "relation_ids": [300, 301],
        "signature": "0123456789abcdef",
        "resolution": 2,
    }


def _client(tmp_path):
    service = ProductStructuralObservationService.open(
        tmp_path / "structural",
        backend="sqlite",
        allow_fallback=False,
    )
    app = FastAPI()
    attach_structural_observation_routes(app, api_key="secret", service=service)
    return service, TestClient(app)


def test_structural_observation_is_raw_idempotent_and_restart_safe(tmp_path):
    service, client = _client(tmp_path)
    headers = {"X-Memoria-Key": "secret"}
    payload = {
        "event": _event(),
        "provenance": {
            "capture_id": "web:capture-1",
            "sha256": "a" * 64,
            "hierarchy_id": "hierarchy:test",
        },
    }

    first = client.post("/api/v1/structural/observations", headers=headers, json=payload)
    assert first.status_code == 201
    first_body = first.json()
    assert first_body["stored"] is True
    assert first_body["duplicate"] is False
    assert first_body["semantic_projection"] is False

    second = client.post("/api/v1/structural/observations", headers=headers, json=payload)
    assert second.status_code == 201
    assert second.json()["stored"] is False
    assert second.json()["duplicate"] is True
    assert second.json()["observation_id"] == first_body["observation_id"]
    assert service.store.count == 1

    recent = client.get("/api/v1/structural/observations/recent", headers=headers)
    assert recent.status_code == 200
    item = recent.json()["items"][0]
    assert item["event"] == _event()
    assert item["provenance"]["capture_id"] == "web:capture-1"
    assert item["semantic_projection"] is False
    assert "subject" not in item and "predicate" not in item and "object" not in item

    restarted = ProductStructuralObservationService.open(
        tmp_path / "structural",
        backend="sqlite",
        allow_fallback=False,
    )
    assert restarted.store.count == 1
    recovered = restarted.store.get(first_body["observation_id"])
    assert recovered == item


def test_structural_observation_same_event_conflicting_provenance_is_rejected(tmp_path):
    _service, client = _client(tmp_path)
    headers = {"X-Memoria-Key": "secret"}

    first = client.post(
        "/api/v1/structural/observations",
        headers=headers,
        json={"event": _event(), "provenance": {"capture_id": "one"}},
    )
    assert first.status_code == 201

    conflict = client.post(
        "/api/v1/structural/observations",
        headers=headers,
        json={"event": _event(), "provenance": {"capture_id": "two"}},
    )
    assert conflict.status_code == 409


def test_structural_routes_require_admin_key(tmp_path):
    _service, client = _client(tmp_path)
    assert client.get("/api/v1/structural/health").status_code == 401
    assert client.post(
        "/api/v1/structural/observations",
        json={"event": _event(), "provenance": {}},
    ).status_code == 401
