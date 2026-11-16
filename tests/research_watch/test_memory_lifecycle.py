"""Research regression scenarios: temporal correction, isolation, and revocation.

No network, provider credentials, or production data are used.
"""
from memoria_resolutiva.product_identity import MemoryScope, OrganizationIdentity
from memoria_resolutiva.product_service import EnterpriseMemoryService


def test_interleaved_corrections_stay_scoped_after_restart(tmp_path):
    service = EnterpriseMemoryService(OrganizationIdentity("watch-org"))
    alice = MemoryScope("watch-org", application_id="assistant", user_id="alice")
    bob = MemoryScope("watch-org", application_id="assistant", user_id="bob")
    route = ("preference", "delivery")
    service.remember(alice, "delivery", "email", route, provenance="alice-2026-01")
    service.remember(bob, "delivery", "sms", route, provenance="bob-2026-01")
    service.update(alice, route, "push", provenance="alice-2026-02")

    service.save(tmp_path)
    loaded = EnterpriseMemoryService.load(tmp_path)
    current = loaded.recall(alice, route)
    historical = loaded.recall(alice, route, version=1)
    other = loaded.recall(bob, route)
    assert (current.payload, current.version) == ("push", 2)
    assert (historical.payload, historical.version) == ("email", 1)
    assert (other.payload, other.version) == ("sms", 1)
    assert loaded.recall(bob, route, version=2) is None
    assert tuple(r.payload for r in loaded.records_under(alice, ("preference",))) == ("push",)
    assert tuple(r.payload for r in loaded.records_under(bob, ("preference",))) == ("sms",)


def test_revoked_fact_does_not_resurface_after_restart(tmp_path):
    service = EnterpriseMemoryService(OrganizationIdentity("watch-org"))
    scope = MemoryScope("watch-org", application_id="assistant", user_id="alice")
    route = ("fact", "location")
    service.remember(scope, "location", "old-city", route)
    service.update(scope, route, "new-city")
    service.revoke(scope, route)
    service.save(tmp_path)

    loaded = EnterpriseMemoryService.load(tmp_path)
    assert loaded.recall(scope, route) is None
    assert loaded.recall(scope, route, version=1) is None
    assert loaded.recall(scope, route, version=2) is None
    assert loaded.records_under(scope, ("fact",)) == ()
    audit = loaded.recall(scope, route, version=1, include_revoked=True)
    assert audit is not None and audit.payload == "old-city" and audit.revoked
