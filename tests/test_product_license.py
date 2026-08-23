from datetime import datetime, timedelta, timezone

from memoria_resolutiva.product_license import (
    LocalAlphaLicenseValidator,
    ProductLicense,
    ProductLicenseStatus,
)


def test_alpha_license_is_active_but_not_cryptographically_verified():
    now = datetime.now(timezone.utc)
    license = ProductLicense(
        license_id="lic-alpha",
        organization_id="org-a",
        plan="early_access",
        valid_from=now - timedelta(days=1),
        valid_until=now + timedelta(days=30),
        capabilities=frozenset({"memory.read", "memory.write", "chat.use"}),
    )
    result = LocalAlphaLicenseValidator().validate(license, organization_id="org-a")
    assert result.status is ProductLicenseStatus.ACTIVE
    assert result.cryptographically_verified is False
    assert result.plan == "early_access"


def test_license_cannot_cross_organization_boundary():
    license = ProductLicense(license_id="lic-a", organization_id="org-a")
    result = LocalAlphaLicenseValidator().validate(license, organization_id="org-b")
    assert result.status is ProductLicenseStatus.INVALID
    assert result.reason == "organization mismatch"


def test_expired_license_is_reported():
    now = datetime.now(timezone.utc)
    license = ProductLicense(
        license_id="lic-expired",
        organization_id="org-a",
        valid_until=now - timedelta(seconds=1),
    )
    assert license.local_status(now) is ProductLicenseStatus.EXPIRED


def test_signature_presence_is_not_signature_verification():
    license = ProductLicense(
        license_id="lic-signed-shape",
        organization_id="org-a",
        issuer="m2a-license-root",
        signature="opaque-signature",
    )
    assert license.cryptographically_verifiable is True
    result = LocalAlphaLicenseValidator().validate(license, organization_id="org-a")
    assert result.cryptographically_verified is False
