from pathlib import Path

import pytest

from memoria_resolutiva.packed_lifecycle import PackedMemoryLifecycle
from memoria_resolutiva.packed_persistence import decode_snapshot, encode_snapshot, load_snapshot, save_snapshot


def build_memory():
    m = PackedMemoryLifecycle(levels=5)
    for _ in range(32):
        m.support("x")
    for _ in range(40):
        m.contradict("x")
    for _ in range(16):
        m.support("x")
    for _ in range(12):
        m.support("y")
    return m


def test_snapshot_round_trip_preserves_state():
    m = build_memory()
    restored = decode_snapshot(encode_snapshot(m))
    assert restored.time == m.time
    assert restored.levels == m.levels
    assert restored.snapshot("x") == m.snapshot("x")
    assert restored.snapshot("y") == m.snapshot("y")
    assert restored.transition_count("x") == m.transition_count("x")
    assert restored.active_depth("x") == m.active_depth("x")
    assert restored.historical_depth("x") == m.historical_depth("x")


def test_snapshot_file_round_trip(tmp_path: Path):
    m = build_memory()
    path = tmp_path / "memory.snapshot"
    save_snapshot(m, path)
    restored = load_snapshot(path)
    assert restored.snapshot("x") == m.snapshot("x")


def test_corruption_is_detected():
    blob = bytearray(encode_snapshot(build_memory()))
    pos = len(blob) // 2
    blob[pos] = (blob[pos] + 1) % 255
    with pytest.raises((ValueError, UnicodeDecodeError, KeyError)):
        decode_snapshot(bytes(blob))
