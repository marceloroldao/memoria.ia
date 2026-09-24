from fastapi import FastAPI
from fastapi.testclient import TestClient

from memoria_resolutiva.cognitive_contract_v2 import (
    StructuralCognitiveAbiServiceV2,
    attach_cognitive_routes_v2,
)
from memoria_resolutiva.resolutive_inference_v2 import ResolutiveInferenceEngineV2
from memoria_resolutiva.structural_trajectory_v2 import StructuralTrajectoryIndex


def _service():
    index = StructuralTrajectoryIndex()
    index.ingest_addresses(
        [1, 2, 3],
        hierarchy_id="abi-http",
        source_id="obs:a",
        sequence=1,
        observation_id="observation:a",
    )
    index.ingest_addresses(
        [1, 2, 3],
        hierarchy_id="abi-http",
        source_id="obs:b",
        sequence=2,
        observation_id="observation:b",
    )
    return StructuralCognitiveAbiServiceV2(ResolutiveInferenceEngineV2(index))


def test_r12_structural_cognitive_service_returns_server_memory_origin():
    result = _service().resolve(
        request_id="req:http:1",
        hierarchy_id="abi-http",
        addresses=[1, 2],
        session_id="session:http",
    )

    assert result.status == "resolved"
    assert result.resolved_state == (3,)
    assert result.origin.response_origin == "server-memory"
    assert result.origin.model_used is False
    assert result.origin.llm_calls == 0


def test_r12_http_transport_exposes_same_versioned_cognitive_envelope():
    app = FastAPI()
    attach_cognitive_routes_v2(app, api_key="secret", service=_service())
    client = TestClient(app)

    response = client.post(
        "/api/v1/cognitive/resolve",
        headers={"x-memoria-key": "secret"},
        json={
            "request_id": "req:http:2",
            "hierarchy_id": "abi-http",
            "addresses": [1, 2],
            "session_id": "session:http",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["schema"] == "memoria.ia-cognitive-abi-v2"
    assert payload["abi_version"] == 2
    assert payload["status"] == "resolved"
    assert payload["cognitive"]["resolved_state"] == [3]
    assert payload["origin"]["execution_plane"] == "server"
    assert payload["origin"]["memory_plane"] == "server"
    assert payload["origin"]["response_origin"] == "server-memory"
    assert payload["origin"]["model_used"] is False


def test_r12_http_transport_preserves_unresolved_and_requires_auth():
    app = FastAPI()
    attach_cognitive_routes_v2(app, api_key="secret", service=_service())
    client = TestClient(app)

    denied = client.post(
        "/api/v1/cognitive/resolve",
        json={"request_id": "req:denied", "hierarchy_id": "abi-http", "addresses": [99]},
    )
    assert denied.status_code == 401

    response = client.post(
        "/api/v1/cognitive/resolve",
        headers={"x-memoria-key": "secret"},
        json={"request_id": "req:http:3", "hierarchy_id": "abi-http", "addresses": [99]},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "unresolved"
    assert payload["origin"]["response_origin"] == "unresolved"
    assert payload["cognitive"]["resolved_state"] == []
