from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Protocol

from .address_trajectory_v2 import AddressTrajectory, AddressTrajectoryMemory


_SCHEMA_VERSION = 1
_ROOT_KEY = b"memoria.address_trajectory.v2/root"
_TRAJECTORY_PREFIX = b"memoria.address_trajectory.v2/trajectory/"


class AtomicBytesBackend(Protocol):
    def write_batch(self, puts: list[tuple[bytes, bytes]]) -> int: ...
    def get(self, key: bytes) -> bytes | None: ...


@dataclass(frozen=True, slots=True)
class AddressTrajectoryBDRStats:
    trajectories: int
    physical_records: int
    bdr_sequence: int


def _encode(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _decode(data: bytes | None, key: bytes) -> object:
    if data is None:
        raise ValueError(f"missing BDR record: {key!r}")
    try:
        return json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid BDR JSON record: {key!r}") from exc


def _trajectory_key(trajectory_id: int) -> bytes:
    return _TRAJECTORY_PREFIX + f"{trajectory_id:020d}".encode("ascii")


def save_address_trajectory_snapshot(
    backend: AtomicBytesBackend,
    memory: AddressTrajectoryMemory,
) -> AddressTrajectoryBDRStats:
    """Persist one V2 snapshot as one logical atomic BDR batch.

    This adapter owns only the V2 byte schema. It deliberately does not add
    entity, temporal CURRENT/HISTORY or epistemic semantics.
    """
    snapshot = memory.snapshot()
    puts: list[tuple[bytes, bytes]] = []
    trajectory_keys: list[str] = []

    for trajectory in snapshot:
        key = _trajectory_key(trajectory.trajectory_id)
        trajectory_keys.append(key.decode("ascii"))
        puts.append((key, _encode({
            "trajectory_id": trajectory.trajectory_id,
            "raw_text": trajectory.raw_text,
            "addresses": list(trajectory.addresses),
            "surfaces": list(trajectory.surfaces),
        })))

    puts.append((_ROOT_KEY, _encode({
        "schema_version": _SCHEMA_VERSION,
        "trajectory_keys": trajectory_keys,
        "trajectory_count": len(snapshot),
    })))
    sequence = backend.write_batch(puts)
    return AddressTrajectoryBDRStats(
        trajectories=len(snapshot),
        physical_records=len(puts),
        bdr_sequence=sequence,
    )


def load_address_trajectory_snapshot(
    backend: AtomicBytesBackend,
) -> AddressTrajectoryMemory:
    manifest = _decode(backend.get(_ROOT_KEY), _ROOT_KEY)
    if not isinstance(manifest, dict):
        raise ValueError("invalid Address-Trajectory V2 BDR manifest")
    if int(manifest.get("schema_version", 0)) != _SCHEMA_VERSION:
        raise ValueError("unsupported Address-Trajectory V2 BDR schema version")

    keys = manifest.get("trajectory_keys", [])
    if not isinstance(keys, list):
        raise ValueError("invalid trajectory key list")

    trajectories: list[AddressTrajectory] = []
    for raw_key in keys:
        if not isinstance(raw_key, str):
            raise ValueError("invalid trajectory key")
        key = raw_key.encode("ascii")
        record = _decode(backend.get(key), key)
        if not isinstance(record, dict):
            raise ValueError(f"invalid trajectory record: {raw_key}")
        trajectories.append(AddressTrajectory(
            trajectory_id=int(record["trajectory_id"]),
            raw_text=str(record["raw_text"]),
            addresses=tuple(str(item) for item in record.get("addresses", [])),
            surfaces=tuple(str(item) for item in record.get("surfaces", [])),
        ))

    expected = int(manifest.get("trajectory_count", len(trajectories)))
    if expected != len(trajectories):
        raise ValueError("incomplete Address-Trajectory V2 BDR snapshot")

    memory = AddressTrajectoryMemory()
    memory.restore(trajectories)
    return memory
