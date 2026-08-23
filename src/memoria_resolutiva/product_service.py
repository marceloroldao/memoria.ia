from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
import os
import tempfile
import zlib
from typing import Iterable, Hashable

from .api_v90 import ResolutiveMemoryAPI
from .product_identity import OrganizationIdentity, MemoryScope

Node = Hashable
PRODUCT_FORMAT = "memoria.ia-enterprise-alpha-v1"


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_name, path)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)


def _manifest_bytes(data: dict) -> bytes:
    raw = json.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")
    envelope = {
        "format": PRODUCT_FORMAT,
        "crc32": zlib.crc32(raw) & 0xFFFFFFFF,
        "payload": raw.decode("utf-8"),
    }
    return json.dumps(envelope, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _read_manifest(path: Path) -> dict:
    envelope = json.loads(path.read_text("utf-8"))
    if envelope.get("format") != PRODUCT_FORMAT:
        raise ValueError("unsupported Memoria.ia Enterprise manifest format")
    raw = envelope["payload"].encode("utf-8")
    if (zlib.crc32(raw) & 0xFFFFFFFF) != int(envelope["crc32"]):
        raise ValueError("Memoria.ia Enterprise manifest checksum mismatch")
    data = json.loads(raw.decode("utf-8"))
    if data.get("format") != PRODUCT_FORMAT:
        raise ValueError("Memoria.ia Enterprise manifest payload mismatch")
    return data


@dataclass(frozen=True, slots=True)
class MemoryRecord:
    organization_id: str
    knowledge_id: str
    payload: object
    modality: str | None
    provenance: tuple[str, ...]
    trajectory: tuple[Node, ...]
    accesses: int


class OrganizationMismatch(PermissionError):
    pass


class EnterpriseMemoryService:
    """Organization-scoped product facade over the validated memory engine.

    This is intentionally below HTTP. Every storage route and internal
    knowledge identifier is qualified by organization so future API layers
    cannot accidentally bypass the tenancy boundary.
    """

    def __init__(self, organization: OrganizationIdentity, memory: ResolutiveMemoryAPI | None = None):
        self.organization = organization
        self._memory = memory or ResolutiveMemoryAPI()

    def _assert_scope(self, scope: MemoryScope) -> None:
        if scope.organization_id != self.organization.organization_id:
            raise OrganizationMismatch(
                f"scope organization {scope.organization_id!r} does not match service organization"
            )

    def _qualified_knowledge_id(self, external_id: str) -> str:
        if not isinstance(external_id, str) or not external_id:
            raise ValueError("knowledge_id must be a non-empty string")
        return f"org:{self.organization.organization_id}:knowledge:{external_id}"

    def _route(self, scope: MemoryScope, trajectory: Iterable[Node]) -> tuple[Node, ...]:
        self._assert_scope(scope)
        tail = tuple(trajectory)
        if not tail:
            raise ValueError("trajectory must not be empty")
        return scope.storage_namespace() + ("memory",) + tail

    def remember(
        self,
        scope: MemoryScope,
        knowledge_id: str,
        payload: object,
        trajectory: Iterable[Node],
        *,
        modality: str = "text",
        provenance: str = "local",
    ) -> None:
        route = self._route(scope, trajectory)
        self._memory.remember(
            self._qualified_knowledge_id(knowledge_id),
            payload,
            route,
            modality=modality,
            provenance=provenance,
        )

    def recall(
        self,
        scope: MemoryScope,
        trajectory: Iterable[Node],
        *,
        include_inactive: bool = False,
    ) -> MemoryRecord | None:
        route = self._route(scope, trajectory)
        node = self._memory.recall(route, include_inactive=include_inactive)
        if node is None:
            return None
        prefix = f"org:{self.organization.organization_id}:knowledge:"
        if not node.knowledge_id.startswith(prefix):
            raise OrganizationMismatch("resolved knowledge belongs to a different organization")
        external_id = node.knowledge_id[len(prefix):]
        modalities = tuple(sorted(node.modalities))
        return MemoryRecord(
            organization_id=self.organization.organization_id,
            knowledge_id=external_id,
            payload=node.payload,
            modality=modalities[0] if len(modalities) == 1 else None,
            provenance=tuple(sorted(node.provenance)),
            trajectory=route,
            accesses=node.accesses,
        )

    def route_status(self, scope: MemoryScope, trajectory: Iterable[Node]):
        return self._memory.route_status(self._route(scope, trajectory))

    def reinforce(self, scope: MemoryScope, trajectory: Iterable[Node], amount: float = 1.0) -> None:
        self._memory.reinforce(self._route(scope, trajectory), amount)

    def challenge(self, scope: MemoryScope, trajectory: Iterable[Node], amount: float = 1.0) -> None:
        self._memory.challenge(self._route(scope, trajectory), amount)

    @property
    def statistics(self) -> dict[str, int | float | str]:
        knowledge = self._memory._memory.knowledge
        return {
            "organization_id": self.organization.organization_id,
            "knowledge_count": knowledge.knowledge_count,
            "route_count": knowledge.route_count,
            "duplication_ratio": knowledge.duplication_ratio(),
        }

    def save(self, directory: str | os.PathLike[str]) -> None:
        root = Path(directory)
        root.mkdir(parents=True, exist_ok=True)
        snapshot = root / "memory.snapshot"
        manifest = root / "enterprise.manifest.json"
        self._memory.save(snapshot)
        data = {
            "format": PRODUCT_FORMAT,
            "organization": {
                "organization_id": self.organization.organization_id,
                "display_name": self.organization.display_name,
            },
            "snapshot": snapshot.name,
        }
        _atomic_write(manifest, _manifest_bytes(data))

    @classmethod
    def load(cls, directory: str | os.PathLike[str]) -> "EnterpriseMemoryService":
        root = Path(directory)
        data = _read_manifest(root / "enterprise.manifest.json")
        org_data = data["organization"]
        organization = OrganizationIdentity(
            organization_id=org_data["organization_id"],
            display_name=org_data.get("display_name"),
        )
        memory = ResolutiveMemoryAPI.load(root / data["snapshot"])
        return cls(organization, memory)
