from fastapi.testclient import TestClient

from memoria_resolutiva.product_http import create_app
from memoria_resolutiva.product_identity import OrganizationIdentity
from memoria_resolutiva.product_service import EnterpriseMemoryService


def client(tmp_path):
    service = EnterpriseMemoryService(OrganizationIdentity("org-a", "Org A"))
    app = create_app(service, api_key="secret", data_dir=tmp_path)
    return TestClient(app)


def test_health_is_public(tmp_path):
    c = client(tmp_path)
    r = c.get("/api/v1/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_protected_routes_require_key(tmp_path):
    c = client(tmp_path)
    r = c.get("/api/v1/admin/status")
    assert r.status_code == 401


def test_store_and_resolve_memory(tmp_path):
    c = client(tmp_path)
    headers = {"X-Memoria-Key": "secret"}
    stored = c.post(
        "/api/v1/memories",
        headers=headers,
        json={
            "knowledge_id": "customer-1",
            "key": "customer.alpha.plan",
            "payload": {"plan": "pro"},
            "scope": {"application_id": "crm"},
        },
    )
    assert stored.status_code == 201

    resolved = c.post(
        "/api/v1/memories/resolve",
        headers=headers,
        json={"key": "customer.alpha.plan", "scope": {"application_id": "crm"}},
    )
    body = resolved.json()
    assert body["hit"] is True
    assert body["record"]["knowledge_id"] == "customer-1"
    assert body["record"]["payload"] == {"plan": "pro"}


def test_scope_isolation_at_http_boundary(tmp_path):
    c = client(tmp_path)
    headers = {"X-Memoria-Key": "secret"}
    c.post(
        "/api/v1/memories",
        headers=headers,
        json={
            "knowledge_id": "k1",
            "key": "same-key",
            "payload": "app-one",
            "scope": {"application_id": "one"},
        },
    )
    miss = c.post(
        "/api/v1/memories/resolve",
        headers=headers,
        json={"key": "same-key", "scope": {"application_id": "two"}},
    )
    assert miss.json() == {"hit": False, "record": None}


def test_store_persists_to_disk(tmp_path):
    c = client(tmp_path)
    headers = {"X-Memoria-Key": "secret"}
    c.post(
        "/api/v1/memories",
        headers=headers,
        json={"knowledge_id": "k1", "key": "persist", "payload": "yes"},
    )
    assert (tmp_path / "memory.snapshot").exists()
    assert (tmp_path / "enterprise.manifest.json").exists()
