from memoria_resolutiva.sqlite_store import SQLiteResolutiveMemory


def test_sqlite_roundtrip_and_stats(tmp_path):
    path = tmp_path / "memory.db"
    payload = b"fisica resolutiva memoria geodesica"
    db = SQLiteResolutiveMemory(path)
    db.add("m1", payload)
    assert db.reconstruct("m1") == payload
    stats = db.stats()
    assert stats["memories"] == 1
    assert stats["unique_nodes"] > 0
    assert set(stats["nodes_per_layer"]) == {0, 1, 2, 3}
    db.close()

    reopened = SQLiteResolutiveMemory(path)
    assert reopened.reconstruct("m1") == payload
    reopened.close()
