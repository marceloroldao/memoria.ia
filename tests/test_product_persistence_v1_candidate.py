from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from memoria_resolutiva.bdr_store import native_bdr_available
from memoria_resolutiva.llm_adapter import MockLLMAdapter
from memoria_resolutiva.product_backup import create_backup, restore_backup
from memoria_resolutiva.product_chat import ProductChatService
from memoria_resolutiva.product_http import create_app
from memoria_resolutiva.product_identity import MemoryScope, OrganizationIdentity
from memoria_resolutiva.product_persistence import (
    PersistentEnterpriseMemoryService,
    ProductSnapshotPersistence,
)


def _seed(service: PersistentEnterpriseMemoryService):
    scope = MemoryScope("org-a")
    service.remember(
        scope,
        "operator-name",
        "Marcelo",
        ("profile", "operator", "name"),
        provenance="test",
    )
    return scope


def test_product_restart_prefers_sqlite_durable_snapshot(tmp_path):
    state = tmp_path / "state"
    persistence = ProductSnapshotPersistence(
        tmp_path / "durable",
        backend="sqlite",
        allow_fallback=False,
    )
    service = PersistentEnterpriseMemoryService(
        OrganizationIdentity("org-a", "Organization A"),
        persistence=persistence,
    )
    scope = _seed(service)
    service.save(state)

    manifest = json.loads((state / "enterprise.manifest.json").read_text("utf-8"))
    assert "persistence" in json.loads(manifest["payload"])

    # Break only the portable copy. A normal restart must still recover from
    # the selected durable backend.
    (state / "memory.snapshot").write_bytes(b"portable-copy-intentionally-corrupted")

    reloaded = PersistentEnterpriseMemoryService.load(
        state,
        persistence=ProductSnapshotPersistence(
            tmp_path / "durable",
            backend="sqlite",
            allow_fallback=False,
        ),
    )
    record = reloaded.recall(scope, ("profile", "operator", "name"))
    assert record is not None
    assert record.payload == "Marcelo"
    assert reloaded.statistics["persistence_backend"] == "sqlite"
    assert reloaded.statistics["portable_snapshot_fallback"] is False


def test_product_restore_can_fall_back_to_matching_portable_snapshot(tmp_path):
    state = tmp_path / "state"
    durable = tmp_path / "durable"
    persistence = ProductSnapshotPersistence(durable, backend="sqlite", allow_fallback=False)
    service = PersistentEnterpriseMemoryService(
        OrganizationIdentity("org-a"),
        persistence=persistence,
    )
    scope = _seed(service)
    service.save(state)

    # Simulate a portable backup restored without its local persistence DB.
    database = durable / "memoria.sqlite3"
    assert database.exists()
    database.unlink()

    reloaded = PersistentEnterpriseMemoryService.load(
        state,
        persistence=ProductSnapshotPersistence(durable, backend="sqlite", allow_fallback=False),
    )
    record = reloaded.recall(scope, ("profile", "operator", "name"))
    assert record is not None
    assert record.payload == "Marcelo"
    assert reloaded.statistics["portable_snapshot_fallback"] is True


