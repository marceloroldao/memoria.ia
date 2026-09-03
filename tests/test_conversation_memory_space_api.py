from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from memoria_resolutiva.conversation_contract import attach_conversation_routes
from memoria_resolutiva.product_conversation import ConversationSemanticService
from memoria_resolutiva.product_evidence import ProductEvidenceService


def _service(root: Path) -> ConversationSemanticService:
    return ConversationSemanticService(ProductEvidenceService.open(root, backend="sqlite", allow_fallback=True))


def _client(service: ConversationSemanticService) -> TestClient:
    app = FastAPI()
    attach_conversation_routes(app, api_key="secret", service=service)
    return TestClient(app)


def _post(client: TestClient, path: str, payload: dict):
    response = client.post(path, headers={"X-Memoria-Key": "secret"}, json=payload)
    assert response.status_code == 200, response.text
    return response.json()


def test_http_provenance_exposes_direct_and_ultimate_memory_spaces(tmp_path: Path):
    root = tmp_path / "evidence"
    service = _service(root)
    client = _client(service)

    user = _post(
        client,
        "/api/v1/conversation/ingest",
        {"role": "user", "text": "meu carro é Jeep", "session_id": "s", "order": 1},
    )
    user_turn = user["stored_memory_ids"][0]

    _post(
        client,
        "/api/v1/conversation/ingest",
        {
            "role": "assistant",
            "text": "seu carro é Jeep",
            "session_id": "s",
            "order": 2,
            "parent_memory_ids": [user_turn],
        },
    )

    resolved = _post(
        client,
        "/api/v1/conversation/resolve",
        {"query": "qual carro?", "session_id": "s"},
    )
    assert resolved["status"] == "HIT"
    assert resolved["provenance"]
    row = resolved["provenance"][0]
    assert row["memory_space"] in {"factual", "generative"}
    assert row["ultimate_memory_space"] == "factual"


def test_generated_only_memory_remains_unresolved_after_restart(tmp_path: Path):
    root = tmp_path / "evidence"
    first = _service(root)
    first.ingest(role="assistant", text="meu carro é Renegade", session_id="s", order=1)
    assert first.resolve(query="qual carro?", session_id="s").status == "UNRESOLVED"

    restarted = _service(root)
    assert restarted.resolve(query="qual carro?", session_id="s").status == "UNRESOLVED"

    client = _client(restarted)
    unresolved = _post(
        client,
        "/api/v1/conversation/resolve",
        {"query": "qual carro?", "session_id": "s"},
    )
    assert unresolved["status"] == "UNRESOLVED"
    assert unresolved["provenance"] == []
