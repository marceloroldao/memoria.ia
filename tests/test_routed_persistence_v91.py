import pytest

from memoria_resolutiva.routed_lifecycle import RoutedLifecycleMemory
from memoria_resolutiva.routed_persistence import decode_routed_snapshot, encode_routed_snapshot


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


def test_round_trip_preserves_shared_payload_and_route_isolation():
    m, visual, collective = build_memory()
    restored = decode_routed_snapshot(encode_routed_snapshot(m))
    assert restored.knowledge.knowledge_count == 1
    assert restored.knowledge.route_count == 2
    assert restored.resolve(visual) is None
    assert restored.resolve(visual, require_active=False).payload == {"class": "cup", "fragile": True}
    assert restored.resolve(collective).knowledge_id == "cup"
    assert restored.status(visual).historical_depth == 4
    assert restored.status(collective).active_depth == 4


def test_corruption_is_rejected():
    m, _, _ = build_memory()
    blob = bytearray(encode_routed_snapshot(m))
    blob[len(blob) // 2] ^= 1
    with pytest.raises((ValueError, UnicodeDecodeError, KeyError)):
        decode_routed_snapshot(bytes(blob))


def test_non_json_payload_is_rejected_explicitly():
    m = RoutedLifecycleMemory()
    m.register("x", object(), ("route", "x"), modality="test", provenance="unit")
    with pytest.raises(TypeError):
        encode_routed_snapshot(m)
