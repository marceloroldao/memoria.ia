from __future__ import annotations

import json
import os
from pathlib import Path
from threading import RLock
from typing import Any

from .structural_observation import StructuralObservationStore
from .structural_state_persistence import ContentAddressedStatePersistence
from .structural_trajectory_v2 import StructuralTrajectory, StructuralTrajectoryIndex


STRUCTURAL_TRAJECTORY_RUNTIME_FORMAT = "memoria.ia-structural-trajectory-runtime-v2"
STRUCTURAL_TRAJECTORY_POINTER_FORMAT = "memoria.ia-structural-trajectory-pointer-v2"


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


class PersistentStructuralTrajectoryRuntimeV2:
    """Durable derived trajectory state over canonical StructuralObservation rows.

    StructuralObservationStore remains authoritative. The checkpoint carries a
    cursor into that append-only sequence; cold reopen replays only the missing
    suffix instead of guessing or rebuilding from a mutable semantic projection.
    """

    def __init__(
        self,
        observations: StructuralObservationStore,
        root: str | Path,
        *,
        backend: str | None = None,
        allow_fallback: bool = True,
    ) -> None:
        self.observations = observations
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.pointer_path = self.root / "current.json"
        self.persistence = ContentAddressedStatePersistence(
            self.root / "persistence",
            namespace="structural-trajectory-runtime-v2",
            backend=backend,
            allow_fallback=allow_fallback,
        )
        self._lock = RLock()
        self.index = StructuralTrajectoryIndex()
        self.cursor_count = 0
        self.cursor_observation_id: str | None = None
        self.replayed_on_open = 0
        self._load_if_present()
        self.replayed_on_open = self.sync()

    @staticmethod
    def _serialize_trajectory(item: StructuralTrajectory) -> dict[str, Any]:
        return {
            "trajectory_id": item.trajectory_id,
            "hierarchy_id": item.hierarchy_id,
            "source_id": item.source_id,
            "sequence": item.sequence,
            "addresses": list(item.addresses),
            "observation_id": item.observation_id,
        }

    @staticmethod
    def _deserialize_trajectory(row: object) -> StructuralTrajectory:
        if not isinstance(row, dict):
            raise ValueError("trajectory row must be an object")
        addresses = row.get("addresses")
        if not isinstance(addresses, list):
            raise ValueError("trajectory addresses must be a list")
        return StructuralTrajectory(
            trajectory_id=str(row.get("trajectory_id") or ""),
            hierarchy_id=str(row.get("hierarchy_id") or ""),
            source_id=str(row.get("source_id") or ""),
            sequence=int(row.get("sequence", -1)),
            addresses=tuple(int(value) for value in addresses),
            observation_id=None if row.get("observation_id") is None else str(row.get("observation_id")),
        )

    @staticmethod
    def _parse_cursor(value: object) -> tuple[int, str | None]:
        if not isinstance(value, dict):
            raise ValueError("trajectory cursor must be an object")
        count = int(value.get("count", 0))
        raw_id = value.get("observation_id")
        observation_id = None if raw_id is None else str(raw_id).strip() or None
        if count < 0:
            raise ValueError("trajectory cursor count must be >= 0")
        if count == 0 and observation_id is not None:
            raise ValueError("empty trajectory cursor cannot name an observation")
        if count > 0 and observation_id is None:
            raise ValueError("non-empty trajectory cursor requires observation_id")
        return count, observation_id

    def _validate_cursor(self) -> None:
        if self.cursor_count > self.observations.count:
            raise ValueError("trajectory cursor is ahead of raw observations")
        if self.cursor_count == 0:
            if self.cursor_observation_id is not None:
                raise ValueError("empty trajectory cursor is inconsistent")
            return
        expected = self.observations.observation_id_at(self.cursor_count - 1)
        if expected != self.cursor_observation_id:
            raise ValueError("trajectory cursor does not match raw observation prefix")

    def _payload(self) -> bytes:
        return _canonical_json(
            {
                "format": STRUCTURAL_TRAJECTORY_RUNTIME_FORMAT,
                "cursor": {
                    "count": self.cursor_count,
                    "observation_id": self.cursor_observation_id,
                },
                "trajectories": [
                    self._serialize_trajectory(item)
                    for item in self.index.snapshot()
                ],
            }
        )

    def snapshot_bytes(self) -> bytes:
        with self._lock:
            return self._payload()

    def _load_if_present(self) -> None:
        if not self.pointer_path.is_file():
            return
        pointer = json.loads(self.pointer_path.read_text("utf-8"))
        if not isinstance(pointer, dict) or pointer.get("format") != STRUCTURAL_TRAJECTORY_POINTER_FORMAT:
            raise ValueError("unsupported structural trajectory pointer format")
        receipt = pointer.get("receipt")
        if not isinstance(receipt, dict):
            raise ValueError("structural trajectory pointer receipt is invalid")
        payload = json.loads(self.persistence.load_bytes(receipt).decode("utf-8"))
        if not isinstance(payload, dict) or payload.get("format") != STRUCTURAL_TRAJECTORY_RUNTIME_FORMAT:
            raise ValueError("unsupported structural trajectory runtime format")
        self.cursor_count, self.cursor_observation_id = self._parse_cursor(payload.get("cursor"))
        rows = payload.get("trajectories")
        if not isinstance(rows, list):
            raise ValueError("structural trajectory runtime trajectories must be a list")
        self.index = StructuralTrajectoryIndex.restore(
            tuple(self._deserialize_trajectory(row) for row in rows)
        )
        self._validate_cursor()

    def _checkpoint(self) -> dict[str, str]:
        receipt = self.persistence.store_bytes(self._payload())
        pointer = {
            "format": STRUCTURAL_TRAJECTORY_POINTER_FORMAT,
            "receipt": receipt.as_dict(),
            "cursor": {
                "count": self.cursor_count,
                "observation_id": self.cursor_observation_id,
            },
        }
        temporary = self.pointer_path.with_suffix(".json.tmp")
        with temporary.open("w", encoding="utf-8", newline="\n") as fh:
            fh.write(json.dumps(pointer, ensure_ascii=False, sort_keys=True, indent=2))
            fh.write("\n")
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(temporary, self.pointer_path)
        return receipt.as_dict()

    def sync(self) -> int:
        with self._lock:
            self._validate_cursor()
            pending = self.observations.ordered_from(self.cursor_count)
            if not pending and self.pointer_path.is_file():
                return 0
            added = 0
            for envelope in pending:
                event = envelope.get("event")
                provenance = envelope.get("provenance")
                if not isinstance(event, dict):
                    raise ValueError("structural observation event must be an object")
                if not isinstance(provenance, dict):
                    raise ValueError("structural observation provenance must be an object")
                hierarchy_id = str(provenance.get("hierarchy_id") or "").strip()
                if not hierarchy_id:
                    raise ValueError("structural observation requires provenance.hierarchy_id")
                before = self.index.count
                self.index.ingest_addresses(
                    event.get("trail", ()),
                    hierarchy_id=hierarchy_id,
                    source_id=str(event.get("source_id") or ""),
                    sequence=int(event.get("sequence", -1)),
                    observation_id=str(envelope.get("observation_id") or ""),
                )
                if self.index.count > before:
                    added += 1
                self.cursor_count += 1
                self.cursor_observation_id = str(envelope["observation_id"])
            self._checkpoint()
            return added

    def resolve_addresses(self, addresses, *, hierarchy_id: str, limit: int = 8):
        with self._lock:
            return self.index.resolve_addresses(addresses, hierarchy_id=hierarchy_id, limit=limit)

    def frontier(self, addresses, *, hierarchy_id: str, direction: str = "forward"):
        with self._lock:
            return self.index.frontier(addresses, hierarchy_id=hierarchy_id, direction=direction)

    def status(self) -> dict[str, Any]:
        with self._lock:
            return {
                "schema": STRUCTURAL_TRAJECTORY_RUNTIME_FORMAT,
                "backend": self.persistence.last_backend or self.persistence.backend or "auto",
                "cursor": {
                    "count": self.cursor_count,
                    "observation_id": self.cursor_observation_id,
                },
                "raw_observations": self.observations.count,
                "pending_observations": self.observations.count - self.cursor_count,
                "trajectories": self.index.count,
                "replayed_on_open": self.replayed_on_open,
                "semantic_projection": False,
            }
