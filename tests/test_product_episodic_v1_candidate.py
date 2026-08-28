from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from memoria_resolutiva.product_evidence import ProductEvidenceService
from memoria_resolutiva.product_episodic import ProductEpisodicService, attach_episodic_routes


def _client(root: Path):
    evidence = ProductEvidenceService.open(root, backend="sqlite", allow_fallback=False)
    app = FastAPI()
    attach_episodic_routes(app, api_key="secret", service=ProductEpisodicService(evidence))
    return TestClient(app), evidence


def test_http_episode_store_recall_restart_same_result(tmp_path: Path):
    root = tmp_path / "evidence"
    client, evidence = _client(root)
    headers = {"X-Memoria-Key": "secret"}

    for payload in (
        {
            "episode_id": "e1", "role": "assistant", "text": "Resumo antigo do projeto Atlas",
            "session_id": "s", "order": 1, "event_type": "summary", "topics": ["atlas"],
        },
        {
            "episode_id": "e2", "role": "assistant", "text": "Resumo novo do projeto Atlas",
            "session_id": "s", "order": 9, "event_type": "summary", "topics": ["atlas"],
        },
    ):
        response = client.post("/api/v1/episodes", json=payload, headers=headers)
        assert response.status_code == 201

    recall = {
        "query": "qual foi o último resumo do Atlas?", "session_id": "s",
        "role": "assistant", "event_type": "summary", "topics": ["atlas"],
    }
    first = client.post("/api/v1/episodes/recall", json=recall, headers=headers)
    assert first.status_code == 200
    assert first.json()["status"] == "HIT"
    assert first.json()["episode_ids"] == ["e2"]
    assert first.json()["selected_context"] == "Resumo novo do projeto Atlas"
    assert first.json()["source_type"] == "assistant_generated"
    assert evidence.receipt is not None

    restarted, _ = _client(root)
    second = restarted.post("/api/v1/episodes/recall", json=recall, headers=headers)
    assert second.status_code == 200
    assert second.json() == first.json()


def test_http_episode_recall_abstains_on_temporal_ambiguity(tmp_path: Path):
    client, _ = _client(tmp_path / "evidence")
    headers = {"X-Memoria-Key": "secret"}
    for episode_id, text in (("a", "nota alfa"), ("b", "nota beta")):
        response = client.post("/api/v1/episodes", json={
            "episode_id": episode_id, "role": "assistant", "text": text,
            "session_id": "s", "order": 4, "event_type": "note",
        }, headers=headers)
        assert response.status_code == 201
    response = client.post("/api/v1/episodes/recall", json={
        "query": "qual foi a última nota?", "session_id": "s", "event_type": "note",
    }, headers=headers)
    assert response.status_code == 200
    assert response.json()["status"] == "UNRESOLVED"
