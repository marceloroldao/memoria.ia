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
PRODUCT_FORMAT = "memoria.ia-enterprise-alpha-v2"
LEGACY_PRODUCT_FORMAT = "memoria.ia-enterprise-alpha-v1"


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
    envelope_format = envelope.get("format")
    if envelope_format not in {PRODUCT_FORMAT, LEGACY_PRODUCT_FORMAT}:
        raise ValueError("unsupported Memoria.ia Enterprise manifest format")
    raw = envelope["payload"].encode("utf-8")
    if (zlib.crc32(raw) & 0xFFFFFFFF) != int(envelope["crc32"]):
        raise ValueError("Memoria.ia Enterprise manifest checksum mismatch")
    data = json.loads(raw.decode("utf-8"))
    if data.get("format") not in {PRODUCT_FORMAT, LEGACY_PRODUCT_FORMAT}:
        raise ValueError("Memoria.ia Enterprise manifest payload mismatch")
    return data


def _route_key(route: tuple[Node, ...]) -> str:
    try:
        return json.dumps(list(route), sort_keys=True, separators=(",", ":"))
    except TypeError as exc:
        raise TypeError("product trajectories must be JSON-serializable") from exc


@dataclass(frozen=True, slots=True)
class MemoryRecord:
    organization_id: str
    knowledge_id: str
    payload: object
    modality: str | None
    provenance: tuple[str, ...]
    trajectory: tuple[Node, ...]
    accesses: int
    version: int = 1
    revoked: bool = False


@dataclass(slots=True)
class _LogicalEntry:
    knowledge_id: str
    latest_version: int
    revoked: bool = False


class OrganizationMismatch(PermissionError):
    pass


class MemoryRevoked(LookupError):
    pass


