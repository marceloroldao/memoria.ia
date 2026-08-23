from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import FrozenSet


class ProductLicenseStatus(str, Enum):
    NOT_CONFIGURED = "not_configured"
    ACTIVE = "active"
    NOT_YET_VALID = "not_yet_valid"
    EXPIRED = "expired"
    SUSPENDED = "suspended"
    INVALID = "invalid"


@dataclass(frozen=True, slots=True)
class ProductLicense:
    """Stable Memoria.ia-side license contract.

    Signature issuance/revocation belongs to the future external license authority.
    Memoria.ia consumes the resulting entitlement; it does not issue licenses.
    """

    license_id: str
    organization_id: str
    product: str = "memoria.ia-enterprise"
    plan: str = "early_access"
    valid_from: datetime | None = None
    valid_until: datetime | None = None
    max_nodes: int = 1
    capabilities: FrozenSet[str] = field(default_factory=frozenset)
    issuer: str | None = None
    signature: str | None = None
    suspended: bool = False

    def __post_init__(self) -> None:
        if not self.license_id or not self.organization_id:
            raise ValueError("license_id and organization_id are required")
        if self.max_nodes < 1:
            raise ValueError("max_nodes must be >= 1")
        object.__setattr__(self, "capabilities", frozenset(self.capabilities))
        for name, value in (("valid_from", self.valid_from), ("valid_until", self.valid_until)):
            if value is not None and value.tzinfo is None:
                raise ValueError(f"{name} must be timezone-aware")
        if self.valid_from and self.valid_until and self.valid_until <= self.valid_from:
            raise ValueError("valid_until must be after valid_from")

    def local_status(self, now: datetime | None = None) -> ProductLicenseStatus:
        """Evaluate local time/status only; this is not cryptographic validation."""
        if self.suspended:
            return ProductLicenseStatus.SUSPENDED
        now = now or datetime.now(timezone.utc)
        if now.tzinfo is None:
            raise ValueError("now must be timezone-aware")
        if self.valid_from and now < self.valid_from:
            return ProductLicenseStatus.NOT_YET_VALID
        if self.valid_until and now >= self.valid_until:
            return ProductLicenseStatus.EXPIRED
        return ProductLicenseStatus.ACTIVE

    @property
    def cryptographically_verifiable(self) -> bool:
        return bool(self.issuer and self.signature)


@dataclass(frozen=True, slots=True)
class LicenseValidationResult:
    status: ProductLicenseStatus
    license_id: str | None
    organization_id: str | None
    plan: str | None
    valid_until: datetime | None
    capabilities: FrozenSet[str]
    max_nodes: int | None
    cryptographically_verified: bool
    reason: str | None = None


class LicenseValidator:
    """Boundary to be implemented by the future external license authority adapter."""

    def validate(self, license: ProductLicense, *, organization_id: str) -> LicenseValidationResult:
        raise NotImplementedError


class LocalAlphaLicenseValidator(LicenseValidator):
    """Alpha-only local entitlement validator.

    It deliberately does not claim signature verification. This lets early-access
    installs exercise plans/capabilities while keeping PKI/license issuance external.
    """

    def validate(self, license: ProductLicense, *, organization_id: str) -> LicenseValidationResult:
        if license.organization_id != organization_id:
            return LicenseValidationResult(
                status=ProductLicenseStatus.INVALID,
                license_id=license.license_id,
                organization_id=license.organization_id,
                plan=license.plan,
                valid_until=license.valid_until,
                capabilities=license.capabilities,
                max_nodes=license.max_nodes,
                cryptographically_verified=False,
                reason="organization mismatch",
            )
        status = license.local_status()
        return LicenseValidationResult(
            status=status,
            license_id=license.license_id,
            organization_id=license.organization_id,
            plan=license.plan,
            valid_until=license.valid_until,
            capabilities=license.capabilities,
            max_nodes=license.max_nodes,
            cryptographically_verified=False,
            reason="alpha local validation only; external signature authority not configured",
        )
