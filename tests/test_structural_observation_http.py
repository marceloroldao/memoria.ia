from __future__ import annotations

import json

from fastapi import FastAPI
from fastapi.testclient import TestClient

from memoria_resolutiva.structural_contract import (
    STRUCTURAL_EVENT_TYPE,
    STRUCTURAL_SCHEMA,
    attach_structural_routes,
)


HEADERS = {"X-Memoria-Key": "secret"}


class FakeEdge:
    def __init__(self, evidence_id: str):
        self.evidence_id = evidence_id


class FakeReceipt:
    def as_dict(self):
        return {"backend": "fake", "durable": True}


class FakeStructuralSink:
    def __init__(self):
        self.requests = []

    def store_structural(self, request):
        self.requests.append(request)
        return FakeEdge(request.episode_id), FakeReceipt()


def app_for(service):
    app = FastAPI()
    attach_structural_routes(app, api_key="secret", service=service)
    return TestClient(app)


def payload():
    return {
        "hierarchy_id": "hierarchy:abc",
        "source_id": "web:capture-1",
        "sequence": 3,
        "byte_offset": 8192,
        "byte_length": 4096,
        "signature": "0011223344556677",
        "resolution": 2,
        "relation_ids": [256, 300, 256],
        "trail_symbols": 1024,
        "content_sha256": "a" * 64,
        "content_type": "text/html; charset=utf-8",
        "observed_at": "2026-09-21T20:00:00Z",
        "url": "https://example.org/page",
        "checkpoint_file": "checkpoint-123.json",
    }


def test_structural_route_is_authenticated_and_deterministic():
    sink = FakeStructuralSink()
    client = app_for(sink)
    assert client.post("/api/v1/structural/events", json=payload()).status_code == 401

    first = client.post("/api/v1/structural/events", headers=HEADERS, json=payload())
    second = client.post("/api/v1/structural/events", headers=HEADERS, json=payload())
    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["episode_id"] == second.json()["episode_id"]
    assert len(sink.requests) == 2
    request = sink.requests[0]
    assert request.event_type == STRUCTURAL_EVENT_TYPE
    assert request.role == "assistant"
    assert request.topics == []
    stored = json.loads(request.text)
    assert stored["schema"] == STRUCTURAL_SCHEMA
    assert stored["hierarchy_id"] == "hierarchy:abc"
    assert stored["relation_ids"] == [256, 300, 256]
    assert stored["trail_symbols"] == 1024


def test_structural_route_rejects_semantically_invalid_relation_symbol():
    sink = FakeStructuralSink()
    body = payload()
    body["relation_ids"] = [42]
    response = app_for(sink).post("/api/v1/structural/events", headers=HEADERS, json=body)
    assert response.status_code == 409
    assert "relation symbols" in response.json()["detail"]
    assert sink.requests == []


def test_structural_route_is_fail_closed_without_native_journal():
    response = app_for(None).post("/api/v1/structural/events", headers=HEADERS, json=payload())
    assert response.status_code == 503
    assert "unavailable" in response.json()["detail"]
