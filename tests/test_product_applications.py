from pathlib import Path

from memoria_resolutiva.product_applications import ApplicationRegistry


def test_application_token_is_shown_once_and_plaintext_is_not_persisted(tmp_path):
    path = tmp_path / "applications.json"
    registry = ApplicationRegistry("org-a", path)
    created = registry.create("crm", scopes={"memory.read", "memory.write"})
    assert created.token.startswith("mem_app_")
    persisted = path.read_text("utf-8")
    assert created.token not in persisted
    assert "verifier" in persisted
    assert "salt" in persisted


def test_application_authentication_and_scopes_survive_restart(tmp_path):
    path = tmp_path / "applications.json"
    registry = ApplicationRegistry("org-a", path)
    created = registry.create("crm", scopes={"memory.read", "chat.use"})

    loaded = ApplicationRegistry("org-a", path)
    auth = loaded.authenticate(created.token)
    assert auth is not None
    assert auth.application_id == "crm"
    assert auth.allows("memory.read")
    assert auth.allows("chat.use")
    assert not auth.allows("memory.write")


def test_wrong_token_and_revoked_application_are_rejected(tmp_path):
    registry = ApplicationRegistry("org-a", tmp_path / "applications.json")
    created = registry.create("crm")
    assert registry.authenticate("wrong") is None
    registry.revoke("crm")
    assert registry.authenticate(created.token) is None


def test_registry_is_bound_to_organization(tmp_path):
    path = tmp_path / "applications.json"
    ApplicationRegistry("org-a", path).create("crm")
    try:
        ApplicationRegistry("org-b", path)
    except ValueError as exc:
        assert "organization mismatch" in str(exc)
    else:
        raise AssertionError("expected organization mismatch")


def test_application_ids_are_unique(tmp_path):
    registry = ApplicationRegistry("org-a", tmp_path / "applications.json")
    registry.create("crm")
    try:
        registry.create("crm")
    except ValueError as exc:
        assert "already exists" in str(exc)
    else:
        raise AssertionError("expected duplicate application rejection")
