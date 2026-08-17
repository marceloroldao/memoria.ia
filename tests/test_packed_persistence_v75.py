import json
from pathlib import Path

import pytest

from memoria_resolutiva.packed_lifecycle import PackedMemoryLifecycle
from memoria_resolutiva.packed_persistence import FORMAT, decode_snapshot, encode_snapshot, load_snapshot, save_snapshot


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
    with pytest.raises((ValueError, UnicodeDecodeError, KeyError, json.JSONDecodeError)):
        decode_snapshot(bytes(blob))


def test_truncated_snapshot_is_rejected():
    blob = encode_snapshot(build_memory())
    with pytest.raises((ValueError, UnicodeDecodeError, KeyError, json.JSONDecodeError)):
        decode_snapshot(blob[: len(blob) // 2])


def test_unsupported_envelope_version_is_rejected():
    envelope = json.loads(encode_snapshot(build_memory()).decode("utf-8"))
    envelope["format"] = FORMAT + "-future"
    with pytest.raises(ValueError, match="unsupported snapshot format"):
        decode_snapshot(json.dumps(envelope).encode("utf-8"))


def test_payload_layer_mismatch_is_rejected():
    envelope = json.loads(encode_snapshot(build_memory()).decode("utf-8"))
    payload = json.loads(envelope["payload"])
    payload["items"]["x"] = payload["items"]["x"][:-1]
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    import zlib
    envelope["payload"] = raw.decode("utf-8")
    envelope["crc32"] = zlib.crc32(raw) & 0xFFFFFFFF
    with pytest.raises(ValueError, match="layer count mismatch"):
        decode_snapshot(json.dumps(envelope, sort_keys=True, separators=(",", ":")).encode("utf-8"))


def test_existing_snapshot_remains_readable_after_failed_pre_replace_write(tmp_path: Path, monkeypatch):
    original = build_memory()
    path = tmp_path / "memory.snapshot"
    save_snapshot(original, path)
    baseline = path.read_bytes()

    replacement = build_memory()
    replacement.support("z")

    import memoria_resolutiva.packed_persistence as pp
    real_replace = pp.os.replace

    def fail_replace(src, dst):
        raise OSError("simulated crash before atomic replace")

    monkeypatch.setattr(pp.os, "replace", fail_replace)
    with pytest.raises(OSError):
        save_snapshot(replacement, path)

    monkeypatch.setattr(pp.os, "replace", real_replace)
    assert path.read_bytes() == baseline
    restored = load_snapshot(path)
    assert restored.snapshot("x") == original.snapshot("x")
