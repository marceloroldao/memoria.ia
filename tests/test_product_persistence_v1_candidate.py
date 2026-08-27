from __future__ import annotations

import json

import pytest

from memoria_resolutiva.bdr_store import native_bdr_available
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
