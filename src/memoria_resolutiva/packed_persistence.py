from __future__ import annotations

import json
import os
import tempfile
import zlib
from pathlib import Path

from .packed_lifecycle import PackedLayerState, PackedMemoryLifecycle


FORMAT = "memoria.ia-packed-v1"


def _payload(memory: PackedMemoryLifecycle) -> dict:
    return {
        "format": FORMAT,
        "levels": memory.levels,
        "activate_threshold": memory.activate_threshold,
        "deactivate_threshold": memory.deactivate_threshold,
        "time": memory.time,
        "items": {
            str(key): [
                {
                    "level": s.level,
                    "strength": s.strength,
                    "active": s.active,
                    "ever_active": s.ever_active,
                    "activation_count": s.activation_count,
                    "deactivation_count": s.deactivation_count,
                    "last_transition_time": s.last_transition_time,
                    "last_transition_kind": s.last_transition_kind,
                    "last_transition_strength": s.last_transition_strength,
                }
                for s in states
            ]
            for key, states in memory._items.items()
        },
    }


def encode_snapshot(memory: PackedMemoryLifecycle) -> bytes:
    raw = json.dumps(_payload(memory), sort_keys=True, separators=(",", ":")).encode("utf-8")
    crc = zlib.crc32(raw) & 0xFFFFFFFF
    envelope = {
        "format": FORMAT,
        "crc32": crc,
        "payload": raw.decode("utf-8"),
    }
    return json.dumps(envelope, sort_keys=True, separators=(",", ":")).encode("utf-8")


def decode_snapshot(blob: bytes) -> PackedMemoryLifecycle:
    envelope = json.loads(blob.decode("utf-8"))
    if envelope.get("format") != FORMAT:
        raise ValueError("unsupported snapshot format")
    raw = envelope["payload"].encode("utf-8")
    expected = int(envelope["crc32"])
    actual = zlib.crc32(raw) & 0xFFFFFFFF
    if actual != expected:
        raise ValueError("snapshot checksum mismatch")
    data = json.loads(raw.decode("utf-8"))
    if data.get("format") != FORMAT:
        raise ValueError("payload format mismatch")

    m = PackedMemoryLifecycle(
        levels=int(data["levels"]),
        activate_threshold=float(data["activate_threshold"]),
        deactivate_threshold=float(data["deactivate_threshold"]),
    )
    m.time = int(data["time"])
    for key, rows in data["items"].items():
        states = []
        for row in rows:
            states.append(PackedLayerState(
                level=int(row["level"]),
                strength=float(row["strength"]),
                active=bool(row["active"]),
                ever_active=bool(row["ever_active"]),
                activation_count=int(row["activation_count"]),
                deactivation_count=int(row["deactivation_count"]),
                last_transition_time=int(row["last_transition_time"]),
                last_transition_kind=int(row["last_transition_kind"]),
                last_transition_strength=float(row["last_transition_strength"]),
            ))
        if len(states) != m.levels:
            raise ValueError("snapshot layer count mismatch")
        m._items[key] = states
    return m


def save_snapshot(memory: PackedMemoryLifecycle, path: str | os.PathLike[str]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    blob = encode_snapshot(memory)
    fd, tmp_name = tempfile.mkstemp(prefix=target.name + ".", suffix=".tmp", dir=target.parent)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(blob)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_name, target)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)


def load_snapshot(path: str | os.PathLike[str]) -> PackedMemoryLifecycle:
    return decode_snapshot(Path(path).read_bytes())
