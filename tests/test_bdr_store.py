from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor

import pytest

from memoria_resolutiva.bdr_store import BDRPolicy, BDRResolutiveMemory, native_bdr_available
from memoria_resolutiva.node import digest_payload
from memoria_resolutiva.sqlite_store import SQLiteResolutiveMemory

pytestmark = pytest.mark.skipif(not native_bdr_available(), reason="native BDR extension not built")


def _payloads():
    return {
        "a": bytes(range(64)),
        "b": (b"resolutive-memory-" * 17)[:211],
        "c": bytes((i * 37) % 256 for i in range(333)),
    }


def test_native_digest_matches_python_blake2b():
    from memoria_resolutiva._bdr_native import digest_payload_native

    payloads = [b"", b"a", bytes(range(128)), bytes(range(256)), os.urandom(511)]
    for layer in range(8):
        for payload in payloads:
            assert digest_payload_native(payload, layer) == digest_payload(payload, layer)


def test_bdr_matches_sqlite_reconstruct_and_stats(tmp_path):
    sqlite = SQLiteResolutiveMemory(tmp_path / "sqlite.db", max_layer=3)
    bdr = BDRResolutiveMemory(tmp_path / "bdr", max_layer=3)
    try:
        for memory_id, payload in _payloads().items():
            sqlite.add(memory_id, payload)
            bdr.add(memory_id, payload)

        for memory_id, payload in _payloads().items():
            assert sqlite.reconstruct(memory_id) == payload
            assert bdr.reconstruct(memory_id) == payload

        assert bdr.stats() == sqlite.stats()
    finally:
        sqlite.close()
        bdr.close()


def test_bdr_reopen_preserves_payload_and_metadata(tmp_path):
    root = tmp_path / "bdr-reopen"
    first = BDRResolutiveMemory(root, max_layer=3)
    expected = _payloads()
    for memory_id, payload in expected.items():
        first.add(memory_id, payload)
    before = first.stats()
    first.close()

    reopened = BDRResolutiveMemory(root, max_layer=3)
    try:
        assert reopened.stats() == before
        for memory_id, payload in expected.items():
            assert reopened.reconstruct(memory_id) == payload
    finally:
        reopened.close()


def test_bdr_rejects_duplicate_memory_id(tmp_path):
    db = BDRResolutiveMemory(tmp_path / "bdr-duplicate", max_layer=2)
    try:
        db.add("same", b"first")
        with pytest.raises(ValueError):
            db.add("same", b"second")
        assert db.reconstruct("same") == b"first"
    finally:
        db.close()


def test_bdr_deferred_batch_is_flushed_on_close(tmp_path):
    root = tmp_path / "bdr-deferred"
    policy = BDRPolicy(sync_every_memories=8)
    db = BDRResolutiveMemory(root, max_layer=2, policy=policy)
    for i in range(5):
        db.add(f"m{i}", bytes([i]) * 96)
    db.close()

    reopened = BDRResolutiveMemory(root, max_layer=2, policy=policy)
    try:
        assert reopened.stats()["memories"] == 5
        for i in range(5):
            assert reopened.reconstruct(f"m{i}") == bytes([i]) * 96
    finally:
        reopened.close()


def test_bdr_serializes_concurrent_logical_writers(tmp_path):
    root = tmp_path / "bdr-concurrent"
    db = BDRResolutiveMemory(root, max_layer=3)
    expected = {f"m{i}": bytes([i % 251]) * (128 + i) for i in range(32)}
    try:
        with ThreadPoolExecutor(max_workers=8) as pool:
            futures = [pool.submit(db.add, memory_id, payload) for memory_id, payload in expected.items()]
            for future in futures:
                future.result()
        assert db.stats()["memories"] == len(expected)
        for memory_id, payload in expected.items():
            assert db.reconstruct(memory_id) == payload
    finally:
        db.close()

    reopened = BDRResolutiveMemory(root, max_layer=3)
    try:
        assert reopened.stats()["memories"] == len(expected)
        for memory_id, payload in expected.items():
            assert reopened.reconstruct(memory_id) == payload
    finally:
        reopened.close()