def test_product_http_store_restart_resolve_and_chat_on_sqlite(tmp_path):
    state = tmp_path / "state"
    durable = tmp_path / "durable"
    service = PersistentEnterpriseMemoryService(
        OrganizationIdentity("org-a", "Org A"),
        persistence=ProductSnapshotPersistence(durable, backend="sqlite", allow_fallback=False),
    )
    app = create_app(
        service,
        api_key="secret",
        data_dir=state,
        chat_service=ProductChatService(service, MockLLMAdapter()),
    )
    client = TestClient(app)
    headers = {"X-Memoria-Key": "secret"}

    stored = client.post(
        "/api/v1/memories",
        headers=headers,
        json={
            "knowledge_id": "plan",
            "key": "customer.plan",
            "payload": "plan is pro",
        },
    )
    assert stored.status_code == 201

    reloaded = PersistentEnterpriseMemoryService.load(
        state,
        persistence=ProductSnapshotPersistence(durable, backend="sqlite", allow_fallback=False),
    )
    restarted = TestClient(
        create_app(
            reloaded,
            api_key="secret",
            data_dir=state,
            chat_service=ProductChatService(reloaded, MockLLMAdapter()),
        )
    )

    resolved = restarted.post(
        "/api/v1/memories/resolve",
        headers=headers,
        json={"key": "customer.plan"},
    )
    assert resolved.status_code == 200
    assert resolved.json()["hit"] is True
    assert resolved.json()["record"]["payload"] == "plan is pro"

    chat = restarted.post(
        "/api/v1/chat",
        headers=headers,
        json={
            "message": "what is the plan?",
            "mode": "memoria",
            "memory_keys": ["customer.plan", "missing"],
        },
    )
    assert chat.status_code == 200
    metrics = chat.json()["metrics"]
    assert metrics["memory_hits"] == 1
    assert metrics["memory_misses"] == 1
    assert metrics["provider"] == "mock"
    assert metrics["retrieved_context_chars"] > 0
    assert metrics["input_tokens"] > 0
    assert reloaded.statistics["persistence_backend"] == "sqlite"


def test_portable_backup_restore_then_product_rehydrates_backend(tmp_path):
    source = tmp_path / "source"
    source_durable = tmp_path / "source-durable"
    service = PersistentEnterpriseMemoryService(
        OrganizationIdentity("org-a"),
        persistence=ProductSnapshotPersistence(source_durable, backend="sqlite", allow_fallback=False),
    )
    scope = _seed(service)
    service.save(source)

    backup = create_backup(source, tmp_path / "portable.zip")
    restored = tmp_path / "restored"
    restore_backup(backup, restored, expected_organization_id="org-a")

    # The portable backup intentionally does not carry the machine-local BDR/
    # SQLite persistence directory. First boot therefore verifies and consumes
    # memory.snapshot, then the next save rehydrates the selected backend.
    restored_durable = tmp_path / "restored-durable"
    reloaded = PersistentEnterpriseMemoryService.load(
        restored,
        persistence=ProductSnapshotPersistence(restored_durable, backend="sqlite", allow_fallback=False),
    )
    assert reloaded.statistics["portable_snapshot_fallback"] is True
    record = reloaded.recall(scope, ("profile", "operator", "name"))
    assert record is not None and record.payload == "Marcelo"

    reloaded.save(restored)
    assert (restored_durable / "memoria.sqlite3").exists()

    second_boot = PersistentEnterpriseMemoryService.load(
        restored,
        persistence=ProductSnapshotPersistence(restored_durable, backend="sqlite", allow_fallback=False),
    )
    assert second_boot.statistics["persistence_backend"] == "sqlite"
    assert second_boot.statistics["portable_snapshot_fallback"] is False
    assert second_boot.recall(scope, ("profile", "operator", "name")).payload == "Marcelo"


@pytest.mark.skipif(not native_bdr_available(), reason="native BDR extension not built")
def test_product_restart_prefers_native_bdr_snapshot(tmp_path):
    state = tmp_path / "state"
    durable = tmp_path / "durable-bdr"
    service = PersistentEnterpriseMemoryService(
        OrganizationIdentity("org-a"),
        persistence=ProductSnapshotPersistence(durable, backend="bdr", allow_fallback=False),
    )
    scope = _seed(service)
    service.save(state)

    (state / "memory.snapshot").write_bytes(b"portable-copy-intentionally-corrupted")

    reloaded = PersistentEnterpriseMemoryService.load(
        state,
        persistence=ProductSnapshotPersistence(durable, backend="bdr", allow_fallback=False),
    )
    record = reloaded.recall(scope, ("profile", "operator", "name"))
    assert record is not None
    assert record.payload == "Marcelo"
    assert reloaded.statistics["persistence_backend"] == "bdr"
    assert reloaded.statistics["portable_snapshot_fallback"] is False
