from __future__ import annotations

import base64
import hashlib
import json
import struct
import time
import uuid
from dataclasses import dataclass, field, replace
from enum import IntEnum
from typing import Any, Iterable, Mapping

try:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (
        Ed25519PrivateKey,
        Ed25519PublicKey,
    )
    from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
except ImportError:  # pragma: no cover - exercised only without optional dependency
    Ed25519PrivateKey = None  # type: ignore[assignment]
    Ed25519PublicKey = None  # type: ignore[assignment]
    Encoding = None  # type: ignore[assignment]
    PublicFormat = None  # type: ignore[assignment]


PROTOCOL_ID = "memoria.ia/a2a/0.1"
MAGIC = b"MA2A"
PRIVATE_PREFIX = ("user", "private")
ALLOWED_SYNC_PREFIXES = (("shared", "global"), ("agent", "peer"))


class A2AError(ValueError):
    """Base exception for MA2A reference-conformance failures."""


class NamespaceForbidden(A2AError):
    pass


class ReplayDetected(A2AError):
    pass


class SignatureError(A2AError):
    pass


class MessageType(IntEnum):
    DISCOVER = 0x01
    DISCOVER_RESP = 0x02
    HELLO = 0x03
    AUTH_CHALLENGE = 0x04
    AUTH_RESPONSE = 0x05
    CAPABILITIES = 0x06
    SESSION_ACCEPT = 0x07
    SESSION_REJECT = 0x08
    RESOLVE_REQ = 0x10
    RESOLVE_RESP = 0x11
    DELTA_EMIT = 0x20
    DELTA_ACK = 0x21
    REINFORCE_SIGNAL = 0x30
    HEARTBEAT = 0x40
    HEARTBEAT_ACK = 0x41
    STATE_CHECKPOINT = 0x50
    CONFLICT_NOTICE = 0x51
    RESYNC_REQ = 0x52
    GOODBYE = 0x60
    ERROR = 0x7F


def normalize_trajectory(trajectory: Iterable[str]) -> tuple[str, ...]:
    parts = tuple(trajectory)
    if not parts:
        raise A2AError("trajectory must contain at least one component")
    if len(parts) > 65535:
        raise A2AError("trajectory has too many components")
    for component in parts:
        if not isinstance(component, str):
            raise A2AError("trajectory components must be strings")
        raw = component.encode("utf-8")
        if not raw or len(raw) > 65535:
            raise A2AError("trajectory component length must be 1..65535 UTF-8 bytes")
    return parts


def canonical_trajectory_bytes(trajectory: Iterable[str]) -> bytes:
    parts = normalize_trajectory(trajectory)
    out = bytearray(struct.pack("!H", len(parts)))
    for component in parts:
        raw = component.encode("utf-8")
        out.extend(struct.pack("!H", len(raw)))
        out.extend(raw)
    return bytes(out)


def trajectory_id(trajectory: Iterable[str]) -> str:
    digest = hashlib.sha256(canonical_trajectory_bytes(trajectory)).hexdigest()
    return f"sha256:{digest}"


def canonical_json_bytes(value: Any) -> bytes:
    """Reference canonical JSON profile used by MA2A/0.1 tests.

    This is intentionally narrow: UTF-8, sorted object keys, no insignificant
    whitespace, and JSON-safe values only. Future protocol versions should pin
    a published canonical JSON standard before interoperability freeze.
    """
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _has_prefix(trajectory: tuple[str, ...], prefix: tuple[str, ...]) -> bool:
    return trajectory[: len(prefix)] == prefix


def enforce_transport_namespace(trajectory: Iterable[str]) -> tuple[str, ...]:
    path = normalize_trajectory(trajectory)
    if _has_prefix(path, PRIVATE_PREFIX):
        raise NamespaceForbidden("user/private trajectories MUST NOT enter transport")
    if not any(_has_prefix(path, p) for p in ALLOWED_SYNC_PREFIXES):
        raise NamespaceForbidden("namespace is not synchronizable in MA2A/0.1")
    return path


