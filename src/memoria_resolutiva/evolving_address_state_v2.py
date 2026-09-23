from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
from threading import RLock
from typing import Iterable

from .structural_state_persistence import ContentAddressedStatePersistence


EVOLVING_ADDRESS_REVISION_FORMAT = "memoria.ia-evolving-address-revision-v2"
EVOLVING_ADDRESS_INDEX_FORMAT = "memoria.ia-evolving-address-index-v2"


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _opaque_addresses(values: Iterable[int]) -> tuple[int, ...]:
    out: list[int] = []
    for raw in values:
        value = int(raw)
        if value < 0:
            raise ValueError("opaque addresses must be >= 0")
        out.append(value)
    return tuple(out)


def _stable_unique_strings(values: Iterable[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    out: list[str] = []
    for raw in values:
        value = str(raw).strip()
        if not value:
            raise ValueError("reference identifiers must be non-empty")
        if value not in seen:
            seen.add(value)
            out.append(value)
    return tuple(out)


@dataclass(frozen=True, slots=True)
class AddressStateRevision:
    revision_id: str
    hierarchy_id: str
    address: int
    sequence: int
    payload_addresses: tuple[int, ...]
    trajectory_ids: tuple[str, ...]
    provenance_ids: tuple[str, ...]
    predecessor_revision_id: str | None

    def as_dict(self) -> dict[str, object]:
        return {
            "format": EVOLVING_ADDRESS_REVISION_FORMAT,
            "revision_id": self.revision_id,
            "hierarchy_id": self.hierarchy_id,
            "address": self.address,
            "sequence": self.sequence,
            "payload_addresses": list(self.payload_addresses),
            "trajectory_ids": list(self.trajectory_ids),
            "provenance_ids": list(self.provenance_ids),
            "predecessor_revision_id": self.predecessor_revision_id,
        }


def _revision_id(
    *,
    hierarchy_id: str,
    address: int,
    sequence: int,
    payload_addresses: tuple[int, ...],
    trajectory_ids: tuple[str, ...],
    provenance_ids: tuple[str, ...],
    predecessor_revision_id: str | None,
) -> str:
    payload = {
        "format": EVOLVING_ADDRESS_REVISION_FORMAT,
        "hierarchy_id": hierarchy_id,
        "address": address,
        "sequence": sequence,
        "payload_addresses": list(payload_addresses),
        "trajectory_ids": list(trajectory_ids),
        "provenance_ids": list(provenance_ids),
        "predecessor_revision_id": predecessor_revision_id,
    }
    return "address-revision:" + hashlib.blake2b(
        _canonical_json(payload),
        digest_size=20,
    ).hexdigest()


class EvolvingAddressStateJournalV2:
    """Append-only revisions for a stable opaque address.

    current_revision means the most recently admitted revision for navigation,
    not a truth verdict. Competing evidence remains elsewhere in provenance and
    trajectory memory for later attractor/inference layers.
    """

    def __init__(self) -> None:
        self._history: dict[tuple[str, int], list[AddressStateRevision]] = {}
        self._by_id: dict[str, AddressStateRevision] = {}

    @property
    def revision_count(self) -> int:
        return len(self._by_id)

    def _key(self, hierarchy_id: str, address: int) -> tuple[str, int]:
        hierarchy = str(hierarchy_id).strip()
        if not hierarchy:
            raise ValueError("hierarchy_id must be non-empty")
        opaque = int(address)
        if opaque < 0:
            raise ValueError("address must be >= 0")
        return hierarchy, opaque

    def append(
        self,
        address: int,
        *,
        hierarchy_id: str,
        sequence: int,
        payload_addresses: Iterable[int] = (),
        trajectory_ids: Iterable[str] = (),
        provenance_ids: Iterable[str] = (),
    ) -> AddressStateRevision:
        key = self._key(hierarchy_id, address)
        sequence = int(sequence)
        if sequence < 0:
            raise ValueError("sequence must be >= 0")
        history = self._history.setdefault(key, [])
        predecessor = None if not history else history[-1].revision_id
        payload = _opaque_addresses(payload_addresses)
        trajectories = _stable_unique_strings(trajectory_ids)
        provenance = _stable_unique_strings(provenance_ids)
        revision_id = _revision_id(
            hierarchy_id=key[0],
            address=key[1],
            sequence=sequence,
            payload_addresses=payload,
            trajectory_ids=trajectories,
            provenance_ids=provenance,
            predecessor_revision_id=predecessor,
        )
        candidate = AddressStateRevision(
            revision_id=revision_id,
            hierarchy_id=key[0],
            address=key[1],
            sequence=sequence,
            payload_addresses=payload,
            trajectory_ids=trajectories,
            provenance_ids=provenance,
            predecessor_revision_id=predecessor,
        )

        if history and sequence < history[-1].sequence:
            raise ValueError("address revision sequence cannot move backward")
        if history and sequence == history[-1].sequence:
            if candidate == history[-1]:
                return history[-1]
            raise ValueError("same address sequence cannot contain conflicting revisions")

        existing = self._by_id.get(revision_id)
        if existing is not None:
            if existing != candidate:
                raise ValueError("address revision id collision")
            return existing

        history.append(candidate)
        self._by_id[revision_id] = candidate
        return candidate

    def restore(self, revisions: Iterable[AddressStateRevision]) -> None:
        if self._by_id or self._history:
            raise ValueError("address state journal must be empty before restore")
        for item in revisions:
            restored = self.append(
                item.address,
                hierarchy_id=item.hierarchy_id,
                sequence=item.sequence,
                payload_addresses=item.payload_addresses,
                trajectory_ids=item.trajectory_ids,
                provenance_ids=item.provenance_ids,
            )
            if restored != item:
                raise ValueError("address state revision history is not canonical")

    def current_revision(self, address: int, *, hierarchy_id: str) -> AddressStateRevision | None:
        history = self._history.get(self._key(hierarchy_id, address), ())
        return None if not history else history[-1]

    def history(self, address: int, *, hierarchy_id: str) -> tuple[AddressStateRevision, ...]:
        return tuple(self._history.get(self._key(hierarchy_id, address), ()))

    def previous_revision(self, revision_id: str) -> AddressStateRevision | None:
        revision = self._by_id.get(str(revision_id))
        if revision is None or revision.predecessor_revision_id is None:
            return None
        return self._by_id.get(revision.predecessor_revision_id)

    def next_revision(self, revision_id: str) -> AddressStateRevision | None:
        revision = self._by_id.get(str(revision_id))
        if revision is None:
            return None
        history = self._history[(revision.hierarchy_id, revision.address)]
        index = history.index(revision)
        return None if index + 1 >= len(history) else history[index + 1]

    def snapshot(self) -> tuple[AddressStateRevision, ...]:
        return tuple(
            revision
            for key in sorted(self._history)
            for revision in self._history[key]
        )


class PersistentEvolvingAddressStateJournalV2:
    """Durable append-only address revision journal with BDR/SQLite payloads.

    Each immutable revision is written to durable storage before its receipt is
    appended and fsynced to the local journal index. Cold reopen reconstructs the
    acknowledged revision sequence without destructive overwrite.
    """

    def __init__(
        self,
        root: str | Path,
        *,
        backend: str | None = None,
        allow_fallback: bool = True,
    ) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.index_path = self.root / "revisions.jsonl"
        self.persistence = ContentAddressedStatePersistence(
            self.root / "persistence",
            namespace="evolving-address-revision-v2",
            backend=backend,
            allow_fallback=allow_fallback,
        )
        self._lock = RLock()
        self.journal = EvolvingAddressStateJournalV2()
        self._rows: list[dict[str, object]] = []
        self._load()

    @staticmethod
    def _decode_revision(payload: bytes) -> AddressStateRevision:
        row = json.loads(payload.decode("utf-8"))
        if not isinstance(row, dict) or row.get("format") != EVOLVING_ADDRESS_REVISION_FORMAT:
            raise ValueError("unsupported evolving address revision format")
        predecessor = row.get("predecessor_revision_id")
        return AddressStateRevision(
            revision_id=str(row.get("revision_id") or ""),
            hierarchy_id=str(row.get("hierarchy_id") or ""),
            address=int(row.get("address", -1)),
            sequence=int(row.get("sequence", -1)),
            payload_addresses=tuple(int(value) for value in row.get("payload_addresses", ())),
            trajectory_ids=tuple(str(value) for value in row.get("trajectory_ids", ())),
            provenance_ids=tuple(str(value) for value in row.get("provenance_ids", ())),
            predecessor_revision_id=None if predecessor is None else str(predecessor),
        )

    def _load(self) -> None:
        if not self.index_path.is_file():
            return
        revisions: list[AddressStateRevision] = []
        for line_number, line in enumerate(self.index_path.read_text("utf-8").splitlines(), start=1):
            if not line.strip():
                continue
            row = json.loads(line)
            if not isinstance(row, dict) or row.get("format") != EVOLVING_ADDRESS_INDEX_FORMAT:
                raise ValueError(f"unsupported evolving address index at line {line_number}")
            receipt = row.get("receipt")
            if not isinstance(receipt, dict):
                raise ValueError(f"invalid evolving address receipt at line {line_number}")
            payload = self.persistence.load_bytes(receipt)
            revision = self._decode_revision(payload)
            if revision.revision_id != str(row.get("revision_id") or ""):
                raise ValueError("evolving address index revision mismatch")
            revisions.append(revision)
            self._rows.append(row)
        self.journal.restore(revisions)

    def append(
        self,
        address: int,
        *,
        hierarchy_id: str,
        sequence: int,
        payload_addresses: Iterable[int] = (),
        trajectory_ids: Iterable[str] = (),
        provenance_ids: Iterable[str] = (),
    ) -> AddressStateRevision:
        with self._lock:
            before = self.journal.revision_count
            candidate = self.journal.append(
                address,
                hierarchy_id=hierarchy_id,
                sequence=sequence,
                payload_addresses=payload_addresses,
                trajectory_ids=trajectory_ids,
                provenance_ids=provenance_ids,
            )
            if self.journal.revision_count == before:
                return candidate

            payload = _canonical_json(candidate.as_dict())
            try:
                receipt = self.persistence.store_bytes(payload)
                row = {
                    "format": EVOLVING_ADDRESS_INDEX_FORMAT,
                    "revision_id": candidate.revision_id,
                    "receipt": receipt.as_dict(),
                }
                with self.index_path.open("a", encoding="utf-8", newline="\n") as fh:
                    fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")
                    fh.flush()
                    os.fsync(fh.fileno())
                self._rows.append(row)
                return candidate
            except Exception:
                self.journal = EvolvingAddressStateJournalV2()
                revisions = [
                    self._decode_revision(self.persistence.load_bytes(row["receipt"]))
                    for row in self._rows
                ]
                self.journal.restore(revisions)
                raise

    def current_revision(self, address: int, *, hierarchy_id: str) -> AddressStateRevision | None:
        with self._lock:
            return self.journal.current_revision(address, hierarchy_id=hierarchy_id)

    def history(self, address: int, *, hierarchy_id: str) -> tuple[AddressStateRevision, ...]:
        with self._lock:
            return self.journal.history(address, hierarchy_id=hierarchy_id)

    def previous_revision(self, revision_id: str) -> AddressStateRevision | None:
        with self._lock:
            return self.journal.previous_revision(revision_id)

    def next_revision(self, revision_id: str) -> AddressStateRevision | None:
        with self._lock:
            return self.journal.next_revision(revision_id)

    @property
    def backend(self) -> str:
        return self.persistence.last_backend or self.persistence.backend or "auto"
