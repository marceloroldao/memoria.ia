from pathlib import Path

import pytest

from memoria_resolutiva.product_identity import MemoryScope, OrganizationIdentity
from memoria_resolutiva.product_service import EnterpriseMemoryService, MemoryRevoked


def test_update_creates_new_version_without_overwriting_old_payload():
    scope = MemoryScope("org-a", application_id="app")
    service = EnterpriseMemoryService(OrganizationIdentity("org-a"))

    first = service.remember(scope, "customer", {"status": "new"}, ("customer", "42"))
    second = service.update(scope, ("customer", "42"), {"status": "active"})

    assert first.version == 1
    assert second.version == 2
    assert service.recall(scope, ("customer", "42")).payload == {"status": "active"}
    assert service.recall(scope, ("customer", "42"), version=1).payload == {"status": "new"}
    assert service.recall(scope, ("customer", "42"), version=2).payload == {"status": "active"}


def test_revoke_hides_latest_memory_but_preserves_auditable_history():
    scope = MemoryScope("org-a")
    service = EnterpriseMemoryService(OrganizationIdentity("org-a"))
    service.remember(scope, "k1", "value", ("key",))

    service.revoke(scope, ("key",))

    assert service.recall(scope, ("key",)) is None
    record = service.recall(scope, ("key",), include_revoked=True)
    assert record is not None
    assert record.revoked is True
    assert record.payload == "value"
    with pytest.raises(MemoryRevoked):
        service.update(scope, ("key",), "new")


def test_version_index_and_revocation_survive_restart(tmp_path: Path):
    scope = MemoryScope("org-a", application_id="app")
    service = EnterpriseMemoryService(OrganizationIdentity("org-a", "Org A"))
    service.remember(scope, "k", "v1", ("item", "1"))
    service.update(scope, ("item", "1"), "v2")
    service.revoke(scope, ("item", "1"))
    service.save(tmp_path)

    loaded = EnterpriseMemoryService.load(tmp_path)

    assert loaded.recall(scope, ("item", "1")) is None
    assert loaded.recall(scope, ("item", "1"), include_revoked=True).version == 2
    assert loaded.recall(scope, ("item", "1"), include_revoked=True, version=1).payload == "v1"
    assert loaded.statistics["logical_memory_count"] == 1
    assert loaded.statistics["revoked_memory_count"] == 1
