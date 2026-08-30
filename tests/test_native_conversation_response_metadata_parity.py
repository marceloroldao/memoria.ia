from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from memoria_resolutiva.native_conversation import NativeConversationService
from memoria_resolutiva.product_conversation import ConversationSemanticService, attach_conversation_routes
from memoria_resolutiva.product_evidence import ProductEvidenceService


HEADERS = {"X-Memoria-Key": "secret"}


def _native_library() -> Path:
    value = os.environ.get("MEMORIA_NATIVE_LIB")
    if not value:
        pytest.skip("MEMORIA_NATIVE_LIB is not set; response parity runs in the host ABI workflow")
    path = Path(value)
    assert path.is_file()
    return path


def _app(service) -> TestClient:
    app = FastAPI()
    attach_conversation_routes(app, api_key="secret", service=service)
    return TestClient(app)


def _python_service(root: Path) -> ConversationSemanticService:
    evidence = ProductEvidenceService.open(root / "python-evidence", backend="sqlite", allow_fallback=False)
    return ConversationSemanticService(evidence)


def _native_service(root: Path, library: Path) -> NativeConversationService:
    return NativeConversationService(
        library_path=library,
        data_dir=root / "native-state",
        organization_id="response-metadata-parity-org",
    )


def _post(client: TestClient, path: str, payload: dict) -> dict:
    response = client.post(path, json=payload, headers=HEADERS)
    assert response.status_code == 200, response.text
    return response.json()


def test_native_conversation_matches_full_supported_response_contract(tmp_path: Path):
    library = _native_library()
    python_service = _python_service(tmp_path)
    native_service = _native_service(tmp_path, library)
    try:
        python_client = _app(python_service)
        native_client = _app(native_service)

        factual = {
            "role": "user",
            "text": "sensor = active",
            "session_id": "fact",
            "order": 7,
            "timestamp": "2026-08-29T17:30:00Z",
        }
        python_ingest = _post(python_client, "/api/v1/conversation/ingest", factual)
        native_ingest = _post(native_client, "/api/v1/conversation/ingest", factual)
        assert native_ingest == python_ingest

        factual_query = {"query": "sensor active", "session_id": "fact"}
        python_resolve = _post(python_client, "/api/v1/conversation/resolve", factual_query)
        native_resolve = _post(native_client, "/api/v1/conversation/resolve", factual_query)
        assert native_resolve == python_resolve

        old_payload = {
            "role": "user",
            "text": "project = standby",
            "session_id": "fix",
            "order": 10,
            "timestamp": "2026-08-29T17:31:00Z",
        }
        old_python = _post(python_client, "/api/v1/conversation/ingest", old_payload)
        old_native = _post(native_client, "/api/v1/conversation/ingest", old_payload)
        assert old_native == old_python

        correction = {
            "role": "user",
            "text": "project = active",
            "session_id": "fix",
            "order": 11,
            "timestamp": "2026-08-29T17:32:00Z",
            "corrects_memory_ids": [old_python["stored_memory_ids"][0]],
        }
        assert _post(native_client, "/api/v1/conversation/ingest", correction) == _post(
            python_client, "/api/v1/conversation/ingest", correction
        )
        assert _post(
            native_client,
            "/api/v1/conversation/resolve",
            {"query": "project active", "session_id": "fix"},
        ) == _post(
            python_client,
            "/api/v1/conversation/resolve",
            {"query": "project active", "session_id": "fix"},
        )

        fallback = {
            "role": "user",
            "text": "cobalt context note for restart",
            "session_id": "fallback",
            "order": 20,
            "timestamp": "2026-08-29T17:33:00Z",
        }
        assert _post(native_client, "/api/v1/conversation/ingest", fallback) == _post(
            python_client, "/api/v1/conversation/ingest", fallback
        )
        assert _post(
            native_client,
            "/api/v1/conversation/resolve",
            {"query": "cobalt context", "session_id": "fallback"},
        ) == _post(
            python_client,
            "/api/v1/conversation/resolve",
            {"query": "cobalt context", "session_id": "fallback"},
        )

        unresolved = {"query": "never stored satellite", "session_id": "fact"}
        assert _post(native_client, "/api/v1/conversation/resolve", unresolved) == _post(
            python_client, "/api/v1/conversation/resolve", unresolved
        )

        native_service.flush()
    finally:
        native_service.close()

    reopened_native = _native_service(tmp_path, library)
    try:
        reopened_client = _app(reopened_native)
        python_client = _app(_python_service(tmp_path))
        assert _post(
            reopened_client,
            "/api/v1/conversation/resolve",
            {"query": "sensor active", "session_id": "fact"},
        ) == _post(
            python_client,
            "/api/v1/conversation/resolve",
            {"query": "sensor active", "session_id": "fact"},
        )
    finally:
        reopened_native.close()
