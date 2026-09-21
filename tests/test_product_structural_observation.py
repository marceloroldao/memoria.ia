from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from memoria_resolutiva.product_structural import (
    ProductStructuralObservationService,
    attach_structural_observation_routes,
)


def _event(sequence=7, trail=None):
    trail = [65, 66, 300, 301] if trail is None else list(trail)
    return {
        "version": 1,
        "source_id": "web:deployment-smoke",
        "sequence": sequence,
        "byte_offset": sequence * 16,
        "byte_length": 16,
        "trail": trail,
        "relation_ids": [item for item in trail if item >= 256],
        "signature": f"{sequence + 1:016x}",
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
    assert first_body["association_sync_observations"] == 1

    second = client.post("/api/v1/structural/observations", headers=headers, json=payload)
    assert second.status_code == 201
    assert second.json()["stored"] is False
    assert second.json()["duplicate"] is True
    assert second.json()["association_sync_observations"] == 0
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
        json={"event": _event(), "provenance": {"hierarchy_id": "hierarchy:test", "capture_id": "one"}},
    )
    assert first.status_code == 201

    conflict = client.post(
        "/api/v1/structural/observations",
        headers=headers,
        json={"event": _event(), "provenance": {"hierarchy_id": "hierarchy:test", "capture_id": "two"}},
    )
    assert conflict.status_code == 409


def test_structural_routes_require_admin_key(tmp_path):
    _service, client = _client(tmp_path)
    assert client.get("/api/v1/structural/health").status_code == 401
    assert client.post(
        "/api/v1/structural/observations",
        json={
            "event": _event(),
            "provenance": {"hierarchy_id": "hierarchy:test"},
        },
    ).status_code == 401


def test_structural_association_query_is_non_semantic_and_restart_safe(tmp_path):
    service, client = _client(tmp_path)
    headers = {"X-Memoria-Key": "secret"}

    first = client.post(
        "/api/v1/structural/observations",
        headers=headers,
        json={
            "event": _event(0, [10]),
            "provenance": {"hierarchy_id": "hierarchy:test", "capture_id": "one"},
        },
    )
    second = client.post(
        "/api/v1/structural/observations",
        headers=headers,
        json={
            "event": _event(1, [20]),
            "provenance": {"hierarchy_id": "hierarchy:test", "capture_id": "two"},
        },
    )
    assert first.status_code == 201
    assert second.status_code == 201

    queried = client.get(
        "/api/v1/structural/associations"
        "?hierarchy_id=hierarchy%3Atest&source=10&channel=temporal&limit=10",
        headers=headers,
    )
    assert queried.status_code == 200
    body = queried.json()
    assert body["semantic_projection"] is False
    assert body["hierarchy_id"] == "hierarchy:test"
    assert body["source"] == 10
    assert body["associations"][0]["target"] == 20
    assert body["associations"][0]["channel"] == "temporal"
    assert body["associations"][0]["weight"] > 0
    assert "predicate" not in body["associations"][0]
    assert "subject" not in body["associations"][0]
    assert "object" not in body["associations"][0]

    restarted, restarted_client = _client(tmp_path)
    status = restarted_client.get(
        "/api/v1/structural/associations/status",
        headers=headers,
    )
    assert status.status_code == 200
    assert status.json()["pending_observations"] == 0
    assert status.json()["derived_observations"] == 2
    assert restarted.associations.replayed_on_open == 0

    after_restart = restarted_client.get(
        "/api/v1/structural/associations"
        "?hierarchy_id=hierarchy%3Atest&source=10&channel=temporal&limit=10",
        headers=headers,
    )
    assert after_restart.status_code == 200
    assert after_restart.json()["associations"] == body["associations"]


def test_structural_ingest_requires_hierarchy_namespace(tmp_path):
    _service, client = _client(tmp_path)
    response = client.post(
        "/api/v1/structural/observations",
        headers={"X-Memoria-Key": "secret"},
        json={
            "event": _event(),
            "provenance": {"capture_id": "missing-hierarchy"},
        },
    )
    assert response.status_code == 422



def test_structural_observation_preserves_optional_physical_time(tmp_path):
    _service, client = _client(tmp_path)
    headers = {"X-Memoria-Key": "secret"}
    payload = {
        "event": _event(3, [10, 20]),
        "provenance": {
            "hierarchy_id": "hierarchy:test",
            "capture_id": "sensor:capture",
        },
        "temporal": {
            "clock_id": "sensor:clock",
            "t_start": 12.25,
            "t_end": 12.5,
            "unit": "s",
        },
    }

    stored = client.post(
        "/api/v1/structural/observations",
        headers=headers,
        json=payload,
    )
    assert stored.status_code == 201

    recent = client.get(
        "/api/v1/structural/observations/recent",
        headers=headers,
    )
    assert recent.status_code == 200
    assert recent.json()["items"][0]["temporal"] == payload["temporal"]


def test_structural_observation_rejects_invalid_physical_interval(tmp_path):
    _service, client = _client(tmp_path)
    response = client.post(
        "/api/v1/structural/observations",
        headers={"X-Memoria-Key": "secret"},
        json={
            "event": _event(),
            "provenance": {"hierarchy_id": "hierarchy:test"},
            "temporal": {
                "clock_id": "sensor:clock",
                "t_start": 2.0,
                "t_end": 1.0,
                "unit": "s",
            },
        },
    )
    assert response.status_code == 409
