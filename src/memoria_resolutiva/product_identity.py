from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import re
from typing import FrozenSet

_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


def _stable_id(value: str, field_name: str) -> str:
    if not isinstance(value, str) or not _ID_RE.fullmatch(value):
        raise ValueError(f"{field_name} must be 1..128 stable identifier characters")
    return value


class CertificateStatus(str, Enum):
    NOT_CONFIGURED = "not_configured"
    UNVERIFIED = "unverified"
    VALID = "valid"
    INVALID = "invalid"
    EXPIRED = "expired"
    REVOKED = "revoked"


class LicenseStatus(str, Enum):
    NOT_CONFIGURED = "not_configured"
    ACTIVE = "active"
    INACTIVE = "inactive"
    EXPIRED = "expired"
    SUSPENDED = "suspended"


@dataclass(frozen=True, slots=True)
class OrganizationIdentity:
    organization_id: str
    display_name: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "organization_id", _stable_id(self.organization_id, "organization_id"))


@dataclass(frozen=True, slots=True)
class NodeIdentity:
    organization_id: str
    node_id: str
    public_key: str | None = None
    certificate_ref: str | None = None
    certificate_status: CertificateStatus = CertificateStatus.NOT_CONFIGURED
    certificate_not_before: datetime | None = None
    certificate_not_after: datetime | None = None
    license_status: LicenseStatus = LicenseStatus.NOT_CONFIGURED
    capabilities: FrozenSet[str] = field(default_factory=frozenset)

    def __post_init__(self) -> None:
        object.__setattr__(self, "organization_id", _stable_id(self.organization_id, "organization_id"))
        object.__setattr__(self, "node_id", _stable_id(self.node_id, "node_id"))
        object.__setattr__(self, "capabilities", frozenset(self.capabilities))
        for name, value in (
            ("certificate_not_before", self.certificate_not_before),
            ("certificate_not_after", self.certificate_not_after),
        ):
            if value is not None and value.tzinfo is None:
                raise ValueError(f"{name} must be timezone-aware")
        if self.certificate_not_before and self.certificate_not_after:
            if self.certificate_not_after <= self.certificate_not_before:
                raise ValueError("certificate_not_after must be after certificate_not_before")

    def certificate_time_valid(self, now: datetime | None = None) -> bool:
        if self.certificate_status is not CertificateStatus.VALID:
            return False
        now = now or datetime.now(timezone.utc)
        if now.tzinfo is None:
            raise ValueError("now must be timezone-aware")
        if self.certificate_not_before and now < self.certificate_not_before:
            return False
        if self.certificate_not_after and now >= self.certificate_not_after:
            return False
        return True

    @property
    def commercially_enabled(self) -> bool:
        """Commercial entitlement is intentionally independent of certificate validity."""
        return self.license_status is LicenseStatus.ACTIVE


@dataclass(frozen=True, slots=True)
class MemoryScope:
    organization_id: str
    application_id: str | None = None
    agent_id: str | None = None
    user_id: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "organization_id", _stable_id(self.organization_id, "organization_id"))
        for field_name in ("application_id", "agent_id", "user_id"):
            value = getattr(self, field_name)
            if value is not None:
                object.__setattr__(self, field_name, _stable_id(value, field_name))

    def storage_namespace(self) -> tuple[str, ...]:
        """Canonical local namespace. Organization is always the first boundary."""
        parts = ["org", self.organization_id]
        if self.application_id is not None:
            parts += ["app", self.application_id]
        if self.agent_id is not None:
            parts += ["agent", self.agent_id]
        if self.user_id is not None:
            parts += ["user", self.user_id]
        return tuple(parts)
