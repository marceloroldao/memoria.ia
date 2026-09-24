from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
from threading import RLock
from typing import Any

from .structural_observation import StructuralObservationStore
from .structural_state_persistence import ContentAddressedStatePersistence
from .structural_trajectory_v2 import StructuralTrajectory, StructuralTrajectoryIndex


BIT_ANALYZE_REALITY_SLICE_SCHEMA = "bit-analyze-reality-slice-structural/v1"
REALITY_SLICE_OBSERVATION_FORMAT = "memoria.ia-bit-analyze-reality-slice-v2"
REALITY_SLICE_INDEX_FORMAT = "memoria.ia-bit-analyze-reality-slice-index-v2"


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _normalize_reality_slice(row: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(row, dict) or row.get("schema") != BIT_ANALYZE_REALITY_SLICE_SCHEMA:
        raise ValueError("unsupported bit.analyze RealitySlice schema")
    source_id = str(row.get("source_id") or "").strip()
    if not source_id:
        raise ValueError("RealitySlice source_id is required")
    slice_id = int(row.get("slice_id", -1))
    if slice_id < 0:
        raise ValueError("RealitySlice slice_id must be >= 0")
    if row.get("semantic_projection") is not False:
        raise ValueError("RealitySlice must remain pre-semantic")

    temporal = row.get("temporal")
    if not isinstance(temporal, dict):
        raise ValueError("RealitySlice temporal envelope is required")
    clock_id = str(temporal.get("clock_id") or "").strip()
    if not clock_id:
        raise ValueError("RealitySlice clock_id is required")
    t_start = float(temporal.get("t_start"))
    t_end = float(temporal.get("t_end"))
    if not math.isfinite(t_start) or not math.isfinite(t_end) or t_end < t_start:
        raise ValueError("invalid RealitySlice temporal window")
    unit = str(temporal.get("unit") or "").strip()
    if not unit:
        raise ValueError("RealitySlice temporal unit is required")

    trail_raw = row.get("trail")
    occurrences_raw = row.get("occurrences")
    provenance_raw = row.get("slice_provenance", ())
    if not isinstance(trail_raw, list) or not isinstance(occurrences_raw, list):
        raise ValueError("RealitySlice trail and occurrences must be lists")
    if len(trail_raw) != len(occurrences_raw):
        raise ValueError("RealitySlice trail/occurrence cardinality mismatch")

    trail: list[int] = []
    occurrences: list[dict[str, object]] = []
    for index, raw in enumerate(occurrences_raw):
        if not isinstance(raw, dict):
            raise ValueError("RealitySlice occurrence must be an object")
        pattern = int(raw.get("pattern", -1))
        trail_pattern = int(trail_raw[index])
        if pattern < 0 or trail_pattern < 0:
            raise ValueError("RealitySlice pattern ids must be >= 0")
        if pattern != trail_pattern:
            raise ValueError("RealitySlice trail must match occurrence order")
        dt_start = float(raw.get("dt_start"))
        dt_end = float(raw.get("dt_end"))
        if not math.isfinite(dt_start) or not math.isfinite(dt_end) or dt_end < dt_start:
            raise ValueError("invalid RealitySlice occurrence interval")
        if dt_start < 0 or t_start + dt_end > t_end + 1e-12:
            raise ValueError("RealitySlice occurrence outside slice window")
        source = int(raw.get("source", 0))
        provenance = int(raw.get("provenance", 0))
        trail.append(pattern)
        occurrences.append(
            {
                "pattern": pattern,
                "dt_start": dt_start,
                "dt_end": dt_end,
                "source": source,
                "provenance": provenance,
            }
        )

    slice_provenance = [int(value) for value in provenance_raw]
    core = {
        "schema": BIT_ANALYZE_REALITY_SLICE_SCHEMA,
        "source_id": source_id,
        "slice_id": slice_id,
        "trail": trail,
        "occurrences": occurrences,
        "slice_provenance": slice_provenance,
        "temporal": {
            "clock_id": clock_id,
            "t_start": t_start,
            "t_end": t_end,
            "unit": unit,
        },
        "semantic_projection": False,
    }
    expected = hashlib.blake2b(_canonical_json(core), digest_size=20).hexdigest()
    supplied = str(row.get("signature") or "").strip().lower()
    if supplied != expected:
        raise ValueError("RealitySlice structural signature mismatch")
    core["signature"] = expected
    return core


def _observation_id(*, hierarchy_id: str, structural_signature: str) -> str:
    payload = {
        "format": REALITY_SLICE_OBSERVATION_FORMAT,
        "hierarchy_id": hierarchy_id,
        "structural_signature": structural_signature,
    }
    return "reality-slice-observation:" + hashlib.blake2b(
        _canonical_json(payload),
        digest_size=20,
    ).hexdigest()


class RealitySliceObservationStoreV2:
    """Durable intake for bit.analyze structural RealitySlice envelopes.

    The upstream envelope remains intact and distinct from byte-oriented
    StructuralEvent. Memoria.ia only adds hierarchy/admission identity around it.
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
        self.index_path = self.root / "index.jsonl"
        self.persistence = ContentAddressedStatePersistence(
            self.root / "persistence",
            namespace="bit-analyze-reality-slice-v2",
            backend=backend,
            allow_fallback=allow_fallback,
        )
        self._lock = RLock()
        self._entries: dict[str, dict[str, object]] = {}
        self._order: list[str] = []
        self._load_index()

    def _load_index(self) -> None:
        if not self.index_path.is_file():
            return
        for line_number, line in enumerate(self.index_path.read_text("utf-8").splitlines(), start=1):
            if not line.strip():
                continue
            row = json.loads(line)
            if not isinstance(row, dict) or row.get("format") != REALITY_SLICE_INDEX_FORMAT:
                raise ValueError(f"unsupported RealitySlice index at line {line_number}")
            observation_id = str(row.get("observation_id") or "")
            receipt = row.get("receipt")
            if not observation_id or not isinstance(receipt, dict):
                raise ValueError(f"invalid RealitySlice index at line {line_number}")
            existing = self._entries.get(observation_id)
            if existing is not None:
                if existing != row:
                    raise ValueError("conflicting duplicate RealitySlice index entry")
                continue
            self._entries[observation_id] = row
            self._order.append(observation_id)

    @property
    def count(self) -> int:
        return len(self._order)

    def append(
        self,
        structural_slice: dict[str, Any],
        *,
        hierarchy_id: str,
    ) -> tuple[dict[str, object], bool]:
        hierarchy = str(hierarchy_id).strip()
        if not hierarchy:
            raise ValueError("hierarchy_id must be non-empty")
        normalized = _normalize_reality_slice(structural_slice)
        observation_id = _observation_id(
            hierarchy_id=hierarchy,
            structural_signature=str(normalized["signature"]),
        )
        envelope: dict[str, object] = {
            "format": REALITY_SLICE_OBSERVATION_FORMAT,
            "observation_id": observation_id,
            "hierarchy_id": hierarchy,
            "structural_slice": normalized,
            "semantic_projection": False,
        }
        payload = _canonical_json(envelope)

        with self._lock:
            existing = self._entries.get(observation_id)
            if existing is not None:
                stored = self.get(observation_id)
                if _canonical_json(stored) != payload:
                    raise ValueError("same RealitySlice observation arrived with conflicting payload")
                return stored, True

            receipt = self.persistence.store_bytes(payload)
            row = {
                "format": REALITY_SLICE_INDEX_FORMAT,
                "observation_id": observation_id,
                "receipt": receipt.as_dict(),
            }
            with self.index_path.open("a", encoding="utf-8", newline="\n") as fh:
                fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")
                fh.flush()
                os.fsync(fh.fileno())
            self._entries[observation_id] = row
            self._order.append(observation_id)
            return envelope, False

    def get(self, observation_id: str) -> dict[str, object]:
        with self._lock:
            row = self._entries.get(str(observation_id))
            if row is None:
                raise KeyError(observation_id)
            payload = self.persistence.load_bytes(row["receipt"])
        envelope = json.loads(payload.decode("utf-8"))
        if envelope.get("format") != REALITY_SLICE_OBSERVATION_FORMAT:
            raise ValueError("unsupported RealitySlice observation format")
        if envelope.get("observation_id") != observation_id:
            raise ValueError("RealitySlice observation identity mismatch")
        return envelope

    def ordered_from(self, offset: int = 0) -> tuple[dict[str, object], ...]:
        if offset < 0:
            raise ValueError("offset must be >= 0")
        with self._lock:
            ids = tuple(self._order[offset:])
        return tuple(self.get(observation_id) for observation_id in ids)


class BitAnalyzeConvergenceV2:
    """Converge byte events and temporal slices on one trajectory substrate.

    Input schemas remain distinct. Only their opaque structural address trails
    converge into StructuralTrajectoryIndex.
    """

    def __init__(
        self,
        *,
        structural_events: StructuralObservationStore,
        reality_slices: RealitySliceObservationStoreV2,
        trajectories: StructuralTrajectoryIndex,
    ) -> None:
        self.structural_events = structural_events
        self.reality_slices = reality_slices
        self.trajectories = trajectories

    def ingest_structural_event(
        self,
        event: dict[str, Any],
        *,
        hierarchy_id: str,
        provenance: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any], StructuralTrajectory, bool]:
        hierarchy = str(hierarchy_id).strip()
        if not hierarchy:
            raise ValueError("hierarchy_id must be non-empty")
        metadata = {} if provenance is None else dict(provenance)
        metadata["hierarchy_id"] = hierarchy
        envelope, repeated = self.structural_events.append(
            event,
            provenance=metadata,
        )
        normalized_event = envelope["event"]
        trajectory = self.trajectories.ingest_addresses(
            normalized_event["trail"],
            hierarchy_id=hierarchy,
            source_id=str(normalized_event["source_id"]),
            sequence=int(normalized_event["sequence"]),
            observation_id=str(envelope["observation_id"]),
        )
        return envelope, trajectory, repeated

    def ingest_reality_slice(
        self,
        structural_slice: dict[str, Any],
        *,
        hierarchy_id: str,
    ) -> tuple[dict[str, object], StructuralTrajectory, bool]:
        envelope, repeated = self.reality_slices.append(
            structural_slice,
            hierarchy_id=hierarchy_id,
        )
        row = envelope["structural_slice"]
        assert isinstance(row, dict)
        trajectory = self.trajectories.ingest_addresses(
            row["trail"],
            hierarchy_id=str(envelope["hierarchy_id"]),
            source_id="bit-analyze-reality-slice:" + str(row["source_id"]),
            sequence=int(row["slice_id"]),
            observation_id=str(envelope["observation_id"]),
        )
        return envelope, trajectory, repeated

    def replay(self) -> int:
        before = self.trajectories.count
        for envelope in self.structural_events.ordered_from(0):
            event = envelope["event"]
            provenance = envelope["provenance"]
            if not isinstance(event, dict) or not isinstance(provenance, dict):
                raise ValueError("invalid StructuralEvent observation envelope")
            hierarchy = str(provenance.get("hierarchy_id") or "").strip()
            if not hierarchy:
                raise ValueError("StructuralEvent replay requires hierarchy_id")
            self.trajectories.ingest_addresses(
                event["trail"],
                hierarchy_id=hierarchy,
                source_id=str(event["source_id"]),
                sequence=int(event["sequence"]),
                observation_id=str(envelope["observation_id"]),
            )
        for envelope in self.reality_slices.ordered_from(0):
            row = envelope["structural_slice"]
            if not isinstance(row, dict):
                raise ValueError("invalid RealitySlice observation envelope")
            self.trajectories.ingest_addresses(
                row["trail"],
                hierarchy_id=str(envelope["hierarchy_id"]),
                source_id="bit-analyze-reality-slice:" + str(row["source_id"]),
                sequence=int(row["slice_id"]),
                observation_id=str(envelope["observation_id"]),
            )
        return self.trajectories.count - before
