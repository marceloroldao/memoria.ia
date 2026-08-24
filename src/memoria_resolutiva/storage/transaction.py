from __future__ import annotations

import base64
import json
import uuid
from dataclasses import dataclass
from typing import Iterable

from .base import BinaryKV


class StorageConflictError(RuntimeError):
    pass


class StorageIntegrityError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class TxEntry:
    key: str
    previous: bytes | None

    def to_json(self) -> dict:
        return {
            "key": self.key,
            "previous": None if self.previous is None else base64.b64encode(self.previous).decode("ascii"),
        }

    @classmethod
    def from_json(cls, data: dict) -> "TxEntry":
        raw = data.get("previous")
        return cls(str(data["key"]), None if raw is None else base64.b64decode(raw))


@dataclass(frozen=True, slots=True)
class TxManifest:
    tx_id: str
    entries: tuple[TxEntry, ...]

    @property
    def keys(self) -> tuple[str, ...]:
        return tuple(entry.key for entry in self.entries)

    def encode(self) -> bytes:
        return json.dumps(
            {"tx_id": self.tx_id, "entries": [entry.to_json() for entry in self.entries]},
            sort_keys=True,
            separators=(",", ":"),
        ).encode()

    @classmethod
    def decode(cls, raw: bytes) -> "TxManifest":
        data = json.loads(raw.decode())
        return cls(str(data["tx_id"]), tuple(TxEntry.from_json(row) for row in data["entries"]))


class TransactionWriter:
    """External transaction protocol layered on durable KV operations.

    Commit is the visibility boundary. The manifest records previous values so
    recovery can restore an interrupted update rather than deleting valid data.
    """

    def __init__(self, db: BinaryKV):
        self.db = db

    def write(self, entries: Iterable[tuple[str, bytes]], *, tx_id: str | None = None) -> str:
        tx_id = tx_id or uuid.uuid4().hex
        rows = tuple(entries)
        seen: set[str] = set()
        if any(key in seen or seen.add(key) for key, _ in rows):
            raise ValueError("transaction contains duplicate keys")
        manifest = TxManifest(
            tx_id,
            tuple(TxEntry(key, self.db.get(key)) for key, _ in rows),
        )
        prefix = f"tx:{tx_id}"
        self.db.put_sync(f"{prefix}:begin", b"1")
        self.db.put_sync(f"{prefix}:manifest", manifest.encode())
        for key, value in rows:
            self.db.put_sync(key, value)
        self.db.put_sync(f"{prefix}:commit", b"1")
        return tx_id

    def rollback(self, tx_id: str) -> None:
        prefix = f"tx:{tx_id}"
        raw = self.db.get(f"{prefix}:manifest")
        if raw is not None:
            manifest = TxManifest.decode(raw)
            for entry in manifest.entries:
                if entry.previous is None:
                    self.db.delete_sync(entry.key)
                else:
                    self.db.put_sync(entry.key, entry.previous)
        for suffix in ("commit", "manifest", "begin"):
            self.db.delete_sync(f"{prefix}:{suffix}")

    def validate_committed(self, tx_id: str) -> TxManifest:
        prefix = f"tx:{tx_id}"
        committed = self.db.get(f"{prefix}:commit") is not None
        raw = self.db.get(f"{prefix}:manifest")
        if not committed:
            raise StorageIntegrityError(f"transaction {tx_id} is not committed")
        if raw is None:
            raise StorageIntegrityError(f"transaction {tx_id} commit has no manifest")
        manifest = TxManifest.decode(raw)
        missing = [key for key in manifest.keys if self.db.get(key) is None]
        if missing:
            raise StorageIntegrityError(f"transaction {tx_id} committed with missing keys: {missing}")
        return manifest
