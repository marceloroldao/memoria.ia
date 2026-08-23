from datetime import datetime, timedelta, timezone

import pytest

from memoria_resolutiva.product_identity import (
    CertificateStatus,
    LicenseStatus,
    MemoryScope,
    NodeIdentity,
    OrganizationIdentity,
)


def test_organization_id_is_stable_and_validated():
    assert OrganizationIdentity("acme-01").organization_id == "acme-01"
    with pytest.raises(ValueError):
        OrganizationIdentity("bad id with spaces")


def test_storage_namespace_always_starts_with_organization():
    a = MemoryScope("org-a", application_id="chat", user_id="u1")
    b = MemoryScope("org-b", application_id="chat", user_id="u1")
    assert a.storage_namespace()[:2] == ("org", "org-a")
    assert b.storage_namespace()[:2] == ("org", "org-b")
    assert a.storage_namespace() != b.storage_namespace()


def test_certificate_validity_and_license_are_independent():
    now = datetime(2026, 8, 23, tzinfo=timezone.utc)
    node = NodeIdentity(
        organization_id="org-a",
        node_id="node-01",
        certificate_status=CertificateStatus.VALID,
        certificate_not_before=now - timedelta(days=1),
        certificate_not_after=now + timedelta(days=1),
        license_status=LicenseStatus.INACTIVE,
    )
    assert node.certificate_time_valid(now)
    assert not node.commercially_enabled


def test_active_license_does_not_make_invalid_certificate_valid():
    node = NodeIdentity(
        organization_id="org-a",
        node_id="node-01",
        certificate_status=CertificateStatus.INVALID,
        license_status=LicenseStatus.ACTIVE,
    )
    assert node.commercially_enabled
    assert not node.certificate_time_valid()


def test_certificate_times_must_be_timezone_aware():
    with pytest.raises(ValueError):
        NodeIdentity(
            organization_id="org-a",
            node_id="node-01",
            certificate_not_after=datetime(2027, 1, 1),
        )
