from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from memoria_resolutiva.llm_adapter import LLMAdapterError
from memoria_resolutiva.product_applications import ApplicationRegistry
from memoria_resolutiva.product_backup import create_backup, restore_backup, validate_backup
from memoria_resolutiva.product_chat import ProductChatService
from memoria_resolutiva.product_http import create_app
from memoria_resolutiva.product_identity import OrganizationIdentity
from memoria_resolutiva.product_persistence import ProductSnapshotPersistence, PersistentEnterpriseMemoryService


class FailingAdapter:
    provider_name = "failing"
    model_name = "unavailable"

    def generate(self, *, message: str, context):
        raise LLMAdapterError("provider unavailable")


def _service(root: Path) -> PersistentEnterpriseMemoryService:
    return PersistentEnterpriseMemoryService(
        OrganizationIdentity("acceptance-org"),
        persistence=ProductSnapshotPersistence(root / "persistence", backend="sqlite", allow_fallback=False),
    )


def test_corrupted_portable_snapshot_does_not_override_valid_durable_backend(tmp_path):
    root = tmp_path / "product"
    service = _service(root)
    app = create_app(service, api_key="admin", data_dir=root)
    client = TestClient(app)
    headers = {"X-Memoria-Key": "admin"}
    stored = client.post("/api/v1/memories", headers=headers, json={
        "knowledge_id": "k1", "key": "customer.plan", "payload": {"plan": "pro"}
    })
    assert stored.status_code == 201

    # Corrupt only the portable copy. The durable SQLite blob remains valid.
    (root / "memory.snapshot").write_bytes(b"corrupted-portable-copy")
    loaded = PersistentEnterpriseMemoryService.load(
        root,
        persistence=ProductSnapshotPersistence(root / "persistence", backend="sqlite", allow_fallback=False),
    )
    app2 = create_app(loaded, api_key="admin", data_dir=root)
    recovered = TestClient(app2).post(
        "/api/v1/memories/resolve", headers=headers, json={"key": "customer.plan"}
    )
    assert recovered.status_code == 200
    assert recovered.json()["hit"] is True
    assert recovered.json()["record"]["payload"] == {"plan": "pro"}
    assert loaded.statistics["portable_snapshot_fallback"] is False


def test_portable_backup_restore_rehydrates_new_local_backend(tmp_path):
    source = tmp_path / "source"
    service = _service(source)
    app = create_app(service, api_key="admin", data_dir=source)
    headers = {"X-Memoria-Key": "admin"}
    client = TestClient(app)
    assert client.post("/api/v1/memories", headers=headers, json={
        "knowledge_id": "k1", "key": "device.mode", "payload": "active"
    }).status_code == 201

    backup = create_backup(source, tmp_path / "portable.zip")
    assert validate_backup(backup).valid

    restored_root = tmp_path / "restored"
    restored_plain = restore_backup(backup, restored_root, expected_organization_id="acceptance-org")
    assert restored_plain.organization.organization_id == "acceptance-org"

    new_persistence = ProductSnapshotPersistence(
        restored_root / "persistence", backend="sqlite", allow_fallback=False
    )
    rehydrated = PersistentEnterpriseMemoryService.load(restored_root, persistence=new_persistence)
    # First load falls back to the validated portable snapshot because the new
    # machine-local backend has no blob yet.
    assert rehydrated.statistics["portable_snapshot_fallback"] is True
    rehydrated.save(restored_root)
    assert rehydrated.statistics["persistence_backend"] == "sqlite"

    loaded_again = PersistentEnterpriseMemoryService.load(
        restored_root,
        persistence=ProductSnapshotPersistence(restored_root / "persistence", backend="sqlite", allow_fallback=False),
    )
    assert loaded_again.statistics["portable_snapshot_fallback"] is False


def test_application_credentials_are_isolated_by_application_scope(tmp_path):
    root = tmp_path / "product"
    service = _service(root)
    registry = ApplicationRegistry("acceptance-org", root / "applications.json")
    app_a = registry.create("app-a")
    app_b = registry.create("app-b")
    app = create_app(service, api_key="admin", data_dir=root, application_registry=registry)
    client = TestClient(app)

    headers_a = {"X-Memoria-Key": app_a.token}
    headers_b = {"X-Memoria-Key": app_b.token}
    assert client.post("/api/v1/memories", headers=headers_a, json={
        "knowledge_id": "shared-id", "key": "shared.key", "payload": "A"
    }).status_code == 201
    assert client.post("/api/v1/memories", headers=headers_b, json={
        "knowledge_id": "shared-id", "key": "shared.key", "payload": "B"
    }).status_code == 201

    ra = client.post("/api/v1/memories/resolve", headers=headers_a, json={"key": "shared.key"})
    rb = client.post("/api/v1/memories/resolve", headers=headers_b, json={"key": "shared.key"})
    assert ra.json()["record"]["payload"] == "A"
    assert rb.json()["record"]["payload"] == "B"

    forbidden = client.post("/api/v1/memories/resolve", headers=headers_a, json={
        "key": "shared.key", "scope": {"application_id": "app-b"}
    })
    assert forbidden.status_code == 403


def test_llm_provider_failure_is_reported_without_losing_memory_state(tmp_path):
    root = tmp_path / "product"
    service = _service(root)
    chat = ProductChatService(service, FailingAdapter())
    app = create_app(service, api_key="admin", data_dir=root, chat_service=chat)
    client = TestClient(app)
    headers = {"X-Memoria-Key": "admin"}

    assert client.post("/api/v1/memories", headers=headers, json={
        "knowledge_id": "k1", "key": "customer.plan", "payload": "pro"
    }).status_code == 201
    failed = client.post("/api/v1/chat", headers=headers, json={
        "message": "what is the plan?", "mode": "memoria", "memory_keys": ["customer.plan"]
    })
    assert failed.status_code == 503
    assert failed.json()["detail"] == "LLM provider unavailable"

    recovered = client.post("/api/v1/memories/resolve", headers=headers, json={"key": "customer.plan"})
    assert recovered.status_code == 200
    assert recovered.json()["hit"] is True
    assert recovered.json()["record"]["payload"] == "pro"
