import os
import stat

from fastapi.testclient import TestClient

from memoria_resolutiva.product_admin_config import attach_configuration_routes
from memoria_resolutiva.product_config import ProductConfigurationStore
from memoria_resolutiva.product_http import create_app
from memoria_resolutiva.product_identity import OrganizationIdentity
from memoria_resolutiva.product_service import EnterpriseMemoryService


def build(tmp_path):
    service = EnterpriseMemoryService(OrganizationIdentity("org-a"))
    app = create_app(service, api_key="admin", data_dir=tmp_path)
    store = ProductConfigurationStore(tmp_path)
    attach_configuration_routes(app, api_key="admin", store=store)
    return TestClient(app), store


def headers():
    return {"X-Memoria-Key": "admin"}


def test_provider_secret_is_write_only_and_file_is_owner_only(tmp_path):
    client, store = build(tmp_path)
    response = client.put(
        "/api/v1/admin/configuration/llm",
        headers=headers(),
        json={"provider": "gemini", "model": "gemini-test", "api_key": "provider-secret"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["llm"]["provider"] == "gemini"
    assert body["llm"]["credential_configured"] is True
    assert "provider-secret" not in response.text

    status_response = client.get("/api/v1/admin/configuration", headers=headers())
    assert status_response.status_code == 200
    assert "provider-secret" not in status_response.text

    assert store.secrets_path.is_file()
    if os.name == "posix":
        mode = stat.S_IMODE(os.stat(store.secrets_path).st_mode)
        assert mode == 0o600
    else:
        # Windows does not implement POSIX chmod permission bits faithfully.
        # The alpha security contract therefore verifies write-only API behavior
        # here; Windows ACL hardening is a separate production security gate.
        assert os.access(store.secrets_path, os.R_OK | os.W_OK)
    assert store.llm().api_key == "provider-secret"


def test_existing_provider_secret_can_be_kept_when_model_changes(tmp_path):
    client, store = build(tmp_path)
    client.put(
        "/api/v1/admin/configuration/llm",
        headers=headers(),
        json={"provider": "openai", "model": "model-a", "api_key": "secret-a"},
    )
    second = client.put(
        "/api/v1/admin/configuration/llm",
        headers=headers(),
        json={"provider": "openai", "model": "model-b"},
    )
    assert second.status_code == 200
    assert store.llm().model == "model-b"
    assert store.llm().api_key == "secret-a"


def test_license_metadata_is_persisted_without_claiming_external_validation(tmp_path):
    client, store = build(tmp_path)
    response = client.put(
        "/api/v1/admin/configuration/license",
        headers=headers(),
        json={
            "license_id": "lic-early-1",
            "plan": "early_access",
            "valid_until": "2027-08-23T00:00:00+00:00",
            "max_nodes": 2,
            "capabilities": ["memory.read", "memory.write", "chat.use"],
        },
    )
    assert response.status_code == 200
    assert response.json()["validation"] == "local-alpha-metadata-only"
    assert response.json()["external_authority"] == "not_configured"
    assert store.license_public_status()["license_id"] == "lic-early-1"


def test_configuration_routes_require_admin_key(tmp_path):
    client, _ = build(tmp_path)
    assert client.get("/api/v1/admin/configuration").status_code == 401
    assert client.put(
        "/api/v1/admin/configuration/llm",
        headers={"X-Memoria-Key": "wrong"},
        json={"provider": "mock", "model": "mock"},
    ).status_code == 401
