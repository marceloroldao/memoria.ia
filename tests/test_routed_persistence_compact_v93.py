import pytest

from memoria_resolutiva.routed_lifecycle import RoutedLifecycleMemory
from memoria_resolutiva.routed_persistence import encode_routed_snapshot
from memoria_resolutiva.routed_persistence_compact import (
    decode_compact_routed_snapshot,
    encode_compact_routed_snapshot,
)


def build_memory():
    m = RoutedLifecycleMemory(levels=5, max_strength=1.25)
    visual = ("private", "robot-7", "vision", "cup")
    collective = ("collective", "fleet", "language", "cup")
    payload = {"class": "cup", "fragile": True}
    m.register("cup", payload, visual, modality="vision", provenance="robot-7")
    m.register("cup", payload, collective, modality="language", provenance="fleet")
    for _ in range(32):
        m.support(visual)
        m.support(collective)
    for _ in range(24):
        m.contradict(visual)
    return m, visual, collective


def test_compact_roundtrip_preserves_route_state_and_shared_payload():
    m, visual, collective = build_memory()
    blob = encode_compact_routed_snapshot(m)
    restored = decode_compact_routed_snapshot(blob)
    assert restored.status(visual).active_depth == -1
    assert restored.status(visual).historical_depth == 4
    assert restored.status(collective).active_depth == 4
    assert restored.knowledge.knowledge_count == 1
    assert restored.knowledge.route_count == 2


def test_compact_is_smaller_than_json_envelope():
    m, _, _ = build_memory()
    compact = encode_compact_routed_snapshot(m)
    verbose = encode_routed_snapshot(m)
    assert len(compact) < len(verbose)


def test_compact_corruption_is_detected():
    m, _, _ = build_memory()
    blob = bytearray(encode_compact_routed_snapshot(m))
    blob[-1] ^= 0xFF
    with pytest.raises((ValueError, zlib.error, Exception)):
        decode_compact_routed_snapshot(bytes(blob))
