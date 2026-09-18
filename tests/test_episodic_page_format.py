from fastapi import FastAPI
from fastapi.testclient import TestClient

from memoria_resolutiva.episodic_contract import attach_episodic_routes


class FakeService:
    def page(self, *, offset=0, limit=512):
        total = 6000
        rows = [{"episode_id": f"ep-{i}"} for i in range(offset, min(total, offset + limit))]
        return {
            "schema": "memoria-episode-page/v1",
            "offset": offset,
            "limit": limit,
            "returned": len(rows),
            "total": total,
            "next_offset": offset + len(rows) if offset + len(rows) < total else None,
            "episodes": rows,
        }

    def format_store(self):
        return {"schema": "memoria-episode-format/v1", "formatted": True, "removed_turns": 10, "removed_episodes": 6000}

    def store(self, request):
        raise NotImplementedError

    def resolve(self, request):
        raise NotImplementedError

    def history(self, *, session_id=None, event_type=None, limit=1000):
        return []


def client():
    app = FastAPI()
    attach_episodic_routes(app, api_key="secret", service=FakeService())
    return TestClient(app)


def test_episode_page_exposes_offsets_beyond_5000():
    response = client().get("/api/v1/episodes/page?offset=5000&limit=700", headers={"X-Memoria-Key": "secret"})
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 6000
    assert body["offset"] == 5000
    assert body["returned"] == 700
    assert body["episodes"][0]["episode_id"] == "ep-5000"
    assert body["next_offset"] == 5700


def test_format_requires_exact_confirmation():
    bad = client().post("/api/v1/episodes/format", json={"confirm": "formatar"}, headers={"X-Memoria-Key": "secret"})
    assert bad.status_code == 400
    ok = client().post("/api/v1/episodes/format", json={"confirm": "FORMATAR"}, headers={"X-Memoria-Key": "secret"})
    assert ok.status_code == 200
    assert ok.json()["removed_episodes"] == 6000
