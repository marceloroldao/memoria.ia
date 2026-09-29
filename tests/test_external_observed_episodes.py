from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json

from fastapi import FastAPI
from fastapi.testclient import TestClient

from memoria_resolutiva.external_episode_contract import (
    FORMAT, PROVENANCE, attach_external_episode_routes, canonical,
)
from memoria_resolutiva.product_evidence import ProductEvidenceService

HEADERS = {"X-Memoria-Key": "secret"}


def _client(root):
    evidence = ProductEvidenceService.open(root, backend="sqlite", allow_fallback=False)
    app = FastAPI()
    attach_external_episode_routes(app, api_key="secret", evidence=evidence)
    return TestClient(app), evidence


def _payload(*, world_id="nov-live-autonomous-001", episode_id="plan:plan_1", tick=30):
    episode = {
        "episode_schema": "npc_episode_v1",
        "episode_id": episode_id,
        "npc_id": "nov",
        "logical_tick": tick,
        "need": "curiosity",
        "target_entity_id": "ancient_tree",
        "strategy_id": "via_shelter:shelter_marker",
        "context": {
            "period": "night", "weather": "clear", "region_id": "clearing",
            "danger_level": 0.35,
        },
        "outcome": {
            "satisfaction": 0.3, "observed_risk": 0.35, "elapsed_ticks": 3,
            "preemptions": 0, "replans": 0,
        },
    }
    return {
        "schema": FORMAT, "source_system": "live.infinita", "world_id": world_id,
        "episode": episode, "episode_sha256": sha256(canonical(episode)).hexdigest(),
    }


def test_external_observation_is_not_user_or_assistant_episode_and_survives_restart(tmp_path):
    root = tmp_path / "evidence"
    client, service = _client(root)
    payload = _payload()
    assert client.post("/api/v1/external/episodes", json=payload).status_code == 401
    response = client.post("/api/v1/external/episodes", json=payload, headers=HEADERS)
    assert response.status_code == 201, response.text
    receipt = response.json()
    assert receipt["ack"] is True and receipt["stored"] is True
    assert receipt["episode_sha256"] == payload["episode_sha256"]
    assert receipt["persistence"]["backend"] == "sqlite"
    assert receipt["persistence"]["state_id"]
    assert receipt["persistence"]["sha256"]
    assert receipt["world_mutated"] is False
    assert receipt["selection_authority"] is False
    rows = service.core.evidence_history(namespace="live:nov-live-autonomous-001")
    assert len(rows) == 1
    assert rows[0].provenance == PROVENANCE
    assert rows[0].predicate == "observed_experience"
    assert rows[0].epoch == 30
    stored_payload = json.loads(rows[0].source_text)
    assert stored_payload["episode"] == payload["episode"]
    assert stored_payload["schema"] == FORMAT
    assert "role" not in stored_payload and "user" not in stored_payload
    assert "assistant" not in stored_payload
    assert service.receipt is not None

    same = client.post("/api/v1/external/episodes", json=payload, headers=HEADERS)
    assert same.status_code == 201 and same.json()["stored"] is False
    assert same.json()["evidence_id"] == receipt["evidence_id"]
    assert len(service.core.evidence_history(namespace="live:nov-live-autonomous-001")) == 1

    reopened, reopened_evidence = _client(root)
    again = reopened.post("/api/v1/external/episodes", json=payload, headers=HEADERS)
    assert again.status_code == 201 and again.json()["stored"] is False
    assert again.json()["evidence_id"] == receipt["evidence_id"]
    assert len(reopened_evidence.core.evidence_history(namespace="live:nov-live-autonomous-001")) == 1


def test_changed_observation_same_source_episode_id_conflicts(tmp_path):
    client, service = _client(tmp_path / "evidence")
    first = _payload()
    assert client.post("/api/v1/external/episodes", json=first, headers=HEADERS).status_code == 201
    changed = deepcopy(first)
    changed["episode"]["outcome"]["satisfaction"] = 0.9
    changed["episode_sha256"] = sha256(canonical(changed["episode"])).hexdigest()
    response = client.post("/api/v1/external/episodes", json=changed, headers=HEADERS)
    assert response.status_code == 409
    assert len(service.core.evidence_history(namespace="live:nov-live-autonomous-001")) == 1
    second_world = _payload(world_id="another-world")
    result = client.post("/api/v1/external/episodes", json=second_world, headers=HEADERS)
    assert result.status_code == 201 and result.json()["stored"] is True
    assert result.json()["evidence_id"] != client.post(
        "/api/v1/external/episodes", json=first, headers=HEADERS
    ).json()["evidence_id"]


def test_rejects_invented_fields_bad_digest_or_wrong_origin(tmp_path):
    client, service = _client(tmp_path / "evidence")
    bad = _payload()
    bad["episode"]["source"] = {"role": "assistant", "text": "fabricated"}
    assert client.post("/api/v1/external/episodes", json=bad, headers=HEADERS).status_code == 422
    assert client.post("/api/v1/external/episodes", json={**_payload(), "episode_sha256": "0"*64},
                       headers=HEADERS).status_code == 422
    assert client.post("/api/v1/external/episodes", json={**_payload(), "source_system": "chatgpt"},
                       headers=HEADERS).status_code == 422
    assert client.post("/api/v1/external/episodes", json={**_payload(), "role": "user"},
                       headers=HEADERS).status_code == 422
    assert not service.core.evidence_history(namespace="live:nov-live-autonomous-001")
