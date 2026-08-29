from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from memoria_resolutiva.native_episodic import NativeEpisodicService
from memoria_resolutiva.product_evidence import ProductEvidenceService
from memoria_resolutiva.product_episodic import ProductEpisodicService, attach_episodic_routes


HEADERS = {"X-Memoria-Key": "secret"}


def _native_library() -> Path:
    value = os.environ.get("MEMORIA_NATIVE_LIB")
    if not value:
        pytest.skip("MEMORIA_NATIVE_LIB is not set; server/native parity runs in the host ABI workflow")
    path = Path(value)
    assert path.is_file()
    return path


def _app(service) -> TestClient:
    app = FastAPI()
    attach_episodic_routes(app, api_key="secret", service=service)
    return TestClient(app)


def _python_service(root: Path) -> ProductEpisodicService:
    evidence = ProductEvidenceService.open(root / "python-evidence", backend="sqlite", allow_fallback=False)
    return ProductEpisodicService(evidence)


def _native_service(root: Path, library: Path) -> NativeEpisodicService:
    return NativeEpisodicService(
        library_path=library,
        data_dir=root / "native-state",
        organization_id="server-parity-org",
    )


def _store_fixture(client: TestClient) -> None:
    rows = (
        {
            "episode_id": "s1-old",
            "role": "assistant",
            "text": "atlas status report session one old",
            "session_id": "s1",
            "order": 10,
            "timestamp": "2026-08-01T10:00:00Z",
            "event_type": "report",
            "topics": ["atlas", "status"],
        },
        {
            "episode_id": "s2",
            "role": "assistant",
            "text": "atlas status report session two",
            "session_id": "s2",
            "order": 20,
            "timestamp": "2026-08-01T10:20:00Z",
            "event_type": "report",
            "topics": ["status", "atlas"],
        },
        {
            "episode_id": "s1-new",
            "role": "assistant",
            "text": "atlas status report session one new",
            "session_id": "s1",
            "order": 15,
            "timestamp": "2026-08-01T10:15:00Z",
            "event_type": "report",
            "topics": ["atlas", "status"],
        },
        {
            "episode_id": "default",
            "role": "user",
            "text": "atlas status report default session",
            "order": 30,
            "timestamp": "2026-08-01T10:30:00Z",
            "event_type": "report",
            "topics": ["atlas", "status"],
        },
    )
    for payload in rows:
        response = client.post("/api/v1/episodes", json=payload, headers=HEADERS)
        assert response.status_code == 201, response.text


def _recall(client: TestClient, *, session_id: str | None, role: str | None = None) -> dict:
    payload = {
        "query": "latest atlas status report",
        "event_type": "report",
        "topics": ["atlas", "status"],
    }
    if session_id is not None:
        payload["session_id"] = session_id
    if role is not None:
        payload["role"] = role
    response = client.post("/api/v1/episodes/recall", json=payload, headers=HEADERS)
    assert response.status_code == 200, response.text
    return response.json()


def _snapshot(client: TestClient) -> dict[str, dict]:
    return {
        "s1": _recall(client, session_id="s1", role="assistant"),
        "s2": _recall(client, session_id="s2", role="assistant"),
        "default": _recall(client, session_id=None, role="user"),
        "missing": _recall(client, session_id="missing", role="assistant"),
    }


def test_native_episodic_service_matches_python_http_contract_and_restart(tmp_path: Path):
    library = _native_library()

    python_service = _python_service(tmp_path)
    native_service = _native_service(tmp_path, library)
    try:
        python_client = _app(python_service)
        native_client = _app(native_service)
        _store_fixture(python_client)
        _store_fixture(native_client)
        python_before = _snapshot(python_client)
        native_before = _snapshot(native_client)
        assert native_before == python_before
        assert python_before["s1"]["episode_ids"] == ["s1-new"]
        assert python_before["s2"]["episode_ids"] == ["s2"]
        assert python_before["default"]["episode_ids"] == ["default"]
        assert python_before["missing"]["status"] == "UNRESOLVED"
        native_service.flush()
    finally:
        native_service.close()

    python_after = _snapshot(_app(_python_service(tmp_path)))
    reopened_native = _native_service(tmp_path, library)
    try:
        native_after = _snapshot(_app(reopened_native))
        assert python_after == python_before
        assert native_after == native_before
        assert native_after == python_after
    finally:
        reopened_native.close()


def test_native_episodic_service_refuses_to_drop_parent_lineage(tmp_path: Path):
    service = _native_service(tmp_path, _native_library())
    try:
        response = _app(service).post(
            "/api/v1/episodes",
            json={
                "episode_id": "derived",
                "role": "assistant",
                "text": "derived episode",
                "session_id": "s",
                "order": 1,
                "parent_memory_ids": ["root-memory"],
            },
            headers=HEADERS,
        )
        assert response.status_code == 409
        assert "parent lineage" in response.json()["detail"]
    finally:
        service.close()