class EnterpriseMemoryService:
    """Organization-scoped product facade over the validated memory engine.

    Product updates are append-only: a new immutable memory version is written
    instead of mutating an existing payload. Revocation is maintained in the
    product index and persisted separately from the research engine snapshot.
    """

    def __init__(
        self,
        organization: OrganizationIdentity,
        memory: ResolutiveMemoryAPI | None = None,
        entries: dict[str, _LogicalEntry] | None = None,
    ):
        self.organization = organization
        self._memory = memory or ResolutiveMemoryAPI()
        self._entries: dict[str, _LogicalEntry] = entries or {}

    def _assert_scope(self, scope: MemoryScope) -> None:
        if scope.organization_id != self.organization.organization_id:
            raise OrganizationMismatch(
                f"scope organization {scope.organization_id!r} does not match service organization"
            )

    def _qualified_knowledge_id(
        self,
        external_id: str,
        version: int | None = None,
        *,
        logical_key: str | None = None,
    ) -> str:
        if not isinstance(external_id, str) or not external_id:
            raise ValueError("knowledge_id must be a non-empty string")
        base = f"org:{self.organization.organization_id}:knowledge:{external_id}"
        if logical_key is not None:
            scope_tag = f"{zlib.crc32(logical_key.encode('utf-8')) & 0xFFFFFFFF:08x}"
            base = f"{base}:scope:{scope_tag}"
        return base if version is None else f"{base}:v{version}"

    def _route(self, scope: MemoryScope, trajectory: Iterable[Node]) -> tuple[Node, ...]:
        self._assert_scope(scope)
        tail = tuple(trajectory)
        if not tail:
            raise ValueError("trajectory must not be empty")
        return scope.storage_namespace() + ("memory",) + tail

    @staticmethod
    def _version_route(logical_route: tuple[Node, ...], version: int) -> tuple[Node, ...]:
        return logical_route + ("version", version)

    def remember(
        self,
        scope: MemoryScope,
        knowledge_id: str,
        payload: object,
        trajectory: Iterable[Node],
        *,
        modality: str = "text",
        provenance: str = "local",
        activate: bool = True,
    ) -> MemoryRecord:
        logical_route = self._route(scope, trajectory)
        key = _route_key(logical_route)
        if key in self._entries:
            raise ValueError("logical memory already exists; use update()")
        version = 1
        route = self._version_route(logical_route, version)
        self._memory.remember(
            self._qualified_knowledge_id(knowledge_id, version, logical_key=key),
            payload,
            route,
            modality=modality,
            provenance=provenance,
        )
        if activate:
            self._memory.reinforce(route, 1.0)
        self._entries[key] = _LogicalEntry(knowledge_id=knowledge_id, latest_version=version)
        record = self.recall(scope, trajectory)
        assert record is not None
        return record

    def update(
        self,
        scope: MemoryScope,
        trajectory: Iterable[Node],
        payload: object,
        *,
        modality: str = "text",
        provenance: str = "local",
    ) -> MemoryRecord:
        logical_route = self._route(scope, trajectory)
        key = _route_key(logical_route)
        entry = self._entries.get(key)
        if entry is None:
            raise KeyError("logical memory does not exist")
        if entry.revoked:
            raise MemoryRevoked("revoked memory cannot be updated")
        version = entry.latest_version + 1
        route = self._version_route(logical_route, version)
        self._memory.remember(
            self._qualified_knowledge_id(entry.knowledge_id, version, logical_key=key),
            payload,
            route,
            modality=modality,
            provenance=provenance,
        )
        self._memory.reinforce(route, 1.0)
        entry.latest_version = version
        record = self.recall(scope, trajectory)
        assert record is not None
        return record

    def revoke(self, scope: MemoryScope, trajectory: Iterable[Node]) -> None:
        logical_route = self._route(scope, trajectory)
        entry = self._entries.get(_route_key(logical_route))
        if entry is None:
            raise KeyError("logical memory does not exist")
        entry.revoked = True

    def recall(
        self,
        scope: MemoryScope,
        trajectory: Iterable[Node],
        *,
        include_inactive: bool = False,
        include_revoked: bool = False,
        version: int | None = None,
    ) -> MemoryRecord | None:
        logical_route = self._route(scope, trajectory)
        key = _route_key(logical_route)
        entry = self._entries.get(key)

        if entry is None:
            node = self._memory.recall(logical_route, include_inactive=include_inactive)
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
                trajectory=logical_route,
                accesses=node.accesses,
            )

        if entry.revoked and not include_revoked:
            return None
        selected_version = entry.latest_version if version is None else version
        if selected_version < 1 or selected_version > entry.latest_version:
            return None
        route = self._version_route(logical_route, selected_version)
        node = self._memory.recall(route, include_inactive=include_inactive)
        if node is None:
            return None
        legacy_prefix = f"org:{self.organization.organization_id}:knowledge:{entry.knowledge_id}:v"
        scoped_prefix = f"org:{self.organization.organization_id}:knowledge:{entry.knowledge_id}:scope:"
        if not (node.knowledge_id.startswith(legacy_prefix) or node.knowledge_id.startswith(scoped_prefix)):
            raise OrganizationMismatch("resolved knowledge belongs to a different organization or scope")
        modalities = tuple(sorted(node.modalities))
        return MemoryRecord(
            organization_id=self.organization.organization_id,
            knowledge_id=entry.knowledge_id,
            payload=node.payload,
            modality=modalities[0] if len(modalities) == 1 else None,
            provenance=tuple(sorted(node.provenance)),
            trajectory=logical_route,
            accesses=node.accesses,
            version=selected_version,
            revoked=entry.revoked,
        )

    def records_under(
        self,
        scope: MemoryScope,
        trajectory_prefix: Iterable[Node],
    ) -> tuple[MemoryRecord, ...]:
        """Enumerate active logical records beneath one scoped trajectory prefix.

        This is a read-only product boundary for structured indexes such as the
        semantic concept catalog. It never exposes the internal entry table.
        """
        prefix_tail = tuple(trajectory_prefix)
        if not prefix_tail:
            raise ValueError("trajectory_prefix must not be empty")
        self._assert_scope(scope)
        scope_prefix = scope.storage_namespace() + ("memory",)
        logical_prefix = scope_prefix + prefix_tail
        records: list[MemoryRecord] = []
        for key, entry in self._entries.items():
            if entry.revoked:
                continue
            try:
                logical_route = tuple(json.loads(key))
            except (TypeError, ValueError, json.JSONDecodeError):
                continue
            if logical_route[: len(logical_prefix)] != logical_prefix:
                continue
            if logical_route[: len(scope_prefix)] != scope_prefix:
                continue
            tail = logical_route[len(scope_prefix) :]
            record = self.recall(scope, tail)
            if record is not None:
                records.append(record)
        records.sort(key=lambda row: _route_key(row.trajectory))
        return tuple(records)

    def route_status(self, scope: MemoryScope, trajectory: Iterable[Node]):
        logical_route = self._route(scope, trajectory)
        entry = self._entries.get(_route_key(logical_route))
        if entry is None:
            return self._memory.route_status(logical_route)
        return self._memory.route_status(self._version_route(logical_route, entry.latest_version))

    def reinforce(self, scope: MemoryScope, trajectory: Iterable[Node], amount: float = 1.0) -> None:
        logical_route = self._route(scope, trajectory)
        entry = self._entries.get(_route_key(logical_route))
        route = logical_route if entry is None else self._version_route(logical_route, entry.latest_version)
        self._memory.reinforce(route, amount)

    def challenge(self, scope: MemoryScope, trajectory: Iterable[Node], amount: float = 1.0) -> None:
        logical_route = self._route(scope, trajectory)
        entry = self._entries.get(_route_key(logical_route))
        route = logical_route if entry is None else self._version_route(logical_route, entry.latest_version)
        self._memory.challenge(route, amount)

    @property
    def statistics(self) -> dict[str, int | float | str]:
        knowledge = self._memory._memory.knowledge
        return {
            "organization_id": self.organization.organization_id,
            "knowledge_count": knowledge.knowledge_count,
            "route_count": knowledge.route_count,
            "logical_memory_count": len(self._entries),
            "revoked_memory_count": sum(1 for entry in self._entries.values() if entry.revoked),
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
            "entries": {
                key: {
                    "knowledge_id": entry.knowledge_id,
                    "latest_version": entry.latest_version,
                    "revoked": entry.revoked,
                }
                for key, entry in self._entries.items()
            },
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
        entries = {
            key: _LogicalEntry(
                knowledge_id=row["knowledge_id"],
                latest_version=int(row["latest_version"]),
                revoked=bool(row.get("revoked", False)),
            )
            for key, row in data.get("entries", {}).items()
        }
        return cls(organization, memory, entries)