@dataclass(frozen=True)
class Frame:
    type: MessageType
    node_id: str
    session_id: str
    sequence: int
    trajectory: tuple[str, ...] | None = None
    payload: Mapping[str, Any] | None = None
    target_node_id: str | None = None
    timestamp_ms: int = field(default_factory=lambda: int(time.time() * 1000))
    message_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    version: int = 1
    flags: int = 0
    state_hash: str | None = None
    signature: str | None = None

    def __post_init__(self) -> None:
        if self.version != 1:
            raise A2AError("MA2A/0.1 requires version=1")
        if self.sequence < 0:
            raise A2AError("sequence must be non-negative")
        if self.trajectory is not None:
            object.__setattr__(self, "trajectory", normalize_trajectory(self.trajectory))
        if not self.node_id or not self.session_id or not self.message_id:
            raise A2AError("node_id, session_id and message_id are required")

    def as_dict(self, *, include_signature: bool = True) -> dict[str, Any]:
        value: dict[str, Any] = {
            "version": self.version,
            "type": self.type.name,
            "flags": self.flags,
            "message_id": self.message_id,
            "session_id": self.session_id,
            "node_id": self.node_id,
            "sequence": self.sequence,
            "timestamp_ms": self.timestamp_ms,
        }
        if self.target_node_id is not None:
            value["target_node_id"] = self.target_node_id
        if self.trajectory is not None:
            value["trajectory"] = list(self.trajectory)
        if self.payload is not None:
            value["payload"] = dict(self.payload)
        if self.state_hash is not None:
            value["state_hash"] = self.state_hash
        if include_signature and self.signature is not None:
            value["signature"] = self.signature
        return value

    def signing_bytes(self) -> bytes:
        if self.trajectory is not None and self.type in {
            MessageType.RESOLVE_REQ,
            MessageType.DELTA_EMIT,
            MessageType.REINFORCE_SIGNAL,
        }:
            enforce_transport_namespace(self.trajectory)
        return canonical_json_bytes(self.as_dict(include_signature=False))

    def with_signature(self, signature: str) -> "Frame":
        return replace(self, signature=signature)


class Ed25519Identity:
    """Small reference identity helper. Requires the `a2a` extra."""

    def __init__(self, private_key: Any):
        if Ed25519PrivateKey is None:
            raise RuntimeError("install memoria-resolutiva[a2a] for Ed25519 support")
        self._private_key = private_key

    @classmethod
    def generate(cls) -> "Ed25519Identity":
        if Ed25519PrivateKey is None:
            raise RuntimeError("install memoria-resolutiva[a2a] for Ed25519 support")
        return cls(Ed25519PrivateKey.generate())

    @property
    def public_key_bytes(self) -> bytes:
        return self._private_key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)

    @property
    def node_id(self) -> str:
        return "agent:" + hashlib.sha256(self.public_key_bytes).hexdigest()

    def sign(self, frame: Frame) -> Frame:
        signature = self._private_key.sign(frame.signing_bytes())
        return frame.with_signature("ed25519:" + base64.b64encode(signature).decode("ascii"))

    @staticmethod
    def verify(frame: Frame, public_key_bytes: bytes) -> None:
        if Ed25519PublicKey is None:
            raise RuntimeError("install memoria-resolutiva[a2a] for Ed25519 support")
        if not frame.signature or not frame.signature.startswith("ed25519:"):
            raise SignatureError("missing or invalid Ed25519 signature encoding")
        try:
            signature = base64.b64decode(frame.signature.split(":", 1)[1], validate=True)
            Ed25519PublicKey.from_public_bytes(public_key_bytes).verify(
                signature, frame.signing_bytes()
            )
        except Exception as exc:  # cryptography deliberately exposes several failure types
            raise SignatureError("signature verification failed") from exc


class ReplayGuard:
    def __init__(self) -> None:
        self._seen_message_ids: set[str] = set()
        self._last_sequence: dict[tuple[str, str], int] = {}

    def accept(self, frame: Frame) -> None:
        if frame.message_id in self._seen_message_ids:
            raise ReplayDetected("duplicate message_id")
        key = (frame.node_id, frame.session_id)
        last = self._last_sequence.get(key, -1)
        if frame.sequence <= last:
            raise ReplayDetected("non-monotonic sequence")
        self._seen_message_ids.add(frame.message_id)
        self._last_sequence[key] = frame.sequence


def state_hash(state: Mapping[str, Any]) -> str:
    return "sha256:" + hashlib.sha256(canonical_json_bytes(dict(state))).hexdigest()


class InMemoryTrajectoryStore:
    """Minimal deterministic store for MA2A protocol tests, not the full memory engine."""

    def __init__(self) -> None:
        self._states: dict[str, dict[str, Any]] = {}
        self._applied: set[str] = set()

    def resolve(self, trajectory: Iterable[str]) -> dict[str, Any] | None:
        path = normalize_trajectory(trajectory)
        value = self._states.get(trajectory_id(path))
        return None if value is None else dict(value)

    def apply_delta(
        self,
        *,
        trajectory: Iterable[str],
        delta: Mapping[str, Any],
        message_id: str,
    ) -> str:
        path = enforce_transport_namespace(trajectory)
        key = trajectory_id(path)
        if message_id in self._applied:
            existing = self._states.get(key, {})
            return state_hash(existing)
        current = dict(self._states.get(key, {}))
        current.update(dict(delta))
        self._states[key] = current
        self._applied.add(message_id)
        return state_hash(current)


def deterministic_conflict_key(
    *, logical_counter: int, timestamp_ms: int, node_id: str, message_id: str
) -> tuple[int, int, str, str]:
    """Tie-break key for already-known concurrent scalar writes.

    Causal/vector-clock ordering must be evaluated before this tie-breaker.
    """
    return (logical_counter, timestamp_ms, node_id, message_id)
