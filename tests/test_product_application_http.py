from fastapi.testclient import TestClient

from memoria_resolutiva.llm_adapter import MockLLMAdapter
from memoria_resolutiva.product_applications import ApplicationRegistry
from memoria_resolutiva.product_chat import ProductChatService
from memoria_resolutiva.product_http import create_app
from memoria_resolutiva.product_identity import OrganizationIdentity
from memoria_resolutiva.product_service import EnterpriseMemoryService


def build(tmp_path):
    service = EnterpriseMemoryService(OrganizationIdentity("org-a", "Org A"))
    registry = ApplicationRegistry("org-a", tmp_path / "applications.json")
    app = create_app(
        service,
        api_key="admin-secret",
        data_dir=tmp_path,
        chat_service=ProductChatService(service, MockLLMAdapter()),
        application_registry=registry,
    )
    return TestClient(app), registry


def admin_headers():
    return {"X-Memoria-Key": "admin-secret"}


def test_admin_creates_application_and_plaintext_credential_is_returned_once(tmp_path):
    client, _ = build(tmp_path)
    response = client.post(
        "/api/v1/admin/applications",
        headers=admin_headers(),
        json={"application_id": "crm", "display_name": "CRM", "scopes": ["memory.read", "memory.write"]},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["application"]["application_id"] == "crm"
    assert body["credential"].startswith("mem_app_")

    listing = client.get("/api/v1/admin/applications", headers=admin_headers()).json()
    assert listing["applications"][0]["application_id"] == "crm"
    assert "credential" not in listing["applications"][0]


def test_app_credential_is_bound_to_application_scope(tmp_path):
    client, registry = build(tmp_path)
    app_one = registry.create("one", scopes={"memory.read", "memory.write"})
    app_two = registry.create("two", scopes={"memory.read", "memory.write"})

    one_headers = {"X-Memoria-Key": app_one.token}
    two_headers = {"X-Memoria-Key": app_two.token}

    stored = client.post(
        "/api/v1/memories",
        headers=one_headers,
        json={"knowledge_id": "k", "key": "private", "payload": "app-one"},
    )
    assert stored.status_code == 201

    own = client.post(
        "/api/v1/memories/resolve",
        headers=one_headers,
        json={"key": "private"},
    )
    assert own.json()["hit"] is True
    assert own.json()["record"]["payload"] == "app-one"

    other = client.post(
        "/api/v1/memories/resolve",
        headers=two_headers,
        json={"key": "private"},
    )
    assert other.json() == {"hit": False, "record": None}

    impersonation = client.post(
        "/api/v1/memories/resolve",
        headers=two_headers,
        json={"key": "private", "scope": {"application_id": "one"}},
    )
    assert impersonation.status_code == 403


def test_missing_scope_is_forbidden(tmp_path):
    client, registry = build(tmp_path)
    readonly = registry.create("readonly", scopes={"memory.read"})
    headers = {"X-Memoria-Key": readonly.token}

    write = client.post(
        "/api/v1/memories",
        headers=headers,
        json={"knowledge_id": "k", "key": "x", "payload": "no"},
    )
    assert write.status_code == 403
    assert "memory.write" in write.json()["detail"]

    chat = client.post(
        "/api/v1/chat",
        headers=headers,
        json={"message": "hello"},
    )
    assert chat.status_code == 403
    assert "chat.use" in chat.json()["detail"]


def test_application_cannot_use_admin_endpoints(tmp_path):
    client, registry = build(tmp_path)
    created = registry.create("crm")
    response = client.get(
        "/api/v1/admin/status",
        headers={"X-Memoria-Key": created.token},
    )
    assert response.status_code == 403


def test_revoked_application_token_stops_working(tmp_path):
    client, registry = build(tmp_path)
    created = registry.create("crm", scopes={"memory.read"})
    headers = {"X-Memoria-Key": created.token}
    before = client.post("/api/v1/memories/resolve", headers=headers, json={"key": "anything"})
    assert before.status_code == 200

    revoked = client.delete("/api/v1/admin/applications/crm", headers=admin_headers())
    assert revoked.status_code == 200
    assert revoked.json()["enabled"] is False

    after = client.post("/api/v1/memories/resolve", headers=headers, json={"key": "anything"})
    assert after.status_code == 401
