from fastapi.testclient import TestClient

from memoria_resolutiva.llm_adapter import MockLLMAdapter
from memoria_resolutiva.product_chat import ProductChatService
from memoria_resolutiva.product_http import create_app
from memoria_resolutiva.product_identity import OrganizationIdentity
from memoria_resolutiva.product_service import EnterpriseMemoryService


def client(tmp_path, *, with_chat=False):
    service = EnterpriseMemoryService(OrganizationIdentity("org-a", "Org A"))
    chat_service = ProductChatService(service, MockLLMAdapter()) if with_chat else None
    app = create_app(service, api_key="secret", data_dir=tmp_path, chat_service=chat_service)
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
    assert stored.json()["version"] == 1

    resolved = c.post(
        "/api/v1/memories/resolve",
        headers=headers,
        json={"key": "customer.alpha.plan", "scope": {"application_id": "crm"}},
    )
    body = resolved.json()
    assert body["hit"] is True
    assert body["record"]["knowledge_id"] == "customer-1"
    assert body["record"]["payload"] == {"plan": "pro"}
    assert body["record"]["version"] == 1


def test_update_creates_version_and_old_version_remains_resolvable(tmp_path):
    c = client(tmp_path)
    headers = {"X-Memoria-Key": "secret"}
    c.post(
        "/api/v1/memories",
        headers=headers,
        json={"knowledge_id": "k", "key": "profile", "payload": {"plan": "basic"}},
    )
    updated = c.put(
        "/api/v1/memories/profile",
        headers=headers,
        json={"payload": {"plan": "pro"}},
    )
    assert updated.status_code == 200
    assert updated.json()["version"] == 2

    latest = c.post(
        "/api/v1/memories/resolve",
        headers=headers,
        json={"key": "profile"},
    ).json()
    old = c.post(
        "/api/v1/memories/resolve",
        headers=headers,
        json={"key": "profile", "version": 1},
    ).json()
    assert latest["record"]["payload"] == {"plan": "pro"}
    assert old["record"]["payload"] == {"plan": "basic"}


def test_revoke_hides_memory_and_audit_can_read_it(tmp_path):
    c = client(tmp_path)
    headers = {"X-Memoria-Key": "secret"}
    c.post(
        "/api/v1/memories",
        headers=headers,
        json={"knowledge_id": "k", "key": "revocable", "payload": "secret"},
    )
    revoked = c.delete("/api/v1/memories/revocable", headers=headers)
    assert revoked.status_code == 200
    assert revoked.json()["revoked"] is True

    hidden = c.post(
        "/api/v1/memories/resolve",
        headers=headers,
        json={"key": "revocable"},
    ).json()
    audit = c.post(
        "/api/v1/memories/resolve",
        headers=headers,
        json={"key": "revocable", "include_revoked": True},
    ).json()
    assert hidden == {"hit": False, "record": None}
    assert audit["hit"] is True
    assert audit["record"]["revoked"] is True


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


def test_chat_is_unavailable_without_adapter(tmp_path):
    c = client(tmp_path)
    r = c.post(
        "/api/v1/chat",
        headers={"X-Memoria-Key": "secret"},
        json={"message": "hello"},
    )
    assert r.status_code == 503


def test_memoria_chat_returns_measured_hit_metrics(tmp_path):
    c = client(tmp_path, with_chat=True)
    headers = {"X-Memoria-Key": "secret"}
    c.post(
        "/api/v1/memories",
        headers=headers,
        json={"knowledge_id": "plan", "key": "customer.plan", "payload": "plan is pro"},
    )
    r = c.post(
        "/api/v1/chat",
        headers=headers,
        json={"message": "what is the plan?", "mode": "memoria", "memory_keys": ["customer.plan", "missing"]},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["metrics"]["memory_hits"] == 1
    assert body["metrics"]["memory_misses"] == 1
    assert body["metrics"]["provider"] == "mock"


def test_compare_reports_observed_token_reduction(tmp_path):
    c = client(tmp_path, with_chat=True)
    headers = {"X-Memoria-Key": "secret"}
    c.post(
        "/api/v1/memories",
        headers=headers,
        json={"knowledge_id": "plan", "key": "customer.plan", "payload": "plan is pro"},
    )
    r = c.post(
        "/api/v1/chat/compare",
        headers=headers,
        json={
            "message": "what is the plan?",
            "baseline_context": ["plan is pro", "irrelevant history " * 20],
            "memory_keys": ["customer.plan"],
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["baseline"]["metrics"]["input_tokens"] > body["memoria"]["metrics"]["input_tokens"]
    assert body["token_reduction"] > 0
