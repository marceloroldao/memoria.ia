from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import base64
import hashlib
import hmac
import json
from pathlib import Path
import os
import secrets
from typing import Iterable


DEFAULT_APP_SCOPES = frozenset({"memory.read", "memory.write", "chat.use"})


@dataclass(frozen=True, slots=True)
class ApplicationRecord:
    organization_id: str
    application_id: str
    display_name: str | None
    scopes: frozenset[str]
    enabled: bool
    created_at: datetime


@dataclass(frozen=True, slots=True)
class ApplicationCredential:
    record: ApplicationRecord
    token: str


@dataclass(frozen=True, slots=True)
class ApplicationAuth:
    organization_id: str
    application_id: str
    scopes: frozenset[str]

    def allows(self, scope: str) -> bool:
        return scope in self.scopes


class ApplicationRegistry:
    """Organization-local application credentials.

    Plaintext tokens are returned only at creation time. Persistence stores a
    per-token salt and PBKDF2-HMAC-SHA256 verifier, never the original token.
    This is an alpha credential boundary, not a replacement for future MA2A PKI.
    """

    FORMAT = "memoria.ia-application-registry-v1"
    ITERATIONS = 310_000

    def __init__(self, organization_id: str, path: str | Path | None = None):
        if not organization_id:
            raise ValueError("organization_id is required")
        self.organization_id = organization_id
        self.path = Path(path) if path is not None else None
        self._entries: dict[str, dict] = {}
        if self.path is not None and self.path.exists():
            self._load()

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    @classmethod
    def _derive(cls, token: str, salt: bytes) -> bytes:
        return hashlib.pbkdf2_hmac("sha256", token.encode("utf-8"), salt, cls.ITERATIONS)

    def create(
        self,
        application_id: str,
        *,
        display_name: str | None = None,
        scopes: Iterable[str] = DEFAULT_APP_SCOPES,
    ) -> ApplicationCredential:
        application_id = application_id.strip()
        if not application_id:
            raise ValueError("application_id is required")
        if application_id in self._entries:
            raise ValueError("application_id already exists")
        normalized_scopes = frozenset(s.strip() for s in scopes if s and s.strip())
        if not normalized_scopes:
            raise ValueError("at least one scope is required")

        token = "mem_app_" + secrets.token_urlsafe(32)
        salt = os.urandom(16)
        verifier = self._derive(token, salt)
        created_at = self._now()
        self._entries[application_id] = {
            "display_name": display_name,
            "scopes": sorted(normalized_scopes),
            "enabled": True,
            "created_at": created_at.isoformat(),
            "salt": base64.b64encode(salt).decode("ascii"),
            "verifier": base64.b64encode(verifier).decode("ascii"),
        }
        self.save()
        return ApplicationCredential(
            record=ApplicationRecord(
                organization_id=self.organization_id,
                application_id=application_id,
                display_name=display_name,
                scopes=normalized_scopes,
                enabled=True,
                created_at=created_at,
            ),
            token=token,
        )

    def list(self) -> list[ApplicationRecord]:
        records = []
        for application_id in sorted(self._entries):
            entry = self._entries[application_id]
            records.append(self._record(application_id, entry))
        return records

    def set_enabled(self, application_id: str, enabled: bool) -> ApplicationRecord:
        entry = self._entries.get(application_id)
        if entry is None:
            raise KeyError(application_id)
        entry["enabled"] = bool(enabled)
        self.save()
        return self._record(application_id, entry)

    def revoke(self, application_id: str) -> ApplicationRecord:
        return self.set_enabled(application_id, False)

    def authenticate(self, token: str) -> ApplicationAuth | None:
        if not token:
            return None
        for application_id, entry in self._entries.items():
            if not entry.get("enabled", False):
                continue
            try:
                salt = base64.b64decode(entry["salt"], validate=True)
                expected = base64.b64decode(entry["verifier"], validate=True)
            except Exception:
                continue
            actual = self._derive(token, salt)
            if hmac.compare_digest(actual, expected):
                return ApplicationAuth(
                    organization_id=self.organization_id,
                    application_id=application_id,
                    scopes=frozenset(entry.get("scopes", [])),
                )
        return None

    def save(self) -> None:
        if self.path is None:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "format": self.FORMAT,
            "organization_id": self.organization_id,
            "applications": self._entries,
        }
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        with tmp.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, self.path)

    def _load(self) -> None:
        data = json.loads(self.path.read_text("utf-8"))
        if data.get("format") != self.FORMAT:
            raise ValueError("unsupported application registry format")
        if data.get("organization_id") != self.organization_id:
            raise ValueError("application registry organization mismatch")
        applications = data.get("applications")
        if not isinstance(applications, dict):
            raise ValueError("invalid application registry")
        self._entries = applications

    def _record(self, application_id: str, entry: dict) -> ApplicationRecord:
        created = datetime.fromisoformat(entry["created_at"])
        if created.tzinfo is None:
            raise ValueError("application created_at must be timezone-aware")
        return ApplicationRecord(
            organization_id=self.organization_id,
            application_id=application_id,
            display_name=entry.get("display_name"),
            scopes=frozenset(entry.get("scopes", [])),
            enabled=bool(entry.get("enabled", False)),
            created_at=created,
        )
