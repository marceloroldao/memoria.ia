from pathlib import Path

import pytest

from memoria_resolutiva.product_identity import MemoryScope, OrganizationIdentity
from memoria_resolutiva.product_service import EnterpriseMemoryService, OrganizationMismatch


def test_organization_scope_is_enforced():
    service = EnterpriseMemoryService(OrganizationIdentity("org-a"))
    good = MemoryScope("org-a", application_id="app-1")
    bad = MemoryScope("org-b", application_id="app-1")

    service.remember(good, "k1", {"answer": 42}, ("topic", "answer"))

    with pytest.raises(OrganizationMismatch):
        service.recall(bad, ("topic", "answer"))


def test_same_external_knowledge_id_can_exist_in_different_organizations():
    a = EnterpriseMemoryService(OrganizationIdentity("org-a"))
    b = EnterpriseMemoryService(OrganizationIdentity("org-b"))
    sa = MemoryScope("org-a")
    sb = MemoryScope("org-b")

    a.remember(sa, "shared-id", "A", ("route",))
    b.remember(sb, "shared-id", "B", ("route",))

    assert a.recall(sa, ("route",)).payload == "A"
    assert b.recall(sb, ("route",)).payload == "B"


def test_application_scopes_do_not_collide_inside_organization():
    service = EnterpriseMemoryService(OrganizationIdentity("org-a"))
    app1 = MemoryScope("org-a", application_id="one")
    app2 = MemoryScope("org-a", application_id="two")

    service.remember(app1, "shared-id", "first", ("same", "tail"))
    service.remember(app2, "shared-id", "second", ("same", "tail"))

    first = service.recall(app1, ("same", "tail"))
    second = service.recall(app2, ("same", "tail"))
    assert first is not None and first.knowledge_id == "shared-id" and first.payload == "first"
    assert second is not None and second.knowledge_id == "shared-id" and second.payload == "second"


def test_restart_preserves_memory_and_organization(tmp_path: Path):
    scope = MemoryScope("org-a", application_id="app")
    service = EnterpriseMemoryService(OrganizationIdentity("org-a", "Organization A"))
    service.remember(scope, "k1", {"customer": "alpha"}, ("customer", "alpha"), provenance="test")
    service.save(tmp_path)

    loaded = EnterpriseMemoryService.load(tmp_path)
    record = loaded.recall(scope, ("customer", "alpha"))

    assert loaded.organization.organization_id == "org-a"
    assert loaded.organization.display_name == "Organization A"
    assert record is not None
    assert record.knowledge_id == "k1"
    assert record.payload == {"customer": "alpha"}
    assert record.provenance == ("test",)


def test_corrupted_manifest_is_rejected(tmp_path: Path):
    scope = MemoryScope("org-a")
    service = EnterpriseMemoryService(OrganizationIdentity("org-a"))
    service.remember(scope, "k1", "value", ("route",))
    service.save(tmp_path)

    manifest = tmp_path / "enterprise.manifest.json"
    data = manifest.read_text("utf-8")
    manifest.write_text(data.replace("org-a", "org-x", 1), "utf-8")

    with pytest.raises(ValueError, match="checksum"):
        EnterpriseMemoryService.load(tmp_path)


def test_statistics_are_scoped_to_instance():
    scope = MemoryScope("org-a")
    service = EnterpriseMemoryService(OrganizationIdentity("org-a"))
    service.remember(scope, "k1", "value", ("route",))

    stats = service.statistics
    assert stats["organization_id"] == "org-a"
    assert stats["knowledge_count"] == 1
    assert stats["route_count"] == 1
