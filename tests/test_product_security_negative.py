from __future__ import annotations

from pathlib import Path
import zipfile

import pytest
from fastapi.testclient import TestClient

from memoria_resolutiva.product_admin_config import attach_configuration_routes
from memoria_resolutiva.product_applications import ApplicationRegistry
from memoria_resolutiva.product_backup import create_backup, restore_backup
from memoria_resolutiva.product_config import ProductConfigurationStore
from memoria_resolutiva.product_http import create_app
from memoria_resolutiva.product_identity import MemoryScope, OrganizationIdentity
from memoria_resolutiva.product_service import EnterpriseMemoryService


def _service(root: Path, organization_id: str, key: str, payload: object) -> EnterpriseMemoryService:
    service = EnterpriseMemoryService(OrganizationIdentity(organization_id))
    service.remember(MemoryScope(organization_id), "fact", payload, ("key", key))
    service.save(root)
    return service


def test_invalid_credentials_fail_closed_without_echoing_supplied_secret(tmp_path: Path):
    service = EnterpriseMemoryService(OrganizationIdentity("org-a"))
    client = TestClient(create_app(service, api_key="admin-secret", data_dir=tmp_path))
    supplied = "attacker-controlled-secret"

    response = client.post(
        "/api/v1/memories/resolve",
        headers={"X-Memoria-Key": supplied},
        json={"key": "anything"},
    )
    assert response.status_code == 401
    assert supplied not in response.text
    assert "admin-secret" not in response.text


def test_application_cannot_escalate_to_admin_configuration(tmp_path: Path):
    service = EnterpriseMemoryService(OrganizationIdentity("org-a"))
    registry = ApplicationRegistry("org-a", tmp_path / "applications.json")
    app_credential = registry.create("reader", scopes={"memory.read"})
    app = create_app(
        service,
        api_key="admin-secret",
        data_dir=tmp_path,
        application_registry=registry,
    )
    configuration = ProductConfigurationStore(tmp_path)
    attach_configuration_routes(app, api_key="admin-secret", store=configuration)
    client = TestClient(app)

    response = client.put(
        "/api/v1/admin/configuration/llm",
        headers={"X-Memoria-Key": app_credential.token},
        json={"provider": "mock", "model": "mock"},
    )
    assert response.status_code == 401
    assert configuration.llm().provider is None


def test_unsupported_provider_is_rejected_without_persisting_configuration(tmp_path: Path):
    service = EnterpriseMemoryService(OrganizationIdentity("org-a"))
    app = create_app(service, api_key="admin-secret", data_dir=tmp_path)
    configuration = ProductConfigurationStore(tmp_path)
    attach_configuration_routes(app, api_key="admin-secret", store=configuration)
    client = TestClient(app)

    response = client.put(
        "/api/v1/admin/configuration/llm",
        headers={"X-Memoria-Key": "admin-secret"},
        json={"provider": "unknown-provider", "model": "x", "api_key": "must-not-persist"},
    )
    assert response.status_code == 422
    assert not configuration.config_path.exists()
    assert not configuration.secrets_path.exists()
    assert "must-not-persist" not in response.text


def test_backup_excludes_application_registry_and_configuration_material(tmp_path: Path):
    source = tmp_path / "source"
    _service(source, "org-a", "fact", {"value": "safe"})
    registry = ApplicationRegistry("org-a", source / "applications.json")
    created = registry.create("crm", scopes={"memory.read"})
    config = ProductConfigurationStore(source)
    config.configure_llm(provider="openai", model="model", api_key="provider-secret")

    backup = create_backup(source, tmp_path / "state.zip")
    raw = backup.read_bytes()
    with zipfile.ZipFile(backup, "r") as archive:
        names = set(archive.namelist())
        assert "applications.json" not in names
        assert "product-config.json" not in names
        assert "product-secrets.json" not in names
    assert created.token.encode() not in raw
    assert b"provider-secret" not in raw


def test_rejected_restore_does_not_modify_existing_good_state(tmp_path: Path):
    source = tmp_path / "source"
    _service(source, "org-a", "incoming", {"value": "incoming"})
    backup = create_backup(source, tmp_path / "good.zip")

    tampered = tmp_path / "tampered.zip"
    with zipfile.ZipFile(backup, "r") as original, zipfile.ZipFile(tampered, "w") as changed:
        for name in original.namelist():
            data = original.read(name)
            if name == "memory.snapshot":
                data += b"tampered"
            changed.writestr(name, data)

    target = tmp_path / "target"
    _service(target, "org-a", "existing", {"value": "keep-me"})
    snapshot_before = (target / "memory.snapshot").read_bytes()
    manifest_before = (target / "enterprise.manifest.json").read_bytes()

    with pytest.raises(ValueError):
        restore_backup(tampered, target, expected_organization_id="org-a")

    assert (target / "memory.snapshot").read_bytes() == snapshot_before
    assert (target / "enterprise.manifest.json").read_bytes() == manifest_before
    reloaded = EnterpriseMemoryService.load(target)
    record = reloaded.recall(MemoryScope("org-a"), ("key", "existing"))
    assert record is not None
    assert record.payload == {"value": "keep-me"}


def test_wrong_organization_restore_does_not_replace_existing_state(tmp_path: Path):
    source = tmp_path / "source"
    _service(source, "org-b", "foreign", "foreign")
    backup = create_backup(source, tmp_path / "foreign.zip")

    target = tmp_path / "target"
    _service(target, "org-a", "local", "local")
    snapshot_before = (target / "memory.snapshot").read_bytes()
    manifest_before = (target / "enterprise.manifest.json").read_bytes()

    with pytest.raises(ValueError, match="organization"):
        restore_backup(backup, target, expected_organization_id="org-a")

    assert (target / "memory.snapshot").read_bytes() == snapshot_before
    assert (target / "enterprise.manifest.json").read_bytes() == manifest_before
