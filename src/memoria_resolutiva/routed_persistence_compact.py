from __future__ import annotations

import json
import struct
import zlib

from .routed_persistence import _payload, decode_routed_snapshot

MAGIC = b"MI93"
VERSION = 1
HEADER = struct.Struct(">4sBII")  # magic, version, raw_len, crc32


def encode_compact_routed_snapshot(memory) -> bytes:
    """Compact v0.93 format: canonical JSON payload compressed with zlib.

    The canonical routed payload remains the source of truth, preserving
    auditability and compatibility with the existing decoder semantics.
    """
    raw = json.dumps(_payload(memory), sort_keys=True, separators=(",", ":")).encode("utf-8")
    crc = zlib.crc32(raw) & 0xFFFFFFFF
    compressed = zlib.compress(raw, level=9)
    return HEADER.pack(MAGIC, VERSION, len(raw), crc) + compressed


def decode_compact_routed_snapshot(blob: bytes):
    if len(blob) < HEADER.size:
        raise ValueError("compact routed snapshot truncated")
    magic, version, raw_len, crc = HEADER.unpack(blob[:HEADER.size])
    if magic != MAGIC:
        raise ValueError("invalid compact routed snapshot magic")
    if version != VERSION:
        raise ValueError("unsupported compact routed snapshot version")
    raw = zlib.decompress(blob[HEADER.size:])
    if len(raw) != raw_len:
        raise ValueError("compact routed snapshot length mismatch")
    if (zlib.crc32(raw) & 0xFFFFFFFF) != crc:
        raise ValueError("compact routed snapshot checksum mismatch")

    # Reuse the validated v0.91 decoder by rebuilding its envelope.
    envelope = {
        "format": "memoria.ia-routed-v1",
        "crc32": crc,
        "payload": raw.decode("utf-8"),
    }
    return decode_routed_snapshot(
        json.dumps(envelope, sort_keys=True, separators=(",", ":")).encode("utf-8")
    )
