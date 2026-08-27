from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
import tempfile

from .bdr_store import BDRResolutiveMemory
from .product_identity import OrganizationIdentity
from .product_service import EnterpriseMemoryService, _atomic_write, _manifest_bytes, _read_manifest
from .sqlite_store import SQLiteResolutiveMemory
from .storage_backend import open_resolutive_memory


@dataclass(frozen=True, slots=True)
class SnapshotReceipt:
    backend: str
    snapshot_id: str
    sha256: str

    def as_dict(self) -> dict[str, str]:
        return {
            "backend": self.backend,
            "snapshot_id": self.snapshot_id,
            "sha256": self.sha256,
        }


class ProductSnapshotPersistence:
    """Durable blob boundary for Product Alpha snapshots.

    The resolutive engine remains the in-memory authority while running. On each
    product save, the already validated engine snapshot is mirrored into the
    selected BDR/SQLite backend. The filesystem snapshot remains as a portable
    backup/export copy. Normal restart prefers the durable backend copy.
    """

    def __init__(
        self,
        root: str | Path,
        *,
        backend: str | None = None,
        allow_fallback: bool = True,
    ) -> None:
        self.root = Path(root)
        self.backend = backend
        self.allow_fallback = allow_fallback
        self.last_backend: str | None = None
        self.portable_fallback_used = False

    @staticmethod
    def _backend_name(store: object) -> str:
        if isinstance(store, BDRResolutiveMemory):
            return "bdr"
        if isinstance(store, SQLiteResolutiveMemory):
            return "sqlite"
        return type(store).__name__.lower()

    def _open(self, *, backend: str | None = None, allow_fallback: bool | None = None):
        store = open_resolutive_memory(
            self.root,
            backend=backend if backend is not None else self.backend,
            allow_fallback=self.allow_fallback if allow_fallback is None else allow_fallback,
        )
        self.last_backend = self._backend_name(store)
        return store

    def store_bytes(self, payload: bytes) -> SnapshotReceipt:
        digest = hashlib.sha256(payload).hexdigest()
        snapshot_id = f"product-snapshot:{digest}"
        store = self._open()
        backend_name = self._backend_name(store)
        try:
            try:
                existing = store.reconstruct(snapshot_id)
            except KeyError:
                existing = None
            if existing is None:
                store.add(snapshot_id, payload)
            elif existing != payload:
                raise ValueError("snapshot id collision in product persistence backend")
        finally:
            store.close()
        return SnapshotReceipt(backend_name, snapshot_id, digest)

    def load_bytes(self, receipt: dict[str, str]) -> bytes:
        backend = str(receipt["backend"]).lower()
        snapshot_id = str(receipt["snapshot_id"])
        expected = str(receipt["sha256"])
        store = self._open(backend=backend, allow_fallback=False)
        try:
            payload = store.reconstruct(snapshot_id)
        finally:
            store.close()
        actual = hashlib.sha256(payload).hexdigest()
        if actual != expected:
            raise ValueError("product snapshot persistence checksum mismatch")
        return payload

    def restore_or_portable_fallback(self, receipt: dict[str, str], portable_path: Path) -> bytes:
        try:
            self.portable_fallback_used = False
            return self.load_bytes(receipt)
        except (KeyError, RuntimeError, OSError):
            if not portable_path.is_file():
                raise
            payload = portable_path.read_bytes()
            expected = str(receipt.get("sha256", ""))
            if hashlib.sha256(payload).hexdigest() != expected:
                raise ValueError("portable snapshot does not match durable persistence receipt")
            self.portable_fallback_used = True
            return payload


class PersistentEnterpriseMemoryService(EnterpriseMemoryService):
    """Product facade with selectable BDR/SQLite snapshot durability."""

    def __init__(
        self,
        organization: OrganizationIdentity,
        memory=None,
        entries=None,
        *,
        persistence: ProductSnapshotPersistence,
    ) -> None:
        super().__init__(organization, memory, entries)
        self.persistence = persistence

    @property
    def statistics(self) -> dict[str, int | float | str | bool | None]:
        stats = dict(super().statistics)
        stats["persistence_backend"] = self.persistence.last_backend or self.persistence.backend or "auto"
        stats["portable_snapshot_fallback"] = self.persistence.portable_fallback_used
        return stats

    def save(self, directory: str | Path) -> None:
        super().save(directory)
        root = Path(directory)
        snapshot = root / "memory.snapshot"
        receipt = self.persistence.store_bytes(snapshot.read_bytes())
        data = _read_manifest(root / "enterprise.manifest.json")
        data["persistence"] = receipt.as_dict()
        _atomic_write(root / "enterprise.manifest.json", _manifest_bytes(data))

    @classmethod
    def load(
        cls,
        directory: str | Path,
        *,
        persistence: ProductSnapshotPersistence,
    ) -> "PersistentEnterpriseMemoryService":
        root = Path(directory)
        data = _read_manifest(root / "enterprise.manifest.json")
        receipt = data.get("persistence")
        snapshot_path = root / data["snapshot"]

        if isinstance(receipt, dict):
            payload = persistence.restore_or_portable_fallback(receipt, snapshot_path)
            with tempfile.TemporaryDirectory(prefix="memoria-product-load-") as tmp:
                staged = Path(tmp) / "memory.snapshot"
                _atomic_write(staged, payload)
                from .api_v90 import ResolutiveMemoryAPI
                memory = ResolutiveMemoryAPI.load(staged)
        else:
            from .api_v90 import ResolutiveMemoryAPI
            memory = ResolutiveMemoryAPI.load(snapshot_path)

        org_data = data["organization"]
        organization = OrganizationIdentity(
            organization_id=org_data["organization_id"],
            display_name=org_data.get("display_name"),
        )
        from .product_service import _LogicalEntry
        entries = {
            key: _LogicalEntry(
                knowledge_id=row["knowledge_id"],
                latest_version=int(row["latest_version"]),
                revoked=bool(row.get("revoked", False)),
            )
            for key, row in data.get("entries", {}).items()
        }
        return cls(organization, memory, entries, persistence=persistence)
