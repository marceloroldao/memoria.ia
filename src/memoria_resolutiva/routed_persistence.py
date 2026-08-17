from __future__ import annotations

import json
import os
import tempfile
import zlib
from pathlib import Path

from .multitrajectory import KnowledgeNode
from .routed_lifecycle import RoutedLifecycleMemory
from .saturating_lifecycle import SaturatingLayerState, SaturatingMemoryLifecycle

FORMAT = "memoria.ia-routed-v1"


def _json_safe(value):
    try:
        json.dumps(value)
    except TypeError as exc:
        raise TypeError("payload and trajectory nodes must be JSON-serializable") from exc
    return value


def _payload(memory: RoutedLifecycleMemory) -> dict:
    knowledge = {}
    for kid, node in memory.knowledge._knowledge.items():
        knowledge[str(kid)] = {
            "payload": _json_safe(node.payload),
            "modalities": sorted(node.modalities),
            "provenance": sorted(node.provenance),
            "accesses": int(node.accesses),
        }

    routes = []
    for route, kid in memory.knowledge._routes.items():
        lifecycle = memory._route_lifecycle[route]
        states = lifecycle._items.get("route", lifecycle._states("route"))
        routes.append({
            "trajectory": _json_safe(list(route)),
            "knowledge_id": str(kid),
            "time": int(lifecycle.time),
            "states": [
                {
                    "level": int(s.level),
                    "strength": float(s.strength),
                    "active": bool(s.active),
                    "ever_active": bool(s.ever_active),
                    "activation_count": int(s.activation_count),
                    "deactivation_count": int(s.deactivation_count),
                }
                for s in states
            ],
        })

    return {
        "format": FORMAT,
        "levels": int(memory.levels),
        "max_strength": float(memory.max_strength),
        "knowledge": knowledge,
        "routes": routes,
    }


def encode_routed_snapshot(memory: RoutedLifecycleMemory) -> bytes:
    raw = json.dumps(_payload(memory), sort_keys=True, separators=(",", ":")).encode("utf-8")
    crc = zlib.crc32(raw) & 0xFFFFFFFF
    envelope = {"format": FORMAT, "crc32": crc, "payload": raw.decode("utf-8")}
    return json.dumps(envelope, sort_keys=True, separators=(",", ":")).encode("utf-8")


def decode_routed_snapshot(blob: bytes) -> RoutedLifecycleMemory:
    envelope = json.loads(blob.decode("utf-8"))
    if envelope.get("format") != FORMAT:
        raise ValueError("unsupported routed snapshot format")
    raw = envelope["payload"].encode("utf-8")
    if (zlib.crc32(raw) & 0xFFFFFFFF) != int(envelope["crc32"]):
        raise ValueError("routed snapshot checksum mismatch")
    data = json.loads(raw.decode("utf-8"))
    if data.get("format") != FORMAT:
        raise ValueError("routed payload format mismatch")

    memory = RoutedLifecycleMemory(
        levels=int(data["levels"]),
        max_strength=float(data["max_strength"]),
    )

    for kid, row in data["knowledge"].items():
        memory.knowledge._knowledge[kid] = KnowledgeNode(
            knowledge_id=kid,
            payload=row["payload"],
            modalities=set(row["modalities"]),
            provenance=set(row["provenance"]),
            accesses=int(row["accesses"]),
        )

    for row in data["routes"]:
        route = tuple(row["trajectory"])
        kid = row["knowledge_id"]
        if kid not in memory.knowledge._knowledge:
            raise ValueError("route references unknown knowledge_id")
        if len(row["states"]) != memory.levels:
            raise ValueError("routed snapshot layer count mismatch")
        memory.knowledge._routes[route] = kid
        lifecycle = SaturatingMemoryLifecycle(
            levels=memory.levels,
            max_strength=memory.max_strength,
        )
        lifecycle.time = int(row["time"])
        lifecycle._items["route"] = [
            SaturatingLayerState(
                level=int(s["level"]),
                strength=float(s["strength"]),
                active=bool(s["active"]),
                ever_active=bool(s["ever_active"]),
                activation_count=int(s["activation_count"]),
                deactivation_count=int(s["deactivation_count"]),
            )
            for s in row["states"]
        ]
        memory._route_lifecycle[route] = lifecycle

    return memory


def save_routed_snapshot(memory: RoutedLifecycleMemory, path: str | os.PathLike[str]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    blob = encode_routed_snapshot(memory)
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


def load_routed_snapshot(path: str | os.PathLike[str]) -> RoutedLifecycleMemory:
    return decode_routed_snapshot(Path(path).read_bytes())
