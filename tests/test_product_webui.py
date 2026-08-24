from fastapi.testclient import TestClient

from memoria_resolutiva.product_http import create_app
from memoria_resolutiva.product_identity import OrganizationIdentity
from memoria_resolutiva.product_service import EnterpriseMemoryService


def test_web_ui_is_served_from_product_app(tmp_path):
    service = EnterpriseMemoryService(OrganizationIdentity("org-a", "Org A"))
    client = TestClient(create_app(service, api_key="secret", data_dir=tmp_path))

    root = client.get("/")
    css = client.get("/ui/style.css")
    js = client.get("/ui/app.js")

    assert root.status_code == 200
    assert "Memoria.ia Enterprise" in root.text
    assert 'data-page="chat"' in root.text
    assert 'data-page="settings"' in root.text
    assert 'data-page="diagnostics"' in root.text
    assert "Configurações" in root.text
    assert "Diagnóstico" in root.text
    assert "Baixar relatório TXT" in root.text
    assert "Chave de administrador" in root.text
    assert "Chave do provedor" in root.text
    assert css.status_code == 200
    assert ".chatbox" in css.text
    assert ".conversation" in css.text
    assert js.status_code == 200
    assert "/api/v1/chat" in js.text
    assert "/api/v1/admin/configuration/llm" in js.text
    assert "localStorage" in js.text
    assert "memoria-report-" in js.text
    assert "API keys and provider secrets are intentionally excluded" in js.text


def test_web_ui_does_not_embed_server_secret(tmp_path):
    service = EnterpriseMemoryService(OrganizationIdentity("org-a", "Org A"))
    client = TestClient(create_app(service, api_key="server-only-secret", data_dir=tmp_path))

    for path in ("/", "/ui/app.js", "/ui/style.css"):
        response = client.get(path)
        assert response.status_code == 200
        assert "server-only-secret" not in response.text
